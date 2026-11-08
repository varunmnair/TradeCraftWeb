import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Box,
  Typography,
  Paper,
  Alert,
  CircularProgress,
  Button,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TableSortLabel,
  Checkbox,
  IconButton,
  Tooltip,
  Menu,
  MenuItem,
  ListItemIcon,
  ListItemText,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Switch,
  FormControlLabel,
} from '@mui/material';
import {
  CloudUpload as UploadIcon,
  Download as DownloadIcon,
  Refresh as RefreshIcon,
  Delete as DeleteIcon,
  Edit as EditIcon,
  PlayArrow as EvaluateIcon,
  MoreVert as MoreIcon,
  Clear as ClearIcon,
} from '@mui/icons-material';
import { api } from '../api/client';
import { EntryStrategySummary, EvaluateStrategyResponse, CellStatus } from '../types';
import { useSession } from '../context/SessionContext';
import { BulkRevisionModal } from '../components/BulkRevisionModal';
import { InlineEditCell } from '../components/InlineEditCell';

type CellStatusMap = Record<string, CellStatus>;

// Broker symbols can carry suffixes/prefixes (e.g. "BEL-EQ", "M&M#") while
// entry strategy symbols are plain. Normalize both sides before comparing.
const normalizeSymbol = (symbol: string): string =>
  symbol.replace(/-(EQ|BE)$/i, '').replace(/#/g, '').trim().toUpperCase();

export default function EntryStrategiesPage() {
  const { sessionId } = useSession();
  const [strategies, setStrategies] = useState<EntryStrategySummary[]>([]);
  const [holdingsSymbols, setHoldingsSymbols] = useState<Set<string>>(new Set());
  const [cmpData, setCmpData] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(false);
  const [holdingsLoading, setHoldingsLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [fileInputKey, setFileInputKey] = useState(0);
  const [selected, setSelected] = useState<string[]>([]);
  const [deleting, setDeleting] = useState(false);
  const [evaluating, setEvaluating] = useState(false);
  const [revisionModalOpen, setRevisionModalOpen] = useState(false);
  const [sortBy, setSortBy] = useState<{ field: string; direction: 'asc' | 'desc' } | null>(null);
  const [cellStatus, setCellStatus] = useState<CellStatusMap>({});
  const [moreAnchor, setMoreAnchor] = useState<null | HTMLElement>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [includeHoldings, setIncludeHoldings] = useState(false);

  const getDelta = useCallback((symbol: string, entry1: number | null): number | null => {
    const cmp = cmpData[symbol];
    if (cmp == null || entry1 == null || entry1 === 0) return null;
    return ((cmp - entry1) / entry1) * 100;
  }, [cmpData]);

  const filteredStrategies = useMemo(() => {
    if (includeHoldings) return strategies;
    return strategies.filter((s) => !holdingsSymbols.has(normalizeSymbol(s.symbol)));
  }, [strategies, includeHoldings, holdingsSymbols]);

  const sortedStrategies = useMemo(() => {
    const base = filteredStrategies;
    if (!sortBy) return base;
    const sorted = [...base];
    sorted.sort((a, b) => {
      let aVal: number | null = 0;
      let bVal: number | null = 0;
      if (sortBy.field === 'delta') {
        aVal = getDelta(a.symbol, a.entry1);
        bVal = getDelta(b.symbol, b.entry1);
      } else if (sortBy.field === 'updated') {
        aVal = new Date(a.updated_at).getTime();
        bVal = new Date(b.updated_at).getTime();
      }
      const aNum = aVal ?? -999999;
      const bNum = bVal ?? -999999;
      return sortBy.direction === 'asc' ? aNum - bNum : bNum - aNum;
    });
    return sorted;
  }, [filteredStrategies, sortBy, getDelta]);

  const handleSort = (field: string) => {
    setSortBy(prev => {
      if (prev?.field === field) {
        return { field, direction: prev.direction === 'asc' ? 'desc' : 'asc' };
      }
      return { field, direction: 'asc' };
    });
  };

  const fetchCmp = useCallback(async (symbols: string[]) => {
    if (symbols.length === 0) return;
    try {
      const response = await api.getCmp(symbols);
      setCmpData(response.prices);
    } catch {
      // CMP fetch is best-effort
    }
  }, []);

  const fetchHoldings = useCallback(async () => {
    if (!sessionId) {
      setHoldingsSymbols(new Set());
      setHoldingsLoading(false);
      return;
    }
    setHoldingsLoading(true);
    try {
      const holdings = await api.getHoldings(sessionId);
      const symbols = new Set<string>();
      for (const row of holdings.holdings || []) {
        if (row.symbol) {
          symbols.add(normalizeSymbol(row.symbol));
        }
      }
      setHoldingsSymbols(symbols);
    } catch {
      setHoldingsSymbols(new Set());
    } finally {
      setHoldingsLoading(false);
    }
  }, [sessionId]);

  const fetchStrategies = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.listEntryStrategies();
      setStrategies(data.strategies);
      setSelected([]);
      setError('');
      fetchCmp(data.strategies.map((s: EntryStrategySummary) => s.symbol));
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : 'Failed to load strategies';
      setError(errMsg);
      if (errMsg.includes('No active broker connection')) {
        setStrategies([]);
      }
    } finally {
      setLoading(false);
    }
  }, [fetchCmp]);

  useEffect(() => {
    fetchStrategies();
  }, [fetchStrategies]);

  useEffect(() => {
    fetchHoldings();
  }, [fetchHoldings]);

  const handleSelectAll = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.checked) {
      setSelected(sortedStrategies.map(s => s.symbol));
    } else {
      setSelected([]);
    }
  };

  const handleSelectOne = (symbol: string) => {
    setSelected(prev =>
      prev.includes(symbol)
        ? prev.filter(s => s !== symbol)
        : [...prev, symbol]
    );
  };

  const handleClearSelection = () => setSelected([]);

  const handleDeleteSelected = async () => {
    if (selected.length === 0) return;
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    setDeleteDialogOpen(false);
    setDeleting(true);
    setError('');

    try {
      const result = await api.bulkDeleteEntryStrategies(selected);
      setSuccess(`Deleted ${result.deleted_count} strategy(ies)`);
      if (result.not_found.length > 0) {
        setError(`Not found: ${result.not_found.join(', ')}`);
      }
      setSelected([]);
      fetchStrategies();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete strategies');
    } finally {
      setDeleting(false);
    }
  };

  const handleEvaluateAll = async () => {
    setEvaluating(true);
    setError('');
    setMoreAnchor(null);
    try {
      const results: EvaluateStrategyResponse[] = await api.evaluateAllStrategies();
      setSuccess(`Evaluated ${results.length} strategies`);
      fetchStrategies();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to evaluate strategies');
    } finally {
      setEvaluating(false);
    }
  };

  const handleOpenRevisionModal = () => {
    if (selected.length === 0) return;
    setRevisionModalOpen(true);
  };

  const handleRevisionModalClose = () => {
    setRevisionModalOpen(false);
  };

  const handleRevisionApplied = () => {
    setRevisionModalOpen(false);
    fetchStrategies();
  };

  const handleFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setError('');
    setSuccess('');

    try {
      const result = await api.uploadEntryStrategyCSV(file);
      let msg = `Upload complete: ${result.created_count} created, ${result.updated_count} updated`;
      if (result.errors.length > 0) {
        msg += `. ${result.errors.length} errors`;
      }
      setSuccess(msg);
      fetchStrategies();
      setFileInputKey(prev => prev + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setUploading(false);
      if (event.target) {
        event.target.value = '';
      }
    }
  };

  const handleDownloadTemplate = () => {
    setMoreAnchor(null);
    try {
      const headers = 'Symbol,Allocated,Entry1,Entry2,Entry3\n';
      const sampleRows =
        'BEL,30000,386.5,375,369\n';
      const blob = new Blob([headers + sampleRows], { type: 'text/csv' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'entry_strategy_template.csv';
      a.click();
      window.URL.revokeObjectURL(url);
    } catch {
      setError('Failed to download template');
    }
  };

  const handleDownloadStrategies = async () => {
    try {
      await api.downloadStrategiesCSV();
      setSuccess('Downloaded entry strategies as CSV');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to download strategies');
    }
  };

  const handleCellSave = useCallback(async (symbol: string, field: string, newValue: number) => {
    const key = `${symbol}:${field}`;
    setCellStatus(prev => ({ ...prev, [key]: 'saving' }));

    try {
      const fields: Record<string, number> = {};
      fields[field] = newValue;
      await api.updateEntryStrategyField(symbol, fields);

      setStrategies(prev => prev.map(s => {
        if (s.symbol !== symbol) return s;
        const updated = { ...s, [field]: newValue };
        // Auto-sort entry prices descending: Entry 1 (highest) > Entry 2 > Entry 3 (lowest)
        const entries = [updated.entry1, updated.entry2, updated.entry3]
          .filter((v): v is number => v != null)
          .sort((a, b) => b - a);
        return {
          ...updated,
          entry1: entries[0] ?? updated.entry1,
          entry2: entries[1] ?? updated.entry2,
          entry3: entries[2] ?? updated.entry3,
        };
      }));
      setCellStatus(prev => ({ ...prev, [key]: 'saved' }));

      setTimeout(() => {
        setCellStatus(prev => {
          const next = { ...prev };
          delete next[key];
          return next;
        });
      }, 2000);
    } catch (err) {
      setCellStatus(prev => ({ ...prev, [key]: 'error' }));
      const msg = err instanceof Error ? err.message : 'Update failed';
      setError(msg);
    }
  }, []);

  const formatCurrency = (v: number) => `₹${v.toLocaleString()}`;
  const formatPrice = (v: number) => `₹${v.toFixed(2)}`;
  const parseNumber = (s: string) => {
    const cleaned = s.replace(/[₹,\s]/g, '');
    const num = parseFloat(cleaned);
    return isNaN(num) ? null : num;
  };

  const isAllSelected = sortedStrategies.length > 0 && selected.length === sortedStrategies.length;
  const isIndeterminate = selected.length > 0 && selected.length < sortedStrategies.length;

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Entry Strategies
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}

      {success && (
        <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccess('')}>
          {success}
        </Alert>
      )}

      <Paper sx={{ p: 2, mb: 2 }}>
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
          <Button
            variant="contained"
            component="label"
            startIcon={uploading ? <CircularProgress size={20} color="inherit" /> : <UploadIcon />}
            disabled={uploading}
          >
            {uploading ? 'Uploading...' : 'Upload CSV'}
            <input
              key={fileInputKey}
              type="file"
              accept=".csv"
              hidden
              onChange={handleFileChange}
              disabled={uploading}
            />
          </Button>

          <Button
            variant="outlined"
            startIcon={<DownloadIcon />}
            onClick={handleDownloadStrategies}
          >
            Download CSV
          </Button>

          <FormControlLabel
            control={
              <Switch
                checked={includeHoldings}
                onChange={(e) => setIncludeHoldings(e.target.checked)}
                color="primary"
              />
            }
            label="Include Holding Symbols"
          />

          {selected.length > 0 && (
            <>
              <Box sx={{ width: 1, height: 0 }} />
              <Chip
                label={`${selected.length} Selected`}
                color="primary"
                variant="outlined"
                sx={{ mr: 1 }}
              />
              <Button
                color="primary"
                variant="contained"
                startIcon={<EditIcon />}
                onClick={handleOpenRevisionModal}
                sx={{ mr: 1 }}
              >
                Revise Entries
              </Button>
              <Button
                color="error"
                variant="outlined"
                startIcon={<DeleteIcon />}
                onClick={handleDeleteSelected}
                disabled={deleting}
              >
                {deleting ? 'Deleting...' : 'Delete'}
              </Button>
              <Button
                startIcon={<ClearIcon />}
                onClick={handleClearSelection}
              >
                Clear
              </Button>
            </>
          )}

          <Box sx={{ flexGrow: 1 }} />

          <Tooltip title="More actions">
            <IconButton onClick={(e) => setMoreAnchor(e.currentTarget)}>
              <MoreIcon />
            </IconButton>
          </Tooltip>

          <Menu
            anchorEl={moreAnchor}
            open={Boolean(moreAnchor)}
            onClose={() => setMoreAnchor(null)}
          >
            <MenuItem onClick={handleEvaluateAll} disabled={evaluating || strategies.length === 0}>
              <ListItemIcon>
                {evaluating ? <CircularProgress size={20} /> : <EvaluateIcon />}
              </ListItemIcon>
              <ListItemText>{evaluating ? 'Evaluating...' : 'Evaluate All'}</ListItemText>
            </MenuItem>
            <MenuItem onClick={handleDownloadTemplate}>
              <ListItemIcon><DownloadIcon /></ListItemIcon>
              <ListItemText>Download Template</ListItemText>
            </MenuItem>
          </Menu>

          <Tooltip title="Refresh strategies">
            <IconButton onClick={() => { fetchStrategies(); fetchHoldings(); }} disabled={loading}>
              {loading ? <CircularProgress size={20} /> : <RefreshIcon />}
            </IconButton>
          </Tooltip>
        </Box>
      </Paper>

      {loading || holdingsLoading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
          <CircularProgress />
        </Box>
      ) : !sessionId ? (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <Typography variant="body1" color="text.secondary">
            No active session. Please start a session to view or manage entry strategies.
          </Typography>
        </Paper>
      ) : strategies.length === 0 ? (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <Typography variant="body1" color="text.secondary">
            No entry strategies found. Upload a CSV file to get started.
          </Typography>
        </Paper>
      ) : filteredStrategies.length === 0 ? (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <Typography variant="body1" color="text.secondary">
            {includeHoldings
              ? 'No entry strategies match the current filter.'
              : 'All entry strategy symbols are currently in holdings. Toggle "Include Holding Symbols" to show them.'}
          </Typography>
        </Paper>
      ) : (
        <Paper>
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell padding="checkbox">
                    <Checkbox
                      indeterminate={isIndeterminate}
                      checked={isAllSelected}
                      onChange={handleSelectAll}
                    />
                  </TableCell>
                  <TableCell>Symbol</TableCell>
                  <TableCell>
                    <TableSortLabel
                      active={sortBy?.field === 'delta'}
                      direction={sortBy?.field === 'delta' ? sortBy.direction : 'asc'}
                      onClick={() => handleSort('delta')}
                    >
                      Delta
                    </TableSortLabel>
                  </TableCell>
                  <TableCell>Allocation</TableCell>
                  <TableCell>Entry 1</TableCell>
                  <TableCell>Entry 2</TableCell>
                  <TableCell>Entry 3</TableCell>
                  <TableCell>Swing</TableCell>
                  <TableCell>Review Status</TableCell>
                  <TableCell>
                    <TableSortLabel
                      active={sortBy?.field === 'updated'}
                      direction={sortBy?.field === 'updated' ? sortBy.direction : 'asc'}
                      onClick={() => handleSort('updated')}
                    >
                      Updated
                    </TableSortLabel>
                  </TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {sortedStrategies.map((strategy) => (
                  <TableRow
                    key={strategy.symbol}
                    hover
                    selected={selected.includes(strategy.symbol)}
                  >
                    <TableCell padding="checkbox">
                      <Checkbox
                        checked={selected.includes(strategy.symbol)}
                        onChange={() => handleSelectOne(strategy.symbol)}
                      />
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" sx={{ fontWeight: 500 }}>
                        {strategy.symbol}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      {(() => {
                        const delta = getDelta(strategy.symbol, strategy.entry1);
                        if (delta == null) return '-';
                        const color = delta > 5 ? 'success.main' : delta >= 0 ? 'warning.main' : 'error.main';
                        return (
                          <Typography variant="body2" sx={{ color, fontWeight: 600 }}>
                            {delta > 0 ? '+' : ''}{delta.toFixed(2)}%
                          </Typography>
                        );
                      })()}
                    </TableCell>
                    <TableCell>
                      <InlineEditCell
                        value={strategy.allocated}
                        format={formatCurrency}
                        parse={parseNumber}
                        onSave={(v) => handleCellSave(strategy.symbol, 'allocated', v)}
                        status={cellStatus[`${strategy.symbol}:allocated`] || 'idle'}
                      />
                    </TableCell>
                    <TableCell>
                      <InlineEditCell
                        value={strategy.entry1}
                        format={formatPrice}
                        parse={parseNumber}
                        onSave={(v) => handleCellSave(strategy.symbol, 'entry1', v)}
                        status={cellStatus[`${strategy.symbol}:entry1`] || 'idle'}
                      />
                    </TableCell>
                    <TableCell>
                      <InlineEditCell
                        value={strategy.entry2}
                        format={formatPrice}
                        parse={parseNumber}
                        onSave={(v) => handleCellSave(strategy.symbol, 'entry2', v)}
                        status={cellStatus[`${strategy.symbol}:entry2`] || 'idle'}
                      />
                    </TableCell>
                    <TableCell>
                      <InlineEditCell
                        value={strategy.entry3}
                        format={formatPrice}
                        parse={parseNumber}
                        onSave={(v) => handleCellSave(strategy.symbol, 'entry3', v)}
                        status={cellStatus[`${strategy.symbol}:entry3`] || 'idle'}
                      />
                    </TableCell>
                    <TableCell>
                      {strategy.swing_eligible == null ? '-' : (
                        <Tooltip
                          title={
                            strategy.swing_reasons?.length
                              ? strategy.swing_reasons.join('\n')
                              : strategy.swing_avg_volume != null
                                ? `Vol: ${strategy.swing_avg_volume.toLocaleString()} | ATR%: ${(strategy.swing_atr_percent ?? 0).toFixed(2)}% | Range%: ${(strategy.swing_range_percent ?? 0).toFixed(2)}%`
                                : "Click 'Evaluate All' for swing analysis details"
                          }
                          arrow
                        >
                          <Chip
                            label={strategy.swing_eligible ? 'Yes' : 'No'}
                            size="small"
                            color={strategy.swing_eligible ? 'success' : 'default'}
                            variant={strategy.swing_eligible ? 'filled' : 'outlined'}
                          />
                        </Tooltip>
                      )}
                    </TableCell>
                    <TableCell>
                      {strategy.review_status ? (
                        <Chip
                          label={strategy.review_status.replace(/_/g, ' ')}
                          size="small"
                          color={
                            strategy.review_status === 'ACTIVE'
                              ? 'success'
                              : strategy.review_status === 'REVIEW_REQUIRED'
                                ? 'warning'
                                : 'error'
                          }
                        />
                      ) : (
                        '-'
                      )}
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" color="text.secondary">
                        {strategy.updated_at
                          ? new Date(strategy.updated_at).toLocaleDateString()
                          : '-'}
                      </Typography>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Paper>
      )}

      {revisionModalOpen && (
        <BulkRevisionModal
          open={revisionModalOpen}
          onClose={handleRevisionModalClose}
          selectedSymbols={selected}
          strategies={strategies}
          onApply={handleRevisionApplied}
        />
      )}

      <Dialog open={deleteDialogOpen} onClose={() => setDeleteDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Delete Entry Strategies</DialogTitle>
        <DialogContent>
          <Alert severity="warning" sx={{ mb: 2 }}>
            You are about to delete <strong>{selected.length}</strong> strategy(ies). Entry levels and allocations will be lost.
          </Alert>
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Symbol</TableCell>
                  <TableCell>Exchange</TableCell>
                  <TableCell>Allocation</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {selected.slice(0, 10).map((symbol) => {
                  const s = strategies.find(st => st.symbol === symbol);
                  if (!s) return null;
                  return (
                    <TableRow key={symbol}>
                      <TableCell>{s.symbol}</TableCell>
                      <TableCell>{s.exchange}</TableCell>
                      <TableCell>₹{(s.allocated ?? 0).toLocaleString()}</TableCell>
                    </TableRow>
                  );
                })}
                {selected.length > 10 && (
                  <TableRow>
                    <TableCell colSpan={3}>...and {selected.length - 10} more</TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </TableContainer>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteDialogOpen(false)} disabled={deleting}>Cancel</Button>
          <Button onClick={handleDeleteConfirm} variant="contained" color="error" disabled={deleting}>
            {deleting ? 'Deleting...' : `Delete ${selected.length} Strategy(ies)`}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
