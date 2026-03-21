import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  Box,
  Typography,
  Paper,
  Alert,
  CircularProgress,
  Button,
  TextField,
  Chip,
  InputAdornment,
  LinearProgress,
} from '@mui/material';
import { DataGrid, GridColDef } from '@mui/x-data-grid';
import { 
  PlayArrow as AnalyzeIcon, 
  Search as SearchIcon,
  CloudSync as SyncIcon,
  Upload as UploadIcon,
} from '@mui/icons-material';
import { api } from '../api/client';
import { useSession } from '../context/SessionContext';
import { useJobRunner } from '../hooks/useJobRunner';

interface ReadinessStatus {
  broker: string;
  market_data_ready: boolean;
  trades_ready: boolean;
  ready_to_analyze: boolean;
  blocking_reason: string | null;
  missing: { cmp: string[]; candles: string[]; trades: string[] };
}

export default function HoldingsPage() {
  const { sessionId, sessionInfo } = useSession();
  
  const [holdings, setHoldings] = useState<Record<string, unknown>[]>([]);
  const [columns, setColumns] = useState<GridColDef[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [searchText, setSearchText] = useState('');
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [readiness, setReadiness] = useState<ReadinessStatus | null>(null);
  const [readinessLoading, setReadinessLoading] = useState(false);
  const [syncJobId, setSyncJobId] = useState<number | null>(null);
  const [syncJobStatus, setSyncJobStatus] = useState<string | null>(null);
  const [uploadMessage, setUploadMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const fetchHoldings = useCallback(async () => {
    if (!sessionId || loading) return;
    setLoading(true);
    try {
      const data = await api.getHoldingsLatest(sessionId);
      const itemsWithId = data.items.map((item, index) => ({
        id: item.Symbol || index,
        ...item
      }));
      setHoldings(itemsWithId);
      generateColumns(data.items);
      setLastUpdated(new Date());
      setError('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch holdings');
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  const fetchReadiness = useCallback(async () => {
    if (!sessionId) return;
    setReadinessLoading(true);
    try {
      const data = await api.getHoldingsAnalyzeStatus(sessionId);
      setReadiness(data);
    } catch (err) {
      console.error('Failed to fetch readiness:', err);
    } finally {
      setReadinessLoading(false);
    }
  }, [sessionId]);

  // Poll sync job status
  useEffect(() => {
    if (!syncJobId) return;

    const pollJob = async () => {
      try {
        const data = await api.getJob(syncJobId);
        setSyncJobStatus(data.job.status);
        if (data.job.status === 'succeeded' || data.job.status === 'failed') {
          setSyncJobId(null);
          fetchReadiness();
        }
      } catch (err) {
        console.error('Failed to poll sync job:', err);
      }
    };

    pollJob();
    const interval = setInterval(pollJob, 2000);
    return () => clearInterval(interval);
  }, [syncJobId, fetchReadiness]);

  const {
    isRunning: isAnalyzing,
    isSuccess: analyzeSuccess,
    isError: analyzeError,
    errorMessage,
    jobStatus,
    jobProgress,
    run: runAnalyze,
    reset: resetAnalyze,
  } = useJobRunner({
    onSuccess: () => {
      fetchHoldings();
    },
    onError: (msg) => {
      setError(msg);
    },
  });

  // Fetch holdings and readiness when session changes
  useEffect(() => {
    if (sessionId) {
      fetchHoldings();
      fetchReadiness();
    }
  }, [sessionId, fetchHoldings, fetchReadiness]);

  const handleSyncTrades = async () => {
    try {
      const result = await api.syncUpstoxTrades(400);
      setSyncJobId(result.job_id);
      setSyncJobStatus('pending');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start sync');
    }
  };

  const handleUploadTradebook = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setUploadMessage(null);
    try {
      const result = await api.uploadZerodhaTradebook(file);
      if (result.errors && result.errors.length > 0) {
        setUploadMessage({
          type: 'error',
          text: `Uploaded ${result.rows_ingested} rows with errors: ${result.errors.join(', ')}`,
        });
      } else {
        setUploadMessage({
          type: 'success',
          text: `Uploaded ${result.rows_ingested} trades for ${result.symbols_covered} symbols`,
        });
      }
      fetchReadiness();
    } catch (err) {
      setUploadMessage({
        type: 'error',
        text: err instanceof Error ? err.message : 'Failed to upload tradebook',
      });
    }
    event.target.value = '';
  };

  const generateColumns = (items: Record<string, unknown>[]) => {
    if (items.length === 0) {
      setColumns([]);
      return;
    }
    
    const firstRow = items[0];
    const cols: GridColDef[] = [];
    
    // Pin Symbol and Name columns
    const pinnedFields = ['Symbol', 'Name'];
    
    Object.keys(firstRow).map((key) => {
      const value = firstRow[key];
      let type: 'string' | 'number' | 'boolean' | 'date' = 'string';
      
      if (typeof value === 'number') type = 'number';
      else if (typeof value === 'boolean') type = 'boolean';
      
      const colDef: GridColDef & { pinned?: 'left' | 'right' } = {
        field: key,
        headerName: key,
        type,
        width: type === 'number' ? 120 : 180,
        flex: type === 'string' ? 1 : 0,
      };
      
      if (pinnedFields.includes(key)) {
        colDef.pinned = 'left';
      }
      
      cols.push(colDef);
    });
    
    setColumns(cols);
  };

  const handleAnalyze = async () => {
    if (!sessionId) {
      setError('No active session. Please start a session first.');
      return;
    }

    if (readiness && !readiness.ready_to_analyze) {
      setError(`Cannot analyze: ${readiness.blocking_reason || 'Missing required data'}`);
      return;
    }
    
    resetAnalyze();
    setError('');
    
    try {
      const response = await api.analyzeHoldings({
        session_id: sessionId,
        filters: {},
        sort_by: 'ROI/Day',
      });
      await runAnalyze(() => Promise.resolve({ job_id: response.job_id }));
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Failed to start analysis';
      if (errorMsg.includes('NOT_READY')) {
        setError('Not ready to analyze. Please sync trades or upload tradebook first.');
        fetchReadiness();
      } else {
        setError(errorMsg);
      }
    }
  };

  // Client-side filtered holdings
  const filteredHoldings = useMemo(() => {
    if (!searchText) return holdings;
    
    const search = searchText.toLowerCase();
    return holdings.filter(row => 
      Object.values(row).some(val => 
        String(val).toLowerCase().includes(search)
      )
    );
  }, [holdings, searchText]);

  if (!sessionId) {
    return (
      <Box>
        <Typography variant="h4" gutterBottom>
          Holdings
        </Typography>
        <Alert severity="warning">
          No active session. Please start a session from the Sessions page first.
        </Alert>
      </Box>
    );
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h4">
          Holdings
        </Typography>
        {lastUpdated && (
          <Typography variant="body2" color="text.secondary">
            Last updated: {lastUpdated.toLocaleTimeString()}
          </Typography>
        )}
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}

      {/* Readiness Banner */}
      {(readinessLoading || syncJobId) && (
        <Paper sx={{ p: 2, mb: 2 }}>
          {readinessLoading ? (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <CircularProgress size={20} />
              <Typography variant="body2">Checking readiness...</Typography>
            </Box>
          ) : syncJobId ? (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <SyncIcon />
              <Typography variant="body2">
                Syncing trades... <Chip label={syncJobStatus || 'pending'} size="small" />
              </Typography>
              <LinearProgress sx={{ flexGrow: 1, ml: 2 }} />
            </Box>
          ) : null}
        </Paper>
      )}

      {/* Trades Sync / Upload Section */}
      {readiness && !readiness.trades_ready && (
        <Paper sx={{ p: 2, mb: 2 }}>
          <Typography variant="subtitle1" gutterBottom>
            {readiness.broker === 'upstox' 
              ? 'Fetch Order History from Upstox'
              : 'Upload Tradebook'}
          </Typography>
          
          {readiness && readiness.broker === 'upstox' && (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <Typography variant="body2" color="text.secondary">
                {readiness.blocking_reason === 'TRADES_SYNC_REQUIRED' 
                  ? 'Order history needs to be synced before analysis.'
                  : 'Click to sync 400 days of order history.'}
              </Typography>
              <Button
                variant="contained"
                color="primary"
                startIcon={<SyncIcon />}
                onClick={handleSyncTrades}
                disabled={Boolean(syncJobId)}
              >
                {syncJobId ? 'Syncing...' : 'Sync Order History'}
              </Button>
            </Box>
          )}

          {readiness && readiness.broker === 'zerodha' && (
            <Box>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Upload your Zerodha tradebook CSV to enable analysis.
                Required columns: symbol,isin,trade_date,exchange,segment,series,trade_type,auction,quantity,price,trade_id,order_id,order_execution_time
              </Typography>
              <Button
                variant="contained"
                component="label"
                startIcon={<UploadIcon />}
              >
                Upload Tradebook
                <input
                  type="file"
                  accept=".csv"
                  hidden
                  onChange={handleUploadTradebook}
                />
              </Button>
              {uploadMessage && (
                <Alert severity={uploadMessage.type} sx={{ mt: 2 }} onClose={() => setUploadMessage(null)}>
                  {uploadMessage.text}
                </Alert>
              )}
            </Box>
          )}
        </Paper>
      )}

      {/* Market Data Missing Warning */}
      {readiness && readiness.blocking_reason === 'MARKET_DATA_MISSING' && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          Market data is not fully loaded. Missing: {readiness.missing.candles.length} symbols for candles, {readiness.missing.cmp.length} symbols for CMP. 
          Please run "Refresh Market Data" from the Administration page.
        </Alert>
      )}

      {/* Controls */}
      <Paper sx={{ p: 2, mb: 2 }}>
        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
          {/* Analyze Button */}
          <Button
            variant="contained"
            startIcon={isAnalyzing ? <CircularProgress size={20} color="inherit" /> : <AnalyzeIcon />}
            onClick={handleAnalyze}
            disabled={isAnalyzing || !readiness?.ready_to_analyze}
          >
            {isAnalyzing ? 'Analyzing...' : holdings.length > 0 ? 'Refresh' : 'Analyze'}
          </Button>
          {!readiness?.ready_to_analyze && readiness && (
            <Chip label="Not Ready" color="warning" size="small" />
          )}
        </Box>

        {/* Job Status */}
        {isAnalyzing && (
          <Box sx={{ mt: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
            <Chip 
              label={jobStatus || 'processing'} 
              color={jobStatus === 'completed' ? 'success' : jobStatus === 'failed' ? 'error' : 'info'}
              size="small"
            />
            <Typography variant="body2" color="text.secondary">
              Analyzing... {(jobProgress * 100).toFixed(0)}% complete
            </Typography>
          </Box>
        )}
      </Paper>

      {/* Results */}
      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
          <CircularProgress />
        </Box>
      ) : holdings.length === 0 ? (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <Typography variant="body1" color="text.secondary">
            No holdings data. Click "Analyze" to fetch holdings for your session.
          </Typography>
        </Paper>
      ) : (
        <Paper sx={{ height: 600, width: '100%' }}>
          <DataGrid
            rows={filteredHoldings}
            columns={columns}
            initialState={{
              pagination: {
                paginationModel: { pageSize: 25 },
              },
              sorting: {
                sortModel: [{ field: 'ROI/Day', sort: 'desc' }],
              },
            }}
            pageSizeOptions={[10, 25, 50, 100]}
            disableRowSelectionOnClick
            slots={{
              toolbar: () => (
                <Box sx={{ p: 1, display: 'flex', gap: 2, alignItems: 'center' }}>
                  <TextField
                    size="small"
                    placeholder="Search..."
                    value={searchText}
                    onChange={(e) => setSearchText(e.target.value)}
                    InputProps={{
                      startAdornment: (
                        <InputAdornment position="start">
                          <SearchIcon />
                        </InputAdornment>
                      ),
                    }}
                    sx={{ width: 250 }}
                  />
                  <Typography variant="body2" color="text.secondary">
                    {filteredHoldings.length} of {holdings.length} rows
                  </Typography>
                </Box>
              ),
            }}
          />
        </Paper>
      )}
    </Box>
  );
}
