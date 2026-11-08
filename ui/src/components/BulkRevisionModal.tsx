import React, { useState, useEffect, useMemo } from 'react';
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
  FormControlLabel,
  Radio,
  RadioGroup,
  CircularProgress,
  Alert,
  Chip,
  TextField,
  Accordion,
  AccordionSummary,
  AccordionDetails,
} from '@mui/material';
import { ExpandMore as ExpandMoreIcon } from '@mui/icons-material';
import { api } from '../api/client';
import { BulkSuggestRevisionItem, BulkApplyRevisionResponse, EntryStrategySummary } from '../types';

interface BulkRevisionModalProps {
  open: boolean;
  onClose: () => void;
  selectedSymbols: string[];
  strategies: EntryStrategySummary[];
  onApply: () => void;
}

interface SymbolRevisionState {
  symbol: string;
  thesis_break_price: number | null;
  revision_reason: string | null;
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
  strategies,
  onApply,
}: BulkRevisionModalProps) {
  const [loading, setLoading] = useState(false);
  const [applying, setApplying] = useState(false);
  const [style, setStyle] = useState<'conservative' | 'balanced' | 'aggressive'>('balanced');
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [advancedOverrides, setAdvancedOverrides] = useState({
    atrPeriod: 14,
    emaFast: 20,
    emaSlow: 50,
    lookback: 60,
    atrMultiplier: 1.0,
  });
  const [suggestions, setSuggestions] = useState<BulkSuggestRevisionItem[]>([]);
  const [revisionState, setRevisionState] = useState<SymbolRevisionState[]>([]);
  const [error, setError] = useState('');
  const [applyResult, setApplyResult] = useState<BulkApplyRevisionResponse | null>(null);
  const [includeHoldings, setIncludeHoldings] = useState(false);

  const holdingSymbols = useMemo(() => {
    const holdingSet = new Set(
      strategies.filter((s) => s.is_holding).map((s) => s.symbol)
    );
    return holdingSet;
  }, [strategies]);

  const effectiveSymbols = useMemo(() => {
    if (includeHoldings) return selectedSymbols;
    return selectedSymbols.filter((sym) => !holdingSymbols.has(sym));
  }, [selectedSymbols, holdingSymbols, includeHoldings]);

  const filteredCount = selectedSymbols.length - effectiveSymbols.length;

  useEffect(() => {
    if (open && effectiveSymbols.length > 0) {
      fetchSuggestions();
    } else if (open) {
      setSuggestions([]);
      setRevisionState([]);
    }
  }, [open, effectiveSymbols, style]);

  const fetchSuggestions = async () => {
    setLoading(true);
    setError('');
    setApplyResult(null);
    try {
      const response = await api.suggestRevisionBulk(
        effectiveSymbols,
        style,
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
        return {
          symbol: item.symbol,
          thesis_break_price: item.thesis_break_price ?? null,
          revision_reason: item.revision_reason ?? null,
          levels,
          anyAccepted,
        };
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
          thesis_break_price: item.thesis_break_price,
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
          <Typography variant="h6">Revise Entries - Bulk Review</Typography>
          <Chip label={`${effectiveSymbols.length} symbols`} size="small" color="primary" />
          {filteredCount > 0 && (
            <Chip label={`${filteredCount} holding(s) excluded`} size="small" color="warning" variant="outlined" />
          )}
        </Box>
      </DialogTitle>
      <DialogContent>
        <Box sx={{ mb: 3, display: 'flex', flexDirection: 'column', gap: 2 }}>
          <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
            <Box>
              <Typography variant="subtitle2" sx={{ mb: 0.5 }}>Revision Style</Typography>
              <RadioGroup
                row
                value={style}
                onChange={(e) => setStyle(e.target.value as 'conservative' | 'balanced' | 'aggressive')}
              >
                <FormControlLabel value="conservative" control={<Radio size="small" />} label="Conservative" />
                <FormControlLabel value="balanced" control={<Radio size="small" />} label="Balanced" />
                <FormControlLabel value="aggressive" control={<Radio size="small" />} label="Aggressive" />
              </RadioGroup>
            </Box>
            <FormControlLabel
              control={
                <Checkbox
                  checked={includeHoldings}
                  onChange={(e) => setIncludeHoldings(e.target.checked)}
                  size="small"
                />
              }
              label="Include holding stocks"
            />
            <Button variant="outlined" onClick={handleRefreshSuggestions} disabled={loading}>
              Refresh Suggestions
            </Button>
          </Box>

          <Accordion expanded={advancedOpen} onChange={() => setAdvancedOpen(!advancedOpen)}>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography variant="subtitle2">Advanced Settings</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                <TextField
                  type="number"
                  label="ATR Period"
                  value={advancedOverrides.atrPeriod}
                  onChange={(e) => setAdvancedOverrides({ ...advancedOverrides, atrPeriod: Number(e.target.value) })}
                  size="small"
                  sx={{ width: 120 }}
                  inputProps={{ min: 5, max: 50 }}
                />
                <TextField
                  type="number"
                  label="EMA Fast"
                  value={advancedOverrides.emaFast}
                  onChange={(e) => setAdvancedOverrides({ ...advancedOverrides, emaFast: Number(e.target.value) })}
                  size="small"
                  sx={{ width: 120 }}
                  inputProps={{ min: 5, max: 50 }}
                />
                <TextField
                  type="number"
                  label="EMA Slow"
                  value={advancedOverrides.emaSlow}
                  onChange={(e) => setAdvancedOverrides({ ...advancedOverrides, emaSlow: Number(e.target.value) })}
                  size="small"
                  sx={{ width: 120 }}
                  inputProps={{ min: 20, max: 200 }}
                />
                <TextField
                  type="number"
                  label="Lookback Days"
                  value={advancedOverrides.lookback}
                  onChange={(e) => setAdvancedOverrides({ ...advancedOverrides, lookback: Number(e.target.value) })}
                  size="small"
                  sx={{ width: 140 }}
                  inputProps={{ min: 20, max: 200 }}
                />
                <TextField
                  type="number"
                  label="ATR Spacing Multiplier"
                  value={advancedOverrides.atrMultiplier}
                  onChange={(e) => setAdvancedOverrides({ ...advancedOverrides, atrMultiplier: Number(e.target.value) })}
                  size="small"
                  sx={{ width: 180 }}
                  inputProps={{ min: 0.1, max: 5.0, step: 0.05 }}
                />
              </Box>
            </AccordionDetails>
          </Accordion>
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
                        {item.thesis_break_price != null && (
                          <Typography variant="caption" display="block" color="text.secondary" sx={{ ml: 4 }}>
                            Break: ₹{item.thesis_break_price.toFixed(2)}
                          </Typography>
                        )}
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
                        <Typography variant="body2" color="text.secondary" sx={{ whiteSpace: 'pre-wrap' }}>
                          {item.revision_reason || e1?.rationale || e2?.rationale || e3?.rationale || '-'}
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
