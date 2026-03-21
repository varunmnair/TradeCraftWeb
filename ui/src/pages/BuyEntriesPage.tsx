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
  Delete as PurgeIcon,
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
  
  const [tabValue, setTabValue] = useState(0);
  const [error, setError] = useState('');

  // Multi-Level Tab State
  const [mlPlan, setMlPlan] = useState<PlanRow[]>([]);
  const [mlOriginalPlan, setMlOriginalPlan] = useState<PlanRow[]>([]);
  const [mlSkipped, setMlSkipped] = useState<{symbol?: string; Symbol?: string; skip_reason?: string; reason?: string}[]>([]);
  const [mlColumns, setMlColumns] = useState<GridColDef[]>([]);
  const [mlLoading, setMlLoading] = useState(false);
  const [mlSearchText, setMlSearchText] = useState('');
  const [mlSelectedRows, setMlSelectedRows] = useState<GridRowSelectionModel>([]);
  const [mlSkippedModalOpen, setMlSkippedModalOpen] = useState(false);
  const [mlRiskEnabled, setMlRiskEnabled] = useState(false);
  const [mlRiskJobRunning, setMlRiskJobRunning] = useState(false);
  const [mlOriginalPlanRows, setMlOriginalPlanRows] = useState<PlanRow[]>([]);
  const [mlHasPlan, setMlHasPlan] = useState(false);

  // Multi-Level Job Runner
  const {
    isRunning: isMlGenerating,
    isSuccess: mlGenerateSuccess,
    isError: mlGenerateError,
    errorMessage: mlGenerateErrorMsg,
    jobStatus: mlJobStatus,
    jobProgress: mlJobProgress,
    run: runMlGenerate,
  } = useJobRunner({
    onSuccess: () => {
      fetchMlPlan();
    },
    onError: (msg) => {
      setError(msg);
    },
  });

  // Dynamic Averaging Tab State
  const [daPlan, setDaPlan] = useState<PlanRow[]>([]);
  const [daOriginalPlan, setDaOriginalPlan] = useState<PlanRow[]>([]);
  const [daSkipped, setDaSkipped] = useState<{symbol?: string; Symbol?: string; skip_reason?: string; reason?: string}[]>([]);
  const [daColumns, setDaColumns] = useState<GridColDef[]>([]);
  const [daLoading, setDaLoading] = useState(false);
  const [daSearchText, setDaSearchText] = useState('');
  const [daSelectedRows, setDaSelectedRows] = useState<GridRowSelectionModel>([]);
  const [daSkippedModalOpen, setDaSkippedModalOpen] = useState(false);
  const [daRiskEnabled, setDaRiskEnabled] = useState(false);
  const [daRiskJobRunning, setDaRiskJobRunning] = useState(false);
  const [daOriginalPlanRows, setDaOriginalPlanRows] = useState<PlanRow[]>([]);
  const [daHasPlan, setDaHasPlan] = useState(false);

  // Dynamic Averaging Job Runner
  const {
    isRunning: isDaGenerating,
    isSuccess: daGenerateSuccess,
    isError: daGenerateError,
    errorMessage: daGenerateErrorMsg,
    jobStatus: daJobStatus,
    jobProgress: daJobProgress,
    run: runDaGenerate,
  } = useJobRunner({
    onSuccess: () => {
      fetchDaPlan();
    },
    onError: (msg) => {
      setError(msg);
    },
  });

  // Confirm dialogs
  const [confirmDialogOpen, setConfirmDialogOpen] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [confirmToken, setConfirmToken] = useState<GTTConfirmResponse | null>(null);
  const [placingOrders, setPlacingOrders] = useState(false);
  const [orderSuccess, setOrderSuccess] = useState(false);

  // DA Confirm dialog
  const [daConfirmDialogOpen, setDaConfirmDialogOpen] = useState(false);
  const [daConfirming, setDaConfirming] = useState(false);
  const [daConfirmToken, setDaConfirmToken] = useState<GTTConfirmResponse | null>(null);
  const [daPlacingOrders, setDaPlacingOrders] = useState(false);
  const [daOrderSuccess, setDaOrderSuccess] = useState(false);

  // Purge dialog
  const [purgeDialogOpen, setPurgeDialogOpen] = useState(false);
  const [purging, setPurging] = useState(false);

  const navigate = useNavigate();

  const currentMlPlan = mlPlan;
  const mlOriginalPlanMap = useMemo(() => {
    const map = new Map<string, PlanRow>();
    for (const row of mlOriginalPlan) {
      map.set(getRowKey(row), row);
    }
    return map;
  }, [mlOriginalPlan]);

  const currentDaPlan = daPlan;

  // Clear selection when plan becomes empty
  useEffect(() => {
    if (currentMlPlan.length === 0) {
      setMlSelectedRows([]);
    }
  }, [currentMlPlan]);

  useEffect(() => {
    if (daPlan.length === 0) {
      setDaSelectedRows([]);
    }
  }, [daPlan]);

  // Auto-generate plans when visiting tab
  useEffect(() => {
    if (!sessionId) return;

    if (tabValue === 0 && !mlHasPlan && !isMlGenerating) {
      // Try to fetch existing plan first
      fetchMlPlan(true);
    } else if (tabValue === 1 && !daHasPlan && !isDaGenerating) {
      fetchDaPlan(true);
    }
  }, [tabValue, sessionId]);

  const fetchMlPlan = async (autoGenerate = false) => {
    if (!sessionId || mlLoading) return;
    setMlLoading(true);
    try {
      const data = await api.getMultiLevelPlanLatest(sessionId);
      const planData = data.plan || [];
      
      if (planData.length > 0 || data.skipped?.length > 0) {
        setMlHasPlan(true);
        
        const planWithMeta: PlanRow[] = planData.map(row => ({
          ...row,
          _originalValues: { ...row },
          _changes: [],
        }));
        
        setMlPlan(planWithMeta);
        setMlOriginalPlan(planWithMeta);
        setMlOriginalPlanRows(planWithMeta);
        
        const skippedItems = (data.skipped || []).map((s) => 
          typeof s === 'object' 
            ? s as {symbol?: string; Symbol?: string; skip_reason?: string; reason?: string}
            : { symbol: String(s), skip_reason: '' }
        );
        setMlSkipped(skippedItems);
        
        if (planWithMeta.length > 0) {
          generateMlColumns(planWithMeta);
        }
      } else if (autoGenerate) {
        // Auto-generate if no plan exists
        handleMlGenerate();
      }
    } catch (err) {
      if (autoGenerate) {
        handleMlGenerate();
      }
    } finally {
      setMlLoading(false);
    }
  };

  const fetchDaPlan = async (autoGenerate = false) => {
    if (!sessionId || daLoading) return;
    setDaLoading(true);
    try {
      const data = await api.getDynamicAveragingLatest(sessionId);
      const planData = data.plan || [];
      
      if (planData.length > 0 || data.skipped?.length > 0) {
        setDaHasPlan(true);
        
        const planWithMeta: PlanRow[] = planData.map(row => ({
          ...row,
          _originalValues: { ...row },
          _changes: [],
        }));
        
        setDaPlan(planWithMeta);
        setDaOriginalPlan(planWithMeta);
        setDaOriginalPlanRows(planWithMeta);
        
        const skippedItems = (data.skipped || []).map((s) => 
          typeof s === 'object' 
            ? s as {symbol?: string; Symbol?: string; skip_reason?: string; reason?: string}
            : { symbol: String(s), skip_reason: '' }
        );
        setDaSkipped(skippedItems);
        
        if (planWithMeta.length > 0) {
          generateDaColumns(planWithMeta);
        }
      } else if (autoGenerate) {
        handleDaGenerate();
      }
    } catch (err) {
      if (autoGenerate) {
        handleDaGenerate();
      }
    } finally {
      setDaLoading(false);
    }
  };

  const generateMlColumns = (items: PlanRow[]) => {
    if (items.length === 0) {
      setMlColumns([]);
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
      
      const renderCell = (params: GridRenderCellParams) => {
        const row = params.row as PlanRow;
        const originalRow = mlOriginalPlanMap.get(getRowKey(row));
        
        if (originalRow && mlRiskEnabled) {
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
    
    if (mlRiskEnabled) {
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
    
    setMlColumns(cols);
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
      
      const renderCell = (params: GridRenderCellParams) => {
        const row = params.row as PlanRow;
        const originalRow = row._originalValues;
        
        if (originalRow && daRiskEnabled) {
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
    
    if (daRiskEnabled) {
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
    
    setDaColumns(cols);
  };

  useEffect(() => {
    if (currentMlPlan.length > 0) {
      generateMlColumns(currentMlPlan);
    }
  }, [mlRiskEnabled]);

  useEffect(() => {
    if (currentDaPlan.length > 0) {
      generateDaColumns(currentDaPlan);
    }
  }, [daRiskEnabled]);

  const handleMlGenerate = async () => {
    if (!sessionId) {
      setError('No active session. Please start a session first.');
      return;
    }
    
    setMlRiskEnabled(false);
    setError('');
    
    try {
      const response = await api.generateMultiLevelPlan({ session_id: sessionId, apply_risk: false });
      await runMlGenerate(() => Promise.resolve({ job_id: response.job_id }));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate plan');
    }
  };

  const handleDaGenerate = async () => {
    if (!sessionId) {
      setError('No active session. Please start a session first.');
      return;
    }
    
    setDaRiskEnabled(false);
    setError('');
    
    try {
      const response = await api.generateDynamicAveragingPlan({ session_id: sessionId, apply_risk: false });
      await runDaGenerate(() => Promise.resolve({ job_id: response.job_id }));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate DA plan');
    }
  };

  const handleMlToggleRisk = async () => {
    if (!sessionId) return;
    
    if (!mlRiskEnabled) {
      setMlRiskJobRunning(true);
      setError('');
      
      try {
        const planToApply = mlPlan.length > 0 ? mlPlan : mlOriginalPlanRows;
        
        const response = await api.applyRisk(sessionId, planToApply);
        
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
          try {
            const data = await api.getRiskPlanLatest(sessionId);
            if (data.plan && data.plan.length > 0) {
              const planMap = new Map<string, PlanRow>();
              mlOriginalPlanRows.forEach(p => planMap.set(getRowKey(p), p));
              
              const adjustedWithMeta: PlanRow[] = data.plan.map(row => {
                const orig = planMap.get(getRowKey(row));
                return {
                  ...row,
                  _originalValues: orig || row,
                  _changes: [],
                };
              });
              
              setMlPlan(adjustedWithMeta);
              setMlRiskEnabled(true);
              
              if (data.skipped) {
                const skippedItems = (data.skipped || []).map((s: unknown) => 
                  typeof s === 'object' 
                    ? s as {symbol?: string; Symbol?: string; skip_reason?: string; reason?: string}
                    : { symbol: String(s), skip_reason: '' }
                );
                setMlSkipped(skippedItems);
              }
            }
          } catch (err) {
            setError('Failed to fetch adjusted plan');
          }
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to apply risk');
      } finally {
        setMlRiskJobRunning(false);
      }
    } else {
      setMlRiskEnabled(false);
      
      const revertedPlan = mlPlan.map(row => {
        const original = row._originalValues || row;
        return {
          ...original,
          risk_adj: 'N/A',
          risk_reasons: '',
          _changes: [],
        };
      });
      setMlPlan(revertedPlan);
    }
  };

  const handleDaToggleRisk = async () => {
    if (!sessionId) return;
    
    if (!daRiskEnabled) {
      setDaRiskJobRunning(true);
      setError('');
      
      try {
        const planToApply = daPlan.length > 0 ? daPlan : daOriginalPlanRows;
        
        const response = await api.applyRisk(sessionId, planToApply);
        
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
          try {
            const data = await api.getRiskPlanLatest(sessionId);
            if (data.plan && data.plan.length > 0) {
              const planMap = new Map<string, PlanRow>();
              daOriginalPlanRows.forEach(p => planMap.set(getRowKey(p), p));
              
              const adjustedWithMeta: PlanRow[] = data.plan.map(row => {
                const orig = planMap.get(getRowKey(row));
                return {
                  ...row,
                  _originalValues: orig || row,
                  _changes: [],
                };
              });
              
              setDaPlan(adjustedWithMeta);
              setDaRiskEnabled(true);
              
              if (data.skipped) {
                const skippedItems = (data.skipped || []).map((s: unknown) => 
                  typeof s === 'object' 
                    ? s as {symbol?: string; Symbol?: string; skip_reason?: string; reason?: string}
                    : { symbol: String(s), skip_reason: '' }
                );
                setDaSkipped(skippedItems);
              }
            }
          } catch (err) {
            setError('Failed to fetch adjusted plan');
          }
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to apply risk');
      } finally {
        setDaRiskJobRunning(false);
      }
    } else {
      setDaRiskEnabled(false);
      
      const revertedPlan = daPlan.map(row => {
        const original = row._originalValues || row;
        return {
          ...original,
          risk_adj: 'N/A',
          risk_reasons: '',
          _changes: [],
        };
      });
      setDaPlan(revertedPlan);
    }
  };

  const handlePurge = async () => {
    if (!sessionId) return;
    
    setPurging(true);
    try {
      await api.purgeEntriesPlans(sessionId);
      setMlHasPlan(false);
      setMlPlan([]);
      setMlOriginalPlan([]);
      setMlSkipped([]);
      setMlRiskEnabled(false);
      setDaHasPlan(false);
      setDaPlan([]);
      setDaOriginalPlan([]);
      setDaSkipped([]);
      setDaRiskEnabled(false);
      setPurgeDialogOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to purge plans');
    } finally {
      setPurging(false);
    }
  };

  const handleMlSelectAll = () => {
    setMlSelectedRows(currentMlPlan.map((_, idx) => idx));
  };

  const handleMlClearSelection = () => {
    setMlSelectedRows([]);
  };

  const handleDaSelectAll = () => {
    const keys = daPlan.map((row) => getRowKey(row));
    setDaSelectedRows(keys as GridRowSelectionModel);
  };

  const handleDaClearSelection = () => {
    setDaSelectedRows([]);
  };

  const handleConfirm = async () => {
    if (!sessionId || mlSelectedRows.length === 0) return;
    
    setConfirming(true);
    setError('');
    
    try {
      const currentPlanMap = new Map(currentMlPlan.map((row) => [getRowKey(row), row]));
      const selectedItems = mlSelectedRows.map(key => currentPlanMap.get(key as string)).filter((item): item is PlanRow => Boolean(item));
      const response = await api.confirmGTT({
        session_id: sessionId,
        plan: selectedItems as unknown as Record<string, unknown>[],
      });
      setConfirmToken(response);
      setConfirmDialogOpen(true);
    } catch (err) {
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
      const currentPlanMap = new Map(currentMlPlan.map((row) => [getRowKey(row), row]));
      const selectedItems = mlSelectedRows.map(key => currentPlanMap.get(key as string)).filter((item): item is PlanRow => Boolean(item));
      const response = await api.applyGTT({
        session_id: sessionId,
        plan: selectedItems as unknown as Record<string, unknown>[],
        confirmation_token: confirmToken.token,
      });
      startJob(response.job_id);
      setOrderSuccess(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to place orders');
    } finally {
      setPlacingOrders(false);
    }
  };

  const handleCloseConfirm = () => {
    setConfirmDialogOpen(false);
    setConfirmToken(null);
    if (orderSuccess) {
      setMlSelectedRows([]);
      setOrderSuccess(false);
    }
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

  const filteredMlPlan = useMemo(() => {
    if (!mlSearchText) return currentMlPlan;
    const search = mlSearchText.toLowerCase();
    return currentMlPlan.filter(row => 
      Object.values(row).some(val => 
        String(val).toLowerCase().includes(search)
      )
    );
  }, [currentMlPlan, mlSearchText]);

  const filteredDaPlan = useMemo(() => {
    if (!daSearchText) return currentDaPlan;
    const search = daSearchText.toLowerCase();
    return daPlan.filter(row => 
      Object.values(row).some(val => 
        String(val).toLowerCase().includes(search)
      )
    );
  }, [daPlan, daSearchText]);

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
        <Tab label="Multi Level Plan" />
        <Tab label="Dynamic Averaging Plan" />
      </Tabs>

      <TabPanel value={tabValue} index={0}>
        <Paper sx={{ p: 2, mb: 2 }}>
          <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
            <Button
              variant="contained"
              startIcon={isMlGenerating || mlRiskJobRunning ? <CircularProgress size={20} color="inherit" /> : <GenerateIcon />}
              onClick={handleMlGenerate}
              disabled={isMlGenerating || mlRiskJobRunning}
            >
              {isMlGenerating ? 'Generating...' : mlRiskJobRunning ? 'Applying Risk...' : mlHasPlan ? 'Refresh' : 'Generate Candidates'}
            </Button>

            <Button
              variant="outlined"
              color="error"
              startIcon={<PurgeIcon />}
              onClick={() => setPurgeDialogOpen(true)}
              disabled={!mlHasPlan && !daHasPlan}
            >
              Clear Plans
            </Button>

            <TextField
              size="small"
              placeholder="Search symbol..."
              value={mlSearchText}
              onChange={(e) => setMlSearchText(e.target.value)}
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
              label={`${mlSelectedRows.length} selected`} 
              color={mlSelectedRows.length > 0 ? 'primary' : 'default'}
            />

            <Box sx={{ flexGrow: 1 }} />

            <FormControlLabel
              control={
                <Switch
                  checked={mlRiskEnabled}
                  onChange={handleMlToggleRisk}
                  disabled={mlRiskJobRunning || mlPlan.length === 0}
                />
              }
              label={mlRiskJobRunning ? 'Applying Risk...' : 'Apply Risk Adjustments'}
            />

            <Button
              variant="contained"
              color="success"
              startIcon={<BuyIcon />}
              onClick={handleConfirm}
              disabled={mlSelectedRows.length === 0 || confirming}
            >
              {confirming ? 'Confirming...' : `Place ${mlSelectedRows.length} Orders`}
            </Button>
          </Box>

          {isMlGenerating && (
            <Box sx={{ mt: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
              <Chip 
                label={mlJobStatus || 'processing'} 
                color={mlJobStatus === 'completed' ? 'success' : mlJobStatus === 'failed' ? 'error' : 'info'}
                size="small"
              />
              <Typography variant="body2" color="text.secondary">
                Generating... {(mlJobProgress * 100).toFixed(0)}% complete
              </Typography>
            </Box>
          )}

          {mlRiskEnabled && (
            <Alert severity="info" sx={{ mt: 2 }}>
              Showing risk-adjusted values. Prices/amounts may be modified based on risk analysis.
            </Alert>
          )}

          {mlSkipped.length > 0 && (
            <Alert severity="warning" sx={{ mt: 2 }} icon={<WarningIcon />}
              action={
                <Button color="inherit" size="small" onClick={() => setMlSkippedModalOpen(true)}>
                  View details
                </Button>
              }
            >
              {mlSkipped.length} items skipped
            </Alert>
          )}
        </Paper>

        {mlLoading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
            <CircularProgress />
          </Box>
        ) : currentMlPlan.length === 0 ? (
          <Paper sx={{ p: 4, textAlign: 'center' }}>
            <Typography variant="body1" color="text.secondary">
              {isMlGenerating ? 'Generating plan...' : 'No entry plan. Click "Generate Candidates" to create a multi-level entry plan.'}
            </Typography>
          </Paper>
        ) : (
          <Paper sx={{ height: 500, width: '100%' }}>
            <DataGrid
              rows={filteredMlPlan}
              columns={mlColumns}
              initialState={{ pagination: { paginationModel: { pageSize: 25 } } }}
              pageSizeOptions={[10, 25, 50]}
              checkboxSelection
              disableRowSelectionOnClick
              rowSelectionModel={mlSelectedRows}
              onRowSelectionModelChange={setMlSelectedRows}
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
              startIcon={isDaGenerating || daRiskJobRunning ? <CircularProgress size={20} color="inherit" /> : <GenerateIcon />}
              onClick={handleDaGenerate}
              disabled={isDaGenerating || daRiskJobRunning}
            >
              {isDaGenerating ? 'Generating...' : daRiskJobRunning ? 'Applying Risk...' : daHasPlan ? 'Refresh' : 'Generate Candidates'}
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

            <FormControlLabel
              control={
                <Switch
                  checked={daRiskEnabled}
                  onChange={handleDaToggleRisk}
                  disabled={daRiskJobRunning || daPlan.length === 0}
                />
              }
              label={daRiskJobRunning ? 'Applying Risk...' : 'Apply Risk Adjustments'}
            />

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

          {isDaGenerating && (
            <Box sx={{ mt: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
              <Chip 
                label={daJobStatus || 'processing'} 
                color={daJobStatus === 'completed' ? 'success' : daJobStatus === 'failed' ? 'error' : 'info'}
                size="small"
              />
              <Typography variant="body2" color="text.secondary">
                Generating... {(daJobProgress * 100).toFixed(0)}% complete
              </Typography>
            </Box>
          )}

          {daRiskEnabled && (
            <Alert severity="info" sx={{ mt: 2 }}>
              Showing risk-adjusted values. Prices/amounts may be modified based on risk analysis.
            </Alert>
          )}

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

        {daLoading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
            <CircularProgress />
          </Box>
        ) : filteredDaPlan.length === 0 ? (
          <Paper sx={{ p: 4, textAlign: 'center' }}>
            <Typography variant="body1" color="text.secondary">
              {isDaGenerating ? 'Generating plan...' : 'No averaging plan. Click "Generate Candidates" to create a dynamic averaging plan.'}
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

      {/* Multi-Level Confirm Dialog */}
      <Dialog open={confirmDialogOpen} onClose={handleCloseConfirm} maxWidth="sm" fullWidth>
        <DialogTitle>Confirm Order Placement</DialogTitle>
        <DialogContent>
          {orderSuccess ? (
            <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2, py: 2 }}>
              <Alert severity="success">Orders placed successfully!</Alert>
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
                You are about to place <strong>{mlSelectedRows.length}</strong> orders{mlRiskEnabled ? ' (risk-adjusted)' : ''}:
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
                    {mlSelectedRows.slice(0, 10).map((key) => {
                      const currentPlanMap = new Map(currentMlPlan.map((row) => [getRowKey(row), row]));
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
                    {mlSelectedRows.length > 10 && (
                      <TableRow>
                        <TableCell colSpan={3}>...and {mlSelectedRows.length - 10} more</TableCell>
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
            <Button onClick={handleCloseConfirm} variant="contained" autoFocus>Done</Button>
          ) : (
            <>
              <Button onClick={handleCloseConfirm} disabled={placingOrders}>Cancel</Button>
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
        <DialogTitle>Confirm Dynamic Averaging Order Placement</DialogTitle>
        <DialogContent>
          {daOrderSuccess ? (
            <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2, py: 2 }}>
              <Alert severity="success">Orders placed successfully!</Alert>
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
            <Button onClick={handleDaCloseConfirm} variant="contained" autoFocus>Done</Button>
          ) : (
            <>
              <Button onClick={handleDaCloseConfirm} disabled={daPlacingOrders}>Cancel</Button>
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

      {/* Purge Dialog */}
      <Dialog open={purgeDialogOpen} onClose={() => setPurgeDialogOpen(false)} maxWidth="xs" fullWidth>
        <DialogTitle>Clear Plans</DialogTitle>
        <DialogContent>
          <Typography variant="body1">
            Are you sure you want to clear all entry plans? This will remove both Multi-Level and Dynamic Averaging plans.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPurgeDialogOpen(false)} disabled={purging}>Cancel</Button>
          <Button onClick={handlePurge} variant="contained" color="error" disabled={purging}>
            {purging ? 'Clearing...' : 'Clear All Plans'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Skipped Items Dialog for Multi-Level */}
      <SkippedItemsDialog
        open={mlSkippedModalOpen}
        onClose={() => setMlSkippedModalOpen(false)}
        title="Skipped Items - Multi Level Plan"
        items={mlSkipped}
      />

      {/* Skipped Items Dialog for Dynamic Averaging */}
      <SkippedItemsDialog
        open={daSkippedModalOpen}
        onClose={() => setDaSkippedModalOpen(false)}
        title="Skipped Items - Dynamic Averaging Plan"
        items={daSkipped}
      />
    </Box>
  );
}
