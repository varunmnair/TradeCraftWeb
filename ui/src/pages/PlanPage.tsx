import React, { useState, useEffect, useMemo } from 'react';
import {
  Box,
  Typography,
  Paper,
  Alert,
  CircularProgress,
  Button,
  Chip,
  Tabs,
  Tab,
} from '@mui/material';
import { DataGrid, GridColDef, GridRowClassNameParams } from '@mui/x-data-grid';
import { PlayArrow as GenerateIcon, Security as RiskIcon } from '@mui/icons-material';
import { api } from '../api/client';
import { useSession } from '../context/SessionContext';
import { useStartJob } from '../context/JobsContext';
import { PlanLatestResponse } from '../types';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;
  return (
    <div role="tabpanel" hidden={value !== index} {...other}>
      {value === index && <Box sx={{ pt: 2 }}>{children}</Box>}
    </div>
  );
}

const AMOUNT_FIELDS = ['allocated', 'amount', 'spendable', 'original_amount', 'risk_adjusted_amount'];

export default function PlanPage() {
  const { sessionId } = useSession();
  const { jobId, start: startJob, job, isDone, isError } = useStartJob();
  
  const [planData, setPlanData] = useState<PlanLatestResponse | null>(null);
  const [columns, setColumns] = useState<GridColDef[]>([]);
  const [skippedColumns, setSkippedColumns] = useState<GridColDef[]>([]);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [applyingRisk, setApplyingRisk] = useState(false);
  const [error, setError] = useState('');
  const [tabValue, setTabValue] = useState(0);
  
  // Store previous plan for diff highlighting
  const [previousPlan, setPreviousPlan] = useState<Record<string, unknown>[] | null>(null);

  // Fetch plan when sessionId changes
  useEffect(() => {
    if (sessionId) {
      fetchPlan();
    }
  }, [sessionId]);

  // Also fetch when job completes
  useEffect(() => {
    if (isDone && !isError && sessionId) {
      fetchPlan();
    }
  }, [isDone, isError]);

  const fetchPlan = async () => {
    if (!sessionId) {
      return;
    }
    setLoading(true);
    try {
      const data = await api.getPlanLatest(sessionId);
      
      // Store current plan as previous before updating
      if (planData?.plan && data.plan.length > 0) {
        setPreviousPlan(planData.plan);
      }
      
      // Add unique id for each row
      const planWithId = data.plan.map((item, index) => ({
        id: item.symbol || item.Symbol || index,
        ...item
      }));
      setPlanData({ ...data, plan: planWithId });
      generateColumns(data.plan, data.skipped);
      setError('');
    } catch (err) {
      // No plan available is OK - just means nothing generated yet
      const errMsg = err instanceof Error ? err.message : '';
      if (!errMsg.includes('No plan available')) {
        setError(errMsg);
      }
      setPlanData(null);
    } finally {
      setLoading(false);
    }
  };

  const generateColumns = (plan: Record<string, unknown>[], skipped: { symbol?: string; Symbol?: string; skip_reason?: string; reason?: string; [key: string]: unknown }[]) => {
    if (plan.length > 0) {
      const cols = generateGridColumns(plan[0], false);
      setColumns(cols);
    } else {
      setColumns([]);
    }
    
    if (skipped.length > 0) {
      setSkippedColumns([
        { field: 'symbol', headerName: 'Symbol', width: 150 },
        { field: 'reason', headerName: 'Reason', flex: 1 },
      ]);
    } else {
      setSkippedColumns([]);
    }
  };

  const generateGridColumns = (row: Record<string, unknown>, isSkipped: boolean): GridColDef[] => {
    return Object.keys(row).map((key) => {
      const value = row[key];
      let type: 'string' | 'number' | 'boolean' | 'date' = 'string';
      if (typeof value === 'number') type = 'number';
      else if (typeof value === 'boolean') type = 'boolean';
      
      return {
        field: key,
        headerName: key,
        type,
        width: type === 'number' ? 130 : 180,
        flex: type === 'string' && !isSkipped ? 1 : 0,
      };
    });
  };

  // Helper to check if a row field has changed
  const isChanged = (row: Record<string, unknown>, field: string): boolean => {
    if (!previousPlan || previousPlan.length === 0) return false;
    
    const prevRow = previousPlan.find((p) => p.symbol === row.symbol || p.Symbol === row.Symbol);
    if (!prevRow) return false;
    
    const currentVal = row[field];
    const prevVal = prevRow[field];
    
    return currentVal !== prevVal;
  };

  const getRowClassName = (params: GridRowClassNameParams<Record<string, unknown>>): string => {
    const row = params.row;
    if (!previousPlan || previousPlan.length === 0) return '';
    
    // Check if any amount field changed
    for (const field of AMOUNT_FIELDS) {
      if (isChanged(row, field)) {
        return 'risk-adjusted-row';
      }
    }
    return '';
  };

  const handleGeneratePlan = async () => {
    if (!sessionId) {
      setError('No active session. Please start a session first.');
      return;
    }
    
    setGenerating(true);
    setError('');
    
    try {
      const response = await api.generatePlan({
        session_id: sessionId,
        apply_risk: false,
      });
      
      startJob(response.job_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate plan');
      setGenerating(false);
    }
  };

  const handleApplyRisk = async () => {
    if (!sessionId || !planData?.plan || planData.plan.length === 0) {
      setError('No plan loaded. Please generate a plan first.');
      return;
    }
    
    setApplyingRisk(true);
    setError('');
    
    try {
      const response = await api.applyRisk(sessionId, planData.plan);
      startJob(response.job_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to apply risk');
      setApplyingRisk(false);
    }
  };

  if (!sessionId) {
    return (
      <Box>
        <Typography variant="h4" gutterBottom>
          Entry Plan
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
        Entry Plan
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}

      {/* Controls */}
      <Paper sx={{ p: 2, mb: 2 }}>
        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
          <Button
            variant="contained"
            startIcon={generating || (job && !isDone) ? <CircularProgress size={20} color="inherit" /> : <GenerateIcon />}
            onClick={handleGeneratePlan}
            disabled={Boolean(generating || (job && !isDone))}
          >
            {generating ? 'Generating...' : job && !isDone ? 'Generating...' : 'Generate Plan'}
          </Button>
          <Button
            variant="contained"
            color="warning"
            startIcon={applyingRisk ? <CircularProgress size={20} color="inherit" /> : <RiskIcon />}
            onClick={handleApplyRisk}
            disabled={Boolean(applyingRisk || !planData?.plan?.length || (job && !isDone))}
          >
            {applyingRisk ? 'Applying...' : 'Apply Risk'}
          </Button>
          
          {/* Job Status */}
          {job && (
            <Chip 
              label={job.status} 
              color={(job.status === 'completed' || job.status === 'succeeded') ? 'success' : job.status === 'failed' ? 'error' : 'info'}
              size="small"
            />
          )}
        </Box>
        
        {previousPlan && (
          <Alert severity="info" sx={{ mt: 2 }} onClose={() => setPreviousPlan(null)}>
            Risk has been applied. Highlighted rows show changes from the previous plan.
          </Alert>
        )}
      </Paper>

      {/* Results */}
      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
          <CircularProgress />
        </Box>
      ) : !planData ? (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <Typography variant="body1" color="text.secondary">
            No plan generated yet. Click "Generate Plan" to create an entry plan.
          </Typography>
        </Paper>
      ) : (
        <>
          <Tabs value={tabValue} onChange={(_, v) => setTabValue(v)} sx={{ mb: 1 }}>
            <Tab label={`Plan (${planData.plan.length})`} />
            <Tab label={`Skipped (${planData.skipped.length})`} />
          </Tabs>
          
          <TabPanel value={tabValue} index={0}>
            {planData.plan.length === 0 ? (
              <Paper sx={{ p: 4, textAlign: 'center' }}>
                <Typography color="text.secondary">No plan items</Typography>
              </Paper>
            ) : (
              <Paper sx={{ height: 500, width: '100%' }}>
                <style>{`
                  .risk-adjusted-row {
                    background-color: #fff3e0 !important;
                  }
                `}</style>
                <DataGrid
                  rows={planData.plan}
                  columns={columns}
                  initialState={{
                    pagination: { paginationModel: { pageSize: 25 } },
                  }}
                  pageSizeOptions={[10, 25, 50]}
                  getRowClassName={getRowClassName}
                  disableRowSelectionOnClick
                />
              </Paper>
            )}
          </TabPanel>
          
          <TabPanel value={tabValue} index={1}>
            {planData.skipped.length === 0 ? (
              <Paper sx={{ p: 4, textAlign: 'center' }}>
                <Typography color="text.secondary">No skipped items</Typography>
              </Paper>
            ) : (
              <Paper sx={{ height: 300, width: '100%' }}>
                <DataGrid
                  rows={planData.skipped.map((item, idx) => {
                    const itemRecord = item as unknown as Record<string, unknown>;
                    const symbol = String(itemRecord?.symbol || itemRecord?.Symbol || item);
                    const reason = String(itemRecord?.skip_reason || itemRecord?.reason || '');
                    return {
                      id: idx,
                      symbol,
                      reason,
                    };
                  })}
                  columns={skippedColumns}
                  initialState={{
                    pagination: { paginationModel: { pageSize: 10 } },
                  }}
                  pageSizeOptions={[10, 25]}
                  disableRowSelectionOnClick
                />
              </Paper>
            )}
          </TabPanel>
        </>
      )}
    </Box>
  );
}
