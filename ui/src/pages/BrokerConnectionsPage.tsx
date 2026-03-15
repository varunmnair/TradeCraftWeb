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
} from '@mui/icons-material';
import { api } from '../api/client';
import { BrokerConnectionResponse, BrokerStatusResponse, ZerodhaStatusResponse } from '../types';

const POLL_INTERVAL_MS = 2000;
const MAX_POLL_ATTEMPTS = 45; // 90 seconds total

const STORAGE_KEY_UPSTOX = 'tradecraftx_upstox_connection_id';
const STORAGE_KEY_ZERODHA = 'tradecraftx_zerodha_connection_id';

interface BrokerStatus {
  connected: boolean;
  broker_user_id: string | null;
  token_updated_at: string | null;
  connection_id: number;
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
  
  const pollingRef = useRef<NodeJS.Timeout | null>(null);

  const fetchConnections = async () => {
    try {
      const data = await api.listBrokerConnections();
      setConnections(data);
      
      // Fetch Upstox status
      try {
        const upstoxResp = await api.getUpstoxStatus();
        if (upstoxResp.connections.length > 0) {
          const conn = upstoxResp.connections[0];
          const status: BrokerStatus = {
            connected: conn.connected,
            broker_user_id: conn.broker_user_id,
            token_updated_at: conn.token_updated_at,
            connection_id: conn.connection_id,
          };
          setUpstoxStatus(status);
          if (status.connected) {
            localStorage.setItem(STORAGE_KEY_UPSTOX, String(status.connection_id));
          } else {
            localStorage.removeItem(STORAGE_KEY_UPSTOX);
          }
        }
      } catch {
        setUpstoxStatus(null);
      }
      
      // Fetch Zerodha status
      try {
        const zerodhaResp = await api.getZerodhaStatus();
        if (zerodhaResp.connections.length > 0) {
          const conn = zerodhaResp.connections[0];
          const status: BrokerStatus = {
            connected: conn.connected,
            broker_user_id: conn.broker_user_id,
            token_updated_at: conn.token_updated_at,
            connection_id: conn.connection_id,
          };
          setZerodhaStatus(status);
          if (status.connected) {
            localStorage.setItem(STORAGE_KEY_ZERODHA, String(status.connection_id));
          } else {
            localStorage.removeItem(STORAGE_KEY_ZERODHA);
          }
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
    if (pollingRef.current) {
      clearTimeout(pollingRef.current);
      pollingRef.current = null;
    }
    setPolling(false);
    setPollAttempts(0);
  }, []);

  const checkUpstoxStatus = useCallback(async (): Promise<BrokerStatus | null> => {
    try {
      const resp = await api.getUpstoxStatus();
      if (resp.connections.length > 0 && resp.connections[0].connected) {
        const conn = resp.connections[0];
        return {
          connected: conn.connected,
          broker_user_id: conn.broker_user_id,
          token_updated_at: conn.token_updated_at,
          connection_id: conn.connection_id,
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
      if (resp.connections.length > 0 && resp.connections[0].connected) {
        const conn = resp.connections[0];
        return {
          connected: conn.connected,
          broker_user_id: conn.broker_user_id,
          token_updated_at: conn.token_updated_at,
          connection_id: conn.connection_id,
        };
      }
    } catch {
      // Ignore
    }
    return null;
  }, []);

  const startPolling = useCallback(async (step: number) => {
    setPolling(true);
    setPollAttempts(0);
    setConnectionStatus(null);
    
    const poll = async () => {
      const status = step === 1 
        ? await checkUpstoxStatus() 
        : await checkZerodhaStatus();
      
      setConnectionStatus(status);
      
      if (status?.connected) {
        clearPolling();
        // Update local status
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
      
      if (pollAttempts >= MAX_POLL_ATTEMPTS) {
        clearPolling();
        setError('Connection timeout. Please try again.');
        return;
      }
      
      setPollAttempts((prev) => prev + 1);
      pollingRef.current = setTimeout(poll, POLL_INTERVAL_MS);
    };
    
    poll();
  }, [checkUpstoxStatus, checkZerodhaStatus, pollAttempts, clearPolling]);

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
      // Step 1: Check if Upstox is already connected
      const upstox = await checkUpstoxStatus();
      
      if (!upstox) {
        // Need to connect Upstox first
        setOauthDialogOpen(true);
        // Start Upstox flow
        await handleConnectUpstox();
        // After upstox completes, continue to zerodha
        return;
      }
      
      // Upstox is connected, proceed with Zerodha
      const response = await api.connectZerodha();
      setOauthConnectionId(response.connection_id);
      
      // Open authorize_url in new tab
      window.open(response.authorize_url, '_blank');
      
      // Show dialog and start polling
      setOauthDialogOpen(true);
      startPolling(2);
    } catch (err: unknown) {
      const errMsg = err instanceof Error ? err.message : String(err);
      // Check if it's the upstox_required error (409)
      if (errMsg.includes('upstox') || errMsg.toLowerCase().includes('upstox required')) {
        // Fallback: need to connect Upstox first
        setOauthDialogOpen(true);
        setOauthStep(1);
        await handleConnectUpstox();
        // After upstox completes, continue to zerodha
      } else {
        setError(errMsg);
      }
    } finally {
      setConnecting(false);
    }
  };

  const handleContinueAfterUpstox = async () => {
    // After Upstox is connected, proceed to Zerodha
    try {
      const response = await api.connectZerodha();
      setOauthConnectionId(response.connection_id);
      setOauthStep(2);
      
      window.open(response.authorize_url, '_blank');
      startPolling(2);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to initiate Zerodha connection');
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

  const [connecting, setConnecting] = useState(false);

  const getStatusChip = (connected: boolean) => {
    return connected 
      ? <Chip label="Connected" color="success" size="small" icon={<CheckIcon />} />
      : <Chip label="Not Connected" size="small" icon={<ErrorIcon />} />;
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
              {getStatusChip(upstoxStatus?.connected ?? false)}
            </Box>
            {upstoxStatus?.connected && (
              <Box sx={{ mt: 1 }}>
                <Typography variant="body2" color="text.secondary">
                  User: {upstoxStatus.broker_user_id || 'N/A'}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Connected: {formatDate(upstoxStatus.token_updated_at)}
                </Typography>
              </Box>
            )}
            <Button
              variant={upstoxStatus?.connected ? "outlined" : "contained"}
              startIcon={<AddIcon />}
              onClick={handleConnectUpstox}
              disabled={connecting}
              sx={{ mt: 2 }}
              fullWidth
            >
              {upstoxStatus?.connected ? 'Reconnect Upstox' : 'Connect Upstox'}
            </Button>
          </CardContent>
        </Card>

        {/* Zerodha Card */}
        <Card sx={{ flex: 1 }}>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
              <ZerodhaIcon sx={{ color: '#283195' }} />
              <Typography variant="h6">Zerodha</Typography>
              {getStatusChip(zerodhaStatus?.connected ?? false)}
            </Box>
            {!upstoxStatus?.connected && (
              <Alert severity="info" sx={{ mb: 1 }} icon={<WarningIcon />}>
                Upstox required for market data
              </Alert>
            )}
            {zerodhaStatus?.connected && (
              <Box sx={{ mt: 1 }}>
                <Typography variant="body2" color="text.secondary">
                  User: {zerodhaStatus.broker_user_id || 'N/A'}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Connected: {formatDate(zerodhaStatus.token_updated_at)}
                </Typography>
              </Box>
            )}
            <Button
              variant={zerodhaStatus?.connected ? "outlined" : "contained"}
              startIcon={<AddIcon />}
              onClick={handleConnectZerodha}
              disabled={connecting || !upstoxStatus?.connected}
              sx={{ mt: 2 }}
              fullWidth
            >
              {zerodhaStatus?.connected ? 'Reconnect Zerodha' : 'Connect Zerodha'}
            </Button>
          </CardContent>
        </Card>
      </Box>

      {/* OAuth Polling Dialog */}
      <Dialog open={oauthDialogOpen} onClose={handleCloseDialog} maxWidth="sm" fullWidth>
        <DialogTitle>
          {oauthStep === 1 
            ? 'Step 1/2: Connect Upstox' 
            : oauthStep === 2 
              ? 'Step 2/2: Connect Zerodha'
              : 'Connecting...'}
        </DialogTitle>
        <DialogContent>
          <Stepper activeStep={oauthStep - 1} sx={{ mb: 3 }}>
            <Step>
              <StepLabel>Upstox</StepLabel>
            </Step>
            <Step>
              <StepLabel>Zerodha</StepLabel>
            </Step>
          </Stepper>
          
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
          
          {/* Polling State */}
          {polling && !connectionStatus?.connected && (
            <Box sx={{ textAlign: 'center', py: 2 }}>
              <CircularProgress sx={{ mb: 2 }} />
              <Typography>
                Waiting for authentication... ({Math.floor(pollAttempts * POLL_INTERVAL_MS / 1000)}s / 90s)
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
          
          {/* Continue to Zerodha after Upstox success */}
          {oauthStep === 1 && connectionStatus?.connected && (
            <Box sx={{ textAlign: 'center', py: 2 }}>
              <Button 
                variant="contained" 
                onClick={handleContinueAfterUpstox}
                fullWidth
              >
                Continue to Zerodha
              </Button>
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          {connectionStatus?.connected ? (
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
