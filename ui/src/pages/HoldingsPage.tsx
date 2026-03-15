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
} from '@mui/material';
import { DataGrid, GridColDef } from '@mui/x-data-grid';
import { 
  PlayArrow as AnalyzeIcon, 
  Search as SearchIcon,
} from '@mui/icons-material';
import { api } from '../api/client';
import { useSession } from '../context/SessionContext';
import { useJobRunner } from '../hooks/useJobRunner';

export default function HoldingsPage() {
  const { sessionId } = useSession();
  
  const [holdings, setHoldings] = useState<Record<string, unknown>[]>([]);
  const [columns, setColumns] = useState<GridColDef[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [searchText, setSearchText] = useState('');
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

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
      console.log('Fetch holdings error:', err);
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

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

  // Fetch holdings when session changes
  useEffect(() => {
    if (sessionId) {
      fetchHoldings();
    }
  }, [sessionId, fetchHoldings]);

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
      setError(err instanceof Error ? err.message : 'Failed to start analysis');
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

      {/* Controls */}
      <Paper sx={{ p: 2, mb: 2 }}>
        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
          {/* Analyze Button */}
          <Button
            variant="contained"
            startIcon={isAnalyzing ? <CircularProgress size={20} color="inherit" /> : <AnalyzeIcon />}
            onClick={handleAnalyze}
            disabled={isAnalyzing}
          >
            {isAnalyzing ? 'Analyzing...' : holdings.length > 0 ? 'Refresh' : 'Analyze'}
          </Button>
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
