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
  InputAdornment,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
} from '@mui/material';
import { DataGrid, GridColDef, GridRowSelectionModel } from '@mui/x-data-grid';
import { 
  Refresh as RefreshIcon,
  Search as SearchIcon,
  Delete as DeleteIcon,
  Tune as NormalizeIcon,
} from '@mui/icons-material';
import { api } from '../api/client';
import { useSession } from '../context/SessionContext';

interface GTTOrder {
  id?: string | number;
  'GTT ID': string;
  Symbol: string;
  Exchange: string;
  'Trigger Price': number;
  LTP: number;
  'Variance (%)': number;
  Qty: number;
  'Buy Amount': number;
}

const WARNING_TEXT = 'DELETE';

export default function GTTPage() {
  const { sessionId } = useSession();
  
  const [orders, setOrders] = useState<GTTOrder[]>([]);
  const [columns, setColumns] = useState<GridColDef[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');
  
  // Filters
  const [searchText, setSearchText] = useState('');
  const [varianceThreshold, setVarianceThreshold] = useState<number | ''>('');
  const [varianceFilterType, setVarianceFilterType] = useState<'gt' | 'lt'>('gt');
  const [selectedRows, setSelectedRows] = useState<GridRowSelectionModel>([]);
  
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
      
      generateColumns(ordersWithId, allDuplicates);
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

  const generateColumns = (ordersData: GTTOrder[], duplicates: Set<string>) => {
    if (ordersData.length === 0) {
      setColumns([]);
      return;
    }
    
    const cols: GridColDef[] = [
      { 
        field: 'GTT ID', 
        headerName: 'GTT ID', 
        width: 100,
        type: 'string',
      },
      { 
        field: 'Symbol', 
        headerName: 'Symbol', 
        width: 120,
        flex: 1,
        type: 'string',
        renderCell: (params) => {
          const isDuplicate = duplicates.has(params.value as string);
          return (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              {isDuplicate && (
                <Chip label="DUP" size="small" color="warning" sx={{ height: 18, fontSize: '0.65rem' }} />
              )}
              <span style={{ color: isDuplicate ? '#ed6c02' : 'inherit' }}>
                {params.value as string}
              </span>
            </Box>
          );
        },
      },
      { 
        field: 'Trigger Price', 
        headerName: 'Trigger', 
        width: 100,
        type: 'number',
      },
      { 
        field: 'LTP', 
        headerName: 'CMP', 
        width: 100,
        type: 'number',
      },
      { 
        field: 'Variance (%)', 
        headerName: 'Variance %', 
        width: 100,
        type: 'number',
        renderCell: (params) => {
          const val = params.value as number;
          const color = val > 0 ? 'success.main' : val < 0 ? 'error.main' : 'text.secondary';
          return (
            <Box sx={{ color, fontWeight: 'bold' }}>
              {val}%
            </Box>
          );
        },
      },
      { 
        field: 'Qty', 
        headerName: 'Qty', 
        width: 80,
        type: 'number',
      },
      { 
        field: 'Buy Amount', 
        headerName: 'Amount', 
        width: 120,
        type: 'number',
      },
    ];
    setColumns(cols);
  };

  // Filtered orders
  const filteredOrders = useMemo(() => {
    let result = orders;
    
    // Search filter
    if (searchText) {
      const search = searchText.toLowerCase();
      result = result.filter(o => 
        o.Symbol?.toLowerCase().includes(search)
      );
    }
    
    // Variance filter
    if (varianceThreshold !== '') {
      if (varianceFilterType === 'gt') {
        result = result.filter(o => 
          (o['Variance (%)'] || 0) > varianceThreshold
        );
      } else {
        result = result.filter(o => 
          (o['Variance (%)'] || 0) < varianceThreshold
        );
      }
    }
    
    // Buy only is already enforced by the backend (analyze_gtt_buy_orders)
    // but we keep the checkbox for UI clarity
    
    return result;
  }, [orders, searchText, varianceThreshold, varianceFilterType]);

  // Total amount and duplicates
  const totalAmount = useMemo(() => {
    return filteredOrders.reduce((sum, o) => sum + (o['Buy Amount'] || 0), 0);
  }, [filteredOrders]);

  const duplicateSymbols = useMemo(() => {
    const symbolCount: Record<string, number> = {};
    filteredOrders.forEach(o => {
      symbolCount[o.Symbol] = (symbolCount[o.Symbol] || 0) + 1;
    });
    return new Set(Object.keys(symbolCount).filter(s => symbolCount[s] > 1));
  }, [filteredOrders]);

  const handleRefresh = () => {
    fetchOrders();
  };

  const handleDeleteClick = () => {
    if (selectedRows.length === 0) return;
    setDeleteDialogOpen(true);
    setDeleteConfirmText('');
  };

  const handleDeleteConfirm = async () => {
    if (deleteConfirmText !== WARNING_TEXT || !sessionId) return;
    
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

  const handleNormalizeClick = () => {
    if (selectedRows.length === 0) return;
    setNormalizeDialogOpen(true);
    setNormalizeConfirmText('');
    setNormalizeResult(null);
  };

  const handleNormalizeConfirm = async () => {
    if (normalizeConfirmText !== 'ADJUST' || !sessionId) return;
    
    setNormalizing(true);
    setError('');
    
    try {
      // selectedRows contains row IDs, not indices
      const selectedOrders = orders.filter(o => o.id !== undefined && selectedRows.includes(o.id));
      const orderIds = selectedOrders.map(o => String(o['GTT ID'] || o.Symbol));
      
      const result = await api.adjustGTTOrders(sessionId, orderIds, targetVariance);
      
      setNormalizeResult(result);
      setSuccessMsg(`Normalized variance: ${result.adjusted.length} adjusted, ${result.failed.length} failed`);
      
      // Refresh after a short delay to show results
      setTimeout(() => {
        fetchOrders();
      }, 1500);
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
      <Box>
        <Typography variant="h4" gutterBottom>
          Buy Orders
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
        Buy Orders
      </Typography>

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

      {/* Toolbar */}
      <Paper sx={{ p: 2, mb: 2, overflowX: 'auto' }}>
        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'nowrap', minWidth: 'max-content' }}>
          <Button
            variant="contained"
            startIcon={loading ? <CircularProgress size={20} color="inherit" /> : <RefreshIcon />}
            onClick={handleRefresh}
            disabled={loading}
          >
            Refresh
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
            sx={{ width: 200 }}
          />

          <TextField
            size="small"
            type="number"
            placeholder="Variance %"
            value={varianceThreshold}
            onChange={(e) => setVarianceThreshold(e.target.value === '' ? '' : Number(e.target.value))}
            sx={{ width: 120 }}
          />

          <Button
            size="small"
            variant={varianceFilterType === 'gt' ? 'contained' : 'outlined'}
            onClick={() => setVarianceFilterType('gt')}
            sx={{ minWidth: 40 }}
          >
            &gt;=
          </Button>
          <Button
            size="small"
            variant={varianceFilterType === 'lt' ? 'contained' : 'outlined'}
            onClick={() => setVarianceFilterType('lt')}
            sx={{ minWidth: 40 }}
          >
            &lt;
          </Button>

          <Box sx={{ flexGrow: 1 }} />

          <Chip 
            label={`${selectedRows.length} selected`} 
            color={selectedRows.length > 0 ? 'primary' : 'default'}
          />

          <Button
            variant="contained"
            color="error"
            startIcon={<DeleteIcon />}
            onClick={handleDeleteClick}
            disabled={selectedRows.length === 0}
          >
            Delete Selected
          </Button>

          <Button
            variant="contained"
            color="info"
            startIcon={<NormalizeIcon />}
            onClick={handleNormalizeClick}
            disabled={selectedRows.length === 0}
          >
            Normalize Variance
          </Button>
        </Box>
      </Paper>

      {/* Orders Table */}
      <Paper sx={{ p: 2, height: 600 }}>
        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
            <CircularProgress />
          </Box>
        ) : error ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 4, flexDirection: 'column', alignItems: 'center', gap: 2 }}>
            <Typography color="error">
              {error}
            </Typography>
            <Button variant="outlined" onClick={handleRefresh}>
              Retry
            </Button>
          </Box>
        ) : filteredOrders.length === 0 ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
            <Typography color="text.secondary">
              {orders.length === 0 ? 'No GTT orders found' : 'No orders match filters'}
            </Typography>
          </Box>
        ) : (
          <DataGrid
            rows={filteredOrders}
            columns={columns}
            initialState={{ pagination: { paginationModel: { pageSize: 25 } } }}
            pageSizeOptions={[10, 25, 50]}
            checkboxSelection
            disableRowSelectionOnClick={false}
            rowSelectionModel={selectedRows}
            onRowSelectionModelChange={setSelectedRows}
            getRowId={(row) => row.id}
          />
        )}
      </Paper>

      {/* Status Bar */}
      <Paper sx={{ p: 1, mt: 2 }}>
        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
          <Chip label={`Total: ${orders.length}`} size="small" />
          <Chip label={`Filtered: ${filteredOrders.length}`} size="small" color="primary" />
          <Chip label={`Selected: ${selectedRows.length}`} size="small" color="secondary" />
        </Box>
      </Paper>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onClose={() => setDeleteDialogOpen(false)} maxWidth="sm" fullWidth>
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
                  <TableCell>Trigger</TableCell>
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
                      <TableCell>{order['Trigger Price']}</TableCell>
                      <TableCell>{order.LTP}</TableCell>
                    </TableRow>
                  );
                })}
                {selectedRows.length > 10 && (
                  <TableRow>
                    <TableCell colSpan={4}>...and {selectedRows.length - 10} more</TableCell>
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
      </Dialog>

      {/* Normalize Variance Dialog */}
      <Dialog open={normalizeDialogOpen} onClose={handleCloseNormalizeDialog} maxWidth="sm" fullWidth>
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
                      <TableCell>Current Trigger</TableCell>
                      <TableCell>CMP</TableCell>
                      <TableCell>Current Var %</TableCell>
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
                          <TableCell>{order['Trigger Price']}</TableCell>
                          <TableCell>{order.LTP}</TableCell>
                          <TableCell>{order['Variance (%)']}%</TableCell>
                        </TableRow>
                      );
                    })}
                    {selectedRows.length > 10 && (
                      <TableRow>
                        <TableCell colSpan={5}>...and {selectedRows.length - 10} more</TableCell>
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
      </Dialog>
    </Box>
  );
}
