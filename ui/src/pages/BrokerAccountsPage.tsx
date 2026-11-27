import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  DialogActions,
  DialogContent,
  DialogTitle,
  Typography,
  useMediaQuery,
  useTheme,
} from '@mui/material';
import {
  Check as CheckIcon,
  Error as ErrorIcon,
  Refresh as RefreshIcon,
  Warning as WarningIcon,
} from '@mui/icons-material';
import { api } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { useBrokerSessionOrchestrator } from '../context/BrokerSessionContext';
import { useSession } from '../context/SessionContext';
import type {
  ActiveConnectionResponse,
  BrokerConnectionResponse,
  SessionResponse,
} from '../types';
import { ResponsiveDialog } from '../components/ResponsiveDialog';
import { ResponsivePageHeader } from '../components/ResponsivePageHeader';
import {
  BrokerAccountCard,
  type BrokerAccountOption,
  type BrokerCardStatus,
} from '../components/broker-connections/MobileBrokerAccountCard';

const POLL_INTERVAL_MS = 2000;
const MAX_POLL_ATTEMPTS = 30;
const BROKERS = ['zerodha', 'upstox'] as const;

const STORAGE_KEY_UPSTOX = 'tradecraftx_upstox_connection_id';
const STORAGE_KEY_ZERODHA = 'tradecraftx_zerodha_connection_id';
const STORAGE_KEY_SESSION = 'tradecraftx_session_id';
const STORAGE_KEY_OAUTH_PENDING = 'tradecraftx_oauth_pending_broker';
const STORAGE_KEY_OAUTH_PENDING_CONNECTION = 'tradecraftx_oauth_pending_connection_id';

type BrokerName = (typeof BROKERS)[number];

interface BrokerStatus {
  connected: boolean;
  broker_user_id: string | null;
  token_updated_at: string | null;
  connection_id: number;
  token_status: 'valid' | 'expired' | 'missing';
}

interface BrokerCardModel {
  broker: BrokerName;
  status: BrokerCardStatus;
  statusLabel: string;
  detail: string | null;
  accounts: BrokerAccountOption[];
  selectedConnectionId: number | null;
  accountId: string | null;
  sessionInfo: { holdings: string; lastRefreshed: string } | null;
  primaryLabel: string;
  primaryDisabled: boolean;
  busy: boolean;
  hasSession: boolean;
  canManage: boolean;
}

const STATUS_LABELS: Record<BrokerCardStatus, string> = {
  NOT_CONNECTED: 'Not Connected',
  CONNECTING: 'Connecting...',
  READY: 'Ready to Trade',
  ATTENTION_REQUIRED: 'Attention Required',
};

function brokerLabel(broker: string | null | undefined): string {
  if (broker === 'zerodha') return 'Zerodha';
  if (broker === 'upstox') return 'Upstox';
  return broker ? broker.charAt(0).toUpperCase() + broker.slice(1) : 'Broker';
}

function friendlyError(message: string | null | undefined): string {
  const text = (message || '').trim();
  if (!text) return 'Session could not be started. Retry.';
  if (/no longer valid|expired|reconnect|invalid/i.test(text)) {
    return 'Broker authentication expired. Reconnect.';
  }
  if (/initialization failed|recovery failed|could not be started/i.test(text)) {
    return 'Session could not be started. Retry.';
  }
  if (/no broker is connected/i.test(text)) {
    return 'Connect a broker to start a trading session.';
  }
  return text;
}

function formatClock(value: string | null): string {
  if (!value) return '—';
  try {
    return new Date(value).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
  } catch {
    return '—';
  }
}

function storageKeyFor(broker: BrokerName, userId?: number): string {
  const base = broker === 'upstox' ? STORAGE_KEY_UPSTOX : STORAGE_KEY_ZERODHA;
  // Connection ids are user-scoped on the server. Keeping them in a global
  // localStorage key leaks the previous account's ids into the next login.
  return userId != null ? `${base}:user-${userId}` : base;
}

function getPendingConnectionId(): number | undefined {
  const raw = window.sessionStorage.getItem(STORAGE_KEY_OAUTH_PENDING_CONNECTION);
  if (!raw) return undefined;
  const parsed = Number(raw);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function connectionErrorMessage(broker: BrokerName, error: unknown): string {
  const label = brokerLabel(broker);
  const code = String((error as { code?: string } | null)?.code || '').toLowerCase();
  if (code === 'internal_error') {
    return `${label} connection failed on the server. Check the server logs and try again.`;
  }
  const message = error instanceof Error ? error.message.trim() : '';
  return message ? `${label} connection failed: ${message}` : `${label} connection failed. Try again.`;
}

function oauthFailureMessage(
  broker: BrokerName | string | null,
  reason: string | null | undefined,
): string {
  const label = brokerLabel(broker);
  const code = (reason || '').trim().toLowerCase();
  if (code === 'cancelled') return `${label} login was cancelled.`;
  if (code === 'invalid_state') return `${label} login timed out. Start a new connection.`;
  if (code === 'missing_token') return `${label} did not return access tokens. Try again.`;
  if (code === 'token_exchange_failed') {
    return `${label} token exchange failed. Check broker credentials and server logs.`;
  }
  if (code === 'store_failed') {
    return `${label} login succeeded but tokens could not be saved. Check server logs.`;
  }
  if (code) return `${label} login failed (${code}). Check server logs.`;
  return `${label} connection failed. Try again.`;
}

function dedupeConnections(
  connections: BrokerConnectionResponse[],
  statuses: Map<number, BrokerStatus>,
  active: ActiveConnectionResponse | null,
): BrokerConnectionResponse[] {
  const groups = new Map<string, BrokerConnectionResponse[]>();
  for (const connection of connections) {
    const identity = statuses.get(connection.id)?.broker_user_id || String(connection.id);
    const key = `${connection.broker_name}:${identity}`;
    const group = groups.get(key) || [];
    group.push(connection);
    groups.set(key, group);
  }

  const score = (connection: BrokerConnectionResponse) => {
    const status = statuses.get(connection.id);
    const valid = status?.connected && status.token_status === 'valid' && status.broker_user_id;
    return (
      (valid ? 1000 : 0) +
      (connection.id === active?.broker_connection_id ? 100 : 0) +
      connection.id
    );
  };

  const result: BrokerConnectionResponse[] = [];
  for (const group of groups.values()) {
    group.sort((left, right) => score(right) - score(left));
    result.push(group[0]);
  }
  return result;
}

export default function BrokerAccountsPage() {
  const [connections, setConnections] = useState<BrokerConnectionResponse[]>([]);
  const [statusByConnection, setStatusByConnection] = useState<Map<number, BrokerStatus>>(
    new Map(),
  );
  const [activeConnection, setActiveConnection] = useState<ActiveConnectionResponse | null>(null);
  const [currentSession, setCurrentSession] = useState<SessionResponse | null>(null);
  const [selectedAccountByBroker, setSelectedAccountByBroker] = useState<
    Partial<Record<BrokerName, number>>
  >({});
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshingData, setRefreshingData] = useState(false);
  const [endingSession, setEndingSession] = useState(false);
  const [busyBroker, setBusyBroker] = useState<BrokerName | null>(null);
  const [activatingBroker, setActivatingBroker] = useState<BrokerName | null>(null);
  const [error, setError] = useState('');
  const [successMessage, setSuccessMessage] = useState('');
  const [lastRefreshedAt, setLastRefreshedAt] = useState<string | null>(null);
  const [disconnectBroker, setDisconnectBroker] = useState<BrokerName | null>(null);
  const [endSessionDialogOpen, setEndSessionDialogOpen] = useState(false);

  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const { user } = useAuth();

  // OAuth flow state
  const [oauthDialogOpen, setOauthDialogOpen] = useState(false);
  const [oauthStep, setOauthStep] = useState<BrokerName | null>(null);
  const [polling, setPolling] = useState(false);
  const [pollAttempts, setPollAttempts] = useState(0);
  const [connectionStatus, setConnectionStatus] = useState<BrokerStatus | null>(null);

  const pollingRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pollAttemptsRef = useRef(0);
  const pollingActiveRef = useRef(false);
  const pollGenerationRef = useRef(0);
  const connectInFlightRef = useRef<BrokerName | null>(null);
  const clearPollingRef = useRef<() => void>(() => {});
  // Lets polling compare against the token that existed when it started
  // without making startPolling change identity on every status refresh.
  const statusByConnectionRef = useRef(statusByConnection);
  statusByConnectionRef.current = statusByConnection;

  const {
    status: readinessStatus,
    message: sessionMessage,
    brokerConnected,
    activateBroker,
    retry: retrySession,
    clearSession,
  } = useBrokerSessionOrchestrator();
  const { sessionId, setSessionId, setSessionInfo } = useSession();

  const runActivation = useCallback(
    async (broker: BrokerName, connectionId: number) => {
      setActivatingBroker(broker);
      setError('');
      setSuccessMessage('');
      try {
        const response = await activateBroker(connectionId, broker);
        if (response?.status === 'READY') {
          setSuccessMessage(
            response.message && /still active/i.test(response.message)
              ? response.message
              : `${brokerLabel(broker)} is ready to trade.`,
          );
        } else if (response) {
          setError(friendlyError(response.message));
        }
      } finally {
        setActivatingBroker(null);
      }
    },
    [activateBroker],
  );

  const fetchConnections = useCallback(async () => {
    setRefreshing(true);
    try {
      const data = await api.listBrokerConnections();

      const active = await api.getActiveConnection().catch(() => null);
      setActiveConnection(active);

      const statuses = new Map<number, BrokerStatus>();
      await Promise.all(
        data.map(async (connection) => {
          try {
            const response =
              connection.broker_name === 'upstox'
                ? await api.getUpstoxStatus(connection.id)
                : await api.getZerodhaStatus(connection.id);
            const match =
              response.connections.find((item) => item.connection_id === connection.id) ||
              response.connections[0];
            if (match) {
              statuses.set(connection.id, {
                connected: match.connected,
                broker_user_id: match.broker_user_id,
                token_updated_at: match.token_updated_at,
                connection_id: match.connection_id,
                token_status: match.token_status,
              });
            }
          } catch {
            // A missing status is treated as disconnected for this account.
          }
        }),
      );
      setStatusByConnection(statuses);
      const visibleConnections = dedupeConnections(data, statuses, active);
      setConnections(visibleConnections);

      for (const broker of BROKERS) {
        const valid = visibleConnections.filter((connection) => {
          const status = statuses.get(connection.id);
          return (
            connection.broker_name === broker &&
            status?.connected &&
            status.token_status === 'valid' &&
            Boolean(status.broker_user_id)
          );
        });
        const preferred =
          valid.find((connection) => connection.id === active?.broker_connection_id) ||
          valid.find((connection) => statuses.get(connection.id)?.broker_user_id === active?.broker_user_id) ||
          valid[0];
        const key = storageKeyFor(broker, user?.id);
        if (preferred) localStorage.setItem(key, String(preferred.id));
        else localStorage.removeItem(key);
      }

      setLastRefreshedAt(new Date().toISOString());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load broker accounts');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [user?.id]);

  useEffect(() => {
    // Drop the old account-agnostic keys once so ids cannot leak across users.
    localStorage.removeItem(STORAGE_KEY_UPSTOX);
    localStorage.removeItem(STORAGE_KEY_ZERODHA);
    void fetchConnections();
  }, [fetchConnections]);

  useEffect(() => {
    if (!sessionId) {
      setCurrentSession(null);
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const session = await api.getSession(sessionId);
        if (cancelled) return;
        setCurrentSession(session);
        setSessionInfo({
          session_id: session.session_id,
          user_id: session.user_id,
          broker: session.broker,
          expires_at: session.expires_at,
          tenant_id: session.tenant_id,
        });
      } catch {
        if (cancelled) return;
        setCurrentSession(null);
        localStorage.removeItem(STORAGE_KEY_SESSION);
        setSessionId(null);
        setSessionInfo(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [sessionId, setSessionId, setSessionInfo]);

  // OAuth completion: desktop popup postMessage and mobile same-tab redirect.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const oauthResult = params.get('oauth');
    if (oauthResult) {
      clearPollingRef.current();
      setError('');
      setSuccessMessage('');
      const pendingBroker = window.sessionStorage.getItem(STORAGE_KEY_OAUTH_PENDING);
      const pendingConnectionRaw = window.sessionStorage.getItem(
        STORAGE_KEY_OAUTH_PENDING_CONNECTION,
      );
      const pendingConnectionId = pendingConnectionRaw ? Number(pendingConnectionRaw) : undefined;
      const broker = params.get('broker') || pendingBroker;
      const reason = params.get('reason') || '';
      window.sessionStorage.removeItem(STORAGE_KEY_OAUTH_PENDING);
      window.sessionStorage.removeItem(STORAGE_KEY_OAUTH_PENDING_CONNECTION);
      setOauthDialogOpen(false);

      const verify = async (): Promise<number | null> => {
        if (broker !== 'zerodha' && broker !== 'upstox') return null;
        try {
          const statuses =
            broker === 'zerodha'
              ? (await api.getZerodhaStatus()).connections
              : (await api.getUpstoxStatus()).connections;
          // Only the connection authorized by this OAuth flow counts; a valid
          // connection from an older account must not silently take over.
          const match = statuses.find(
            (status) =>
              status.connected &&
              status.token_status === 'valid' &&
              status.connection_id === pendingConnectionId,
          );
          return match?.connection_id ?? null;
        } catch {
          return null;
        }
      };

      void (async () => {
        const verifiedConnectionId = oauthResult === 'success' ? await verify() : null;
        await fetchConnections();
        if (oauthResult === 'success' && verifiedConnectionId != null) {
          await runActivation(broker as BrokerName, verifiedConnectionId);
        } else if (oauthResult === 'success') {
          setError(`${brokerLabel(broker)} connection could not be verified. Try again.`);
        } else {
          console.warn('OAuth callback failed', { broker, reason });
          setError(oauthFailureMessage(broker, reason));
        }
      })();

      window.history.replaceState({}, document.title, window.location.pathname);
    }

    const apiOrigin = (() => {
      try {
        return new URL(import.meta.env.VITE_API_BASE_URL || window.location.origin).origin;
      } catch {
        return window.location.origin;
      }
    })();

    const handleMessage = (event: MessageEvent) => {
      if (event.origin !== window.location.origin && event.origin !== apiOrigin) return;
      if (event.data?.type !== 'tradecraftx-oauth-complete') return;
      setBusyBroker(null);
      const pendingBroker = event.data.broker || window.sessionStorage.getItem(STORAGE_KEY_OAUTH_PENDING);
      const connectionId = getPendingConnectionId();
      window.sessionStorage.removeItem(STORAGE_KEY_OAUTH_PENDING);
      window.sessionStorage.removeItem(STORAGE_KEY_OAUTH_PENDING_CONNECTION);
      if (event.data.success && (pendingBroker === 'zerodha' || pendingBroker === 'upstox')) {
        void (async () => {
          if (connectionId !== undefined) await runActivation(pendingBroker, connectionId);
          else setError(`${brokerLabel(pendingBroker)} connection could not be verified. Try again.`);
          void fetchConnections();
        })();
      } else {
        console.warn('OAuth popup reported failure', event.data);
        setError(oauthFailureMessage(pendingBroker, event.data.reason));
      }
      setOauthDialogOpen(false);
    };
    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, [fetchConnections, runActivation]);

  useEffect(() => {
    return () => {
      if (pollingRef.current) clearTimeout(pollingRef.current);
    };
  }, []);

  const clearPolling = useCallback(() => {
    // Invalidate any in-flight poll chain before a new one can start.
    pollGenerationRef.current += 1;
    pollingActiveRef.current = false;
    if (pollingRef.current) {
      clearTimeout(pollingRef.current);
      pollingRef.current = null;
    }
    setPolling(false);
    setPollAttempts(0);
    pollAttemptsRef.current = 0;
  }, []);
  clearPollingRef.current = clearPolling;

  const checkBrokerStatus = useCallback(
    async (broker: BrokerName, connectionId?: number): Promise<BrokerStatus | null> => {
      try {
        const response =
          broker === 'upstox' ? await api.getUpstoxStatus() : await api.getZerodhaStatus();
        const match =
          (connectionId === undefined
            ? undefined
            : response.connections.find((status) => status.connection_id === connectionId)) ||
          response.connections.find(
            (status) => status.connected && status.token_status === 'valid',
          ) ||
          response.connections[0];
        if (!match) return null;
        return {
          connected: match.connected,
          broker_user_id: match.broker_user_id,
          token_updated_at: match.token_updated_at,
          connection_id: match.connection_id,
          token_status: match.token_status,
        };
      } catch {
        return null;
      }
    },
    [],
  );

  const startPolling = useCallback(
    async (broker: BrokerName, connectionId?: number) => {
      const generation = pollGenerationRef.current + 1;
      pollGenerationRef.current = generation;
      pollingActiveRef.current = true;
      pollAttemptsRef.current = 0;
      setPolling(true);
      setPollAttempts(0);
      setConnectionStatus(null);

      // An expired token on the pending connection is expected at reconnect:
      // it is the token we are about to replace. Remember it so polling waits
      // for new tokens instead of failing immediately.
      let baselineTokenUpdatedAt: string | null | undefined;
      if (connectionId !== undefined) {
        const known = statusByConnectionRef.current.has(connectionId);
        baselineTokenUpdatedAt = known
          ? statusByConnectionRef.current.get(connectionId)?.token_updated_at ?? null
          : undefined;
      }
      const isCurrent = () =>
        pollingActiveRef.current && generation === pollGenerationRef.current;

      const poll = async () => {
        if (!isCurrent()) return;
        const status = await checkBrokerStatus(broker, connectionId);
        if (!isCurrent()) return;
        setConnectionStatus(status);
        const tokenChanged =
          baselineTokenUpdatedAt !== undefined &&
          status?.token_updated_at !== baselineTokenUpdatedAt;

        if (status?.connected && status.token_status === 'valid') {
          clearPolling();
          window.sessionStorage.removeItem(STORAGE_KEY_OAUTH_PENDING);
          window.sessionStorage.removeItem(STORAGE_KEY_OAUTH_PENDING_CONNECTION);
          await fetchConnections();
          await runActivation(broker, status.connection_id);
          return;
        }
        // Only a newly stored token that is already expired is a real failure;
        // the pre-existing expired token is what this reconnect is replacing.
        if (status?.token_status === 'expired' && tokenChanged) {
          clearPolling();
          setError('Broker authentication expired. Reconnect.');
          return;
        }

        const attempts = pollAttemptsRef.current + 1;
        pollAttemptsRef.current = attempts;
        setPollAttempts(attempts);
        if (attempts >= MAX_POLL_ATTEMPTS) {
          clearPolling();
          setError(
            `${brokerLabel(broker)} connection timed out waiting for login. ` +
              `Last status: ${status?.token_status ?? 'not found'}. ` +
              'Check the login tab or server logs.',
          );
          return;
        }
        pollingRef.current = setTimeout(poll, POLL_INTERVAL_MS);
      };

      void poll();
    },
    [checkBrokerStatus, clearPolling, fetchConnections, runActivation],
  );

  const getStoredConnectionId = (broker: BrokerName): number | undefined => {
    const raw = window.localStorage.getItem(storageKeyFor(broker, user?.id));
    if (!raw) return undefined;
    const parsed = Number(raw);
    return Number.isFinite(parsed) ? parsed : undefined;
  };

  const launchOAuth = (
    authorizeUrl: string,
    broker: BrokerName,
    connectionId: number,
    popup: Window | null,
  ) => {
    window.sessionStorage.setItem(STORAGE_KEY_OAUTH_PENDING, broker);
    window.sessionStorage.setItem(STORAGE_KEY_OAUTH_PENDING_CONNECTION, String(connectionId));
    if (isMobile) {
      clearPollingRef.current();
      window.location.assign(authorizeUrl);
      return;
    }
    if (popup && !popup.closed) {
      popup.location.replace(authorizeUrl);
    }
  };

  const handleConnect = async (broker: BrokerName, connectionId?: number) => {
    if (connectInFlightRef.current === broker) return;
    // Open the popup synchronously inside the click handler. Opening it after
    // the /connect await makes browsers treat it as unsolicited and block it,
    // so the OAuth callback never reaches the backend.
    const popup = isMobile
      ? null
      : window.open('about:blank', 'tradecraftx-oauth', 'width=600,height=760');
    if (!isMobile && !popup) {
      setError('Login popup was blocked. Allow popups for this site and try again.');
      return;
    }

    connectInFlightRef.current = broker;
    setBusyBroker(broker);
    setError('');
    setSuccessMessage('');
    try {
      const response =
        broker === 'upstox'
          ? await api.connectUpstox(
              connectionId ?? getStoredConnectionId(broker),
              isMobile ? 'mobile' : 'popup',
            )
          : await api.connectZerodha(
              connectionId ?? getStoredConnectionId(broker),
              isMobile ? 'mobile' : 'popup',
            );
      setOauthStep(broker);
      launchOAuth(response.authorize_url, broker, response.connection_id, popup);
      if (!isMobile) {
        if (!popup || popup.closed) {
          setError('Login popup was closed. Allow popups for this site and try again.');
          return;
        }
        setOauthDialogOpen(true);
        void startPolling(broker, response.connection_id);
      }
    } catch (err) {
      popup?.close();
      setError(connectionErrorMessage(broker, err));
      if (err instanceof Error && err.message) {
        console.error(err.message);
      }
    } finally {
      connectInFlightRef.current = null;
      if (!isMobile) setBusyBroker(null);
    }
  };

  const handleRefreshData = async () => {
    if (!sessionId) return;
    setError('');
    setSuccessMessage('');
    setRefreshingData(true);
    try {
      const session = await api.refreshSession(sessionId);
      setCurrentSession(session);
      setSessionInfo({
        session_id: session.session_id,
        user_id: session.user_id,
        broker: session.broker,
        expires_at: session.expires_at,
        tenant_id: session.tenant_id,
      });
      setSuccessMessage('Session data refreshed.');
      setLastRefreshedAt(new Date().toISOString());
      await fetchConnections();
    } catch (err) {
      setError(friendlyError(err instanceof Error ? err.message : 'Session could not be started.'));
      if (err instanceof Error && err.message.toLowerCase().includes('not found')) {
        setCurrentSession(null);
        localStorage.removeItem(STORAGE_KEY_SESSION);
        setSessionId(null);
        setSessionInfo(null);
      }
    } finally {
      setRefreshingData(false);
    }
  };

  const confirmEndSession = async () => {
    if (!sessionId) return;
    setEndingSession(true);
    setError('');
    setSuccessMessage('');
    try {
      await api.closeSession(sessionId);
      setCurrentSession(null);
      clearSession();
      setSuccessMessage('Trading session ended. The broker connection remains active.');
      await fetchConnections();
    } catch (err) {
      setError(friendlyError(err instanceof Error ? err.message : 'Session could not be ended.'));
    } finally {
      setEndingSession(false);
      setEndSessionDialogOpen(false);
    }
  };

  const confirmDisconnect = async () => {
    const broker = disconnectBroker;
    if (!broker) return;
    setBusyBroker(broker);
    setError('');
    setSuccessMessage('');
    try {
      if (broker === 'upstox') await api.disconnectUpstox();
      else await api.disconnectZerodha();
      setCurrentSession(null);
      clearSession();
      setSuccessMessage(`${brokerLabel(broker)} disconnected.`);
      await fetchConnections();
    } catch (err) {
      setError(
        `${brokerLabel(broker)} disconnect failed. Try again. ${
          err instanceof Error ? err.message : ''
        }`.trim(),
      );
    } finally {
      setBusyBroker(null);
      setDisconnectBroker(null);
    }
  };

  const activeConnectionId = activeConnection?.broker_connection_id ?? null;
  const brokerCards: BrokerCardModel[] = BROKERS.map((broker) => {
    const brokerConnections = connections.filter((connection) => connection.broker_name === broker);
    const candidates: Array<BrokerAccountOption & { tokenUpdatedAt: string | null }> = [];
    for (const connection of brokerConnections) {
      const status = statusByConnection.get(connection.id);
      if (status?.connected && status.token_status === 'valid' && status.broker_user_id) {
        candidates.push({
          connectionId: connection.id,
          brokerUserId: status.broker_user_id,
          tokenUpdatedAt: status.token_updated_at,
        });
      }
    }
    // Prefer the active connection, then the most recently authenticated record,
    // so historical rows for the same broker user never duplicate a card.
    candidates.sort((left, right) => {
      if (left.connectionId === activeConnectionId) return -1;
      if (right.connectionId === activeConnectionId) return 1;
      return (right.tokenUpdatedAt || '').localeCompare(left.tokenUpdatedAt || '');
    });
    const uniqueAccounts = new Map<string, BrokerAccountOption>();
    for (const candidate of candidates) {
      if (!uniqueAccounts.has(candidate.brokerUserId)) {
        uniqueAccounts.set(candidate.brokerUserId, {
          connectionId: candidate.connectionId,
          brokerUserId: candidate.brokerUserId,
        });
      }
    }
    const accounts = Array.from(uniqueAccounts.values());
    const explicitlySelected = selectedAccountByBroker[broker];
    const selected =
      accounts.find((account) => account.connectionId === explicitlySelected) ||
      accounts.find((account) => account.connectionId === activeConnectionId) ||
      (accounts.length === 1 ? accounts[0] : undefined);
    const needsSelection = accounts.length > 1 && !selected;
    const expired = brokerConnections.some(
      (connection) => statusByConnection.get(connection.id)?.token_status === 'expired',
    );
    const isActive = Boolean(selected && activeConnectionId === selected.connectionId);
    const hasSession = Boolean(sessionId && currentSession && isActive);
    const sessionReady = isActive && hasSession && readinessStatus === 'READY';
    const busy = busyBroker === broker || activatingBroker === broker;

    let status: BrokerCardStatus;
    let detail: string | null = null;
    if (busy || (oauthStep === broker && polling)) {
      status = 'CONNECTING';
      detail =
        busyBroker === broker || (oauthStep === broker && polling)
          ? 'Authenticating...'
          : readinessStatus === 'LOADING'
            ? 'Loading data...'
            : 'Starting session...';
    } else if (needsSelection) {
      status = 'ATTENTION_REQUIRED';
      detail = 'Select an account to continue.';
    } else if (accounts.length === 0 && expired) {
      status = 'ATTENTION_REQUIRED';
      detail = 'Broker authentication expired. Reconnect.';
    } else if (isActive && readinessStatus === 'ERROR') {
      status = 'ATTENTION_REQUIRED';
      detail = 'Session could not be started. Retry.';
    } else if (sessionReady) {
      status = 'READY';
    } else {
      status = 'NOT_CONNECTED';
    }

    return {
      broker,
      status,
      statusLabel: STATUS_LABELS[status],
      detail,
      accounts,
      selectedConnectionId: selected?.connectionId ?? null,
      accountId: selected?.brokerUserId ?? null,
      sessionInfo: sessionReady
        ? {
            holdings: refreshingData ? 'Loading...' : 'Loaded',
            lastRefreshed: formatClock(lastRefreshedAt),
          }
        : null,
      primaryLabel:
        status === 'CONNECTING'
          ? 'Connecting...'
          : sessionReady
            ? 'Refresh Data'
            : accounts.length > 0
              ? `Use ${brokerLabel(broker)}`
              : 'Connect',
      primaryDisabled: needsSelection,
      busy,
      hasSession,
      canManage: accounts.length > 0 || expired,
    };
  });

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  const displayedError = error || (readinessStatus === 'ERROR' && sessionMessage ? friendlyError(sessionMessage) : '');

  return (
    <Box>
      <ResponsivePageHeader
        title="Broker Accounts"
        description="Choose the broker for this device's trading session"
        actions={
          <Button
            variant="outlined"
            startIcon={<RefreshIcon />}
            onClick={() => void fetchConnections()}
            disabled={refreshing || Boolean(busyBroker)}
            fullWidth={isMobile}
            sx={{ minHeight: isMobile ? 44 : undefined }}
          >
            {refreshing ? 'Refreshing...' : 'Refresh Status'}
          </Button>
        }
      />

      {displayedError && (
        <Alert
          severity="error"
          sx={{ mb: 2 }}
          onClose={() => {
            setError('');
            setSuccessMessage('');
          }}
          action={
            brokerConnected && readinessStatus === 'ERROR' ? (
              <Button color="inherit" size="small" onClick={() => void retrySession()}>
                Retry
              </Button>
            ) : undefined
          }
        >
          {displayedError}
        </Alert>
      )}
      {successMessage && !displayedError && (
        <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccessMessage('')}>
          {successMessage}
        </Alert>
      )}

      <Box
        sx={{
          display: 'grid',
          gap: 2,
          gridTemplateColumns: { xs: '1fr', md: 'repeat(2, minmax(0, 1fr))' },
        }}
      >
        {brokerCards.map((card) => (
          <BrokerAccountCard
            key={card.broker}
            broker={card.broker}
            status={card.status}
            statusLabel={card.statusLabel}
            detail={card.detail}
            accounts={card.accounts}
            selectedConnectionId={card.selectedConnectionId}
            accountId={card.accountId}
            sessionInfo={card.sessionInfo}
            primaryLabel={card.primaryLabel}
            primaryDisabled={card.primaryDisabled}
            busy={card.busy}
            hasSession={card.hasSession}
            canManage={card.canManage}
            onSelectAccount={(connectionId) =>
              setSelectedAccountByBroker((previous) => ({ ...previous, [card.broker]: connectionId }))
            }
            onPrimary={() => {
              if (card.status === 'READY') void handleRefreshData();
              else if (card.selectedConnectionId !== null)
                void runActivation(card.broker, card.selectedConnectionId);
              else if (card.accounts.length > 0) return;
              else void handleConnect(card.broker);
            }}
            onRefreshStatus={() => void fetchConnections()}
            onEndSession={() => setEndSessionDialogOpen(true)}
            onReconnect={() =>
              void handleConnect(card.broker, card.selectedConnectionId ?? undefined)
            }
            onDisconnect={() => setDisconnectBroker(card.broker)}
          />
        ))}
      </Box>

      {/* OAuth progress dialog (desktop popup; mobile uses same-tab redirect) */}
      <ResponsiveDialog
        open={oauthDialogOpen}
        onClose={() => {
          clearPolling();
          setOauthDialogOpen(false);
          setOauthStep(null);
          setConnectionStatus(null);
          setBusyBroker(null);
        }}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle>Connecting {brokerLabel(oauthStep)}</DialogTitle>
        <DialogContent>
          <Box sx={{ textAlign: 'center', py: 2 }}>
            {connectionStatus?.connected ? (
              <>
                <CheckIcon color="success" sx={{ fontSize: 48, mb: 1 }} />
                <Typography>Connected. Starting your trading session...</Typography>
              </>
            ) : connectionStatus?.token_status === 'expired' && !polling ? (
              <>
                <WarningIcon color="warning" sx={{ fontSize: 48, mb: 1 }} />
                <Typography>Broker authentication expired. Reconnect.</Typography>
              </>
            ) : polling ? (
              <>
                <CircularProgress sx={{ mb: 2 }} />
                <Typography>Authenticating...</Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                  Complete the login in the opened tab, then close it.
                </Typography>
              </>
            ) : pollAttempts >= MAX_POLL_ATTEMPTS ? (
              <>
                <ErrorIcon color="error" sx={{ fontSize: 48, mb: 1 }} />
                <Typography>{brokerLabel(oauthStep)} connection failed. Try again.</Typography>
              </>
            ) : (
              <Typography>
                Complete {brokerLabel(oauthStep)} login in the opened tab, then select “I completed
                login”.
              </Typography>
            )}
          </Box>
        </DialogContent>
        <DialogActions>
          {connectionStatus?.connected || connectionStatus?.token_status === 'expired' ? (
            <Button
              onClick={() => {
                clearPolling();
                setOauthDialogOpen(false);
                setOauthStep(null);
                setConnectionStatus(null);
                setBusyBroker(null);
              }}
              variant="contained"
            >
              Done
            </Button>
          ) : (
            <>
              <Button
                onClick={() => {
                  clearPolling();
                  setOauthDialogOpen(false);
                  setOauthStep(null);
                  setConnectionStatus(null);
                  setBusyBroker(null);
                }}
              >
                Cancel
              </Button>
              {pollAttempts < MAX_POLL_ATTEMPTS && (
                <Button
                  onClick={() => oauthStep && void startPolling(oauthStep, getPendingConnectionId())}
                  variant="contained"
                  disabled={polling}
                >
                  I completed login
                </Button>
              )}
            </>
          )}
        </DialogActions>
      </ResponsiveDialog>

      {/* End session confirmation */}
      <ResponsiveDialog
        open={endSessionDialogOpen}
        onClose={() => setEndSessionDialogOpen(false)}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle>End trading session?</DialogTitle>
        <DialogContent>
          <Typography variant="body2">
            This ends only this device's trading session. The broker connection stays connected,
            and sessions on other devices are unaffected.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEndSessionDialogOpen(false)}>Cancel</Button>
          <Button
            onClick={() => void confirmEndSession()}
            color="error"
            variant="contained"
            disabled={endingSession}
          >
            {endingSession ? 'Ending...' : 'End Session'}
          </Button>
        </DialogActions>
      </ResponsiveDialog>

      {/* Disconnect confirmation */}
      <ResponsiveDialog
        open={Boolean(disconnectBroker)}
        onClose={() => setDisconnectBroker(null)}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle>Disconnect {brokerLabel(disconnectBroker)}?</DialogTitle>
        <DialogContent>
          <Typography variant="body2">
            This will remove the saved {brokerLabel(disconnectBroker)} connection from TradeCraftWeb
            and may affect other devices using this account.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDisconnectBroker(null)}>Cancel</Button>
          <Button
            onClick={() => void confirmDisconnect()}
            color="error"
            variant="contained"
            disabled={busyBroker !== null}
          >
            {busyBroker ? 'Disconnecting...' : 'Disconnect'}
          </Button>
        </DialogActions>
      </ResponsiveDialog>
    </Box>
  );
}
