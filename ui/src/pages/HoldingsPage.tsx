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
  TextField,
  IconButton,
  Tooltip,
  TooltipProps,
} from '@mui/material';
import { DataGrid, GridColDef, GridSortModel, GridRenderCellParams } from '@mui/x-data-grid';
import { 
  Refresh as RefreshIcon,
  CloudSync as SyncIcon,
  Upload as UploadIcon,
  InfoOutlined,
} from '@mui/icons-material';
import { api } from '../api/client';
import { useSession } from '../context/SessionContext';
import type { HoldingsRow, OrderHistoryStatus, AgeReason, Trade } from '../types';

const AGE_REASON_MESSAGES: Record<Exclude<AgeReason, null>, string> = {
  order_history_not_fetched: "Order history not fetched. Click 'Get Order History' to calculate age.",
  no_trades_for_symbol: "No trade history found for this symbol in the fetched period.",
  no_buy_trades: "Only sell trades found. Cannot calculate holding age.",
  buy_trades_beyond_400_days: "Oldest buy trade is beyond 400 days. Age capped at 400 days.",
};

const getHoldingsColumns = (): GridColDef[] => [
  { field: 'symbol', headerName: 'Symbol', width: 120, sortable: true },
  { field: 'exchange', headerName: 'Exchange', width: 80, sortable: true },
  { field: 'quantity', headerName: 'Qty', type: 'number', width: 80, sortable: true },
  { field: 'average_price', headerName: 'Avg Price', type: 'number', width: 100, sortable: true },
  { field: 'last_price', headerName: 'CMP', type: 'number', width: 100, sortable: true },
  { field: 'invested', headerName: 'Invested', type: 'number', width: 110, sortable: true },
  { field: 'profit', headerName: 'Profit', type: 'number', width: 100, sortable: true },
  { field: 'profit_pct', headerName: 'Profit %', type: 'number', width: 90, sortable: true },
  { field: 'quality', headerName: 'Quality', width: 100, sortable: true },
  {
    field: 'age',
    headerName: 'Age',
    type: 'number',
    width: 100,
    sortable: true,
    renderCell: (params: GridRenderCellParams<HoldingsRow>) => {
      const { row } = params;
      if (row.age === null && row.age_reason) {
        return (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, width: '100%' }}>
            <span style={{ color: '#999' }}>-</span>
            <Tooltip title={AGE_REASON_MESSAGES[row.age_reason]} arrow>
              <InfoOutlined sx={{ fontSize: 16, color: '#999', cursor: 'help' }} />
            </Tooltip>
          </Box>
        );
      }
      return params.value ?? '-';
    },
  },
  { field: 'roi_per_day', headerName: 'ROI/Day', type: 'number', width: 100, sortable: true },
  { field: 'profit_per_day', headerName: 'Profit/Day', type: 'number', width: 110, sortable: true },
  { field: 'weighted_roi', headerName: 'W ROI', type: 'number', width: 100, sortable: true },
  { field: 'trend', headerName: 'Trend', width: 100, sortable: true },
];

export default function HoldingsPage() {
  const { sessionId, sessionInfo } = useSession();
  
  const [holdings, setHoldings] = useState<HoldingsRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [orderHistory, setOrderHistory] = useState<OrderHistoryStatus | null>(null);
  const [fetchingOrderHistory, setFetchingOrderHistory] = useState(false);
  const [uploadingOrderHistory, setUploadingOrderHistory] = useState(false);
  const [orderHistoryDays, setOrderHistoryDays] = useState<number>(100);
  const [sortModel, setSortModel] = useState<GridSortModel>([
    { field: 'weighted_roi', sort: 'desc' },
  ]);
  const [symbolSearch, setSymbolSearch] = useState('');
  const [trades, setTrades] = useState<Trade[]>([]);
  const [searchingTrades, setSearchingTrades] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  const handleSearchTrades = useCallback(async () => {
    if (!sessionId || !symbolSearch.trim()) return;
    setSearchingTrades(true);
    setSearchError(null);
    try {
      const result = await api.getTrades(sessionId, symbolSearch.trim());
      setTrades(result.trades || []);
    } catch (err) {
      setTrades([]);
      setSearchError(err instanceof Error ? err.message : 'Failed to search trades');
    } finally {
      setSearchingTrades(false);
    }
  }, [sessionId, symbolSearch]);

  const fetchHoldings = useCallback(async () => {
    if (!sessionId || loading) return;
    setLoading(true);
    try {
      const data = await api.getAnalyzedHoldings(sessionId);
      const itemsWithId = data.results.map((item: any, index: number) => ({
        id: item.symbol || index,
        ...item,
      }));
      setHoldings(itemsWithId);
      setLastUpdated(new Date());
      setError('');
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Failed to fetch holdings';
      if (errorMsg.includes('Session expired') || errorMsg.includes('Session not found')) {
        setError('Session expired. Please restart your session from the Sessions page.');
      } else {
        setError(errorMsg);
      }
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    if (sessionId) {
      fetchHoldings();
      // Also fetch order history status
      api.getOrderHistoryStatus(sessionId).then(setOrderHistory).catch(() => setOrderHistory(null));
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
      const result = await api.fetchOrderHistory(sessionId, orderHistoryDays);
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

  const formatNumber = (value: number | null, decimals: number = 2) => {
    if (value === null || value === undefined) return '-';
    return value.toFixed(decimals);
  };

  const formatCurrency = (value: number | null) => {
    if (value === null || value === undefined) return '-';
    return `₹${value.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  };

  const formatDateRange = (from: string, to: string) => {
    const fromDate = new Date(from);
    const toDate = new Date(to);
    const format = (d: Date) => d.toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
    return `${format(fromDate)} - ${format(toDate)}`;
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
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Typography variant="h4">
            Holdings
          </Typography>
          <Tooltip title="Refresh holdings">
            <IconButton 
              onClick={handleRefresh} 
              disabled={loading}
              size="small"
              sx={{ ml: 1 }}
            >
              {loading ? <CircularProgress size={20} /> : <RefreshIcon />}
            </IconButton>
          </Tooltip>
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          {lastUpdated && (
            <Typography variant="body2" color="text.secondary">
              Last updated: {lastUpdated.toLocaleTimeString()}
            </Typography>
          )}
        </Box>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}

      {/* Consolidated Order History Section */}
      <Paper sx={{ p: 1.5, mb: 2 }}>
        {/* Header row with controls */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
          <Typography variant="body2" color="text.secondary">
            Order History:
            {orderHistory?.available ? (
              <>
                {orderHistory.trade_count} trades • {orderHistory.symbol_count} symbols
                {orderHistory.date_from && orderHistory.date_to && (
                  <> • {formatDateRange(orderHistory.date_from, orderHistory.date_to)}</>
                )}
              </>
            ) : (
              <span>Not fetched</span>
            )}
          </Typography>

          {orderHistory?.source && (
            <Chip
              label={orderHistory.source === 'upstox_api' ? 'Upstox' : 'Zerodha CSV'}
              size="small"
              sx={{ height: 20, fontSize: '0.7rem' }}
            />
          )}

          {orderHistory?.fetched_at && (
            <Typography variant="caption" color="text.secondary">
              fetched {new Date(orderHistory.fetched_at).toLocaleDateString()}
            </Typography>
          )}

          {/* Spacer */}
          <Box sx={{ flex: 1 }} />

          {/* Days input */}
          <TextField
            type="number"
            size="small"
            value={orderHistoryDays}
            onChange={(e) => setOrderHistoryDays(Math.max(1, parseInt(e.target.value) || 100))}
            sx={{ width: 70 }}
            inputProps={{ min: 1, style: { padding: '4px 8px' } }}
          />

          {/* Fetch button */}
          {isUpstox ? (
            <Button
              variant="contained"
              size="small"
              startIcon={fetchingOrderHistory ? <CircularProgress size={16} color="inherit" /> : <SyncIcon />}
              onClick={handleFetchOrderHistory}
              disabled={fetchingOrderHistory}
            >
              {fetchingOrderHistory ? 'Fetching...' : 'Fetch'}
            </Button>
          ) : (
            <Button
              variant="contained"
              component="label"
              size="small"
              startIcon={uploadingOrderHistory ? <CircularProgress size={16} color="inherit" /> : <UploadIcon />}
              disabled={uploadingOrderHistory}
            >
              {uploadingOrderHistory ? 'Uploading...' : 'Upload'}
              <input
                type="file"
                accept=".csv"
                hidden
                onChange={handleUploadOrderHistory}
              />
            </Button>
          )}

          {/* Search */}
          <TextField
            size="small"
            placeholder="Symbol"
            value={symbolSearch}
            onChange={(e) => setSymbolSearch(e.target.value.toUpperCase())}
            onKeyPress={(e) => e.key === 'Enter' && handleSearchTrades()}
            sx={{ width: 120 }}
            inputProps={{ style: { padding: '4px 8px' } }}
          />
          <Button
            variant="outlined"
            size="small"
            onClick={handleSearchTrades}
            disabled={searchingTrades || !symbolSearch.trim()}
          >
            {searchingTrades ? '...' : 'Search'}
          </Button>
        </Box>

        {/* Loading bar */}
        {fetchingOrderHistory && <LinearProgress sx={{ mt: 1 }} />}

        {/* Error message */}
        {searchError && (
          <Alert severity="error" sx={{ mt: 1 }} onClose={() => setSearchError(null)}>
            {searchError}
          </Alert>
        )}

        {/* Search results - expanded section */}
        {(trades.length > 0 || (symbolSearch && trades.length === 0 && !searchingTrades)) && (
          <Box sx={{ mt: 2, pt: 2, borderTop: '1px solid #eee' }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
              <Typography variant="body2" color="text.secondary">
                {trades.length > 0
                  ? `${trades.length} trade${trades.length !== 1 ? 's' : ''} for ${symbolSearch}`
                  : `No trades for ${symbolSearch}${orderHistory?.available ? ' in fetched history' : ''}`
                }
              </Typography>
              <Button
                size="small"
                onClick={() => {
                  setSymbolSearch('');
                  setTrades([]);
                }}
                sx={{ minWidth: 'auto', p: 0.5 }}
              >
                ✕
              </Button>
            </Box>
            {trades.length > 0 && (
              <Box sx={{ maxHeight: 200, overflow: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
                  <thead>
                    <tr style={{ backgroundColor: '#f5f5f5' }}>
                      <th style={{ padding: '6px', textAlign: 'left', borderBottom: '1px solid #ddd' }}>Date</th>
                      <th style={{ padding: '6px', textAlign: 'left', borderBottom: '1px solid #ddd' }}>Side</th>
                      <th style={{ padding: '6px', textAlign: 'right', borderBottom: '1px solid #ddd' }}>Qty</th>
                      <th style={{ padding: '6px', textAlign: 'right', borderBottom: '1px solid #ddd' }}>Price</th>
                      <th style={{ padding: '6px', textAlign: 'right', borderBottom: '1px solid #ddd' }}>Value</th>
                    </tr>
                  </thead>
                  <tbody>
                    {trades.map((trade, index) => (
                      <tr key={index} style={{ borderBottom: '1px solid #eee' }}>
                        <td style={{ padding: '6px' }}>{trade.trade_date || '-'}</td>
                        <td style={{ padding: '6px', color: trade.side === 'BUY' ? 'green' : 'red' }}>
                          {trade.side}
                        </td>
                        <td style={{ padding: '6px', textAlign: 'right' }}>{trade.quantity}</td>
                        <td style={{ padding: '6px', textAlign: 'right' }}>₹{trade.price.toFixed(2)}</td>
                        <td style={{ padding: '6px', textAlign: 'right' }}>₹{(trade.quantity * trade.price).toFixed(2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Box>
            )}
          </Box>
        )}
      </Paper>

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
            columns={getHoldingsColumns()}
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
