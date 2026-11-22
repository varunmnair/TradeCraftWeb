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
  useMediaQuery,
  useTheme,
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
import { useNavigate } from 'react-router-dom';
import { EntryStrategySummary, EvaluateStrategyResponse, CellStatus } from '../types';
import { useSession } from '../context/SessionContext';
import { BulkRevisionModal } from '../components/BulkRevisionModal';
import { InlineEditCell } from '../components/InlineEditCell';
import { ResponsiveToolbar } from '../components/ResponsiveToolbar';
import { ResponsiveDialog } from '../components/ResponsiveDialog';
import { MobileEntryStrategyCard } from '../components/entry-strategies/MobileEntryStrategyCard';
import {
  EntryStrategiesMobileControls,
  INITIAL_ENTRY_STRATEGY_FILTERS,
  type EntryStrategyFilters,
} from '../components/entry-strategies/EntryStrategiesMobileControls';
import { MobileStrategyEditDialog } from '../components/entry-strategies/MobileStrategyEditDialog';
import { MobileVersionHistory } from '../components/entry-strategies/MobileVersionHistory';
import {
  formatAllocation,
  formatDate,
  formatPrice,
  getDeltaColor,
  getReviewStatusColor,
  getReviewStatusLabel,
  parseNumericInput,
  sortEntryValues,
  type StrategyFormValues,
} from '../components/entry-strategies/strategyDisplay';
import type { VersionItem } from '../types';

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
  const [mobileSearch, setMobileSearch] = useState('');
  const [mobileFilters, setMobileFilters] = useState<EntryStrategyFilters>(
    INITIAL_ENTRY_STRATEGY_FILTERS,
  );
  const [editingStrategy, setEditingStrategy] = useState<EntryStrategySummary | null>(null);
  const [editSaving, setEditSaving] = useState(false);
  const [editError, setEditError] = useState('');
  const [historyDialogOpen, setHistoryDialogOpen] = useState(false);
  const [historySymbol, setHistorySymbol] = useState('');
  const [historyVersions, setHistoryVersions] = useState<VersionItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState('');

  const navigate = useNavigate();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

  const getDelta = useCallback((symbol: string, entry1: number | null): number | null => {
    const cmp = cmpData[symbol];
    if (cmp == null || entry1 == null || entry1 === 0) return null;
    return ((cmp - entry1) / entry1) * 100;
  }, [cmpData]);

  const filteredStrategies = useMemo(() => {
    if (includeHoldings) return strategies;
    return strategies.filter((s) => !holdingsSymbols.has(normalizeSymbol(s.symbol)));
  }, [strategies, includeHoldings, holdingsSymbols]);

  const searchedStrategies = useMemo(() => {
    let list = filteredStrategies;
    const query = mobileSearch.trim().toUpperCase();
    if (query) {
      list = list.filter((strategy) => strategy.symbol.toUpperCase().includes(query));
    }
    if (mobileFilters.reviewStatus !== 'ALL') {
      list = list.filter((strategy) =>
        mobileFilters.reviewStatus === 'NONE'
          ? !strategy.review_status
          : strategy.review_status === mobileFilters.reviewStatus,
      );
    }
    if (mobileFilters.swingEligibility !== 'ALL') {
      list = list.filter((strategy) => {
        if (mobileFilters.swingEligibility === 'YES') return strategy.swing_eligible === true;
        if (mobileFilters.swingEligibility === 'NO') return strategy.swing_eligible === false;
        return strategy.swing_eligible == null;
      });
    }
    if (mobileFilters.reviewDue !== 'ALL') {
      list = list.filter((strategy) =>
        mobileFilters.reviewDue === 'YES'
          ? strategy.review_status === 'REVIEW_REQUIRED'
          : strategy.review_status !== 'REVIEW_REQUIRED',
      );
    }
    return list;
  }, [filteredStrategies, mobileSearch, mobileFilters]);

  const sortedStrategies = useMemo(() => {
    const base = searchedStrategies;
    if (!sortBy) return base;
    const sorted = [...base];
    sorted.sort((a, b) => {
      if (sortBy.field === 'symbol') {
        return sortBy.direction === 'asc'
          ? a.symbol.localeCompare(b.symbol)
          : b.symbol.localeCompare(a.symbol);
      }
      let aVal: number | null = 0;
      let bVal: number | null = 0;
      if (sortBy.field === 'delta') {
        aVal = getDelta(a.symbol, a.entry1);
        bVal = getDelta(b.symbol, b.entry1);
      } else if (sortBy.field === 'updated') {
        aVal = new Date(a.updated_at).getTime();
        bVal = new Date(b.updated_at).getTime();
      } else if (sortBy.field === 'allocated') {
        aVal = a.allocated;
        bVal = b.allocated;
      } else if (sortBy.field === 'cmp') {
        aVal = cmpData[a.symbol] ?? null;
        bVal = cmpData[b.symbol] ?? null;
      }
      const aNum = aVal ?? -999999;
      const bNum = bVal ?? -999999;
      return sortBy.direction === 'asc' ? aNum - bNum : bNum - aNum;
    });
    return sorted;
  }, [searchedStrategies, sortBy, getDelta, cmpData]);

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
        return {
          ...updated,
          ...sortEntryValues(updated.entry1, updated.entry2, updated.entry3),
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

  const handleOpenEdit = (strategy: EntryStrategySummary) => {
    setEditingStrategy(strategy);
    setEditError('');
  };

  const handleCloseEdit = () => {
    if (editSaving) return;
    setEditingStrategy(null);
    setEditError('');
  };

  const handleMobileSave = async (values: StrategyFormValues) => {
    if (!editingStrategy) return;
    const symbol = editingStrategy.symbol;
    setEditSaving(true);
    setEditError('');
    try {
      const result = await api.updateEntryStrategyField(symbol, values);
      setStrategies((previous) =>
        previous.map((strategy) =>
          strategy.symbol === symbol
            ? {
                ...strategy,
                allocated: values.allocated ?? strategy.allocated,
                ...sortEntryValues(values.entry1, values.entry2, values.entry3),
                updated_at: result.updated_at,
              }
            : strategy,
        ),
      );
      setSuccess(`Updated ${symbol}`);
      setEditingStrategy(null);
    } catch (err) {
      setEditError(err instanceof Error ? err.message : 'Failed to save strategy');
    } finally {
      setEditSaving(false);
    }
  };

  const handleClearMobileFilters = () => {
    setMobileSearch('');
    setMobileFilters(INITIAL_ENTRY_STRATEGY_FILTERS);
  };

  const handleViewHistory = async (strategy: EntryStrategySummary) => {
    setHistorySymbol(strategy.symbol);
    setHistoryDialogOpen(true);
    setHistoryVersions([]);
    setHistoryError('');
    setHistoryLoading(true);
    try {
      const data = await api.getVersionHistory(strategy.symbol);
      setHistoryVersions(data.versions);
    } catch (err) {
      setHistoryError(err instanceof Error ? err.message : 'Failed to load version history');
    } finally {
      setHistoryLoading(false);
    }
  };

  const handleCloseHistory = () => {
    setHistoryDialogOpen(false);
    setHistorySymbol('');
    setHistoryVersions([]);
    setHistoryError('');
  };

  const handleOpenFullDetailFromHistory = () => {
    const symbol = historySymbol;
    handleCloseHistory();
    navigate(`/entry-strategies/${encodeURIComponent(symbol)}`);
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
        <ResponsiveToolbar sx={{ flexWrap: 'wrap' }}>
          <Box
            sx={{
              display: { xs: 'none', sm: 'flex' },
              gap: 1,
              alignItems: 'center',
              flexWrap: 'wrap',
            }}
          >
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
          </Box>

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
            <Box sx={{ display: { xs: 'none', sm: 'flex' }, gap: 1, alignItems: 'center' }}>
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
            </Box>
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
            {!isMobile && (
              <MenuItem onClick={handleDownloadTemplate}>
                <ListItemIcon><DownloadIcon /></ListItemIcon>
                <ListItemText>Download Template</ListItemText>
              </MenuItem>
            )}
          </Menu>

          <Tooltip title="Refresh strategies">
            <IconButton onClick={() => { fetchStrategies(); fetchHoldings(); }} disabled={loading}>
              {loading ? <CircularProgress size={20} /> : <RefreshIcon />}
            </IconButton>
          </Tooltip>
        </ResponsiveToolbar>
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
      ) : isMobile ? (
        <Box>
          <EntryStrategiesMobileControls
            search={mobileSearch}
            onSearchChange={setMobileSearch}
            sortBy={sortBy}
            onSort={handleSort}
            filters={mobileFilters}
            onFiltersChange={setMobileFilters}
            onClearFilters={handleClearMobileFilters}
          />
          {sortedStrategies.length === 0 ? (
            <Paper sx={{ p: 3, textAlign: 'center' }}>
              <Typography variant="body1" color="text.secondary">
                No strategies match the current search or filters.
              </Typography>
            </Paper>
          ) : (
            sortedStrategies.map((strategy) => (
              <MobileEntryStrategyCard
                key={strategy.symbol}
                strategy={strategy}
                cmp={cmpData[strategy.symbol] ?? null}
                delta={getDelta(strategy.symbol, strategy.entry1)}
                onEdit={handleOpenEdit}
                onOpenDetail={(symbol) =>
                  navigate(`/entry-strategies/${encodeURIComponent(symbol)}`)
                }
                onViewHistory={handleViewHistory}
              />
            ))
          )}
        </Box>
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
                        format={formatAllocation}
                        parse={parseNumericInput}
                        onSave={(v) => handleCellSave(strategy.symbol, 'allocated', v)}
                        status={cellStatus[`${strategy.symbol}:allocated`] || 'idle'}
                      />
                    </TableCell>
                    <TableCell>
                      <InlineEditCell
                        value={strategy.entry1}
                        format={formatPrice}
                        parse={parseNumericInput}
                        onSave={(v) => handleCellSave(strategy.symbol, 'entry1', v)}
                        status={cellStatus[`${strategy.symbol}:entry1`] || 'idle'}
                      />
                    </TableCell>
                    <TableCell>
                      <InlineEditCell
                        value={strategy.entry2}
                        format={formatPrice}
                        parse={parseNumericInput}
                        onSave={(v) => handleCellSave(strategy.symbol, 'entry2', v)}
                        status={cellStatus[`${strategy.symbol}:entry2`] || 'idle'}
                      />
                    </TableCell>
                    <TableCell>
                      <InlineEditCell
                        value={strategy.entry3}
                        format={formatPrice}
                        parse={parseNumericInput}
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

      <MobileStrategyEditDialog
        open={editingStrategy !== null}
        strategy={editingStrategy}
        saving={editSaving}
        errorMessage={editError}
        onClose={handleCloseEdit}
        onSave={handleMobileSave}
      />

      <ResponsiveDialog
        open={historyDialogOpen}
        onClose={handleCloseHistory}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Version History — {historySymbol}</DialogTitle>
        <DialogContent dividers>
          <MobileVersionHistory
            versions={historyVersions}
            currentAllocation={
              strategies.find((strategy) => strategy.symbol === historySymbol)?.allocated ?? null
            }
            loading={historyLoading}
            error={historyError}
            onOpenFullDetail={handleOpenFullDetailFromHistory}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseHistory}>Close</Button>
        </DialogActions>
      </ResponsiveDialog>
    </Box>
  );
}
