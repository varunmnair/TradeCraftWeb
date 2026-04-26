import { useState, useCallback, useEffect } from 'react';
import {
  Box,
  Typography,
  Paper,
  Button,
  Alert,
  CircularProgress,
  Card,
  CardContent,
  Tabs,
  Tab,
  Modal,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  IconButton,
  TextField,
  LinearProgress,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
} from '@mui/material';
import {
  AdminPanelSettings as AdminIcon,
  Refresh as RefreshIcon,
  Upload as UploadIcon,
  Close as CloseIcon,
  Delete as DeleteIcon,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import type { JobStatusResponse } from '../types';

interface SymbolCatalogStatus {
  total_symbols: number;
  last_updated_at: string | null;
}

interface CMPStatus {
  cached_symbols: number;
  last_updated: string | null;
  ttl_seconds: number;
  has_analytics_token: boolean;
  note: string;
}

interface OhlcvStatus {
  config_days: number;
  total_symbols: number;
  date_from: string | null;
  date_to: string | null;
  total_candles: number;
  last_updated: string | null;
  last_ohlcv_job: {
    job_id: number;
    symbols_refreshed: number;
    symbols_skipped: number;
    symbols_failed: number;
    days: number;
    updated_at: string | null;
  } | null;
}

interface OhlcvInspectData {
  symbol: string;
  date_from: string | null;
  date_to: string | null;
  candles: Array<{
    date: string;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
  }>;
  error?: string;
}

interface JobFailures {
  job_id: number;
  job_type: string;
  operation: string | null;
  total: number;
  succeeded: number;
  failed: number;
  failures: Array<{ symbol: string; excerpt: string }>;
}

export default function AdminPage() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<'market' | 'users'>('market');
  
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error' | 'warning' | 'info'; text: string } | null>(null);
  const [catalogStatus, setCatalogStatus] = useState<SymbolCatalogStatus | null>(null);
  const [cmpStatus, setCmpStatus] = useState<CMPStatus | null>(null);
  const [ohlcvStatus, setOhlcvStatus] = useState<OhlcvStatus | null>(null);
  const [ohlcvJobId, setOhlcvJobId] = useState<number | null>(null);
  const [ohlcvJobStatus, setOhlcvJobStatus] = useState<JobStatusResponse | null>(null);
  const [upstoxError, setUpstoxError] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [failuresModalOpen, setFailuresModalOpen] = useState(false);
  const [jobFailures, setJobFailures] = useState<JobFailures | null>(null);
  const [loadingFailures, setLoadingFailures] = useState(false);
  const [activeFailuresType, setActiveFailuresType] = useState<'ohlcv'>('ohlcv');
  const [ohlcvDays, setOhlcvDays] = useState<number>(200);
  const [ohlcvConfigLoading, setOhlcvConfigLoading] = useState(false);
  const [inspectSymbol, setInspectSymbol] = useState('');
  const [inspectData, setInspectData] = useState<OhlcvInspectData | null>(null);
  const [inspectLoading, setInspectLoading] = useState(false);
  const [purgeConfirmOpen, setPurgeConfirmOpen] = useState(false);

  const fetchCatalogStatus = useCallback(async () => {
    try {
      const catalog = await api.getSymbolCatalogStatus();
      setCatalogStatus(catalog);
    } catch (err) {
      console.error('Failed to fetch catalog status:', err);
    }
  }, []);

  const fetchCMPStatus = useCallback(async () => {
    try {
      const data = await api.getCMPStatus();
      setCmpStatus(data);
    } catch (err) {
      console.error('Failed to fetch CMP status:', err);
    }
  }, []);

  const fetchOhlcvStatus = useCallback(async () => {
    try {
      const data = await api.getOHLCVStatus();
      setOhlcvStatus(data);
      if (data.config_days) {
        setOhlcvDays(data.config_days);
      }
    } catch (err) {
      console.error('Failed to fetch OHLCV status:', err);
    }
  }, []);

  const handleSaveOhlcvConfig = async () => {
    setOhlcvConfigLoading(true);
    setMessage(null);
    try {
      await api.updateOHLCVConfig(ohlcvDays);
      setMessage({
        type: 'success',
        text: `OHLCV config saved: ${ohlcvDays} days`,
      });
    } catch (err) {
      setMessage({
        type: 'error',
        text: err instanceof Error ? err.message : 'Failed to save OHLCV config',
      });
    } finally {
      setOhlcvConfigLoading(false);
    }
  };

  const handleInspectSymbol = async () => {
    if (!inspectSymbol.trim()) return;
    setInspectLoading(true);
    setInspectData(null);
    try {
      const data = await api.inspectOHLCV(inspectSymbol.trim(), 100);
      setInspectData(data);
    } catch (err) {
      setMessage({
        type: 'error',
        text: err instanceof Error ? err.message : 'Failed to inspect symbol',
      });
    } finally {
      setInspectLoading(false);
    }
  };

  const handlePurgeAll = async () => {
    setLoading(true);
    setMessage(null);
    setPurgeConfirmOpen(false);
    try {
      const result = await api.purgeAllOHLCV();
      setMessage({
        type: 'success',
        text: `Purged ${result.candles_deleted} candles and ${result.metadata_deleted} metadata entries`,
      });
      fetchOhlcvStatus();
    } catch (err) {
      setMessage({
        type: 'error',
        text: err instanceof Error ? err.message : 'Failed to purge OHLCV data',
      });
    } finally {
      setLoading(false);
    }
  };

  const handleRefreshOhlcv = async () => {
    setLoading(true);
    setMessage(null);
    setOhlcvJobStatus(null);
    try {
      const result = await api.refreshOHLCV(ohlcvDays);
      setOhlcvJobId(result.job_id);
      if (result.symbols_count === 0) {
        setMessage({
          type: 'info',
          text: 'No symbols with existing OHLCV data to refresh',
        });
      } else {
        setMessage({
          type: 'success',
          text: `OHLCV refresh started for ${result.symbols_count} existing symbols...`,
        });
      }
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Failed to start OHLCV refresh';
      if (errorMsg.includes('UPSTOX_NOT_CONNECTED')) {
        setUpstoxError(true);
        if (errorMsg.includes('expired')) {
          setMessage({
            type: 'warning',
            text: 'Upstox session has expired. Please reconnect Upstox from the Brokers page.',
          });
        } else {
          setMessage({
            type: 'warning',
            text: 'No active Upstox connection found. Please connect Upstox from the Brokers page.',
          });
        }
      } else {
        setMessage({
          type: 'error',
          text: errorMsg,
        });
      }
    } finally {
      setLoading(false);
    }
  };



  useEffect(() => {
    fetchCatalogStatus();
    fetchCMPStatus();
    fetchOhlcvStatus();
  }, [fetchCatalogStatus, fetchCMPStatus, fetchOhlcvStatus]);

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] || null;
    setSelectedFile(file);
    if (file) {
      setMessage(null);
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) return;
    
    setLoading(true);
    setMessage(null);
    try {
      await api.importSymbolCatalog(selectedFile);
      setMessage({
        type: 'success',
        text: `Symbol catalog import started for ${selectedFile.name}...`,
      });
    } catch (err) {
      setMessage({
        type: 'error',
        text: err instanceof Error ? err.message : 'Failed to upload',
      });
    } finally {
      setLoading(false);
      setSelectedFile(null);
    }
  };

  const fetchJobFailures = async (failureJobId: number) => {
    setLoadingFailures(true);
    try {
      const data = await api.getJobFailures(failureJobId);
      setJobFailures(data);
      setFailuresModalOpen(true);
    } catch (err) {
      console.error('Failed to fetch failures:', err);
    } finally {
      setLoadingFailures(false);
    }
  };

  const downloadFailures = () => {
    if (!jobFailures) return;
    
    const csv = [
      'Symbol,Error',
      ...jobFailures.failures.map(f => `"${f.symbol}","${f.excerpt}"`),
    ].join('\n');
    
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${activeFailuresType}-failures-${jobFailures.job_id}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return 'Never';
    try {
      return new Date(dateStr).toLocaleString();
    } catch {
      return dateStr;
    }
  };

  const catalogSymbolCount = catalogStatus?.total_symbols || 0;

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
        <AdminIcon fontSize="large" />
        <Typography variant="h4">Administration</Typography>
      </Box>

      <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 3 }}>
        <Tabs value={activeTab} onChange={(_, v) => setActiveTab(v)}>
          <Tab label="Market Data" value="market" />
          <Tab label="User Management" value="users" />
        </Tabs>
      </Box>

      {message && (
        <Alert
          severity={message.type}
          sx={{ mb: 2 }}
          onClose={() => setMessage(null)}
          action={
            message.type === 'warning' ? (
              <Button color="inherit" size="small" onClick={() => navigate('/broker-connections')}>
                Go to Brokers
              </Button>
            ) : undefined
          }
        >
          {message.text}
        </Alert>
      )}

      {activeTab === 'market' && (
        <>
          {upstoxError && (
            <Alert severity="warning" sx={{ mb: 2 }}>
              Upstox is not connected. Please connect Upstox from the Brokers page to refresh market data.
              <Button
                color="inherit"
                size="small"
                onClick={() => navigate('/broker-connections')}
                sx={{ ml: 2 }}
              >
                Connect Upstox
              </Button>
            </Alert>
          )}

          {/* Symbol Catalog Card */}
          <Paper sx={{ p: 3, mb: 3 }}>
            <Typography variant="h6" gutterBottom>
              Symbol Catalog
            </Typography>
            
            <Box sx={{ display: 'flex', gap: 2, mb: 2, alignItems: 'center' }}>
              <Typography variant="body2" color="text.secondary">
                {catalogStatus ? (
                  <>
                    {catalogStatus.total_symbols} symbols | Last updated: {formatDate(catalogStatus.last_updated_at)}
                  </>
                ) : (
                  'Loading...'
                )}
              </Typography>
              <Button
                size="small"
                startIcon={<RefreshIcon />}
                onClick={fetchCatalogStatus}
                disabled={loading}
              >
                Refresh Status
              </Button>
            </Box>

            <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
              <Button
                component="label"
                variant="outlined"
                startIcon={<UploadIcon />}
              >
                Choose CSV File
                <input
                  type="file"
                  hidden
                  accept=".csv"
                  onChange={handleFileSelect}
                />
              </Button>

              {selectedFile && (
                <>
                  <Typography variant="body2" color="text.secondary">
                    {selectedFile.name}
                  </Typography>
                  <Button
                    variant="contained"
                    color="warning"
                    onClick={handleUpload}
                    disabled={loading}
                  >
                    {loading ? 'Uploading...' : 'Upload & Replace'}
                  </Button>
                </>
              )}
            </Box>
          </Paper>

          {/* CMP Card */}
          <Paper sx={{ p: 3, mb: 3 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Typography variant="h6">
                CMP Cache (Current Market Price)
              </Typography>
              <Button
                size="small"
                startIcon={<RefreshIcon />}
                onClick={fetchCMPStatus}
                disabled={loading}
              >
                Refresh Status
              </Button>
            </Box>

            {loading ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', py: 2 }}>
                <CircularProgress size={24} />
              </Box>
            ) : (
              <>
                <Typography variant="body1" sx={{ mb: 1 }}>
                  {cmpStatus?.cached_symbols || 0} symbols cached in memory
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                  TTL: {cmpStatus?.ttl_seconds || 300} seconds (5 minutes)
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                  Last updated: {formatDate(cmpStatus?.last_updated || null)}
                </Typography>
                <Alert severity="info" sx={{ mt: 1 }}>
                  {cmpStatus?.note || 'CMP is fetched on-demand and cached in-memory'}
                </Alert>
                {!cmpStatus?.has_analytics_token && (
                  <Alert severity="warning" sx={{ mt: 1 }}>
                    UPSTOX_ANALYTICS_TOKEN not configured. CMP fetching may fail.
                  </Alert>
                )}
              </>
            )}
          </Paper>

          {/* OHLCV Card */}
          <Paper sx={{ p: 3, mb: 3 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Typography variant="h6">
                OHLCV (Daily Candles)
              </Typography>
              <Button
                size="small"
                startIcon={<RefreshIcon />}
                onClick={fetchOhlcvStatus}
                disabled={loading}
              >
                Refresh Status
              </Button>
            </Box>

            {loading ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', py: 2 }}>
                <CircularProgress size={24} />
              </Box>
            ) : (
              <>
                {/* Data Status */}
                <Box sx={{ display: 'flex', gap: 3, mb: 2 }}>
                  <Box>
                    <Typography variant="body2" color="text.secondary">Total Symbols</Typography>
                    <Typography variant="h6">{ohlcvStatus?.total_symbols || 0}</Typography>
                  </Box>
                  <Box>
                    <Typography variant="body2" color="text.secondary">Date Range</Typography>
                    <Typography variant="body1">
                      {ohlcvStatus?.date_from || '-'} to {ohlcvStatus?.date_to || '-'}
                    </Typography>
                  </Box>
                  <Box>
                    <Typography variant="body2" color="text.secondary">Total Candles</Typography>
                    <Typography variant="h6">{ohlcvStatus?.total_candles || 0}</Typography>
                  </Box>
                </Box>

                {ohlcvStatus?.last_ohlcv_job && (
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                    Last job: {ohlcvStatus.last_ohlcv_job.symbols_refreshed} refreshed, {ohlcvStatus.last_ohlcv_job.symbols_skipped} skipped, {ohlcvStatus.last_ohlcv_job.symbols_failed} failed ({formatDate(ohlcvStatus.last_ohlcv_job.updated_at)})
                    {ohlcvStatus.last_ohlcv_job.symbols_failed > 0 && (
                      <Button
                        size="small"
                        onClick={() => {
                          setActiveFailuresType('ohlcv');
                          fetchJobFailures(ohlcvStatus.last_ohlcv_job!.job_id);
                        }}
                        disabled={loadingFailures}
                        sx={{ ml: 1 }}
                      >
                        View Failures
                      </Button>
                    )}
                  </Typography>
                )}

                <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', mb: 2 }}>
                  <Typography variant="body2" color="text.secondary">
                    Config (days):
                  </Typography>
                  <TextField
                    type="number"
                    size="small"
                    value={ohlcvDays}
                    onChange={(e) => setOhlcvDays(Math.min(500, Math.max(30, parseInt(e.target.value) || 200)))}
                    sx={{ width: 80 }}
                    inputProps={{ min: 30, max: 500 }}
                  />
                  <Button
                    variant="outlined"
                    size="small"
                    onClick={handleSaveOhlcvConfig}
                    disabled={ohlcvConfigLoading}
                  >
                    {ohlcvConfigLoading ? 'Saving...' : 'Save'}
                  </Button>
                </Box>

                <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', mb: 2 }}>
                  <Button
                    variant="contained"
                    color="primary"
                    onClick={handleRefreshOhlcv}
                    disabled={loading || (ohlcvJobStatus?.job && ['pending', 'running'].includes(ohlcvJobStatus.job.status))}
                    startIcon={loading || (ohlcvJobStatus?.job && ['pending', 'running'].includes(ohlcvJobStatus.job.status)) ? <CircularProgress size={20} color="inherit" /> : <RefreshIcon />}
                  >
                    Refresh Data
                  </Button>
                  <Button
                    variant="outlined"
                    color="error"
                    onClick={() => setPurgeConfirmOpen(true)}
                    disabled={loading}
                  >
                    Purge All
                  </Button>
                </Box>

                {/* Inspect Symbol Section */}
                <Box sx={{ mt: 3, pt: 2, borderTop: 1, borderColor: 'divider' }}>
                  <Typography variant="subtitle2" sx={{ mb: 1 }}>Inspect Symbol</Typography>
                  <Box sx={{ display: 'flex', gap: 1, mb: 1 }}>
                    <TextField
                      size="small"
                      placeholder="Symbol (e.g. LODHA)"
                      value={inspectSymbol}
                      onChange={(e) => setInspectSymbol(e.target.value.toUpperCase())}
                      onKeyPress={(e) => e.key === 'Enter' && handleInspectSymbol()}
                      sx={{ width: 120 }}
                    />
                    <Button
                      variant="outlined"
                      size="small"
                      onClick={handleInspectSymbol}
                      disabled={inspectLoading || !inspectSymbol.trim()}
                    >
                      {inspectLoading ? '...' : 'Inspect'}
                    </Button>
                  </Box>

                  {inspectData && (
                    <Box sx={{ mt: 1 }}>
                      {inspectData.error ? (
                        <Alert severity="warning" sx={{ mb: 1 }}>{inspectData.error}</Alert>
                      ) : (
                        <>
                          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                            {inspectData.symbol}: {inspectData.date_from} to {inspectData.date_to} ({inspectData.candles.length} candles)
                          </Typography>
                          <TableContainer sx={{ maxHeight: 200 }}>
                            <Table size="small">
                              <TableHead>
                                <TableRow>
                                  <TableCell>Date</TableCell>
                                  <TableCell>Open</TableCell>
                                  <TableCell>High</TableCell>
                                  <TableCell>Low</TableCell>
                                  <TableCell>Close</TableCell>
                                  <TableCell>Volume</TableCell>
                                </TableRow>
                              </TableHead>
                              <TableBody>
                                {inspectData.candles.slice(0, 30).map((candle, idx) => (
                                  <TableRow key={idx}>
                                    <TableCell>{candle.date}</TableCell>
                                    <TableCell>{candle.open?.toFixed(2)}</TableCell>
                                    <TableCell>{candle.high?.toFixed(2)}</TableCell>
                                    <TableCell>{candle.low?.toFixed(2)}</TableCell>
                                    <TableCell>{candle.close?.toFixed(2)}</TableCell>
                                    <TableCell>{candle.volume?.toLocaleString()}</TableCell>
                                  </TableRow>
                                ))}
                              </TableBody>
                            </Table>
                          </TableContainer>
                        </>
                      )}
                    </Box>
                  )}
                </Box>

                {ohlcvJobId && ohlcvJobStatus?.job && ['pending', 'running'].includes(ohlcvJobStatus.job.status) && (
                  <Box sx={{ mt: 2 }}>
                    <LinearProgress sx={{ mb: 1 }} />
                    <Typography variant="body2" color="text.secondary">
                      Job #{ohlcvJobId} - {Math.round((ohlcvJobStatus.job.progress || 0) * 100)}% complete
                    </Typography>
                  </Box>
                )}
              </>
            )}
          </Paper>
        </>
      )}

      {activeTab === 'users' && (
        <Paper sx={{ p: 3 }}>
          <Typography variant="h6" gutterBottom>
            User Management
          </Typography>
          <Alert severity="info">
            User management coming soon
          </Alert>
        </Paper>
      )}

      {/* Purge Confirmation Dialog */}
      <Dialog open={purgeConfirmOpen} onClose={() => setPurgeConfirmOpen(false)}>
        <DialogTitle>Confirm Purge All OHLCV Data?</DialogTitle>
        <DialogContent>
          <Typography>
            This will permanently delete all OHLCV candle data and metadata for all symbols.
            This action cannot be undone.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPurgeConfirmOpen(false)}>Cancel</Button>
          <Button variant="contained" color="error" onClick={handlePurgeAll}>
            Purge All
          </Button>
        </DialogActions>
      </Dialog>

      {/* Failures Modal */}
      <Modal
        open={failuresModalOpen}
        onClose={() => setFailuresModalOpen(false)}
        aria-labelledby="failures-modal-title"
      >
        <Paper sx={{
          position: 'absolute',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          width: '90%',
          maxWidth: 600,
          maxHeight: '80vh',
          p: 3,
          overflow: 'auto',
        }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <DialogTitle id="failures-modal-title" sx={{ p: 0 }}>
              {activeFailuresType === 'ohlcv' ? 'OHLCV' : 'CMP'} Fetch Failures
            </DialogTitle>
            <IconButton onClick={() => setFailuresModalOpen(false)} size="small">
              <CloseIcon />
            </IconButton>
          </Box>
          
          <DialogContent>
            {loadingFailures ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
                <CircularProgress />
              </Box>
            ) : jobFailures ? (
              <>
                <Box sx={{ mb: 2 }}>
                  <Typography variant="body2" color="text.secondary">
                    {jobFailures.succeeded} succeeded, {jobFailures.failed} failed out of {jobFailures.total}
                  </Typography>
                </Box>
                
                <TableContainer sx={{ maxHeight: 400 }}>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Symbol</TableCell>
                        <TableCell>Error</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {jobFailures.failures.map((f, idx) => (
                        <TableRow key={idx}>
                          <TableCell>{f.symbol}</TableCell>
                          <TableCell>{f.excerpt}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              </>
            ) : null}
          </DialogContent>
          
          <DialogActions>
            <Button onClick={() => setFailuresModalOpen(false)}>Close</Button>
            {jobFailures && jobFailures.failures.length > 0 && (
              <Button variant="contained" onClick={downloadFailures}>
                Download Failures
              </Button>
            )}
          </DialogActions>
        </Paper>
      </Modal>
    </Box>
  );
}
