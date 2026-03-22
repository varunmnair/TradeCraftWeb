import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Typography,
  Paper,
  Alert,
  CircularProgress,
  Button,
  Chip,
  LinearProgress,
} from '@mui/material';
import { DataGrid, GridColDef, GridSortModel } from '@mui/x-data-grid';
import { 
  Refresh as RefreshIcon,
  CloudSync as SyncIcon,
  Upload as UploadIcon,
  Delete as DeleteIcon,
} from '@mui/icons-material';
import { api } from '../api/client';
import { useSession } from '../context/SessionContext';
import type { HoldingsRow, OrderHistoryStatus } from '../types';

const HOLDINGS_COLUMNS: GridColDef[] = [
  { field: 'symbol', headerName: 'Symbol', width: 120, sortable: true },
  { field: 'exchange', headerName: 'Exchange', width: 80, sortable: true },
  { field: 'quantity', headerName: 'Qty', type: 'number', width: 80, sortable: true },
  { field: 'average_price', headerName: 'Avg Price', type: 'number', width: 100, sortable: true },
  { field: 'last_price', headerName: 'CMP', type: 'number', width: 100, sortable: true },
  { field: 'invested', headerName: 'Invested', type: 'number', width: 110, sortable: true },
  { field: 'pnl', headerName: 'P&L', type: 'number', width: 100, sortable: true },
  { field: 'pnl_pct', headerName: 'P&L %', type: 'number', width: 80, sortable: true },
  { field: 'avg_buy_price', headerName: 'Avg Buy', type: 'number', width: 100, sortable: true },
  { field: 'total_buy_qty', headerName: 'Buy Qty', type: 'number', width: 90, sortable: true },
  { field: 'buy_value', headerName: 'Buy Value', type: 'number', width: 110, sortable: true },
  { field: 'avg_sell_price', headerName: 'Avg Sell', type: 'number', width: 100, sortable: true },
  { field: 'total_sell_qty', headerName: 'Sell Qty', type: 'number', width: 90, sortable: true },
  { field: 'sell_value', headerName: 'Sell Value', type: 'number', width: 110, sortable: true },
  { field: 'net_value', headerName: 'Net Value', type: 'number', width: 110, sortable: true },
  { field: 'first_buy_date', headerName: 'First Buy', width: 110, sortable: true },
  { field: 'last_buy_date', headerName: 'Last Buy', width: 110, sortable: true },
  { field: 'trend', headerName: 'Trend', width: 80, sortable: true },
  { field: 'trend_days', headerName: 'Trend Days', type: 'number', width: 100, sortable: true },
  { field: 'trend_roi', headerName: 'Trend ROI', type: 'number', width: 100, sortable: true },
];

export default function HoldingsPage() {
  const { sessionId, sessionInfo } = useSession();
  
  const [holdings, setHoldings] = useState<HoldingsRow[]>([]);
  const [columns, setColumns] = useState<GridColDef[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [orderHistory, setOrderHistory] = useState<OrderHistoryStatus | null>(null);
  const [fetchingOrderHistory, setFetchingOrderHistory] = useState(false);
  const [uploadingOrderHistory, setUploadingOrderHistory] = useState(false);
  const [sortModel, setSortModel] = useState<GridSortModel>([
    { field: 'symbol', sort: 'asc' },
  ]);

  const fetchHoldings = useCallback(async () => {
    if (!sessionId || loading) return;
    setLoading(true);
    try {
      const data = await api.getHoldings(sessionId);
      const itemsWithId = data.holdings.map((item, index) => ({
        id: item.symbol || index,
        ...item,
      }));
      setHoldings(itemsWithId);
      setOrderHistory(data.order_history);
      setLastUpdated(new Date());
      setError('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch holdings');
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    if (sessionId) {
      fetchHoldings();
    }
  }, [sessionId, fetchHoldings]);

  const handleRefresh = () => {
    fetchHoldings();
  };

  const handleFetchOrderHistory = async () => {
    if (!sessionId) return;
    setFetchingOrderHistory(true);
    setError('');
    try {
      const result = await api.fetchOrderHistory(sessionId, 400);
      setOrderHistory(result);
      fetchHoldings();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch order history');
    } finally {
      setFetchingOrderHistory(false);
    }
  };

  const handleUploadOrderHistory = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file || !sessionId) return;

    setUploadingOrderHistory(true);
    setError('');
    try {
      const result = await api.uploadOrderHistory(sessionId, file);
      setOrderHistory(result);
      fetchHoldings();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to upload order history');
    } finally {
      setUploadingOrderHistory(false);
    }
    event.target.value = '';
  };

  const handleClearOrderHistory = async () => {
    if (!sessionId) return;
    try {
      await api.clearOrderHistory(sessionId);
      setOrderHistory({
        available: false,
        trade_count: 0,
        symbol_count: 0,
        fetched_at: null,
        source: null,
      });
      fetchHoldings();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to clear order history');
    }
  };

  const formatNumber = (value: number | null, decimals: number = 2) => {
    if (value === null || value === undefined) return '-';
    return value.toFixed(decimals);
  };

  const formatCurrency = (value: number | null) => {
    if (value === null || value === undefined) return '-';
    return `₹${value.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  };

  const broker = sessionInfo?.broker || 'upstox';
  const isUpstox = broker === 'upstox';

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
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          {lastUpdated && (
            <Typography variant="body2" color="text.secondary">
              Last updated: {lastUpdated.toLocaleTimeString()}
            </Typography>
          )}
          <Button
            variant="outlined"
            startIcon={loading ? <CircularProgress size={20} /> : <RefreshIcon />}
            onClick={handleRefresh}
            disabled={loading}
          >
            Refresh
          </Button>
        </Box>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}

      {/* Order History Section - Only show when order history is available or being fetched */}
      {orderHistory?.available && (
        <Paper sx={{ p: 2, mb: 2 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 2 }}>
            <Box>
              <Typography variant="h6" gutterBottom>
                Order History
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                {orderHistory.trade_count} trades for {orderHistory.symbol_count} symbols
                {orderHistory.fetched_at && (
                  <span> (fetched {new Date(orderHistory.fetched_at).toLocaleString()})</span>
                )}
                {orderHistory.source && (
                  <Chip 
                    label={orderHistory.source === 'upstox_api' ? 'Upstox API' : 'Zerodha CSV'} 
                    size="small" 
                    sx={{ ml: 1 }} 
                  />
                )}
              </Typography>
            </Box>
            
            <Box sx={{ display: 'flex', gap: 1 }}>
              <Button
                variant="outlined"
                color="error"
                startIcon={<DeleteIcon />}
                onClick={handleClearOrderHistory}
              >
                Clear
              </Button>
            </Box>
          </Box>
        </Paper>
      )}

      {/* Fetch Order History - Show when order history is not available */}
      {!orderHistory?.available && (
        <Paper sx={{ p: 2, mb: 2 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 2 }}>
            <Box>
              <Typography variant="h6" gutterBottom>
                Order History
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Load order history to see buy/sell details in holdings table.
              </Typography>
            </Box>
            
            <Box sx={{ display: 'flex', gap: 1 }}>
              {isUpstox ? (
                <Button
                  variant="contained"
                  color="primary"
                  startIcon={fetchingOrderHistory ? <CircularProgress size={20} color="inherit" /> : <SyncIcon />}
                  onClick={handleFetchOrderHistory}
                  disabled={fetchingOrderHistory}
                >
                  {fetchingOrderHistory ? 'Fetching...' : 'Fetch Order History'}
                </Button>
              ) : (
                <Button
                  variant="contained"
                  component="label"
                  startIcon={uploadingOrderHistory ? <CircularProgress size={20} color="inherit" /> : <UploadIcon />}
                  disabled={uploadingOrderHistory}
                >
                  {uploadingOrderHistory ? 'Uploading...' : 'Fetch Order History'}
                  <input
                    type="file"
                    accept=".csv"
                    hidden
                    onChange={handleUploadOrderHistory}
                  />
                </Button>
              )}
            </Box>
          </Box>
          
          {fetchingOrderHistory && (
            <LinearProgress sx={{ mt: 2 }} />
          )}
        </Paper>
      )}

      {/* Holdings Table */}
      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
          <CircularProgress />
        </Box>
      ) : holdings.length === 0 ? (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <Typography variant="body1" color="text.secondary">
            No holdings data. Click "Refresh" to fetch holdings from your broker.
          </Typography>
        </Paper>
      ) : (
        <Paper sx={{ height: 600, width: '100%' }}>
          <DataGrid
            rows={holdings}
            columns={columns.length > 0 ? columns : HOLDINGS_COLUMNS}
            sortModel={sortModel}
            onSortModelChange={setSortModel}
            initialState={{
              pagination: {
                paginationModel: { pageSize: 25 },
              },
            }}
            pageSizeOptions={[10, 25, 50, 100]}
            disableRowSelectionOnClick
            density="comfortable"
            slots={{
              noRowsOverlay: () => (
                <Box sx={{ p: 2, textAlign: 'center' }}>
                  <Typography color="text.secondary">No holdings to display</Typography>
                </Box>
              ),
            }}
          />
        </Paper>
      )}
    </Box>
  );
}
