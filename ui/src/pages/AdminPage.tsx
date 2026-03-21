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
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import type { JobStatusResponse } from '../types';

interface SymbolCatalogStatus {
  total_symbols: number;
  last_updated_at: string | null;
}

interface CMPStatus {
  total_symbols: number;
  cmp_present_count: number;
  last_cmp_job: {
    job_id: number;
    processed: number;
    succeeded: number;
    failed: number;
    updated_at: string | null;
  } | null;
}

interface OhlcvStatus {
  total_candles: number;
  symbols_with_candles: number;
  last_ohlcv_job: {
    job_id: number;
    processed_symbols: number;
    succeeded_symbols: number;
    failed_symbols: number;
    days: number;
    updated_at: string | null;
  } | null;
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
  const [message, setMessage] = useState<{ type: 'success' | 'error' | 'warning'; text: string } | null>(null);
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
  const [activeFailuresType, setActiveFailuresType] = useState<'cmp' | 'ohlcv'>('cmp');
  const [ohlcvDays, setOhlcvDays] = useState<number>(200);

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
    } catch (err) {
      console.error('Failed to fetch OHLCV status:', err);
    }
  }, []);

  const handleRefreshOhlcv = async () => {
    setLoading(true);
    setMessage(null);
    setOhlcvJobStatus(null);
    try {
      const result = await api.refreshOHLCV(ohlcvDays);
      setOhlcvJobId(result.job_id);
      setMessage({
        type: 'success',
        text: `OHLCV refresh started for ${ohlcvDays} days...`,
      });
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

  const handleLoadLastOhlcvJob = async () => {
    try {
      const lastJob = await api.getLastOHLCVJob();
      if (lastJob.job_id) {
        setOhlcvJobId(lastJob.job_id);
        const job = await api.getJob(lastJob.job_id);
        setOhlcvJobStatus(job);
        setMessage({
          type: 'success',
          text: `Loaded job #${lastJob.job_id}`,
        });
      } else {
        setMessage({
          type: 'warning',
          text: 'No OHLCV job found',
        });
      }
    } catch (err) {
      console.error('Failed to load last OHLCV job:', err);
    }
  };

  const handleRefreshCMP = async () => {
    setLoading(true);
    setMessage(null);
    try {
      await api.refreshCMP();
      setMessage({
        type: 'success',
        text: 'CMP refresh started...',
      });
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Failed to start CMP refresh';
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
                CMP (Current Market Price)
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
                <Typography variant="body1" sx={{ mb: 2 }}>
                  {cmpStatus?.cmp_present_count || 0} / {cmpStatus?.total_symbols || 0} symbols have CMP
                </Typography>

                {cmpStatus?.last_cmp_job && (
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                    Last job: {cmpStatus.last_cmp_job.succeeded} succeeded, {cmpStatus.last_cmp_job.failed} failed ({formatDate(cmpStatus.last_cmp_job.updated_at)})
                    {cmpStatus.last_cmp_job.failed > 0 && (
                      <Button
                        size="small"
                        onClick={() => fetchJobFailures(cmpStatus.last_cmp_job!.job_id)}
                        disabled={loadingFailures}
                        sx={{ ml: 1 }}
                      >
                        View Failures
                      </Button>
                    )}
                  </Typography>
                )}

                <Button
                  variant="contained"
                  color="primary"
                  onClick={handleRefreshCMP}
                  disabled={loading}
                  startIcon={loading ? <CircularProgress size={20} color="inherit" /> : <RefreshIcon />}
                >
                  {loading ? 'Fetching...' : 'Fetch CMP'}
                </Button>
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
                <Typography variant="body1" sx={{ mb: 2 }}>
                  {ohlcvStatus?.symbols_with_candles || 0} symbols with {ohlcvStatus?.total_candles || 0} total candles
                </Typography>

                {ohlcvStatus?.last_ohlcv_job && (
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                    Last job: {ohlcvStatus.last_ohlcv_job.succeeded_symbols} succeeded, {ohlcvStatus.last_ohlcv_job.failed_symbols} failed ({formatDate(ohlcvStatus.last_ohlcv_job.updated_at)})
                    {ohlcvStatus.last_ohlcv_job.failed_symbols > 0 && (
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
                    Days back:
                  </Typography>
                  <TextField
                    type="number"
                    size="small"
                    value={ohlcvDays}
                    onChange={(e) => setOhlcvDays(Math.max(1, parseInt(e.target.value) || 200))}
                    sx={{ width: 100 }}
                    inputProps={{ min: 1 }}
                  />
                </Box>

                <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                  <Button
                    variant="contained"
                    color="primary"
                    onClick={handleRefreshOhlcv}
                    disabled={loading || (ohlcvJobStatus?.job && ['pending', 'running'].includes(ohlcvJobStatus.job.status))}
                    startIcon={loading || (ohlcvJobStatus?.job && ['pending', 'running'].includes(ohlcvJobStatus.job.status)) ? <CircularProgress size={20} color="inherit" /> : <RefreshIcon />}
                  >
                    Fetch OHLCV
                  </Button>
                  <Button
                    variant="outlined"
                    size="small"
                    onClick={handleLoadLastOhlcvJob}
                  >
                    Load Last Job
                  </Button>
                  {ohlcvJobId && (
                    <Button
                      size="small"
                      onClick={() => navigate(`/jobs/${ohlcvJobId}`)}
                    >
                      View Job #{ohlcvJobId}
                    </Button>
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
