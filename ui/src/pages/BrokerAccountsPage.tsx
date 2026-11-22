import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  Menu,
  MenuItem,
  Step,
  StepLabel,
  Stepper,
  Tooltip,
  Typography,
  useMediaQuery,
  useTheme,
} from '@mui/material';
import {
  Add as AddIcon,
  Check as CheckIcon,
  Cloud as ZerodhaIcon,
  CloudDone as UpstoxIcon,
  Delete as DeleteIcon,
  Error as ErrorIcon,
  MoreVert as MoreIcon,
  Refresh as RefreshIcon,
  StopCircle as EndSessionIcon,
  Warning as WarningIcon,
} from '@mui/icons-material';
import { api } from '../api/client';
import { useBrokerSessionOrchestrator } from '../context/BrokerSessionContext';
import { useSession } from '../context/SessionContext';
import type {
  BrokerAccountStatus,
  BrokerConnectionResponse,
  SessionResponse,
} from '../types';
import { ResponsiveDialog } from '../components/ResponsiveDialog';
import { ResponsivePageHeader } from '../components/ResponsivePageHeader';
import { MobileBrokerAccountCard } from '../components/broker-connections/MobileBrokerAccountCard';

const POLL_INTERVAL_MS = 2000;
const MAX_POLL_ATTEMPTS = 30;

const STORAGE_KEY_UPSTOX = 'tradecraftx_upstox_connection_id';
const STORAGE_KEY_ZERODHA = 'tradecraftx_zerodha_connection_id';
const STORAGE_KEY_SESSION = 'tradecraftx_session_id';
const STORAGE_KEY_OAUTH_PENDING = 'tradecraftx_oauth_pending_broker';

type BrokerName = 'upstox' | 'zerodha';
type ConnectionTone = 'default' | 'warning' | 'success';

interface BrokerStatus {
  connected: boolean;
  broker_user_id: string | null;
  token_updated_at: string | null;
  connection_id: number;
  expires_at: string | null;
  token_status: 'valid' | 'expired' | 'missing';
}

interface AccountView {
  connection: BrokerConnectionResponse;
  status: BrokerStatus | null;
  connected: boolean;
  connectionLabel: string;
  connectionTone: ConnectionTone;
  accountId: string;
  tradingStatus: string;
  dataStatus: string;
  lastRefresh: string;
  hasSession: boolean;
}

function brokerLabel(broker: string | null | undefined): string {
  if (broker === 'zerodha') return 'Zerodha';
  if (broker === 'upstox') return 'Upstox';
  return broker ? broker.charAt(0).toUpperCase() + broker.slice(1) : 'Broker';
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return 'Not available';
  try {
    return new Date(dateStr).toLocaleString();
  } catch {
    return dateStr;
  }
}

function connectionView(status: BrokerStatus | null): {
  label: string;
  tone: ConnectionTone;
  connected: boolean;
} {
  if (!status || status.token_status === 'missing') {
    return { label: 'Disconnected', tone: 'default', connected: false };
  }
  if (status.token_status === 'expired' || !status.connected) {
    return { label: 'Expired', tone: 'warning', connected: false };
  }
  return { label: 'Connected', tone: 'success', connected: true };
}

function BrokerIcon({ broker }: { broker: string }) {
  return broker === 'upstox' ? (
    <UpstoxIcon color="primary" fontSize="small" />
  ) : (
    <ZerodhaIcon fontSize="small" sx={{ color: '#283195' }} />
  );
}

export default function BrokerAccountsPage() {
  const [connections, setConnections] = useState<BrokerConnectionResponse[]>([]);
  const [statusByConnection, setStatusByConnection] = useState<Map<number, BrokerStatus>>(
    new Map(),
  );
  const [upstoxStatus, setUpstoxStatus] = useState<BrokerStatus | null>(null);
  const [zerodhaStatus, setZerodhaStatus] = useState<BrokerStatus | null>(null);
  const [activeConnectionId, setActiveConnectionId] = useState<number | null>(null);
  const [currentSession, setCurrentSession] = useState<SessionResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshingData, setRefreshingData] = useState(false);
  const [endingSession, setEndingSession] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState('');
  const [successMessage, setSuccessMessage] = useState('');
  const [lastRefreshedAt, setLastRefreshedAt] = useState<string | null>(null);
  const [disconnectBroker, setDisconnectBroker] = useState<BrokerName | null>(null);
  const [endSessionDialogOpen, setEndSessionDialogOpen] = useState(false);
  const [accountMenuAnchor, setAccountMenuAnchor] = useState<HTMLElement | null>(null);
  const [menuAccount, setMenuAccount] = useState<AccountView | null>(null);

  // OAuth flow state
  const [oauthDialogOpen, setOauthDialogOpen] = useState(false);
  const [oauthStep, setOauthStep] = useState<BrokerName | null>(null);
  const [polling, setPolling] = useState(false);
  const [pollAttempts, setPollAttempts] = useState(0);
  const [connectionStatus, setConnectionStatus] = useState<BrokerStatus | null>(null);

  const pollingRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pollAttemptsRef = useRef(0);
  const pollingActiveRef = useRef(false);
  const clearPollingRef = useRef<() => void>(() => {});

  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

  const {
    status: readinessStatus,
    message: sessionMessage,
    brokerConnected,
    candidates,
    requiresSelection,
    bootstrap: bootstrapSession,
    retry: retrySession,
    clearSession,
  } = useBrokerSessionOrchestrator();
  const { sessionId, setSessionId, setSessionInfo } = useSession();

  const fetchConnections = useCallback(async () => {
    try {
      const data = await api.listBrokerConnections();
      setConnections(data);

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
                expires_at: match.expires_at,
                token_status: match.token_status,
              });
            }
          } catch {
            // A missing status is treated as disconnected for this account.
          }
        }),
      );
      setStatusByConnection(statuses);

      for (const broker of ['upstox', 'zerodha'] as BrokerName[]) {
        const firstConnected = data.find(
          (connection) =>
            connection.broker_name === broker && statuses.get(connection.id)?.connected,
        );
        const status = firstConnected ? statuses.get(firstConnected.id) ?? null : null;
        if (broker === 'upstox') setUpstoxStatus(status);
        else setZerodhaStatus(status);
        const storageKey = broker === 'upstox' ? STORAGE_KEY_UPSTOX : STORAGE_KEY_ZERODHA;
        if (status) localStorage.setItem(storageKey, String(status.connection_id));
        else localStorage.removeItem(storageKey);
      }

      try {
        const active = await api.getActiveConnection();
        setActiveConnectionId(active.broker_connection_id);
      } catch {
        setActiveConnectionId(null);
      }

      setLastRefreshedAt(new Date().toISOString());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load broker accounts');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
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
      const pendingBroker = window.sessionStorage.getItem(STORAGE_KEY_OAUTH_PENDING);
      const broker = params.get('broker') || pendingBroker;
      const reason = params.get('reason') || '';
      window.sessionStorage.removeItem(STORAGE_KEY_OAUTH_PENDING);
      setOauthDialogOpen(false);

      const verify = async (): Promise<boolean> => {
        if (!broker) return false;
        try {
          const statuses =
            broker === 'zerodha'
              ? (await api.getZerodhaStatus()).connections
              : (await api.getUpstoxStatus()).connections;
          return statuses.some((status) => status.connected);
        } catch {
          return false;
        }
      };

      void (async () => {
        const verified = oauthResult === 'success' ? await verify() : false;
        await fetchConnections();
        if (oauthResult === 'success' && verified) {
          setSuccessMessage(`${brokerLabel(broker)} connected successfully.`);
          await bootstrapSession({ broker_name: broker ?? undefined });
        } else if (oauthResult === 'success') {
          setError(`${brokerLabel(broker)} connection could not be verified. Please try again.`);
        } else {
          const suffix = reason === 'cancelled' ? ' was cancelled.' : ' could not be completed.';
          setError(`${brokerLabel(broker)} connection${suffix} Please try again.`);
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
      const pendingBroker = event.data.broker || window.sessionStorage.getItem(STORAGE_KEY_OAUTH_PENDING);
      window.sessionStorage.removeItem(STORAGE_KEY_OAUTH_PENDING);
      if (event.data.success) {
        setSuccessMessage(`${brokerLabel(pendingBroker)} connection completed. Status refreshed.`);
        void bootstrapSession({ broker_name: pendingBroker ?? undefined });
      } else {
        setError(`${brokerLabel(pendingBroker)} connection could not be completed. Please try again.`);
      }
      void fetchConnections();
    };
    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, [bootstrapSession, fetchConnections]);

  useEffect(() => {
    return () => {
      if (pollingRef.current) clearTimeout(pollingRef.current);
    };
  }, []);

  const clearPolling = useCallback(() => {
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

  const checkBrokerStatus = useCallback(async (broker: BrokerName) => {
    try {
      const response =
        broker === 'upstox' ? await api.getUpstoxStatus() : await api.getZerodhaStatus();
      const first = response.connections[0];
      if (!first) return null;
      return {
        connected: first.connected,
        broker_user_id: first.broker_user_id,
        token_updated_at: first.token_updated_at,
        connection_id: first.connection_id,
        expires_at: first.expires_at,
        token_status: first.token_status,
      };
    } catch {
      return null;
    }
  }, []);

  const startPolling = useCallback(
    async (broker: BrokerName) => {
      pollingActiveRef.current = true;
      pollAttemptsRef.current = 0;
      setPolling(true);
      setPollAttempts(0);
      setConnectionStatus(null);

      const poll = async () => {
        if (!pollingActiveRef.current) return;
        const status = await checkBrokerStatus(broker);
        setConnectionStatus(status);

        if (status?.connected) {
          clearPolling();
          await fetchConnections();
          void bootstrapSession({ broker_name: broker });
          return;
        }
        if (status?.token_status === 'expired') {
          clearPolling();
          return;
        }

        const attempts = pollAttemptsRef.current + 1;
        pollAttemptsRef.current = attempts;
        setPollAttempts(attempts);
        if (attempts >= MAX_POLL_ATTEMPTS) {
          clearPolling();
          setError('Connection timeout. Please try again.');
          return;
        }
        pollingRef.current = setTimeout(poll, POLL_INTERVAL_MS);
      };

      void poll();
    },
    [bootstrapSession, checkBrokerStatus, clearPolling, fetchConnections],
  );

  const getStoredConnectionId = (key: string): number | undefined => {
    const raw = window.localStorage.getItem(key);
    if (!raw) return undefined;
    const parsed = Number(raw);
    return Number.isFinite(parsed) ? parsed : undefined;
  };

  const launchOAuth = (
    authorizeUrl: string,
    broker: BrokerName,
  ) => {
    window.sessionStorage.setItem(STORAGE_KEY_OAUTH_PENDING, broker);
    if (isMobile) {
      clearPollingRef.current();
      window.location.assign(authorizeUrl);
      return;
    }
    window.open(authorizeUrl, '_blank');
  };

  const handleConnect = async (broker: BrokerName) => {
    setConnecting(true);
    setError('');
    setSuccessMessage('');
    try {
      const response =
        broker === 'upstox'
          ? await api.connectUpstox(
              getStoredConnectionId(STORAGE_KEY_UPSTOX),
              isMobile ? 'mobile' : 'popup',
            )
          : await api.connectZerodha(
              getStoredConnectionId(STORAGE_KEY_ZERODHA),
              isMobile ? 'mobile' : 'popup',
            );
      setOauthStep(broker);
      launchOAuth(response.authorize_url, broker);
      if (!isMobile) {
        setOauthDialogOpen(true);
        void startPolling(broker);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to initiate ${brokerLabel(broker)} connection`);
    } finally {
      setConnecting(false);
    }
  };

  const handleRefreshData = async () => {
    if (!sessionId) {
      await bootstrapSession({});
      return;
    }
    setRefreshingData(true);
    setError('');
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
      await fetchConnections();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to refresh session data');
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
    try {
      await api.closeSession(sessionId);
      setCurrentSession(null);
      clearSession();
      setSuccessMessage('Trading session ended. The broker connection remains active.');
      await fetchConnections();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to end trading session');
    } finally {
      setEndingSession(false);
      setEndSessionDialogOpen(false);
    }
  };

  const confirmDisconnect = async () => {
    const broker = disconnectBroker;
    if (!broker) return;
    setConnecting(true);
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
      setError(err instanceof Error ? err.message : `Failed to disconnect ${broker}`);
    } finally {
      setConnecting(false);
      setDisconnectBroker(null);
    }
  };

  const handleSelectAccount = async (candidate: BrokerAccountStatus) => {
    setError('');
    await bootstrapSession({
      broker_name: candidate.broker_name,
      broker_connection_id: candidate.connection_id,
    });
  };

  const selectionBrokers = Array.from(
    new Set(candidates.map((candidate) => candidate.broker_name).filter(Boolean)),
  );

  const accountViews: AccountView[] = connections.map((connection) => {
    const status = statusByConnection.get(connection.id) ?? null;
    const view = connectionView(status);
    const isActive =
      activeConnectionId === connection.id ||
      (Boolean(currentSession) && currentSession?.broker === connection.broker_name);
    const hasSession = Boolean(sessionId && currentSession && isActive);

    let tradingStatus = 'No session';
    if (view.connected) {
      if (hasSession && readinessStatus === 'READY') tradingStatus = 'Ready to Trade';
      else if (isActive && readinessStatus === 'INITIALIZING') {
        tradingStatus = 'Preparing trading session.';
      } else if (isActive && readinessStatus === 'LOADING') {
        tradingStatus = 'Loading session data.';
      } else if (isActive && readinessStatus === 'CONNECTED') {
        tradingStatus = 'Broker connected. Preparing trading session.';
      } else if (isActive && readinessStatus === 'ERROR') {
        tradingStatus = 'Unable to initialize session. Retry.';
      } else tradingStatus = 'Not started';
    }

    const dataStatus =
      refreshingData || (isActive && readinessStatus === 'LOADING')
        ? 'Loading session data…'
        : hasSession
          ? 'Data loaded'
          : 'Not loaded';

    return {
      connection,
      status,
      connected: view.connected,
      connectionLabel: view.label,
      connectionTone: view.tone,
      accountId: status?.broker_user_id || `#${connection.id}`,
      tradingStatus,
      dataStatus,
      lastRefresh: formatDate(lastRefreshedAt),
      hasSession,
    };
  });

  const openAccountMenu = (event: React.MouseEvent<HTMLElement>, account: AccountView) => {
    setMenuAccount(account);
    setAccountMenuAnchor(event.currentTarget);
  };

  const closeAccountMenu = () => {
    setAccountMenuAnchor(null);
    setMenuAccount(null);
  };

  const runAccountAction = (action: () => void) => {
    closeAccountMenu();
    action();
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      <ResponsivePageHeader
        title="Broker Accounts"
        description="Manage broker connections and this device's trading session"
        actions={
          <Button
            variant="outlined"
            startIcon={<RefreshIcon />}
            onClick={() => {
              void fetchConnections();
            }}
            disabled={refreshing}
            fullWidth={isMobile}
            sx={{ minHeight: isMobile ? 44 : undefined }}
          >
            {refreshing ? 'Refreshing...' : 'Refresh Status'}
          </Button>
        }
      />

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}
      {successMessage && (
        <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccessMessage('')}>
          {successMessage}
        </Alert>
      )}
      {requiresSelection && (
        <Alert severity="info" sx={{ mb: 2 }}>
          <Typography variant="body2" sx={{ mb: 1 }}>
            {sessionMessage || 'Multiple broker accounts detected. Select one to continue.'}
          </Typography>
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
            {selectionBrokers.length > 1
              ? selectionBrokers.map((broker) => (
                  <Button
                    key={broker}
                    size="small"
                    variant="outlined"
                    onClick={() => void bootstrapSession({ broker_name: broker })}
                  >
                    {brokerLabel(broker)}
                  </Button>
                ))
              : candidates.map((candidate) => (
                  <Button
                    key={candidate.connection_id}
                    size="small"
                    variant="outlined"
                    onClick={() => void handleSelectAccount(candidate)}
                  >
                    {candidate.broker_user_id || `#${candidate.connection_id}`}
                  </Button>
                ))}
          </Box>
        </Alert>
      )}
      {readinessStatus === 'ERROR' && sessionMessage && !requiresSelection && (
        <Alert
          severity="warning"
          sx={{ mb: 2 }}
          action={
            brokerConnected ? (
              <Button color="inherit" size="small" onClick={() => void retrySession()}>
                Retry
              </Button>
            ) : (
              <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                <Button color="inherit" size="small" onClick={() => void handleConnect('upstox')}>
                  Connect Upstox
                </Button>
                <Button color="inherit" size="small" onClick={() => void handleConnect('zerodha')}>
                  Connect Zerodha
                </Button>
              </Box>
            )
          }
        >
          {sessionMessage}
        </Alert>
      )}

      {isMobile ? (
        <Box>
          {accountViews.map((account) => (
            <MobileBrokerAccountCard
              key={account.connection.id}
              broker={account.connection.broker_name as BrokerName}
              accountId={account.accountId}
              connectionLabel={account.connectionLabel}
              connectionTone={account.connectionTone}
              tradingStatus={account.tradingStatus}
              dataStatus={account.dataStatus}
              lastRefresh={account.lastRefresh}
              connecting={connecting}
              refreshing={refreshingData}
              hasSession={account.hasSession}
              onPrimary={() => {
                if (account.connected) void handleRefreshData();
                else void handleConnect(account.connection.broker_name as BrokerName);
              }}
              onRefreshStatus={() => {
                void fetchConnections();
              }}
              onEndSession={() => setEndSessionDialogOpen(true)}
              onReconnect={() => void handleConnect(account.connection.broker_name as BrokerName)}
              onDisconnect={() => setDisconnectBroker(account.connection.broker_name as BrokerName)}
            />
          ))}
        </Box>
      ) : (
        <Box sx={{ display: 'grid', gap: 1.5 }}>
          {accountViews.map((account) => (
            <Card key={account.connection.id}>
              <CardContent sx={{ py: 1.75, '&:last-child': { pb: 1.75 } }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, minWidth: 0 }}>
                  <BrokerIcon broker={account.connection.broker_name} />
                  <Typography variant="subtitle1" fontWeight={700}>
                    {brokerLabel(account.connection.broker_name)}
                  </Typography>
                  <Typography variant="body2" color="text.secondary" noWrap>
                    {account.accountId}
                  </Typography>
                  <Chip
                    label={account.connectionLabel}
                    size="small"
                    color={account.connectionTone}
                    icon={account.connectionTone === 'success' ? <CheckIcon /> : <ErrorIcon />}
                  />
                  <Chip
                    label={account.tradingStatus}
                    size="small"
                    variant="outlined"
                    color={account.tradingStatus === 'Ready to Trade' ? 'success' : 'default'}
                  />
                  <Box sx={{ flex: 1 }} />
                  <Tooltip title="More actions">
                    <IconButton
                      size="small"
                      onClick={(event) => openAccountMenu(event, account)}
                      aria-label={`More actions for ${brokerLabel(account.connection.broker_name)}`}
                    >
                      <MoreIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                </Box>

                <Box
                  sx={{
                    display: 'grid',
                    gridTemplateColumns: { xs: '1fr', sm: 'repeat(4, minmax(0, 1fr))' },
                    gap: 1,
                    mt: 1.5,
                  }}
                >
                  <Detail label="Connection" value={account.connectionLabel} />
                  <Detail label="Trading session" value={account.tradingStatus} />
                  <Detail label="Data loading" value={account.dataStatus} />
                  <Detail label="Last refresh" value={account.lastRefresh} />
                </Box>

                <Box sx={{ display: 'flex', gap: 1, mt: 1.5 }}>
                  <Button
                    variant={account.connected ? 'outlined' : 'contained'}
                    size="small"
                    startIcon={account.connected ? <RefreshIcon /> : <AddIcon />}
                    onClick={() => {
                      if (account.connected) void handleRefreshData();
                      else void handleConnect(account.connection.broker_name as BrokerName);
                    }}
                    disabled={connecting || refreshingData}
                  >
                    {account.connected ? 'Refresh Data' : 'Connect'}
                  </Button>
                </Box>
              </CardContent>
            </Card>
          ))}
        </Box>
      )}

      <Menu
        anchorEl={accountMenuAnchor}
        open={Boolean(accountMenuAnchor)}
        onClose={closeAccountMenu}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
        transformOrigin={{ vertical: 'top', horizontal: 'right' }}
      >
        <MenuItem
          onClick={() => {
            void fetchConnections();
            closeAccountMenu();
          }}
        >
          <RefreshIcon fontSize="small" sx={{ mr: 1 }} />
          Refresh status
        </MenuItem>
        {menuAccount?.connected && (
          <MenuItem
            onClick={() =>
              runAccountAction(() => void handleConnect(menuAccount.connection.broker_name as BrokerName))
            }
            disabled={connecting}
          >
            <AddIcon fontSize="small" sx={{ mr: 1 }} />
            Reconnect broker
          </MenuItem>
        )}
        {menuAccount?.hasSession && (
          <MenuItem onClick={() => runAccountAction(() => setEndSessionDialogOpen(true))}>
            <EndSessionIcon fontSize="small" sx={{ mr: 1 }} />
            End session
          </MenuItem>
        )}
        {menuAccount?.connected && (
          <MenuItem
            onClick={() =>
              runAccountAction(() =>
                setDisconnectBroker(menuAccount.connection.broker_name as BrokerName),
              )
            }
            disabled={connecting}
          >
            <DeleteIcon fontSize="small" sx={{ mr: 1 }} />
            Disconnect broker
          </MenuItem>
        )}
      </Menu>

      {/* OAuth Polling Dialog */}
      <ResponsiveDialog
        open={oauthDialogOpen}
        onClose={() => {
          clearPolling();
          setOauthDialogOpen(false);
          setOauthStep(null);
          setConnectionStatus(null);
        }}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Connecting {brokerLabel(oauthStep)}...</DialogTitle>
        <DialogContent>
          <Stepper activeStep={oauthStep === 'zerodha' ? 1 : 0} sx={{ mb: 3 }}>
            <Step>
              <StepLabel>Upstox</StepLabel>
            </Step>
            <Step>
              <StepLabel>Zerodha</StepLabel>
            </Step>
          </Stepper>

          {connectionStatus?.connected && (
            <Box sx={{ textAlign: 'center', py: 2 }}>
              <CheckIcon color="success" sx={{ fontSize: 48, mb: 2 }} />
              <Typography variant="h6" color="success">
                Connected successfully!
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Broker User ID: {connectionStatus.broker_user_id || 'N/A'}
              </Typography>
            </Box>
          )}
          {connectionStatus?.token_status === 'expired' && !polling && (
            <Box sx={{ textAlign: 'center', py: 2 }}>
              <WarningIcon color="warning" sx={{ fontSize: 48, mb: 2 }} />
              <Typography variant="h6" color="warning">
                Token Expired
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Your access token has expired. Please reconnect.
              </Typography>
            </Box>
          )}
          {polling && !connectionStatus?.connected && (
            <Box sx={{ textAlign: 'center', py: 2 }}>
              <CircularProgress sx={{ mb: 2 }} />
              <Typography>
                Waiting for authentication... (
                {Math.floor((pollAttempts * POLL_INTERVAL_MS) / 1000)}s / 60s)
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                Complete the login in the opened tab, then close it.
              </Typography>
            </Box>
          )}
          {!polling && !connectionStatus?.connected && pollAttempts >= MAX_POLL_ATTEMPTS && (
            <Box sx={{ textAlign: 'center', py: 2 }}>
              <ErrorIcon color="error" sx={{ fontSize: 48, mb: 2 }} />
              <Typography color="error">Connection timed out</Typography>
              <Button
                variant="outlined"
                onClick={() => oauthStep && void startPolling(oauthStep)}
                sx={{ mt: 2 }}
              >
                Retry
              </Button>
            </Box>
          )}
          {!connectionStatus && !polling && (
            <Box sx={{ textAlign: 'center', py: 2 }}>
              <Typography>
                Complete {brokerLabel(oauthStep)} login in the opened tab, then click below to
                verify.
              </Typography>
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          {connectionStatus?.connected || connectionStatus?.token_status === 'expired' ? (
            <Button
              onClick={() => {
                clearPolling();
                setOauthDialogOpen(false);
                setOauthStep(null);
                setConnectionStatus(null);
              }}
              variant="contained"
              autoFocus
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
                }}
              >
                Cancel
              </Button>
              {pollAttempts < MAX_POLL_ATTEMPTS && (
                <Button
                  onClick={() => oauthStep && void startPolling(oauthStep)}
                  variant="contained"
                  autoFocus
                  disabled={polling}
                >
                  I completed login
                </Button>
              )}
            </>
          )}
        </DialogActions>
      </ResponsiveDialog>

      {/* End Session confirmation */}
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
            This removes the broker account from TradeCraftX on all devices. Active sessions using
            this connection on other devices will be affected. This is different from End Session,
            which ends only this device's session.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDisconnectBroker(null)}>Cancel</Button>
          <Button
            onClick={() => void confirmDisconnect()}
            color="error"
            variant="contained"
            disabled={connecting}
          >
            {connecting ? 'Disconnecting...' : 'Disconnect'}
          </Button>
        </DialogActions>
      </ResponsiveDialog>
    </Box>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <Box sx={{ minWidth: 0 }}>
      <Typography variant="caption" color="text.secondary" display="block">
        {label}
      </Typography>
      <Typography variant="body2" fontWeight={600} noWrap title={value}>
        {value}
      </Typography>
    </Box>
  );
}
