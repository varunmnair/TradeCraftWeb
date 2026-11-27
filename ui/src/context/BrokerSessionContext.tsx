import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { api } from '../api/client';
import {
  dispatchSessionChanged,
  SESSION_RESTORE_REQUIRED_EVENT,
  type SessionChangedDetail,
} from '../utils/sessionEvents';
import type {
  BrokerSessionBootstrapRequest,
  BrokerSessionBootstrapResponse,
  SessionReadiness,
  SessionResponse,
} from '../types';
import { useAuth } from './AuthContext';
import { useSession } from './SessionContext';

const SESSION_STORAGE_KEY = 'tradecraftx_session_id';

export interface BrokerSessionState {
  status: SessionReadiness;
  message: string | null;
  brokerConnected: boolean;
}

interface BrokerSessionOrchestratorValue extends BrokerSessionState {
  bootstrap: (
    request?: BrokerSessionBootstrapRequest,
  ) => Promise<BrokerSessionBootstrapResponse | null>;
  /** Explicitly activate a broker connection for this device. */
  activateBroker: (
    brokerConnectionId: number,
    brokerName?: string,
  ) => Promise<BrokerSessionBootstrapResponse | null>;
  retry: () => Promise<BrokerSessionBootstrapResponse | null>;
  clearSession: () => void;
}

const initialState: BrokerSessionState = {
  status: 'CONNECTED',
  message: null,
  brokerConnected: false,
};

const BrokerSessionContext = createContext<BrokerSessionOrchestratorValue | undefined>(
  undefined,
);

function sessionInfoFromResponse(
  response: BrokerSessionBootstrapResponse,
): SessionResponse | null {
  const session = response.session;
  if (!session?.session_id && !response.session_id) return null;
  return {
    session_id: session?.session_id || response.session_id || '',
    user_id: session?.user_id || response.broker_user_id || '',
    broker: session?.broker || response.broker_name || '',
    expires_at: session?.expires_at,
    tenant_id: session?.tenant_id,
  };
}

export function BrokerSessionOrchestratorProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const { setSessionId, setSessionInfo, setSelectedConnectionId } = useSession();
  const [state, setState] = useState<BrokerSessionState>(initialState);

  const initializedForRef = useRef<string | null>(null);
  const lastRequestRef = useRef<BrokerSessionBootstrapRequest>({});
  const inFlightRef = useRef<Map<string, Promise<BrokerSessionBootstrapResponse | null>>>(
    new Map(),
  );
  const activeSessionRef = useRef<SessionChangedDetail>({
    session_id: null,
    broker_connection_id: null,
  });

  const publishSessionChange = useCallback((detail: SessionChangedDetail) => {
    const previous = activeSessionRef.current;
    if (
      previous.session_id === detail.session_id &&
      previous.broker_connection_id === detail.broker_connection_id
    ) {
      return;
    }
    activeSessionRef.current = detail;
    dispatchSessionChanged(detail);
  }, []);

  const reset = useCallback(() => {
    publishSessionChange({ session_id: null, broker_connection_id: null });
    setState(initialState);
    setSessionId(null);
    setSessionInfo(null);
    setSelectedConnectionId(null);
    localStorage.removeItem(SESSION_STORAGE_KEY);
  }, [publishSessionChange, setSelectedConnectionId, setSessionId, setSessionInfo]);

  const bootstrap = useCallback(
    async (
      request: BrokerSessionBootstrapRequest = {},
    ): Promise<BrokerSessionBootstrapResponse | null> => {
      lastRequestRef.current = request;

      const key = [
        request.broker_name || '',
        request.broker_connection_id ?? '',
        request.warm_start === false ? 'no-warm' : 'warm',
      ].join('|');
      const existing = inFlightRef.current.get(key);
      if (existing) return existing;

      setState((previous) => ({
        ...previous,
        status: 'INITIALIZING',
        message: null,
      }));

      const task = (async () => {
        try {
          await new Promise<void>((resolve) => setTimeout(resolve, 0));
          setState((previous) => ({ ...previous, status: 'LOADING' }));
          const response = await api.bootstrapSession(request);

          const ready = response.status === 'READY' && Boolean(response.session_id);
          publishSessionChange({
            session_id: ready ? response.session_id ?? null : null,
            broker_connection_id: ready ? response.connection_id ?? null : null,
          });

          if (ready && response.session_id) {
            const info = sessionInfoFromResponse(response);
            setSessionId(response.session_id);
            setSessionInfo(info);
            setSelectedConnectionId(response.connection_id ?? null);
            localStorage.setItem(SESSION_STORAGE_KEY, response.session_id);
          } else {
            setSessionId(null);
            setSessionInfo(null);
            setSelectedConnectionId(null);
            localStorage.removeItem(SESSION_STORAGE_KEY);
          }

          setState({
            status: response.status,
            message: response.message ?? null,
            brokerConnected: response.broker_connected,
          });
          return response;
        } catch (error) {
          const message =
            error instanceof Error && error.message
              ? error.message
              : 'Unable to check broker session readiness.';
          setState((previous) => ({
            ...previous,
            status: 'ERROR',
            message,
          }));
          return null;
        } finally {
          inFlightRef.current.delete(key);
        }
      })();

      inFlightRef.current.set(key, task);
      return task;
    },
    [publishSessionChange, setSelectedConnectionId, setSessionId, setSessionInfo],
  );

  const activateBroker = useCallback(
    (brokerConnectionId: number, brokerName?: string) =>
      bootstrap({
        broker_connection_id: brokerConnectionId,
        ...(brokerName ? { broker_name: brokerName } : {}),
      }),
    [bootstrap],
  );

  const retry = useCallback(() => bootstrap(lastRequestRef.current), [bootstrap]);

  const clearSession = useCallback(() => {
    publishSessionChange({ session_id: null, broker_connection_id: null });
    setState((previous) => ({
      ...previous,
      status: 'CONNECTED',
      message: 'Trading session ended. Select an account to continue.',
    }));
    setSessionId(null);
    setSessionInfo(null);
    setSelectedConnectionId(null);
    localStorage.removeItem(SESSION_STORAGE_KEY);
  }, [publishSessionChange, setSelectedConnectionId, setSessionId, setSessionInfo]);

  useEffect(() => {
    if (!user?.id) {
      initializedForRef.current = null;
      reset();
      return;
    }
    const userId = String(user.id);
    if (initializedForRef.current === userId) return;
    initializedForRef.current = userId;

    // Login never activates a broker. Only explicit activation or session
    // recovery calls bootstrap; OAuth completion does so explicitly.
    setState(initialState);
  }, [reset, user?.id]);

  useEffect(() => {
    const handleRestoreRequired = () => {
      void bootstrap({});
    };
    window.addEventListener(SESSION_RESTORE_REQUIRED_EVENT, handleRestoreRequired);
    return () => window.removeEventListener(SESSION_RESTORE_REQUIRED_EVENT, handleRestoreRequired);
  }, [bootstrap]);

  return (
    <BrokerSessionContext.Provider
      value={{ ...state, bootstrap, activateBroker, retry, clearSession }}
    >
      {children}
    </BrokerSessionContext.Provider>
  );
}

export function useBrokerSessionOrchestrator(): BrokerSessionOrchestratorValue {
  const context = useContext(BrokerSessionContext);
  if (!context) {
    throw new Error(
      'useBrokerSessionOrchestrator must be used within BrokerSessionOrchestratorProvider',
    );
  }
  return context;
}
