import { useState, useEffect, useMemo } from 'react';
import {
  Box,
  Typography,
  Paper,
  Alert,
  CircularProgress,
  Button,
  Chip,
  TextField,
  DialogTitle,
  DialogContent,
  DialogActions,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  useMediaQuery,
  useTheme,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
} from '@mui/material';
import {
  Refresh as RefreshIcon,
  Delete as DeleteIcon,
  Tune as NormalizeIcon,
} from '@mui/icons-material';
import { api } from '../api/client';
import { useSession } from '../context/SessionContext';
import { ResponsiveDialog } from '../components/ResponsiveDialog';
import { ResponsivePageHeader } from '../components/ResponsivePageHeader';
import { TradePageLayout } from '../components/TradePageLayout';
import { GTTMobileActionBar } from '../components/gtt/GTTMobileActionBar';
import { MobileGTTOrderCard } from '../components/gtt/MobileGTTOrderCard';
import type { GTTOrder, GttSideFilter, GttStatusFilter } from '../components/gtt/gttDisplay';
import { orderSide, orderStatus } from '../components/gtt/gttDisplay';
import { newPlacementKey } from '../utils/placementIdempotency';
import { TradeDataTable } from '../components/tradeTable/TradeDataTable';
import type { TradeColumnDef } from '../components/tradeTable/types';
import { tradeTableRegistry } from '../config/tradeTableRegistry';
import { uiPageConfigToTradeTableConfig, useUiPageConfig } from '../hooks/useUiPageConfig';

const WARNING_TEXT = 'DELETE';

export default function GTTPage() {
  const { sessionId } = useSession();
  
  const [orders, setOrders] = useState<GTTOrder[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');
  
  // Domain filters (pre-filter before config-driven table)
  const [varianceThreshold, setVarianceThreshold] = useState<number | ''>('');
  const [varianceFilterType, setVarianceFilterType] = useState<'gt' | 'lt'>('gt');
  const [sideFilter, setSideFilter] = useState<GttSideFilter>('all');
  const [statusFilter, setStatusFilter] = useState<GttStatusFilter>('all');
  const [selectedRows, setSelectedRows] = useState<Array<string | number>>([]);

  const { config: uiConfig } = useUiPageConfig('buy_orders');

  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  
  // Delete dialog
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deleteConfirmText, setDeleteConfirmText] = useState('');
  const [deleting, setDeleting] = useState(false);

  // Normalize variance dialog
  const [normalizeDialogOpen, setNormalizeDialogOpen] = useState(false);
  const [normalizeConfirmText, setNormalizeConfirmText] = useState('');
  const [targetVariance, setTargetVariance] = useState<number>(2);
  const [normalizing, setNormalizing] = useState(false);
  const [normalizeResult, setNormalizeResult] = useState<{
    adjusted: Array<{ GTT_ID: string; Symbol: string; old_trigger: number; new_trigger: number; old_variance: number; new_variance: number; status: string; reason?: string }>;
    failed: Array<{ GTT_ID: string; Symbol: string; status: string; reason: string }>;
  } | null>(null);

  // Fetch orders
  const fetchOrders = async () => {
    console.log('GTTPage: fetchOrders called, sessionId:', sessionId);
    if (!sessionId || sessionId.trim() === '') {
      setError('No session ID available - please start a session first');
      return;
    }
    setLoading(true);
    setError('');
    try {
      // Skip session refresh for now - fetch GTT orders directly
      console.log('GTTPage: Fetching GTT orders for session:', sessionId);
      const data = await api.getGTTOrders(sessionId);
      console.log('GTTPage: Got GTT orders:', data);
      const ordersWithId = (data.orders || []).map((item, index) => {
        const order = item as unknown as GTTOrder;
        // Create unique ID: prefer GTT ID, then Symbol+Trigger+index
        const uniqueId = order['GTT ID'] || `${order.Symbol}-${order['Trigger Price']}-${index}`;
        return {
          id: uniqueId,
          ...order
        };
      });
      setOrders(ordersWithId);
      
      // Compute duplicates from all orders
      const symbolCount: Record<string, number> = {};
      ordersWithId.forEach(o => {
        symbolCount[o.Symbol] = (symbolCount[o.Symbol] || 0) + 1;
      });
      const allDuplicates = new Set(Object.keys(symbolCount).filter(s => symbolCount[s] > 1));

    } catch (err) {
      console.error('GTT fetch error:', err);
      setError(err instanceof Error ? err.message : 'Failed to load orders');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (sessionId && sessionId.trim()) {
      fetchOrders();
    }
  }, [sessionId]);

  // Filtered orders
  const filteredOrders = useMemo(() => {
    let result = orders;
    
    if (sideFilter !== 'all') {
      result = result.filter((order) => orderSide(order) === sideFilter);
    }

    if (statusFilter !== 'all') {
      result = result.filter((order) => {
        const status = orderStatus(order);
        return statusFilter === 'active' ? status === 'active' : status !== 'active';
      });
    }
    
    // Variance filter
    if (varianceThreshold !== '') {
      if (varianceFilterType === 'gt') {
        result = result.filter(o => 
          (o['Variance (%)'] ?? 0) > varianceThreshold
        );
      } else {
        result = result.filter(o => 
          (o['Variance (%)'] ?? 0) < varianceThreshold
        );
      }
    }
    
    // Buy only is already enforced by the backend (analyze_gtt_buy_orders)
    // but we keep the checkbox for UI clarity
    
    return result;
  }, [orders, varianceThreshold, varianceFilterType, sideFilter, statusFilter]);

  // Total amount and duplicates
  const totalAmount = useMemo(() => {
    return filteredOrders.reduce((sum, o) => sum + (o['Buy Amount'] ?? 0), 0);
  }, [filteredOrders]);

  const duplicateSymbols = useMemo(() => {
    const symbolCount: Record<string, number> = {};
    filteredOrders.forEach(o => {
      symbolCount[o.Symbol] = (symbolCount[o.Symbol] || 0) + 1;
    });
    return new Set(Object.keys(symbolCount).filter(s => symbolCount[s] > 1));
  }, [filteredOrders]);

  const tableConfig = useMemo(() => {
    const base = tradeTableRegistry.buy_orders.config;
    const runtimeColumns = (base.columns as TradeColumnDef<GTTOrder>[]).map((col) => {
      if (col.id === 'Symbol') {
        return {
          ...col,
          required: true,
          valueGetter: (row: GTTOrder) => row.Symbol,
          renderCell: (row: GTTOrder) => {
            const isDup = duplicateSymbols.has(row.Symbol);
            return (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                {isDup && <Chip label="DUP" size="small" color="warning" sx={{ height: 18, fontSize: '0.65rem' }} />}
                <span style={{ color: isDup ? '#ed6c02' : 'inherit' }}>{row.Symbol}</span>
              </Box>
            );
          },
        };
      }
      if (col.id === 'Trigger Price' || col.id === 'LTP') {
        return {
          ...col,
          valueGetter: (row: GTTOrder) => (row as any)[col.id],
          formatValue: (val: unknown) => (val == null ? 'N/A' : Number(val).toLocaleString()),
        };
      }
      if (col.id === 'Variance (%)') {
        return {
          ...col,
          valueGetter: (row: GTTOrder) => row['Variance (%)'],
          renderCell: (row: GTTOrder) => {
            const val = row['Variance (%)'];
            if (val == null) return <Typography variant="body2" color="text.disabled">N/A</Typography>;
            const bg = val < 0 ? '#ffcdd2' : '#c8e6c9';
            return <Box sx={{ backgroundColor: bg, width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'flex-end', px: 1 }}>{val.toFixed(2)}%</Box>;
          },
        };
      }
      if (col.id === 'Buy Amount') {
        return {
          ...col,
          valueGetter: (row: GTTOrder) => row['Buy Amount'],
          formatValue: (val: unknown) => (val == null ? 'N/A' : Number(val).toLocaleString()),
        };
      }
      if (col.id === 'Status') {
        return {
          ...col,
          valueGetter: (row: GTTOrder) => (row as any)['Order Status'] ?? (row as any).Status ?? '',
          filterOptions: [{ value: 'ACTIVE', label: 'Active' }, { value: 'TRIGGERED', label: 'Triggered' }, { value: 'CANCELLED', label: 'Cancelled' }, { value: 'DELETED', label: 'Deleted' }, { value: 'EXPIRED', label: 'Expired' }],
        };
      }
      if (col.id === 'GTT ID') {
        return { ...col, valueGetter: (row: GTTOrder) => row['GTT ID'] };
      }
      if (col.id === 'Qty') {
        return { ...col, valueGetter: (row: GTTOrder) => row.Qty };
      }
      return col;
    });
    const baseConfig = { ...base, columns: runtimeColumns };
    const effective = uiConfig ? uiPageConfigToTradeTableConfig<any>('buy_orders', uiConfig, baseConfig as any) : (baseConfig as any);
    const mergedColumns = (effective.columns as TradeColumnDef<any>[]).map((col) => {
      const runtime = runtimeColumns.find((c) => c.id === col.id);
      return runtime ? { ...runtime, ...col, renderCell: runtime.renderCell ?? col.renderCell, formatValue: runtime.formatValue ?? col.formatValue, filterOptions: runtime.filterOptions ?? col.filterOptions, valueGetter: runtime.valueGetter ?? col.valueGetter } : col;
    });
    return { ...effective, columns: mergedColumns } as any;
  }, [uiConfig, duplicateSymbols]);

  const handleRefresh = () => {
    fetchOrders();
  };

  const handleDeleteClick = (rowId?: string | number, ids?: Array<string | number>) => {
    const next = ids ?? (rowId !== undefined ? [rowId] : selectedRows);
    if (next.length === 0) return;
    setSelectedRows(next);
    setError('');
    setDeleteDialogOpen(true);
    setDeleteConfirmText('');
  };

  const handleDeleteConfirm = async () => {
    if (deleteConfirmText !== WARNING_TEXT || !sessionId || deleting) return;
    
    setDeleting(true);
    setError('');
    
    try {
      // selectedRows contains row IDs, not indices - find matching orders
      const selectedOrders = orders.filter(o => o.id !== undefined && selectedRows.includes(o.id));
      const orderIds = selectedOrders.map(o => String(o['GTT ID'] || o.Symbol));
      
      const result = await api.deleteGTTOrders(sessionId, orderIds);
      
      setSuccessMsg(`Successfully deleted ${result.count} order(s)`);
      setDeleteDialogOpen(false);
      setSelectedRows([]);
      fetchOrders();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete orders');
    } finally {
      setDeleting(false);
    }
  };

  const handleNormalizeClick = (rowId?: string | number, ids?: Array<string | number>) => {
    const next = ids ?? (rowId !== undefined ? [rowId] : selectedRows);
    if (next.length === 0) return;
    setSelectedRows(next);
    setError('');
    setNormalizeDialogOpen(true);
    setNormalizeConfirmText('');
    setNormalizeResult(null);
  };

  const handleNormalizeConfirm = async () => {
    if (normalizeConfirmText !== 'ADJUST' || !sessionId || normalizing) return;
    
    setNormalizing(true);
    setError('');
    
    try {
      // selectedRows contains row IDs, not indices
      const selectedOrders = orders.filter(o => o.id !== undefined && selectedRows.includes(o.id));
      const orderIds = selectedOrders.map(o => String(o['GTT ID'] || o.Symbol));
      
      const result = await api.adjustGTTOrders(
        sessionId,
        orderIds,
        targetVariance,
        newPlacementKey('gtt-adjust'),
      );
      
      setNormalizeResult(result);
      setSuccessMsg(`Normalized variance: ${result.adjusted.length} adjusted, ${result.failed.length} failed`);
      
      // Refresh after completion so the browser and broker state stay aligned.
      fetchOrders();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to normalize variance');
    } finally {
      setNormalizing(false);
    }
  };

  const handleCloseNormalizeDialog = () => {
    setNormalizeDialogOpen(false);
    setNormalizeConfirmText('');
    setNormalizeResult(null);
  };

  if (!sessionId) {
    return (
      <TradePageLayout header={<ResponsivePageHeader title="Buy Orders" />}>
        <Alert severity="warning">
          No active session. Please start a session from the Sessions page first.
        </Alert>
      </TradePageLayout>
    );
  }

  return (
    <TradePageLayout
      sx={{ pb: isMobile ? '88px' : 0 }}
      header={
        <ResponsivePageHeader
          title="Buy Orders"
          description="Active GTT buy orders for this session"
        />
      }
    >

      {/* Total Amount Display */}
      {orders.length > 0 && (
        <Paper sx={{ p: 2, mb: 2, bgcolor: 'primary.light', color: 'primary.contrastText' }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Typography variant="h6">
              Total Buy Amount Required:
            </Typography>
            <Typography variant="h5" fontWeight="bold">
              ₹{totalAmount.toLocaleString()}
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', gap: 2, mt: 1 }}>
            <Typography variant="body2">
              Total Orders: {filteredOrders.length}
            </Typography>
            {duplicateSymbols.size > 0 && (
              <Typography variant="body2" color="warning.dark">
                Duplicates: {duplicateSymbols.size} symbol(s)
              </Typography>
            )}
          </Box>
        </Paper>
      )}

      {/* Error/Success Messages */}
      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}
      
      {successMsg && (
        <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccessMsg('')}>
          {successMsg}
        </Alert>
      )}

      {/* Orders Table */}
      <TradeDataTable<GTTOrder>
        config={tableConfig}
        rows={filteredOrders}
        getRowId={(row) => (row as any).id ?? `${row['GTT ID']}-${row.Symbol}`}
        loading={loading}
        error={error || null}
        onRetry={handleRefresh}
        emptyTitle={orders.length === 0 ? 'No GTT orders found' : 'No orders match filters'}
        onSelectionChange={setSelectedRows}
        isRowSelectable={(row) => (row.Side ?? 'BUY') === 'BUY'}
        selectionActions={[
          {
            label: 'Delete Selected',
            color: 'error',
            variant: 'contained',
            icon: <DeleteIcon />,
            onClick: (ids) => handleDeleteClick(undefined, ids),
          },
          {
            label: 'Normalize Variance',
            color: 'info',
            variant: 'contained',
            icon: <NormalizeIcon />,
            onClick: (ids) => handleNormalizeClick(undefined, ids),
          },
        ]}
        renderMobileCard={(row, selected, toggleSelect) => (
          <MobileGTTOrderCard
            order={row}
            selected={selected}
            duplicate={duplicateSymbols.has(row.Symbol)}
            onToggleSelect={() => toggleSelect()}
            onDelete={() => handleDeleteClick((row as any).id)}
            onNormalize={() => handleNormalizeClick((row as any).id)}
          />
        )}
        toolbarExtra={
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', alignItems: 'center', mb: 1 }}>
            <FormControl size="small" sx={{ minWidth: 110 }}>
              <InputLabel>Side</InputLabel>
              <Select value={sideFilter} label="Side" onChange={(e) => setSideFilter(e.target.value as GttSideFilter)}>
                <MenuItem value="all">All</MenuItem>
                <MenuItem value="BUY">BUY</MenuItem>
                <MenuItem value="SELL">SELL</MenuItem>
              </Select>
            </FormControl>
            <FormControl size="small" sx={{ minWidth: 120 }}>
              <InputLabel>Status</InputLabel>
              <Select value={statusFilter} label="Status" onChange={(e) => setStatusFilter(e.target.value as GttStatusFilter)}>
                <MenuItem value="all">All</MenuItem>
                <MenuItem value="active">Active</MenuItem>
                <MenuItem value="inactive">Inactive</MenuItem>
              </Select>
            </FormControl>
            <TextField
              size="small"
              type="number"
              placeholder="Variance %"
              value={varianceThreshold}
              onChange={(e) => setVarianceThreshold(e.target.value === '' ? '' : Number(e.target.value))}
              sx={{ width: 120 }}
            />
            <Button size="small" variant={varianceFilterType === 'gt' ? 'contained' : 'outlined'} onClick={() => setVarianceFilterType('gt')} sx={{ minWidth: 40 }}>&gt;</Button>
            <Button size="small" variant={varianceFilterType === 'lt' ? 'contained' : 'outlined'} onClick={() => setVarianceFilterType('lt')} sx={{ minWidth: 40 }}>&lt;</Button>
            <Button variant="outlined" startIcon={<RefreshIcon />} onClick={handleRefresh} disabled={loading} sx={{ ml: 'auto' }}>Refresh</Button>
          </Box>
        }
      />

      {/* Status Bar */}
      <Paper sx={{ p: 1, mt: 2 }}>
        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
          <Chip label={`Total: ${orders.length}`} size="small" />
          <Chip label={`Filtered: ${filteredOrders.length}`} size="small" color="primary" />
          <Chip label={`Selected: ${selectedRows.length}`} size="small" color="secondary" />
        </Box>
      </Paper>

      <GTTMobileActionBar
        count={selectedRows.length}
        disabled={deleting || normalizing}
        onDelete={() => handleDeleteClick()}
        onNormalize={() => handleNormalizeClick()}
        onClear={() => setSelectedRows([])}
      />

      {/* Delete Confirmation Dialog */}
      <ResponsiveDialog open={deleteDialogOpen} onClose={() => setDeleteDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>
          Confirm Delete GTT Orders
        </DialogTitle>
        <DialogContent>
          <Alert severity="warning" sx={{ mb: 2 }}>
            You are about to delete <strong>{selectedRows.length}</strong> GTT order(s). This action cannot be undone.
          </Alert>
          
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>GTT ID</TableCell>
                  <TableCell>Symbol</TableCell>
                  <TableCell>Qty</TableCell>
                  <TableCell>Trigger</TableCell>
                  <TableCell>Order Price</TableCell>
                  <TableCell>CMP</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {selectedRows.slice(0, 10).map((id) => {
                  const order = orders.find(o => o.id === id);
                  if (!order) return null;
                  return (
                    <TableRow key={order['GTT ID'] || order.Symbol || id}>
                      <TableCell>{order['GTT ID'] || '-'}</TableCell>
                      <TableCell>{order.Symbol}</TableCell>
                      <TableCell>{order.Qty}</TableCell>
                      <TableCell>{order['Trigger Price']}</TableCell>
                      <TableCell>{order['Order Price'] ?? order['Trigger Price']}</TableCell>
                      <TableCell>{order.LTP !== null && order.LTP !== undefined ? order.LTP.toFixed(2) : 'N/A'}</TableCell>
                    </TableRow>
                  );
                })}
                {selectedRows.length > 10 && (
                  <TableRow>
                    <TableCell colSpan={6}>...and {selectedRows.length - 10} more</TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </TableContainer>

          <Box sx={{ mt: 2 }}>
            <TextField
              fullWidth
              label={`Type "${WARNING_TEXT}" to confirm`}
              value={deleteConfirmText}
              onChange={(e) => setDeleteConfirmText(e.target.value)}
              helperText="This will permanently delete the selected GTT orders"
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteDialogOpen(false)} disabled={deleting}>
            Cancel
          </Button>
          <Button 
            onClick={handleDeleteConfirm} 
            variant="contained" 
            color="error"
            disabled={deleteConfirmText !== WARNING_TEXT || deleting}
          >
            {deleting ? 'Deleting...' : `Delete ${selectedRows.length} Orders`}
          </Button>
        </DialogActions>
      </ResponsiveDialog>

      {/* Normalize Variance Dialog */}
      <ResponsiveDialog open={normalizeDialogOpen} onClose={handleCloseNormalizeDialog} maxWidth="sm" fullWidth>
        <DialogTitle>
          Normalize Variance for Selected Orders
        </DialogTitle>
        <DialogContent>
          {normalizeResult ? (
            <Box>
              <Alert severity="success" sx={{ mb: 2 }}>
                Variance normalization complete!
              </Alert>
              <Typography variant="subtitle2" gutterBottom>
                Adjusted Orders:
              </Typography>
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Symbol</TableCell>
                      <TableCell>Old Trigger</TableCell>
                      <TableCell>New Trigger</TableCell>
                      <TableCell>Old Var %</TableCell>
                      <TableCell>New Var %</TableCell>
                      <TableCell>Status</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {normalizeResult.adjusted.map((order) => (
                      <TableRow key={order.GTT_ID}>
                        <TableCell>{order.Symbol}</TableCell>
                        <TableCell>{order.old_trigger}</TableCell>
                        <TableCell>{order.new_trigger}</TableCell>
                        <TableCell>{order.old_variance}%</TableCell>
                        <TableCell>{order.new_variance}%</TableCell>
                        <TableCell>
                          {order.status === 'adjusted' ? (
                            <Chip label="Adjusted" size="small" color="success" />
                          ) : (
                            <Chip label="Skipped" size="small" color="default" />
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
              
              {normalizeResult.failed.length > 0 && (
                <>
                  <Typography variant="subtitle2" gutterBottom sx={{ mt: 2 }}>
                    Failed Orders:
                  </Typography>
                  <TableContainer>
                    <Table size="small">
                      <TableHead>
                        <TableRow>
                          <TableCell>Symbol</TableCell>
                          <TableCell>Reason</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {normalizeResult.failed.map((order) => (
                          <TableRow key={order.GTT_ID}>
                            <TableCell>{order.Symbol}</TableCell>
                            <TableCell>{order.reason}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                </>
              )}
            </Box>
          ) : (
            <>
              <Alert severity="info" sx={{ mb: 2 }}>
                Adjust trigger prices for <strong>{selectedRows.length}</strong> selected order(s) to achieve target variance of <strong>{targetVariance}%</strong>.
              </Alert>
              
              <TextField
                fullWidth
                type="number"
                label="Target Variance (%)"
                value={targetVariance}
                onChange={(e) => setTargetVariance(Number(e.target.value))}
                helperText="Enter target variance percentage (e.g., 2 for 2%)"
                sx={{ mb: 2 }}
              />

              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>GTT ID</TableCell>
                      <TableCell>Symbol</TableCell>
                      <TableCell>Qty</TableCell>
                      <TableCell>Current Trigger</TableCell>
                      <TableCell>Order Price</TableCell>
                      <TableCell>CMP</TableCell>
                      <TableCell>Current Var %</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {selectedRows.slice(0, 10).map((id) => {
                      const order = orders.find(o => o.id === id);
                      if (!order) return null;
                      const hasCmp = order.LTP !== null && order.LTP !== undefined;
                      const ltp = order.LTP;
                      const variance = order['Variance (%)'];
                      return (
                        <TableRow key={order['GTT ID'] || order.Symbol || id}>
                          <TableCell>{order['GTT ID'] || '-'}</TableCell>
                          <TableCell>{order.Symbol}</TableCell>
                          <TableCell>{order.Qty}</TableCell>
                          <TableCell>{order['Trigger Price']}</TableCell>
                          <TableCell>{order['Order Price'] ?? order['Trigger Price']}</TableCell>
                          <TableCell>{hasCmp && ltp !== null ? ltp.toFixed(2) : 'N/A'}</TableCell>
                          <TableCell>{variance !== null && variance !== undefined ? `${variance.toFixed(2)}%` : 'N/A'}</TableCell>
                        </TableRow>
                      );
                    })}
                    {selectedRows.length > 10 && (
                      <TableRow>
                        <TableCell colSpan={7}>...and {selectedRows.length - 10} more</TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </TableContainer>

              <Box sx={{ mt: 2 }}>
                <TextField
                  fullWidth
                  label='Type "ADJUST" to confirm'
                  value={normalizeConfirmText}
                  onChange={(e) => setNormalizeConfirmText(e.target.value)}
                  helperText="This will modify the trigger prices for selected orders"
                />
              </Box>
            </>
          )}
        </DialogContent>
        <DialogActions>
          {normalizeResult ? (
            <Button onClick={handleCloseNormalizeDialog} variant="contained" autoFocus>
              Done
            </Button>
          ) : (
            <>
              <Button onClick={handleCloseNormalizeDialog} disabled={normalizing}>
                Cancel
              </Button>
              <Button 
                onClick={handleNormalizeConfirm} 
                variant="contained" 
                color="info"
                disabled={normalizeConfirmText !== 'ADJUST' || normalizing}
              >
                {normalizing ? 'Adjusting...' : `Normalize ${selectedRows.length} Orders`}
              </Button>
            </>
          )}
        </DialogActions>
      </ResponsiveDialog>
    </TradePageLayout>
  );
}
