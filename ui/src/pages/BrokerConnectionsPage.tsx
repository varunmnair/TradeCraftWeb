import React, { useEffect, useState, useCallback, useRef } from 'react';
import {
  Box,
  Typography,
  Button,
  Paper,
  Card,
  CardContent,
  Alert,
  CircularProgress,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Chip,
  Stepper,
  Step,
  StepLabel,
  TextField,
} from '@mui/material';
import { 
  Add as AddIcon, 
  Check as CheckIcon, 
  Error as ErrorIcon, 
  Warning as WarningIcon,
  CloudDone as UpstoxIcon,
  Cloud as ZerodhaIcon,
  Refresh as RefreshIcon,
  Delete as DeleteIcon,
} from '@mui/icons-material';
import { api } from '../api/client';
import { BrokerConnectionResponse, BrokerStatusResponse, ZerodhaStatusResponse } from '../types';

const POLL_INTERVAL_MS = 2000;
const MAX_POLL_ATTEMPTS = 30; // 60 seconds total

const STORAGE_KEY_UPSTOX = 'tradecraftx_upstox_connection_id';
const STORAGE_KEY_ZERODHA = 'tradecraftx_zerodha_connection_id';
const STORAGE_KEY_SESSION = 'tradecraftx_session_id';

interface BrokerStatus {
  connected: boolean;
  broker_user_id: string | null;
  token_updated_at: string | null;
  connection_id: number;
  expires_at: string | null;
  token_status: 'valid' | 'expired' | 'missing';
}

export default function BrokerConnectionsPage() {
  const [connections, setConnections] = useState<BrokerConnectionResponse[]>([]);
  const [upstoxStatus, setUpstoxStatus] = useState<BrokerStatus | null>(null);
  const [zerodhaStatus, setZerodhaStatus] = useState<BrokerStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  
  // OAuth flow state
  const [oauthDialogOpen, setOauthDialogOpen] = useState(false);
  const [oauthStep, setOauthStep] = useState(0); // 0: idle, 1: upstox, 2: zerodha
  const [polling, setPolling] = useState(false);
  const [pollAttempts, setPollAttempts] = useState(0);
  const [connectionStatus, setConnectionStatus] = useState<BrokerStatus | null>(null);
  const [oauthConnectionId, setOauthConnectionId] = useState<number | null>(null);
  
  const pollingRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pollAttemptsRef = useRef(0);
  const pollingActiveRef = useRef(false);

  const fetchConnections = async () => {
    try {
      const data = await api.listBrokerConnections();
      setConnections(data);
      
      // Fetch Upstox status - now returns ALL connections, get first one
      try {
        const upstoxResp = await api.getUpstoxStatus();
        const firstUpstox = upstoxResp.connections[0];
        if (firstUpstox) {
          const status: BrokerStatus = {
            connected: firstUpstox.connected,
            broker_user_id: firstUpstox.broker_user_id,
            token_updated_at: firstUpstox.token_updated_at,
            connection_id: firstUpstox.connection_id,
            expires_at: firstUpstox.expires_at,
            token_status: firstUpstox.token_status,
          };
          setUpstoxStatus(status);
          if (firstUpstox.connected) {
            localStorage.setItem(STORAGE_KEY_UPSTOX, String(status.connection_id));
          } else {
            localStorage.removeItem(STORAGE_KEY_UPSTOX);
          }
        } else {
          setUpstoxStatus(null);
          localStorage.removeItem(STORAGE_KEY_UPSTOX);
        }
      } catch {
        setUpstoxStatus(null);
      }
      
      // Fetch Zerodha status
      try {
        const zerodhaResp = await api.getZerodhaStatus();
        const firstZerodha = zerodhaResp.connections[0];
        if (firstZerodha) {
          const status: BrokerStatus = {
            connected: firstZerodha.connected,
            broker_user_id: firstZerodha.broker_user_id,
            token_updated_at: firstZerodha.token_updated_at,
            connection_id: firstZerodha.connection_id,
            expires_at: firstZerodha.expires_at,
            token_status: firstZerodha.token_status,
          };
          setZerodhaStatus(status);
          if (firstZerodha.connected) {
            localStorage.setItem(STORAGE_KEY_ZERODHA, String(status.connection_id));
          } else {
            localStorage.removeItem(STORAGE_KEY_ZERODHA);
          }
        } else {
          setZerodhaStatus(null);
          localStorage.removeItem(STORAGE_KEY_ZERODHA);
        }
      } catch {
        setZerodhaStatus(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load connections');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchConnections();
  }, []);

  const handleRefresh = async () => {
    setRefreshing(true);
    setError('');
    try {
      await fetchConnections();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to refresh');
    } finally {
      setRefreshing(false);
    }
  };

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollingRef.current) {
        clearTimeout(pollingRef.current);
      }
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

  const checkUpstoxStatus = useCallback(async (): Promise<BrokerStatus | null> => {
    try {
      const resp = await api.getUpstoxStatus();
      // Return first connection (now includes all statuses)
      const first = resp.connections[0];
      if (first) {
        return {
          connected: first.connected,
          broker_user_id: first.broker_user_id,
          token_updated_at: first.token_updated_at,
          connection_id: first.connection_id,
          expires_at: first.expires_at,
          token_status: first.token_status,
        };
      }
    } catch {
      // Ignore
    }
    return null;
  }, []);

  const checkZerodhaStatus = useCallback(async (): Promise<BrokerStatus | null> => {
    try {
      const resp = await api.getZerodhaStatus();
      // Return first connection (now includes all statuses)
      const first = resp.connections[0];
      if (first) {
        return {
          connected: first.connected,
          broker_user_id: first.broker_user_id,
          token_updated_at: first.token_updated_at,
          connection_id: first.connection_id,
          expires_at: first.expires_at,
          token_status: first.token_status,
        };
      }
    } catch {
      // Ignore
    }
    return null;
  }, []);

  const startPolling = useCallback(async (step: number) => {
    pollingActiveRef.current = true;
    pollAttemptsRef.current = 0;
    setPolling(true);
    setPollAttempts(0);
    setConnectionStatus(null);
    
    const poll = async () => {
      if (!pollingActiveRef.current) return;
      
      const status = step === 1 
        ? await checkUpstoxStatus() 
        : await checkZerodhaStatus();
      
      setConnectionStatus(status);
      
      if (status?.connected) {
        pollingActiveRef.current = false;
        clearPolling();
        if (step === 1) {
          setUpstoxStatus(status);
          localStorage.setItem(STORAGE_KEY_UPSTOX, String(status.connection_id));
        } else {
          setZerodhaStatus(status);
          localStorage.setItem(STORAGE_KEY_ZERODHA, String(status.connection_id));
        }
        await fetchConnections();
        return;
      }
      
      // Also check for expired tokens - user might need to reconnect
      if (status?.token_status === 'expired') {
        pollingActiveRef.current = false;
        clearPolling();
        if (step === 1) {
          setUpstoxStatus(status);
        } else {
          setZerodhaStatus(status);
        }
        return;
      }
      
      const currentAttempts = pollAttemptsRef.current + 1;
      pollAttemptsRef.current = currentAttempts;
      setPollAttempts(currentAttempts);
      
      if (currentAttempts >= MAX_POLL_ATTEMPTS) {
        pollingActiveRef.current = false;
        clearPolling();
        setError('Connection timeout. Please try again.');
        return;
      }
      
      pollingRef.current = setTimeout(poll, POLL_INTERVAL_MS);
    };
    
    poll();
  }, [checkUpstoxStatus, checkZerodhaStatus, clearPolling]);

  const handleConnectUpstox = async () => {
    setConnecting(true);
    setError('');
    try {
      const response = await api.connectUpstox();
      setOauthConnectionId(response.connection_id);
      setOauthStep(1);
      
      // Open authorize_url in new tab
      window.open(response.authorize_url, '_blank');
      
      // Show dialog and start polling
      setOauthDialogOpen(true);
      startPolling(1);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to initiate Upstox connection');
    } finally {
      setConnecting(false);
    }
  };

  const handleConnectZerodha = async () => {
    setConnecting(true);
    setError('');
    setOauthStep(2);
    
    try {
      // Zerodha can be connected independently - no Upstox required
      const response = await api.connectZerodha();
      setOauthConnectionId(response.connection_id);
      
      // Open authorize_url in new tab
      window.open(response.authorize_url, '_blank');
      
      // Show dialog and start polling
      setOauthDialogOpen(true);
      startPolling(2);
    } catch (err: unknown) {
      const errMsg = err instanceof Error ? err.message : String(err);
      setError(errMsg);
    } finally {
      setConnecting(false);
    }
  };

  const handleICompletedLogin = () => {
    if (oauthStep === 1) {
      startPolling(1);
    } else if (oauthStep === 2) {
      startPolling(2);
    }
  };

  const handleCloseDialog = () => {
    clearPolling();
    setOauthDialogOpen(false);
    setOauthStep(0);
    setConnectionStatus(null);
    setOauthConnectionId(null);
  };

  const handleRetry = () => {
    if (oauthStep === 1) {
      startPolling(1);
    } else if (oauthStep === 2) {
      startPolling(2);
    }
  };

  const handleDisconnectUpstox = async () => {
    if (!confirm('Disconnect Upstox? You will need to reconnect to use Upstox. Any active sessions will be terminated.')) return;
    try {
      await api.disconnectUpstox();
      setUpstoxStatus(null);
      localStorage.removeItem(STORAGE_KEY_UPSTOX);
      localStorage.removeItem(STORAGE_KEY_SESSION);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to disconnect Upstox');
    }
  };

  const handleDisconnectZerodha = async () => {
    if (!confirm('Disconnect Zerodha? You will need to reconnect to use Zerodha. Any active sessions will be terminated.')) return;
    try {
      await api.disconnectZerodha();
      setZerodhaStatus(null);
      localStorage.removeItem(STORAGE_KEY_ZERODHA);
      localStorage.removeItem(STORAGE_KEY_SESSION);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to disconnect Zerodha');
    }
  };

  const [connecting, setConnecting] = useState(false);

  const getStatusChip = (status: BrokerStatus | null) => {
    if (!status) {
      return <Chip label="Not Connected" size="small" icon={<ErrorIcon />} />;
    }
    if (status.token_status === 'expired') {
      return <Chip label="Expired" color="warning" size="small" icon={<WarningIcon />} />;
    }
    if (status.token_status === 'missing') {
      return <Chip label="Not Connected" size="small" icon={<ErrorIcon />} />;
    }
    return <Chip label="Connected" color="success" size="small" icon={<CheckIcon />} />;
  };

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return 'N/A';
    try {
      return new Date(dateStr).toLocaleString();
    } catch {
      return dateStr;
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  const steps = oauthStep === 1 
    ? ['Upstox Login'] 
    : oauthStep === 2 
      ? ['Upstox Login', 'Zerodha Login'] 
      : [];

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4">Broker Connections</Typography>
        <Button
          variant="outlined"
          startIcon={<RefreshIcon />}
          onClick={handleRefresh}
          disabled={refreshing}
        >
          {refreshing ? 'Refreshing...' : 'Refresh Status'}
        </Button>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}

      {/* Status Cards */}
      <Box sx={{ display: 'flex', gap: 2, mb: 3 }}>
        {/* Upstox Card */}
        <Card sx={{ flex: 1 }}>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
              <UpstoxIcon color="primary" />
              <Typography variant="h6">Upstox</Typography>
              {getStatusChip(upstoxStatus)}
            </Box>
            {upstoxStatus && (
              <Box sx={{ mt: 1 }}>
                <Typography variant="body2" color="text.secondary">
                  User: {upstoxStatus.broker_user_id || 'N/A'}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Status: {upstoxStatus.token_status}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Updated: {formatDate(upstoxStatus.token_updated_at)}
                </Typography>
                {upstoxStatus.expires_at && (
                  <Typography variant="body2" color="text.secondary">
                    Expires: {formatDate(upstoxStatus.expires_at)}
                  </Typography>
                )}
              </Box>
            )}
            <Box sx={{ display: 'flex', gap: 1, mt: 2 }}>
              <Button
                variant={upstoxStatus?.token_status === 'valid' ? "outlined" : "contained"}
                startIcon={<AddIcon />}
                onClick={handleConnectUpstox}
                disabled={connecting}
                fullWidth
              >
                {upstoxStatus?.token_status === 'valid' ? 'Reconnect' : 'Connect'}
              </Button>
              {upstoxStatus?.token_status === 'valid' && (
                <Button
                  variant="outlined"
                  color="error"
                  startIcon={<DeleteIcon />}
                  onClick={handleDisconnectUpstox}
                  disabled={connecting}
                >
                  Disconnect
                </Button>
              )}
            </Box>
          </CardContent>
        </Card>

        {/* Zerodha Card */}
        <Card sx={{ flex: 1 }}>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
              <ZerodhaIcon sx={{ color: '#283195' }} />
              <Typography variant="h6">Zerodha</Typography>
              {getStatusChip(zerodhaStatus)}
            </Box>
            {zerodhaStatus && (
              <Box sx={{ mt: 1 }}>
                <Typography variant="body2" color="text.secondary">
                  User: {zerodhaStatus.broker_user_id || 'N/A'}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Status: {zerodhaStatus.token_status}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Updated: {formatDate(zerodhaStatus.token_updated_at)}
                </Typography>
                {zerodhaStatus.expires_at && (
                  <Typography variant="body2" color="text.secondary">
                    Expires: {formatDate(zerodhaStatus.expires_at)}
                  </Typography>
                )}
              </Box>
            )}
            <Box sx={{ display: 'flex', gap: 1, mt: 2 }}>
              <Button
                variant={zerodhaStatus?.token_status === 'valid' ? "outlined" : "contained"}
                startIcon={<AddIcon />}
                onClick={handleConnectZerodha}
                disabled={connecting}
                fullWidth
              >
                {zerodhaStatus?.token_status === 'valid' ? 'Reconnect' : 'Connect'}
              </Button>
              {zerodhaStatus?.token_status === 'valid' && (
                <Button
                  variant="outlined"
                  color="error"
                  startIcon={<DeleteIcon />}
                  onClick={handleDisconnectZerodha}
                  disabled={connecting}
                >
                  Disconnect
                </Button>
              )}
            </Box>
          </CardContent>
        </Card>
      </Box>

      {/* OAuth Polling Dialog */}
      <Dialog open={oauthDialogOpen} onClose={handleCloseDialog} maxWidth="sm" fullWidth>
        <DialogTitle>
          {oauthStep === 1 
            ? 'Connecting Upstox...' 
            : oauthStep === 2 
              ? 'Connecting Zerodha...'
              : 'Connecting...'}
        </DialogTitle>
        <DialogContent>
          {oauthStep === 1 || oauthStep === 2 ? (
            <Stepper activeStep={oauthStep - 1} sx={{ mb: 3 }}>
              <Step>
                <StepLabel>Upstox</StepLabel>
              </Step>
              <Step>
                <StepLabel>Zerodha</StepLabel>
              </Step>
            </Stepper>
          ) : (
            <Box sx={{ mb: 3 }} />
          )}
          
          {/* Success State */}
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
          
          {/* Expired Token State */}
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
          
          {/* Polling State */}
          {polling && !connectionStatus?.connected && (
            <Box sx={{ textAlign: 'center', py: 2 }}>
              <CircularProgress sx={{ mb: 2 }} />
              <Typography>
                Waiting for authentication... ({Math.floor(pollAttempts * POLL_INTERVAL_MS / 1000)}s / 60s)
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                Please complete the login in the opened tab, then close it.
              </Typography>
            </Box>
          )}
          
          {/* Timeout State */}
          {!polling && !connectionStatus?.connected && pollAttempts >= MAX_POLL_ATTEMPTS && (
            <Box sx={{ textAlign: 'center', py: 2 }}>
              <ErrorIcon color="error" sx={{ fontSize: 48, mb: 2 }} />
              <Typography color="error">
                Connection timed out
              </Typography>
              <Button 
                variant="outlined" 
                onClick={handleRetry}
                sx={{ mt: 2 }}
              >
                Retry
              </Button>
            </Box>
          )}
          
          {/* Initial State - Waiting for user to complete login */}
          {!connectionStatus && !polling && (
            <Box sx={{ textAlign: 'center', py: 2 }}>
              <Typography>
                Complete {oauthStep === 1 ? 'Upstox' : 'Zerodha'} login in the opened tab, then click below to verify.
              </Typography>
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          {(connectionStatus?.connected || connectionStatus?.token_status === 'expired') ? (
            <Button onClick={handleCloseDialog} variant="contained" autoFocus>
              Done
            </Button>
          ) : (
            <>
              <Button onClick={handleCloseDialog}>
                Cancel
              </Button>
              {pollAttempts < MAX_POLL_ATTEMPTS && (
                <Button 
                  onClick={handleICompletedLogin} 
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
      </Dialog>
    </Box>
  );
}
