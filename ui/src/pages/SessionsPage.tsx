import React, { useEffect, useState, useCallback } from 'react';
import {
  Box,
  Typography,
  Button,
  Paper,
  Card,
  CardContent,
  Alert,
  CircularProgress,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Chip,
  IconButton,
  TextField,
  Checkbox,
  FormControlLabel,
} from '@mui/material';
import { PlayArrow as StartIcon, Refresh as RefreshIcon, Check as CheckIcon, Warning as WarningIcon } from '@mui/icons-material';
import { api } from '../api/client';
import { useSession } from '../context/SessionContext';
import { BrokerConnectionResponse, SessionResponse, UpstoxConnectionStatus, ZerodhaConnectionStatus } from '../types';

const SESSION_STORAGE_KEY = 'tradecraftx_session_id';

interface BrokerStatus {
  connected: boolean;
  broker_user_id: string | null;
  token_updated_at: string | null;
  connection_id: number;
}

export default function SessionsPage() {
  const [connections, setConnections] = useState<BrokerConnectionResponse[]>([]);
  const [connectionStatuses, setConnectionStatuses] = useState<{
    upstox: Map<number, UpstoxConnectionStatus>;
    zerodha: Map<number, ZerodhaConnectionStatus>;
  }>({ upstox: new Map(), zerodha: new Map() });
  const [currentSession, setCurrentSession] = useState<SessionResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [starting, setStarting] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  
  // Form state
  const [selectedBrokerName, setSelectedBrokerName] = useState<string>('');
  const [selectedTradingConnectionId, setSelectedTradingConnectionId] = useState<number | ''>('');
  const [selectedMarketDataConnectionId, setSelectedMarketDataConnectionId] = useState<number | ''>('');
  const [warmStart, setWarmStart] = useState(true);
  
  const { selectedConnectionId, setSelectedConnectionId, sessionId, setSessionId, setSessionInfo } = useSession();

  // Load session from localStorage on mount
  useEffect(() => {
    const storedSessionId = localStorage.getItem(SESSION_STORAGE_KEY);
    if (storedSessionId) {
      setSessionId(storedSessionId);
    }
  }, [setSessionId]);

  // Fetch current session if we have one stored
  const fetchCurrentSession = useCallback(async (sid: string) => {
    try {
      const session = await api.getSession(sid);
      setCurrentSession(session);
      setSessionInfo({
        session_id: session.session_id,
        user_id: session.user_id,
        broker: session.broker,
        expires_at: session.expires_at,
        tenant_id: session.tenant_id,
      });
    } catch {
      // Session invalid - clear it
      setCurrentSession(null);
      localStorage.removeItem(SESSION_STORAGE_KEY);
      setSessionId(null);
      setSessionInfo(null);
    }
  }, [setSessionId, setSessionInfo]);

  // Fetch current session when sessionId changes
  useEffect(() => {
    if (sessionId) {
      fetchCurrentSession(sessionId);
    } else {
      setCurrentSession(null);
    }
  }, [sessionId, fetchCurrentSession]);

  const fetchData = async () => {
    try {
      const conns = await api.listBrokerConnections();
      setConnections(conns);
      
      // Fetch status for each connection
      const upstoxStatusMap = new Map<number, UpstoxConnectionStatus>();
      const zerodhaStatusMap = new Map<number, ZerodhaConnectionStatus>();
      
      for (const conn of conns) {
        try {
          if (conn.broker_name === 'upstox') {
            const statusResponse = await api.getUpstoxStatus(conn.id);
            if (statusResponse.connections[0]) {
              upstoxStatusMap.set(conn.id, statusResponse.connections[0]);
            }
          } else if (conn.broker_name === 'zerodha') {
            const statusResponse = await api.getZerodhaStatus(conn.id);
            if (statusResponse.connections[0]) {
              zerodhaStatusMap.set(conn.id, statusResponse.connections[0]);
            }
          }
        } catch {
          // Ignore status errors
        }
      }
      setConnectionStatuses({ upstox: upstoxStatusMap, zerodha: zerodhaStatusMap });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  // Get available connections for each broker
  const getAvailableConnections = useCallback((brokerName: string): BrokerConnectionResponse[] => {
    return connections.filter(conn => {
      if (conn.broker_name !== brokerName) return false;
      const statusMap = brokerName === 'upstox' ? connectionStatuses.upstox : connectionStatuses.zerodha;
      const status = statusMap.get(conn.id);
      return status?.connected ?? false;
    });
  }, [connections, connectionStatuses]);

  const getActiveUpstoxConnections = useCallback((): { id: number; userId: string }[] => {
    return connections
      .filter(conn => conn.broker_name === 'upstox')
      .filter(conn => connectionStatuses.upstox.get(conn.id)?.connected)
      .map(conn => ({
        id: conn.id,
        userId: connectionStatuses.upstox.get(conn.id)?.broker_user_id || `ID: ${conn.id}`
      }));
  }, [connections, connectionStatuses]);

  // Auto-select market data when trading broker changes
  useEffect(() => {
    if (selectedBrokerName === 'zerodha') {
      const upstoxConns = getActiveUpstoxConnections();
      if (upstoxConns.length === 1) {
        setSelectedMarketDataConnectionId(upstoxConns[0].id);
      } else if (upstoxConns.length > 1 && selectedMarketDataConnectionId === '') {
        // Multiple upstox - keep empty for user to select
      }
    } else if (selectedBrokerName === 'upstox') {
      // For Upstox, market data = trading
      const upstoxConns = getAvailableConnections('upstox');
      if (upstoxConns.length === 1) {
        setSelectedMarketDataConnectionId(upstoxConns[0].id);
      }
    }
  }, [selectedBrokerName]);

  const handleBrokerNameChange = (value: string) => {
    setSelectedBrokerName(value);
    setSelectedTradingConnectionId('');
    setSelectedMarketDataConnectionId('');
  };

  const handleStartSession = async () => {
    if (!selectedTradingConnectionId || !selectedBrokerName) {
      setError('Please select a broker and connection');
      return;
    }
    
    setStarting(true);
    setError('');
    try {
      const sessionRequest: {
        broker_connection_id: number;
        broker_name: string;
        warm_start: boolean;
        market_data_connection_id?: number;
      } = {
        broker_connection_id: selectedTradingConnectionId as number,
        broker_name: selectedBrokerName,
        warm_start: warmStart,
      };
      
      // For Zerodha, add market_data_connection_id (Upstox)
      if (selectedBrokerName === 'zerodha' && selectedMarketDataConnectionId) {
        sessionRequest.market_data_connection_id = selectedMarketDataConnectionId as number;
      }
      
      const session = await api.startSession(sessionRequest);
      setCurrentSession(session);
      setSessionId(session.session_id);
      setSessionInfo({
        session_id: session.session_id,
        user_id: session.user_id,
        broker: session.broker,
        expires_at: session.expires_at,
        tenant_id: session.tenant_id,
      });
      localStorage.setItem(SESSION_STORAGE_KEY, session.session_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start session');
    } finally {
      setStarting(false);
    }
  };

  const handleRefreshSession = async () => {
    if (!sessionId) return;
    setRefreshing(true);
    setError('');
    try {
      const session = await api.refreshSession(sessionId);
      setCurrentSession(session);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to refresh session');
      if (err instanceof Error && err.message.includes('not found')) {
        setCurrentSession(null);
        localStorage.removeItem(SESSION_STORAGE_KEY);
        setSessionId(null);
      }
    } finally {
      setRefreshing(false);
    }
  };

  const handleClearSession = () => {
    setCurrentSession(null);
    localStorage.removeItem(SESSION_STORAGE_KEY);
    setSessionId(null);
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  const upstoxConnections = getAvailableConnections('upstox');
  const zerodhaConnections = getAvailableConnections('zerodha');
  const activeUpstoxConnections = getActiveUpstoxConnections();

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Sessions
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}

      {/* Current Session Card */}
      {currentSession && (
        <Card sx={{ mb: 3, bgcolor: '#e8f5e9' }}>
          <CardContent>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Box>
                <Typography variant="h6" gutterBottom>
                  Active Session
                </Typography>
                <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
                  <Chip 
                    icon={<CheckIcon />} 
                    label="Connected" 
                    color="success" 
                    size="small" 
                  />
                  <Typography variant="body2">
                    <strong>Session ID:</strong> {currentSession.session_id}
                  </Typography>
                </Box>
                <Typography variant="body2" color="text.secondary">
                  <strong>Trading Broker:</strong> {currentSession.broker} | <strong>User:</strong> {currentSession.user_id}
                </Typography>
                {currentSession.expires_at && (
                  <Typography variant="body2" color="text.secondary">
                    <strong>Expires:</strong> {new Date(currentSession.expires_at).toLocaleString()}
                  </Typography>
                )}
              </Box>
              <Box sx={{ display: 'flex', gap: 1 }}>
                <IconButton 
                  onClick={handleRefreshSession} 
                  disabled={refreshing}
                  color="primary"
                  title="Refresh session"
                >
                  {refreshing ? <CircularProgress size={24} /> : <RefreshIcon />}
                </IconButton>
                <Button 
                  variant="outlined" 
                  color="error" 
                  size="small"
                  onClick={handleClearSession}
                >
                  Clear
                </Button>
              </Box>
            </Box>
          </CardContent>
        </Card>
      )}

      {/* Start New Session */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          Start New Session
        </Typography>
        
        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', mb: 2 }}>
          {/* Broker Name Selector */}
          <FormControl sx={{ minWidth: 180 }}>
            <InputLabel>Trading Broker</InputLabel>
            <Select
              value={selectedBrokerName}
              label="Trading Broker"
              onChange={(e) => handleBrokerNameChange(e.target.value)}
              disabled={starting}
            >
              <MenuItem value="">Select broker</MenuItem>
              <MenuItem value="upstox">Upstox</MenuItem>
              <MenuItem value="zerodha">Zerodha</MenuItem>
            </Select>
          </FormControl>

          {/* Trading Connection Selector */}
          <FormControl sx={{ minWidth: 250 }}>
            <InputLabel>Trading Connection</InputLabel>
            <Select
              value={selectedTradingConnectionId}
              label="Trading Connection"
              onChange={(e) => setSelectedTradingConnectionId(e.target.value as number)}
              disabled={starting || !selectedBrokerName}
            >
              <MenuItem value="">Select connection</MenuItem>
              {selectedBrokerName === 'upstox' && upstoxConnections.map(conn => (
                <MenuItem key={conn.id} value={conn.id}>
                  Upstox (ID: {conn.id})
                </MenuItem>
              ))}
              {selectedBrokerName === 'zerodha' && zerodhaConnections.map(conn => (
                <MenuItem key={conn.id} value={conn.id}>
                  Zerodha (ID: {conn.id})
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          {/* Market Data Connection (only for Zerodha) */}
          {selectedBrokerName === 'zerodha' && (
            <FormControl sx={{ minWidth: 250 }}>
              <InputLabel>Market Data (Upstox)</InputLabel>
              <Select
                value={selectedMarketDataConnectionId}
                label="Market Data (Upstox)"
                onChange={(e) => setSelectedMarketDataConnectionId(e.target.value as number)}
                disabled={starting}
              >
                <MenuItem value="">Auto-select</MenuItem>
                {activeUpstoxConnections.map(conn => (
                  <MenuItem key={conn.id} value={conn.id}>
                    Upstox - {conn.userId}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          )}
        </Box>

        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
          <Button
            variant="contained"
            startIcon={<StartIcon />}
            onClick={handleStartSession}
            disabled={!selectedBrokerName || !selectedTradingConnectionId || starting}
          >
            {starting ? 'Starting...' : 'Start Session'}
          </Button>
          
          <FormControlLabel
            control={
              <Checkbox
                checked={warmStart}
                onChange={(e) => setWarmStart(e.target.checked)}
              />
            }
            label="Warm start (load data)"
          />
        </Box>
        
        {connections.length === 0 && (
          <Alert severity="warning" sx={{ mt: 2 }} icon={<WarningIcon />}>
            No broker connections found. Please connect a broker first.
          </Alert>
        )}
        
        {/* Info for Zerodha sessions */}
        {selectedBrokerName === 'zerodha' && (
          <Alert severity="info" sx={{ mt: 2 }}>
            <strong>Zerodha Trading:</strong> Market data (CMP quotes) will be fetched from Upstox. 
            {activeUpstoxConnections.length === 0 && ' Please ensure Upstox is connected.'}
          </Alert>
        )}

        {selectedBrokerName === 'upstox' && (
          <Alert severity="info" sx={{ mt: 2 }}>
            <strong>Upstox:</strong> Trading and market data both use Upstox connection.
          </Alert>
        )}
      </Paper>

      {/* Session Info */}
      {!currentSession && !starting && (
        <Paper sx={{ p: 2 }}>
          <Typography variant="body2" color="text.secondary">
            No active session. Select a trading broker and connection, then click "Start Session" to begin.
            Your session will be saved and restored on page reload.
          </Typography>
        </Paper>
      )}
    </Box>
  );
}
