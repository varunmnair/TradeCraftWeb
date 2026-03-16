import React, { useState, useEffect, useMemo } from 'react';
import {
  Box,
  Typography,
  Paper,
  Alert,
  CircularProgress,
  Button,
  TextField,
  Chip,
  Tabs,
  Tab,
  Switch,
  FormControlLabel,
  InputAdornment,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Tooltip,
} from '@mui/material';
import { DataGrid, GridColDef, GridRowSelectionModel, GridRenderCellParams } from '@mui/x-data-grid';
import { 
  PlayArrow as GenerateIcon, 
  Search as SearchIcon,
  ShoppingCart as BuyIcon,
  Warning as WarningIcon,
  Refresh as ResetIcon,
  TrendingDown as PriceDownIcon,
  TrendingUp as PriceUpIcon,
  ArrowForward as ArrowForwardIcon,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { useSession } from '../context/SessionContext';
import { useStartJob } from '../context/JobsContext';
import { GTTConfirmResponse } from '../types';
import { SkippedItemsDialog } from '../components/SkippedItemsDialog';
import { useJobRunner } from '../hooks/useJobRunner';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;
  return (
    <div role="tabpanel" hidden={value !== index} {...other}>
      {value === index && <Box sx={{ pt: 3 }}>{children}</Box>}
    </div>
  );
}

interface PlanRow extends Record<string, unknown> {
  _originalValues?: Record<string, unknown>;
  _changes?: string[];
}

const LEVEL_FIELDS = ['entry1', 'entry2', 'entry3', 'trigger1', 'trigger2', 'trigger3'];
const AMOUNT_FIELDS = ['amount1', 'amount2', 'amount3', 'allocated', 'spendable'];
const QTY_FIELDS = ['quantity', 'qty1', 'qty2', 'qty3'];

const getRowKey = (row: Record<string, unknown>): string => {
  const symbol = row.Symbol || row.symbol || row.tradingsymbol || '';
  const level = row.Level || row.level || row.entry_level || row.entry || row.leg || '1';
  return `${symbol}-${level}`;
};

function computeChanges(original: Record<string, unknown>, adjusted: Record<string, unknown>): string[] {
  const changes: string[] = [];
  
  for (const field of LEVEL_FIELDS) {
    const origVal = original[field];
    const adjVal = adjusted[field];
    if (origVal !== undefined && adjVal !== undefined && Number(origVal) !== Number(adjVal)) {
      changes.push('Price');
      break;
    }
  }
  
  for (const field of AMOUNT_FIELDS) {
    const origVal = original[field];
    const adjVal = adjusted[field];
    if (origVal !== undefined && adjVal !== undefined && Number(origVal) !== Number(adjVal)) {
      changes.push('Amount');
      break;
    }
  }
  
  for (const field of QTY_FIELDS) {
    const origVal = original[field];
    const adjVal = adjusted[field];
    if (origVal !== undefined && adjVal !== undefined && Number(origVal) !== Number(adjVal)) {
      changes.push('Quantity');
      break;
    }
  }
  
  return changes;
}

export default function BuyEntriesPage() {
  const { sessionId } = useSession();
  const { start: startJob, job, isDone, isError } = useStartJob();
  
  // Job runners for each strategy
  const {
    isRunning: isGenerating,
    isSuccess: generateSuccess,
    isError: generateError,
    errorMessage: generateErrorMsg,
    jobStatus: generateJobStatus,
    jobProgress: generateJobProgress,
    run: runGenerate,
    reset: resetGenerate,
  } = useJobRunner({
    onSuccess: () => {
      fetchPlan();
    },
    onError: (msg) => {
      setError(msg);
    },
  });

  const {
    isRunning: isDaGenerating,
    isSuccess: daGenerateSuccess,
    isError: daGenerateError,
    errorMessage: daGenerateErrorMsg,
    jobStatus: daGenerateJobStatus,
    jobProgress: daGenerateJobProgress,
    run: runDaGenerate,
    reset: resetDaGenerate,
  } = useJobRunner({
    onSuccess: () => {
      fetchDaPlan();
    },
    onError: (msg) => {
      setError(msg);
    },
  });
  
  const [tabValue, setTabValue] = useState(0);
  const [plan, setPlan] = useState<PlanRow[]>([]);
  const [originalPlan, setOriginalPlan] = useState<PlanRow[]>([]);
  const [riskAdjustedPlan, setRiskAdjustedPlan] = useState<PlanRow[]>([]);
  const [skipped, setSkipped] = useState<{symbol?: string; Symbol?: string; skip_reason?: string; reason?: string}[]>([]);
  const [columns, setColumns] = useState<GridColDef[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [searchText, setSearchText] = useState('');
  const [selectedRows, setSelectedRows] = useState<GridRowSelectionModel>([]);
  
  // Skipped modal state
  const [skippedModalOpen, setSkippedModalOpen] = useState(false);
  
  // Risk toggle state
  const [riskEnabled, setRiskEnabled] = useState(false);
  const [riskJobRunning, setRiskJobRunning] = useState(false);
  const [originalPlanRows, setOriginalPlanRows] = useState<PlanRow[]>([]);
  
  // DA Tab state
  const [daPlan, setDaPlan] = useState<PlanRow[]>([]);
  const [daSkipped, setDaSkipped] = useState<{symbol?: string; Symbol?: string; skip_reason?: string; reason?: string}[]>([]);
  const [daColumns, setDaColumns] = useState<GridColDef[]>([]);
  const [daLoading, setDaLoading] = useState(false);
  const [daSearchText, setDaSearchText] = useState('');
  const [daSelectedRows, setDaSelectedRows] = useState<GridRowSelectionModel>([]);
  
  // DA Skipped modal state
  const [daSkippedModalOpen, setDaSkippedModalOpen] = useState(false);
  
  // DA Confirm dialog
  const [daConfirmDialogOpen, setDaConfirmDialogOpen] = useState(false);
  const [daConfirming, setDaConfirming] = useState(false);
  const [daConfirmToken, setDaConfirmToken] = useState<GTTConfirmResponse | null>(null);
  const [daPlacingOrders, setDaPlacingOrders] = useState(false);
  const [daOrderSuccess, setDaOrderSuccess] = useState(false);

  const navigate = useNavigate();
  
  // Confirm dialog
  const [confirmDialogOpen, setConfirmDialogOpen] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [confirmToken, setConfirmToken] = useState<GTTConfirmResponse | null>(null);
  const [placingOrders, setPlacingOrders] = useState(false);
  const [orderSuccess, setOrderSuccess] = useState(false);

  // Get current plan (plan already contains the correct data - original or risk-adjusted)
  const currentPlan = plan;

  // Get original plan (for diff highlighting)
  const originalPlanMap = useMemo(() => {
    const map = new Map<string, PlanRow>();
    for (const row of originalPlan) {
      map.set(getRowKey(row), row);
    }
    return map;
  }, [originalPlan]);

  // Clear selection when plan becomes empty
  useEffect(() => {
    if (currentPlan.length === 0) {
      setSelectedRows([]);
    }
  }, [currentPlan]);

  // Fetch plan when job is done OR when sessionId changes
  useEffect(() => {
    if (sessionId) {
      fetchPlan();
    }
  }, [sessionId]);

  const fetchPlan = async () => {
    if (!sessionId || loading) return;
    setLoading(true);
    try {
      const data = await api.getPlanLatest(sessionId);
      const planData = data.plan || [];
      
      // Store as original plan
      const planWithMeta: PlanRow[] = planData.map(row => ({
        ...row,
        _originalValues: { ...row },
        _changes: [],
      }));
      
      setPlan(planWithMeta);
      setOriginalPlan(planWithMeta);
      setOriginalPlanRows(planWithMeta);
      
      // If risk is currently enabled, don't reset - keep adjusted plan
      // Otherwise set display to the fetched plan
      
      // Convert skipped items to objects
      const skippedItems = (data.skipped || []).map((s) => 
        typeof s === 'object' 
          ? s as {symbol?: string; Symbol?: string; skip_reason?: string; reason?: string}
          : { symbol: String(s), skip_reason: '' }
      );
      setSkipped(skippedItems);
      
      if (planWithMeta.length > 0) {
        generateColumns(planWithMeta);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch plan');
    } finally {
      setLoading(false);
    }
  };

  const generateColumns = (items: PlanRow[]) => {
    if (items.length === 0) {
      setColumns([]);
      return;
    }
    
    const firstRow = items[0];
    const cols: GridColDef[] = [];
    
    Object.keys(firstRow).map((key) => {
      if (key.startsWith('_')) return; // Skip internal fields
      
      const value = firstRow[key];
      let type: 'string' | 'number' | 'boolean' | 'date' = 'string';
      
      if (typeof value === 'number') type = 'number';
      else if (typeof value === 'boolean') type = 'boolean';
      
      // Custom cell renderer for diff highlighting
      const renderCell = (params: GridRenderCellParams) => {
        const row = params.row as PlanRow;
        const originalRow = originalPlanMap.get(getRowKey(row));
        
        if (originalRow && riskEnabled) {
          const origVal = originalRow[key];
          const currVal = params.value;
          
          const origNum = Number(origVal);
          const currNum = Number(currVal);
          const isNumericChange = !isNaN(origNum) && !isNaN(currNum) && origNum !== currNum;
          
          if (isNumericChange) {
            const changed = currNum < origNum ? 'decreased' : 'increased';
            return (
              <Tooltip title={`Original: ${origVal} → Now: ${currVal}`}>
                <Box sx={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  gap: 0.5,
                  color: changed === 'decreased' ? 'error.main' : 'success.main',
                  fontWeight: 'bold',
                }}>
                  {changed === 'decreased' ? <PriceDownIcon fontSize="small" /> : <PriceUpIcon fontSize="small" />}
                  {String(currVal)}
                </Box>
              </Tooltip>
            );
          }
        }
        return String(params.value ?? '');
      };
      
      cols.push({
        field: key,
        headerName: key,
        type,
        width: type === 'number' ? 120 : 180,
        flex: type === 'string' ? 1 : 0,
        renderCell,
      });
    });
    
    // Add Changes column when risk is enabled
    if (riskEnabled) {
      cols.push({
        field: '_changes',
        headerName: 'Changes',
        width: 150,
        renderCell: (params: GridRenderCellParams) => {
          const row = params.row as PlanRow;
          const changes = row._changes || [];
          if (changes.length === 0) return '-';
          return (
            <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
              {changes.map(change => (
                <Chip 
                  key={change} 
                  label={change} 
                  size="small" 
                  color={change === 'Price' ? 'warning' : change === 'Amount' ? 'info' : 'secondary'}
                  variant="outlined"
                />
              ))}
            </Box>
          );
        },
      });
    }
    
    setColumns(cols);
  };

  // Regenerate columns when risk toggle changes
  useEffect(() => {
    if (currentPlan.length > 0) {
      generateColumns(currentPlan);
    }
  }, [riskEnabled]);

  const handleGenerate = async () => {
    if (!sessionId) {
      setError('No active session. Please start a session first.');
      return;
    }
    
    // Reset risk state
    setRiskEnabled(false);
    setRiskAdjustedPlan([]);
    
    setError('');
    
    try {
      const response = await api.generatePlan({ session_id: sessionId, apply_risk: false });
      await runGenerate(() => Promise.resolve({ job_id: response.job_id }));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate plan');
    }
  };

  const handleToggleRisk = async () => {
    if (!sessionId) return;
    
    if (!riskEnabled) {
      // Turning risk ON - apply risk
      setRiskJobRunning(true);
      setError('');
      
      try {
        const planToApply = plan.length > 0 ? plan : originalPlanRows;
        
        const response = await api.applyRisk(sessionId, planToApply);
        
        // Poll for job completion
        const pollJob = async (): Promise<boolean> => {
          let attempts = 0;
          while (attempts < 30) {
            await new Promise(r => setTimeout(r, 2000));
            try {
              const jobData = await api.getJob(response.job_id);
              if (jobData.job.status === 'completed' || jobData.job.status === 'succeeded') {
                return true;
              } else if (jobData.job.status === 'failed') {
                setError('Risk adjustment job failed');
                return false;
              }
            } catch {}
            attempts++;
          }
          setError('Timeout waiting for risk adjustment');
          return false;
        };
        
        const success = await pollJob();
        
        if (success) {
          // Fetch the latest plan with risk adjustments
          try {
            const data = await api.getRiskPlanLatest(sessionId);
            if (data.plan && data.plan.length > 0) {
              // Add metadata to plan rows - use originalPlanRows to preserve pre-risk values
              const planMap = new Map<string, PlanRow>();
              originalPlanRows.forEach(p => planMap.set(getRowKey(p), p));
              
              const adjustedWithMeta: PlanRow[] = data.plan.map(row => {
                const orig = planMap.get(getRowKey(row));
                return {
                  ...row,
                  _originalValues: orig || row,
                  _changes: [],
                };
              });
              
              setPlan(adjustedWithMeta);
              setRiskEnabled(true);
              
              // Update skipped if present
              if (data.skipped) {
                const skippedItems = (data.skipped || []).map((s: unknown) => 
                  typeof s === 'object' 
                    ? s as {symbol?: string; Symbol?: string; skip_reason?: string; reason?: string}
                    : { symbol: String(s), skip_reason: '' }
                );
                setSkipped(skippedItems);
              }
            }
          } catch (err) {
            setError('Failed to fetch adjusted plan');
          }
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to apply risk');
      } finally {
        setRiskJobRunning(false);
      }
    } else {
      // Turning risk OFF - revert to original values
      setRiskEnabled(false);
      
      // Revert each row to its original values
      const revertedPlan = plan.map(row => {
        const original = row._originalValues || row;
        return {
          ...original,
          risk_adj: 'N/A',
          risk_reasons: '',
          _changes: [],
        };
      });
      setPlan(revertedPlan);
    }
  };

  // DA Functions
  const fetchDaPlan = async () => {
    if (!sessionId || daLoading) return;
    setDaLoading(true);
    try {
      const data = await api.getDynamicAvgLatest(sessionId);
      const planData = data.plan || [];
      
      const planWithMeta: PlanRow[] = planData.map(row => ({
        ...row,
        _originalValues: { ...row },
        _changes: [],
      }));
      
      setDaPlan(planWithMeta);
      
      // Convert skipped items to objects
      const skippedItems = (data.skipped || []).map((s) => 
        typeof s === 'object' 
          ? s as {symbol?: string; Symbol?: string; skip_reason?: string; reason?: string}
          : { symbol: String(s), skip_reason: '' }
      );
      setDaSkipped(skippedItems);
      
      if (planWithMeta.length > 0) {
        generateDaColumns(planWithMeta);
      }
    } catch (err) {
      console.log('Fetch DA plan error:', err);
    } finally {
      setDaLoading(false);
    }
  };

  const generateDaColumns = (items: PlanRow[]) => {
    if (items.length === 0) {
      setDaColumns([]);
      return;
    }
    
    const firstRow = items[0];
    const cols: GridColDef[] = [];
    
    Object.keys(firstRow).map((key) => {
      if (key.startsWith('_')) return;
      
      const value = firstRow[key];
      let type: 'string' | 'number' | 'boolean' | 'date' = 'string';
      
      if (typeof value === 'number') type = 'number';
      else if (typeof value === 'boolean') type = 'boolean';
      
      cols.push({
        field: key,
        headerName: key,
        type,
        width: type === 'number' ? 120 : 180,
        flex: type === 'string' ? 1 : 0,
      });
    });
    
    setDaColumns(cols);
  };

  // Clear DA selection when plan changes to avoid stale indices
  useEffect(() => {
    setDaSelectedRows([]);
  }, [daPlan]);

  // Fetch DA plan when tab changes to DA or when job completes
  useEffect(() => {
    if (tabValue === 1 && sessionId) {
      fetchDaPlan();
    }
  }, [tabValue, sessionId]);

  const handleDaGenerate = async () => {
    if (!sessionId) {
      setError('No active session. Please start a session first.');
      return;
    }
    
    setError('');
    
    try {
      const response = await api.generateDynamicAvgPlan(sessionId);
      await runDaGenerate(() => Promise.resolve({ job_id: response.job_id }));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate DA plan');
    }
  };

  const handleDaSelectAll = () => {
    const keys = daPlan.map((row) => getRowKey(row));
    setDaSelectedRows(keys as GridRowSelectionModel);
  };

  const handleDaClearSelection = () => {
    setDaSelectedRows([]);
  };

  const handleDaConfirm = async () => {
    if (!sessionId || daSelectedRows.length === 0) return;
    
    setDaConfirming(true);
    setError('');
    
    try {
      const daPlanMap = new Map(daPlan.map((row) => [getRowKey(row), row]));
      const selectedItems = daSelectedRows.map(key => daPlanMap.get(key as string)).filter((item): item is PlanRow => Boolean(item));
      const response = await api.confirmGTT({
        session_id: sessionId,
        plan: selectedItems as unknown as Record<string, unknown>[],
      });
      setDaConfirmToken(response);
      setDaConfirmDialogOpen(true);
    } catch (err) {
      console.error('DA confirm error:', err);
      setError(err instanceof Error ? err.message : 'Failed to confirm');
    } finally {
      setDaConfirming(false);
    }
  };

  const handleDaPlaceOrders = async () => {
    if (!sessionId || !daConfirmToken) return;
    
    setDaPlacingOrders(true);
    setError('');
    
    try {
      const daPlanMap = new Map(daPlan.map((row) => [getRowKey(row), row]));
      const selectedItems = daSelectedRows.map(key => daPlanMap.get(key as string)).filter((item): item is PlanRow => Boolean(item));
      const response = await api.applyGTT({
        session_id: sessionId,
        plan: selectedItems as unknown as Record<string, unknown>[],
        confirmation_token: daConfirmToken.token,
      });
      startJob(response.job_id);
      setDaOrderSuccess(true);
    } catch (err) {
      console.error('DA apply error:', err);
      setError(err instanceof Error ? err.message : 'Failed to place orders');
    } finally {
      setDaPlacingOrders(false);
    }
  };

  const handleDaCloseConfirm = () => {
    setDaConfirmDialogOpen(false);
    setDaConfirmToken(null);
    if (daOrderSuccess) {
      setDaSelectedRows([]);
      setDaOrderSuccess(false);
    }
  };

  // Client-side filtered DA plan
  const filteredDaPlan = useMemo(() => {
    if (!daSearchText) return daPlan;
    
    const search = daSearchText.toLowerCase();
    return daPlan.filter(row => 
      Object.values(row).some(val => 
        String(val).toLowerCase().includes(search)
      )
    );
  }, [daPlan, daSearchText]);

  const handleSelectAll = () => {
    setSelectedRows(currentPlan.map((_, idx) => idx));
  };

  const handleClearSelection = () => {
    setSelectedRows([]);
  };

  const handleConfirm = async () => {
    if (!sessionId || selectedRows.length === 0) return;
    
    setConfirming(true);
    setError('');
    
    try {
      const currentPlanMap = new Map(currentPlan.map((row) => [getRowKey(row), row]));
      const selectedItems = selectedRows.map(key => currentPlanMap.get(key as string)).filter((item): item is PlanRow => Boolean(item));
      console.log('Confirm - sample item fields:', selectedItems[0] ? Object.keys(selectedItems[0]) : 'none');
      const response = await api.confirmGTT({
        session_id: sessionId,
        plan: selectedItems as unknown as Record<string, unknown>[],
      });
      setConfirmToken(response);
      setConfirmDialogOpen(true);
    } catch (err) {
      console.error('Confirm error:', err);
      setError(err instanceof Error ? err.message : 'Failed to confirm');
    } finally {
      setConfirming(false);
    }
  };

  const handlePlaceOrders = async () => {
    if (!sessionId || !confirmToken) return;
    
    setPlacingOrders(true);
    setError('');
    
    try {
      const currentPlanMap = new Map(currentPlan.map((row) => [getRowKey(row), row]));
      const selectedItems = selectedRows.map(key => currentPlanMap.get(key as string)).filter((item): item is PlanRow => Boolean(item));
      const response = await api.applyGTT({
        session_id: sessionId,
        plan: selectedItems as unknown as Record<string, unknown>[],
        confirmation_token: confirmToken.token,
      });
      startJob(response.job_id);
      setOrderSuccess(true);
    } catch (err) {
      console.error('PlaceOrders error:', err);
      setError(err instanceof Error ? err.message : 'Failed to place orders');
    } finally {
      setPlacingOrders(false);
    }
  };

  const handleCloseConfirm = () => {
    setConfirmDialogOpen(false);
    setConfirmToken(null);
    if (orderSuccess) {
      setSelectedRows([]);
      setOrderSuccess(false);
    }
  };

  // Client-side filtered plan
  const filteredPlan = useMemo(() => {
    if (!searchText) return currentPlan;
    
    const search = searchText.toLowerCase();
    return currentPlan.filter(row => 
      Object.values(row).some(val => 
        String(val).toLowerCase().includes(search)
      )
    );
  }, [currentPlan, searchText]);

  if (!sessionId) {
    return (
      <Box>
        <Typography variant="h4" gutterBottom>
          Buy / Entries
        </Typography>
        <Alert severity="warning">
          No active session. Please start a session from the Sessions page first.
        </Alert>
      </Box>
    );
  }

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Buy / Entries
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}

      <Tabs value={tabValue} onChange={(_, v) => setTabValue(v)} sx={{ mb: 2 }}>
        <Tab label="Multi-Level Entry" />
        <Tab label="Dynamic Averaging" />
      </Tabs>

      <TabPanel value={tabValue} index={0}>
        <Paper sx={{ p: 2, mb: 2 }}>
          <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
            <Button
              variant="contained"
              startIcon={isGenerating || riskJobRunning ? <CircularProgress size={20} color="inherit" /> : <GenerateIcon />}
              onClick={handleGenerate}
              disabled={isGenerating || riskJobRunning}
            >
              {isGenerating ? 'Generating...' : riskJobRunning ? 'Applying Risk...' : plan.length > 0 ? 'Refresh' : 'Generate Candidates'}
            </Button>

            <TextField
              size="small"
              placeholder="Search symbol..."
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

            <Chip 
              label={`${selectedRows.length} selected`} 
              color={selectedRows.length > 0 ? 'primary' : 'default'}
            />

            <Box sx={{ flexGrow: 1 }} />

            {/* Risk Toggle */}
            <FormControlLabel
              control={
                <Switch
                  checked={riskEnabled}
                  onChange={handleToggleRisk}
                  disabled={riskJobRunning || plan.length === 0}
                />
              }
              label={riskJobRunning ? 'Applying Risk...' : 'Apply Risk Adjustments'}
            />

            <Button
              variant="contained"
              color="success"
              startIcon={<BuyIcon />}
              onClick={handleConfirm}
              disabled={selectedRows.length === 0 || confirming}
            >
              {confirming ? 'Confirming...' : `Place ${selectedRows.length} Orders`}
            </Button>
          </Box>

          {/* Job Status */}
          {isGenerating && (
            <Box sx={{ mt: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
              <Chip 
                label={generateJobStatus || 'processing'} 
                color={generateJobStatus === 'completed' ? 'success' : generateJobStatus === 'failed' ? 'error' : 'info'}
                size="small"
              />
              <Typography variant="body2" color="text.secondary">
                Generating... {(generateJobProgress * 100).toFixed(0)}% complete
              </Typography>
            </Box>
          )}

          {/* Risk status */}
          {riskEnabled && (
            <Alert severity="info" sx={{ mt: 2 }}>
              Showing risk-adjusted values. Prices/amounts may be modified based on risk analysis.
            </Alert>
          )}

          {/* Skipped items summary */}
          {skipped.length > 0 && (
            <Alert severity="warning" sx={{ mt: 2 }} icon={<WarningIcon />}
              action={
                <Button color="inherit" size="small" onClick={() => setSkippedModalOpen(true)}>
                  View details
                </Button>
              }
            >
              {skipped.length} items skipped
            </Alert>
          )}
        </Paper>

        {/* Results */}
        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
            <CircularProgress />
          </Box>
        ) : currentPlan.length === 0 ? (
          <Paper sx={{ p: 4, textAlign: 'center' }}>
            <Typography variant="body1" color="text.secondary">
              No entry plan. Click "Generate Candidates" to create a multi-level entry plan.
            </Typography>
          </Paper>
        ) : (
          <Paper sx={{ height: 500, width: '100%' }}>
            <DataGrid
              rows={filteredPlan}
              columns={columns}
              initialState={{ pagination: { paginationModel: { pageSize: 25 } } }}
              pageSizeOptions={[10, 25, 50]}
              checkboxSelection
              disableRowSelectionOnClick
              rowSelectionModel={selectedRows}
              onRowSelectionModelChange={setSelectedRows}
              getRowId={(row) => getRowKey(row)}
            />
          </Paper>
        )}
      </TabPanel>

      <TabPanel value={tabValue} index={1}>
        <Paper sx={{ p: 2, mb: 2 }}>
          <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
            <Button
              variant="contained"
              startIcon={isDaGenerating ? <CircularProgress size={20} color="inherit" /> : <GenerateIcon />}
              onClick={handleDaGenerate}
              disabled={isDaGenerating}
            >
              {isDaGenerating ? 'Generating...' : daPlan.length > 0 ? 'Refresh' : 'Generate Averaging Candidates'}
            </Button>

            <TextField
              size="small"
              placeholder="Search symbol..."
              value={daSearchText}
              onChange={(e) => setDaSearchText(e.target.value)}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon />
                  </InputAdornment>
                ),
              }}
              sx={{ width: 250 }}
            />

            <Chip 
              label={`${daSelectedRows.length} selected`} 
              color={daSelectedRows.length > 0 ? 'primary' : 'default'}
            />

            <Box sx={{ flexGrow: 1 }} />

            <Button
              variant="contained"
              color="success"
              startIcon={<BuyIcon />}
              onClick={handleDaConfirm}
              disabled={daSelectedRows.length === 0 || daConfirming}
            >
              {daConfirming ? 'Confirming...' : `Place ${daSelectedRows.length} Orders`}
            </Button>
          </Box>

          {/* Job Status */}
          {isDaGenerating && tabValue === 1 && (
            <Box sx={{ mt: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
              <Chip 
                label={daGenerateJobStatus || 'processing'} 
                color={daGenerateJobStatus === 'completed' ? 'success' : daGenerateJobStatus === 'failed' ? 'error' : 'info'}
                size="small"
              />
              <Typography variant="body2" color="text.secondary">
                Generating... {(daGenerateJobProgress * 100).toFixed(0)}% complete
              </Typography>
            </Box>
          )}

          {/* Skipped items summary */}
          {daSkipped.length > 0 && (
            <Alert severity="warning" sx={{ mt: 2 }} icon={<WarningIcon />}
              action={
                <Button color="inherit" size="small" onClick={() => setDaSkippedModalOpen(true)}>
                  View details
                </Button>
              }
            >
              {daSkipped.length} items skipped
            </Alert>
          )}
        </Paper>

        {/* Results */}
        {daLoading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
            <CircularProgress />
          </Box>
        ) : filteredDaPlan.length === 0 ? (
          <Paper sx={{ p: 4, textAlign: 'center' }}>
            <Typography variant="body1" color="text.secondary">
              No averaging plan. Click "Generate Averaging Candidates" to create a dynamic averaging plan.
            </Typography>
          </Paper>
        ) : (
          <Paper sx={{ height: 500, width: '100%' }}>
            <DataGrid
              rows={filteredDaPlan}
              columns={daColumns}
              initialState={{ pagination: { paginationModel: { pageSize: 25 } } }}
              pageSizeOptions={[10, 25, 50]}
              checkboxSelection
              disableRowSelectionOnClick
              rowSelectionModel={daSelectedRows}
              onRowSelectionModelChange={setDaSelectedRows}
              getRowId={(row) => getRowKey(row)}
            />
          </Paper>
        )}
      </TabPanel>

      {/* Confirm Dialog */}
      <Dialog open={confirmDialogOpen} onClose={handleCloseConfirm} maxWidth="sm" fullWidth>
        <DialogTitle>
          Confirm Order Placement
        </DialogTitle>
        <DialogContent>
          {orderSuccess ? (
            <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2, py: 2 }}>
              <Alert severity="success">
                Orders placed successfully!
              </Alert>
              <Button
                variant="contained"
                endIcon={<ArrowForwardIcon />}
                onClick={() => navigate('/gtt')}
              >
                Review Buy Orders
              </Button>
            </Box>
          ) : (
            <>
              <Typography variant="body1" sx={{ mb: 2 }}>
                You are about to place <strong>{selectedRows.length}</strong> orders{riskEnabled ? ' (risk-adjusted)' : ''}:
              </Typography>
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Symbol</TableCell>
                      <TableCell>Entry</TableCell>
                      <TableCell>Amount</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {selectedRows.slice(0, 10).map((key) => {
                      const currentPlanMap = new Map(currentPlan.map((row) => [getRowKey(row), row]));
                      const item = currentPlanMap.get(key as string);
                      if (!item) return null;
                      const price = Number(item.price) || 0;
                      const qty = Number(item.qty) || 0;
                      const amount = price && qty ? Math.round(price * qty) : 0;
                      return (
                        <TableRow key={key as string}>
                          <TableCell>{String(item.Symbol || item.symbol || item.tradingsymbol || '-')}</TableCell>
                          <TableCell>{String(item.Entry || item.entry || item.entry1 || item.trigger1 || item.level || '-')}</TableCell>
                          <TableCell>{amount > 0 ? `₹${amount.toLocaleString()}` : String(item.original_amount || item.Allocated || item.allocated || '-')}</TableCell>
                        </TableRow>
                      );
                    })}
                    {selectedRows.length > 10 && (
                      <TableRow>
                        <TableCell colSpan={3}>...and {selectedRows.length - 10} more</TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </TableContainer>
              {confirmToken && (
                <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
                  Token expires: {new Date(confirmToken.expires_at).toLocaleString()}
                </Typography>
              )}
            </>
          )}
        </DialogContent>
        <DialogActions>
          {orderSuccess ? (
            <Button onClick={handleCloseConfirm} variant="contained" autoFocus>
              Done
            </Button>
          ) : (
            <>
              <Button onClick={handleCloseConfirm} disabled={placingOrders}>
                Cancel
              </Button>
              <Button 
                onClick={handlePlaceOrders} 
                variant="contained" 
                color="success"
                disabled={placingOrders}
              >
                {placingOrders ? 'Placing...' : 'Place Orders'}
              </Button>
            </>
          )}
        </DialogActions>
      </Dialog>

      {/* DA Confirm Dialog */}
      <Dialog open={daConfirmDialogOpen} onClose={handleDaCloseConfirm} maxWidth="sm" fullWidth>
        <DialogTitle>
          Confirm Dynamic Averaging Order Placement
        </DialogTitle>
        <DialogContent>
          {daOrderSuccess ? (
            <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2, py: 2 }}>
              <Alert severity="success">
                Orders placed successfully!
              </Alert>
              <Button
                variant="contained"
                endIcon={<ArrowForwardIcon />}
                onClick={() => navigate('/gtt')}
              >
                Review Buy Orders
              </Button>
            </Box>
          ) : (
            <>
              <Typography variant="body1" sx={{ mb: 2 }}>
                You are about to place <strong>{daSelectedRows.length}</strong> averaging orders:
              </Typography>
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Symbol</TableCell>
                      <TableCell>Leg</TableCell>
                      <TableCell>Trigger</TableCell>
                      <TableCell>Qty</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {daSelectedRows.slice(0, 10).map((key) => {
                      const daPlanMap = new Map(daPlan.map((row) => [getRowKey(row), row]));
                      const item = daPlanMap.get(key as string);
                      if (!item) return null;
                      return (
                        <TableRow key={key as string}>
                          <TableCell>{String(item.symbol || item.Symbol || '-')}</TableCell>
                          <TableCell>{String(item.leg || '-')}</TableCell>
                          <TableCell>{String(item.trigger || item.price || '-')}</TableCell>
                          <TableCell>{String(item.qty || item.quantity || '-')}</TableCell>
                        </TableRow>
                      );
                    })}
                    {daSelectedRows.length > 10 && (
                      <TableRow>
                        <TableCell colSpan={4}>...and {daSelectedRows.length - 10} more</TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </TableContainer>
              {daConfirmToken && (
                <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
                  Token expires: {new Date(daConfirmToken.expires_at).toLocaleString()}
                </Typography>
              )}
            </>
          )}
        </DialogContent>
        <DialogActions>
          {daOrderSuccess ? (
            <Button onClick={handleDaCloseConfirm} variant="contained" autoFocus>
              Done
            </Button>
          ) : (
            <>
              <Button onClick={handleDaCloseConfirm} disabled={daPlacingOrders}>
                Cancel
              </Button>
              <Button 
                onClick={handleDaPlaceOrders} 
                variant="contained" 
                color="success"
                disabled={daPlacingOrders}
              >
                {daPlacingOrders ? 'Placing...' : 'Place Orders'}
              </Button>
            </>
          )}
        </DialogActions>
      </Dialog>

      {/* Skipped Items Dialog for Multi-Level Entry */}
      <SkippedItemsDialog
        open={skippedModalOpen}
        onClose={() => setSkippedModalOpen(false)}
        title="Skipped Items - Multi-Level Entry"
        items={skipped}
      />

      {/* Skipped Items Dialog for Dynamic Averaging */}
      <SkippedItemsDialog
        open={daSkippedModalOpen}
        onClose={() => setDaSkippedModalOpen(false)}
        title="Skipped Items - Dynamic Averaging"
        items={daSkipped}
      />
    </Box>
  );
}
