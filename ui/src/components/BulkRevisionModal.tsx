import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Box,
  Typography,
  Checkbox,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  CircularProgress,
  Alert,
  Chip,
} from '@mui/material';
import { api } from '../api/client';
import { BulkSuggestRevisionItem, BulkApplyRevisionResponse } from '../types';

interface BulkRevisionModalProps {
  open: boolean;
  onClose: () => void;
  selectedSymbols: string[];
  onApply: () => void;
}

interface SymbolRevisionState {
  symbol: string;
  levels: {
    [levelNo: number]: {
      originalPrice: number;
      suggestedPrice: number;
      rationale: string;
      accepted: boolean;
    };
  };
  anyAccepted: boolean;
}

export function BulkRevisionModal({
  open,
  onClose,
  selectedSymbols,
  onApply,
}: BulkRevisionModalProps) {
  const [loading, setLoading] = useState(false);
  const [applying, setApplying] = useState(false);
  const [method, setMethod] = useState('align_to_cmp');
  const [pctAdjustment, setPctAdjustment] = useState(5);
  const [suggestions, setSuggestions] = useState<BulkSuggestRevisionItem[]>([]);
  const [revisionState, setRevisionState] = useState<SymbolRevisionState[]>([]);
  const [error, setError] = useState('');
  const [applyResult, setApplyResult] = useState<BulkApplyRevisionResponse | null>(null);

  useEffect(() => {
    if (open && selectedSymbols.length > 0) {
      fetchSuggestions();
    }
  }, [open, selectedSymbols]);

  const fetchSuggestions = async () => {
    setLoading(true);
    setError('');
    setApplyResult(null);
    try {
      const response = await api.suggestRevisionBulk(
        selectedSymbols,
        method,
        pctAdjustment
      );
      setSuggestions(response.suggestions);

      const initialState: SymbolRevisionState[] = response.suggestions.map((item) => {
        const levels: SymbolRevisionState['levels'] = {};
        let anyAccepted = false;
        item.revised_levels.forEach((rev) => {
          levels[rev.level_no] = {
            originalPrice: rev.original_price,
            suggestedPrice: rev.suggested_price,
            rationale: rev.rationale,
            accepted: false,
          };
        });
        return { symbol: item.symbol, levels, anyAccepted };
      });
      setRevisionState(initialState);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch suggestions');
    } finally {
      setLoading(false);
    }
  };

  const handleRefreshSuggestions = async () => {
    await fetchSuggestions();
  };

  const handleToggleSymbol = (symbol: string, checked: boolean) => {
    setRevisionState((prev) =>
      prev.map((item) => {
        if (item.symbol !== symbol) return item;
        const newLevels = { ...item.levels };
        Object.keys(newLevels).forEach((levelNo) => {
          newLevels[Number(levelNo)] = {
            ...newLevels[Number(levelNo)],
            accepted: checked,
          };
        });
        return { ...item, levels: newLevels, anyAccepted: checked };
      })
    );
  };

  const handleToggleLevel = (symbol: string, levelNo: number, checked: boolean) => {
    setRevisionState((prev) =>
      prev.map((item) => {
        if (item.symbol !== symbol) return item;
        const newLevels = { ...item.levels };
        if (newLevels[levelNo]) {
          newLevels[levelNo] = { ...newLevels[levelNo], accepted: checked };
        }
        const anyAccepted = Object.values(newLevels).some((l) => l.accepted);
        return { ...item, levels: newLevels, anyAccepted };
      })
    );
  };

  const handleApply = async () => {
    setApplying(true);
    setError('');
    try {
      const updates = revisionState
        .filter((item) => item.anyAccepted)
        .map((item) => ({
          symbol: item.symbol,
          levels: Object.entries(item.levels)
            .filter(([_, level]) => level.accepted)
            .map(([levelNo, level]) => ({
              level_no: Number(levelNo),
              new_price: level.suggestedPrice,
            })),
        }));

      if (updates.length === 0) {
        setError('Please select at least one level to apply');
        setApplying(false);
        return;
      }

      const result = await api.applyRevisionBulk(updates);
      setApplyResult(result);
      
      if (result.total_failed === 0) {
        onApply();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to apply revisions');
    } finally {
      setApplying(false);
    }
  };

  const handleClose = () => {
    setSuggestions([]);
    setRevisionState([]);
    setError('');
    setApplyResult(null);
    onClose();
  };

  const getCmpPrice = (symbol: string) => {
    const item = suggestions.find((s) => s.symbol === symbol);
    return item?.cmp_price;
  };

  const totalSelected = revisionState.reduce(
    (sum, item) => sum + Object.values(item.levels).filter((l) => l.accepted).length,
    0
  );

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="lg" fullWidth>
      <DialogTitle>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Typography variant="h6">Revise Entry Levels - Bulk Review</Typography>
          <Chip label={`${selectedSymbols.length} symbols selected`} size="small" color="primary" />
        </Box>
      </DialogTitle>
      <DialogContent>
        <Box sx={{ mb: 3, display: 'flex', gap: 2, alignItems: 'center' }}>
          <FormControl size="small" sx={{ minWidth: 200 }}>
            <InputLabel>Method</InputLabel>
            <Select
              value={method}
              label="Method"
              onChange={(e) => setMethod(e.target.value)}
            >
              <MenuItem value="align_to_cmp">Align to CMP</MenuItem>
              <MenuItem value="volatility_band">Volatility Band</MenuItem>
              <MenuItem value="gap_fill">Gap Fill</MenuItem>
              <MenuItem value="fixed_adjustment">Fixed Adjustment</MenuItem>
            </Select>
          </FormControl>
          {(method === 'volatility_band' || method === 'fixed_adjustment') && (
            <FormControl size="small" sx={{ minWidth: 120 }}>
              <InputLabel>Adjustment %</InputLabel>
              <Select
                value={pctAdjustment}
                label="Adjustment %"
                onChange={(e) => setPctAdjustment(e.target.value as number)}
              >
                <MenuItem value={3}>3%</MenuItem>
                <MenuItem value={5}>5%</MenuItem>
                <MenuItem value={10}>10%</MenuItem>
                <MenuItem value={15}>15%</MenuItem>
              </Select>
            </FormControl>
          )}
          <Button variant="outlined" onClick={handleRefreshSuggestions} disabled={loading}>
            Refresh Suggestions
          </Button>
        </Box>

        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
            {error}
          </Alert>
        )}

        {applyResult && (
          <Alert 
            severity={applyResult.total_failed === 0 ? 'success' : 'warning'} 
            sx={{ mb: 2 }}
          >
            Applied: {applyResult.total_updated} symbols updated, {applyResult.total_failed} failed
          </Alert>
        )}

        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
            <CircularProgress />
          </Box>
        ) : revisionState.length === 0 ? (
          <Typography color="text.secondary">No suggestions to display</Typography>
        ) : (
          <TableContainer component={Paper} variant="outlined">
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell sx={{ fontWeight: 'bold', minWidth: 120 }}>
                    <Checkbox
                      checked={revisionState.every((s) => s.anyAccepted)}
                      indeterminate={revisionState.some((s) => s.anyAccepted) && !revisionState.every((s) => s.anyAccepted)}
                      onChange={(e) => {
                        const checked = e.target.checked;
                        setRevisionState((prev) =>
                          prev.map((item) => ({
                            ...item,
                            anyAccepted: checked,
                            levels: Object.fromEntries(
                              Object.entries(item.levels).map(([lno, lvl]) => [
                                lno,
                                { ...lvl, accepted: checked },
                              ])
                            ),
                          }))
                        );
                      }}
                    />
                    Symbol
                  </TableCell>
                  <TableCell sx={{ fontWeight: 'bold' }}>CMP</TableCell>
                  <TableCell sx={{ fontWeight: 'bold' }} align="center" colSpan={3}>
                    Current Levels
                  </TableCell>
                  <TableCell sx={{ fontWeight: 'bold' }} align="center" colSpan={3}>
                    Suggested Levels
                  </TableCell>
                  <TableCell sx={{ fontWeight: 'bold' }}>Reason</TableCell>
                </TableRow>
                <TableRow>
                  <TableCell />
                  <TableCell />
                  <TableCell align="center">E1</TableCell>
                  <TableCell align="center">E2</TableCell>
                  <TableCell align="center">E3</TableCell>
                  <TableCell align="center">E1</TableCell>
                  <TableCell align="center">E2</TableCell>
                  <TableCell align="center">E3</TableCell>
                  <TableCell />
                </TableRow>
              </TableHead>
              <TableBody>
                {revisionState.map((item) => {
                  const cmpPrice = getCmpPrice(item.symbol);
                  const e1 = item.levels[1];
                  const e2 = item.levels[2];
                  const e3 = item.levels[3];
                  
                  return (
                    <TableRow key={item.symbol} hover>
                      <TableCell>
                        <Checkbox
                          checked={item.anyAccepted}
                          onChange={(e) => handleToggleSymbol(item.symbol, e.target.checked)}
                        />
                        {item.symbol}
                      </TableCell>
                      <TableCell>
                        {cmpPrice ? `₹${cmpPrice.toFixed(2)}` : '-'}
                      </TableCell>
                      <TableCell align="center">
                        {e1 ? `₹${e1.originalPrice.toFixed(2)}` : '-'}
                      </TableCell>
                      <TableCell align="center">
                        {e2 ? `₹${e2.originalPrice.toFixed(2)}` : '-'}
                      </TableCell>
                      <TableCell align="center">
                        {e3 ? `₹${e3.originalPrice.toFixed(2)}` : '-'}
                      </TableCell>
                      <TableCell align="center">
                        {e1 ? (
                          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 0.5 }}>
                            <Checkbox
                              size="small"
                              checked={e1.accepted}
                              onChange={(e) => handleToggleLevel(item.symbol, 1, e.target.checked)}
                            />
                            <Typography variant="body2" color={e1.accepted ? 'primary' : 'text.primary'}>
                              ₹{e1.suggestedPrice.toFixed(2)}
                            </Typography>
                          </Box>
                        ) : '-'}
                      </TableCell>
                      <TableCell align="center">
                        {e2 ? (
                          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 0.5 }}>
                            <Checkbox
                              size="small"
                              checked={e2.accepted}
                              onChange={(e) => handleToggleLevel(item.symbol, 2, e.target.checked)}
                            />
                            <Typography variant="body2" color={e2.accepted ? 'primary' : 'text.primary'}>
                              ₹{e2.suggestedPrice.toFixed(2)}
                            </Typography>
                          </Box>
                        ) : '-'}
                      </TableCell>
                      <TableCell align="center">
                        {e3 ? (
                          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 0.5 }}>
                            <Checkbox
                              size="small"
                              checked={e3.accepted}
                              onChange={(e) => handleToggleLevel(item.symbol, 3, e.target.checked)}
                            />
                            <Typography variant="body2" color={e3.accepted ? 'primary' : 'text.primary'}>
                              ₹{e3.suggestedPrice.toFixed(2)}
                            </Typography>
                          </Box>
                        ) : '-'}
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" color="text.secondary">
                          {e1?.rationale || e2?.rationale || e3?.rationale || '-'}
                        </Typography>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </TableContainer>
        )}

        <Box sx={{ mt: 2, display: 'flex', justifyContent: 'flex-end' }}>
          <Typography variant="body2" color="text.secondary">
            {totalSelected} level(s) selected for update
          </Typography>
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose}>Cancel</Button>
        <Button
          variant="contained"
          onClick={handleApply}
          disabled={applying || totalSelected === 0}
          startIcon={applying && <CircularProgress size={20} />}
        >
          {applying ? 'Applying...' : `Apply ${totalSelected} Changes`}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
