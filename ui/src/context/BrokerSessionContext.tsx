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
import type {
  BrokerAccountStatus,
  BrokerSessionBootstrapRequest,
  BrokerSessionBootstrapResponse,
  SessionReadiness,
  SessionResponse,
} from '../types';
import { useAuth } from './AuthContext';
import { useSession } from './SessionContext';

const SESSION_STORAGE_KEY = 'tradecraftx_session_id';
const OAUTH_PENDING_KEY = 'tradecraftx_oauth_pending_broker';

export interface BrokerSessionState {
  status: SessionReadiness;
  message: string | null;
  brokerConnected: boolean;
  requiresSelection: boolean;
  candidates: BrokerAccountStatus[];
  brokerName: string | null;
  connectionId: number | null;
}

interface BrokerSessionOrchestratorValue extends BrokerSessionState {
  bootstrap: (
    request?: BrokerSessionBootstrapRequest,
  ) => Promise<BrokerSessionBootstrapResponse | null>;
  retry: () => Promise<BrokerSessionBootstrapResponse | null>;
  clearSession: () => void;
}

const initialState: BrokerSessionState = {
  status: 'INITIALIZING',
  message: null,
  brokerConnected: false,
  requiresSelection: false,
  candidates: [],
  brokerName: null,
  connectionId: null,
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

  const reset = useCallback(() => {
    setState(initialState);
    setSessionId(null);
    setSessionInfo(null);
    setSelectedConnectionId(null);
    localStorage.removeItem(SESSION_STORAGE_KEY);
  }, [setSelectedConnectionId, setSessionId, setSessionInfo]);

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
        requiresSelection: false,
      }));

      const task = (async () => {
        try {
          await new Promise<void>((resolve) => setTimeout(resolve, 0));
          setState((previous) => ({ ...previous, status: 'LOADING' }));
          const response = await api.bootstrapSession(request);

          if (response.status === 'READY' && response.session_id) {
            const info = sessionInfoFromResponse(response);
            setSessionId(response.session_id);
            setSessionInfo(info);
            setSelectedConnectionId(response.connection_id ?? null);
            localStorage.setItem(SESSION_STORAGE_KEY, response.session_id);
          } else {
            setSessionId(null);
            setSessionInfo(null);
            localStorage.removeItem(SESSION_STORAGE_KEY);
          }

          setState({
            status: response.status,
            message: response.message ?? null,
            brokerConnected: response.broker_connected,
            requiresSelection: response.requires_selection,
            candidates: response.candidates ?? [],
            brokerName: response.broker_name ?? null,
            connectionId: response.connection_id ?? null,
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
    [setSelectedConnectionId, setSessionId, setSessionInfo],
  );

  const retry = useCallback(() => bootstrap(lastRequestRef.current), [bootstrap]);

  const clearSession = useCallback(() => {
    setState((previous) => ({
      ...previous,
      status: 'CONNECTED',
      message: null,
      requiresSelection: false,
    }));
    setSessionId(null);
    setSessionInfo(null);
    localStorage.removeItem(SESSION_STORAGE_KEY);
  }, [setSessionId, setSessionInfo]);

  useEffect(() => {
    if (!user?.id) {
      initializedForRef.current = null;
      reset();
      return;
    }
    const userId = String(user.id);
    if (initializedForRef.current === userId) return;
    initializedForRef.current = userId;

    const params = new URLSearchParams(window.location.search);
    const oauthReturning =
      params.has('oauth') || Boolean(window.sessionStorage.getItem(OAUTH_PENDING_KEY));
    if (oauthReturning) return;

    void bootstrap({});
  }, [bootstrap, reset, user?.id]);

  return (
    <BrokerSessionContext.Provider value={{ ...state, bootstrap, retry, clearSession }}>
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
