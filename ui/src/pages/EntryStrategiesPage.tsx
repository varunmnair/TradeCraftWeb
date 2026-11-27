import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Alert, Box, Button, Checkbox, Chip, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle,
  FormControlLabel, IconButton, ListItemIcon, ListItemText, Menu, MenuItem, Paper, Switch, Table, TableBody,
  TableCell, TableContainer, TableHead, TablePagination, TableRow, TableSortLabel, Tooltip, Typography,
} from '@mui/material';
import {
  Clear as ClearIcon, CloudUpload as UploadIcon, Delete as DeleteIcon, Download as DownloadIcon,
  Edit as EditIcon, MoreVert as MoreIcon, PlayArrow as EvaluateIcon, Refresh as RefreshIcon,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { useSession } from '../context/SessionContext';
import { useBrokerSessionOrchestrator } from '../context/BrokerSessionContext';
import type { EntryStrategySummary, CellStatus } from '../types';
import { BulkRevisionModal } from '../components/BulkRevisionModal';
import { InlineEditCell } from '../components/InlineEditCell';
import { MobileEntryStrategyCard } from '../components/entry-strategies/MobileEntryStrategyCard';
import { MobileStrategyEditDialog } from '../components/entry-strategies/MobileStrategyEditDialog';
import { MobileVersionHistory } from '../components/entry-strategies/MobileVersionHistory';
import { formatAllocation, formatDate, formatPrice, parseNumericInput } from '../components/entry-strategies/strategyDisplay';
import { ResponsiveDialog } from '../components/ResponsiveDialog';
import { ResponsivePageHeader } from '../components/ResponsivePageHeader';
import { TradePageLayout } from '../components/TradePageLayout';
import { TradeStatusAlert } from '../components/TradeStatusAlert';
import { TradeSummaryStrip } from '../components/TradeSummaryStrip';
import { TradeMobileFilterDialog } from '../components/tradeTable/TradeMobileFilterDialog';
import { TradeSelectionToolbar } from '../components/tradeTable/TradeSelectionToolbar';
import { TradeTableToolbar } from '../components/tradeTable/TradeTableToolbar';
import { resolveTradeTableConfig, getFilterableColumns, getVisibleOrderedColumns } from '../components/tradeTable/config';
import { applyTradeFilters, applyTradeSort } from '../components/tradeTable/tableState';
import type { TradeColumnDef, TradeFilterRule, TradeSortState } from '../components/tradeTable/types';
import { tradeTableRegistry } from '../config/tradeTableRegistry';
import { uiPageConfigToTradeTableConfig, useUiPageConfig } from '../hooks/useUiPageConfig';
import { useTheme } from '@mui/material/styles';
import useMediaQuery from '@mui/material/useMediaQuery';

type StrategyRow = EntryStrategySummary & { id: string; cmp: number | null; delta_pct: number | null; [k: string]: unknown };

export default function EntryStrategiesPage() {
  const navigate = useNavigate();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

  const [strategies, setStrategies] = useState<EntryStrategySummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [selected, setSelected] = useState<string[]>([]);
  const [moreAnchor, setMoreAnchor] = useState<null | HTMLElement>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [includeHoldings, setIncludeHoldings] = useState(true);
  const [holdingsSymbols, setHoldingsSymbols] = useState<Set<string>>(new Set());
  const [holdingsLoading, setHoldingsLoading] = useState(false);
  const [revisionModalOpen, setRevisionModalOpen] = useState(false);
  const [evaluating, setEvaluating] = useState(false);
  const [fileInputKey, setFileInputKey] = useState(0);
  const [editingStrategy, setEditingStrategy] = useState<EntryStrategySummary | null>(null);
  const [editSaving, setEditSaving] = useState(false);
  const [editError, setEditError] = useState('');
  const [historyDialogOpen, setHistoryDialogOpen] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState('');
  const [historyVersions, setHistoryVersions] = useState<any[]>([]);
  const [historySymbol, setHistorySymbol] = useState('');
  const [cmpData, setCmpData] = useState<Record<string, number>>({});
  const [cellStatus, setCellStatus] = useState<Record<string, CellStatus>>({});
  const [cellErrors, setCellErrors] = useState<Record<string, string>>({});

  // Table config/state
  const { config: uiConfig } = useUiPageConfig('entry_strategies');
  const [filters, setFilters] = useState<TradeFilterRule[]>([]);
  const [mobileFiltersOpen, setMobileFiltersOpen] = useState(false);
  const [sort, setSort] = useState<TradeSortState | null>(null);
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(25);
  const [columnVisibility, setColumnVisibility] = useState<Record<string, boolean>>({});

  const { sessionId } = useSession();
  const { status: sessionReadiness, message: sessionMessage, retry: retrySession } = useBrokerSessionOrchestrator();
  const sessionReady = sessionReadiness === 'READY';

  const getDelta = useCallback((symbol: string, entry1: number | null): number | null => {
    const cmp = cmpData[symbol];
    if (cmp == null || entry1 == null || entry1 === 0) return null;
    return ((cmp - entry1) / entry1) * 100;
  }, [cmpData]);

  const rows: StrategyRow[] = useMemo(() => strategies.map((s) => ({
    ...s,
    id: s.symbol,
    cmp: cmpData[s.symbol] ?? null,
    delta_pct: getDelta(s.symbol, s.entry1),
  })), [strategies, cmpData, getDelta]);

  const filteredByHoldings = useMemo(() => {
    if (includeHoldings || holdingsSymbols.size === 0) return rows;
    return rows.filter((s) => !holdingsSymbols.has(s.symbol));
  }, [rows, includeHoldings, holdingsSymbols]);

  const tableConfig = useMemo(() => {
    const base = tradeTableRegistry.entry_strategies.config;
    const runtimeColumns = (base.columns as TradeColumnDef<StrategyRow>[]).map((col) => {
      if (col.id === 'symbol') return { ...col, required: true };
      if (col.id === 'review_status') return { ...col, filterOptions: ['ACTIVE', 'REVIEW_REQUIRED', 'PAUSED'].map((v) => ({ value: v, label: v.replace(/_/g, ' ') })) };
      if (col.id === 'swing_eligible') return { ...col, filterOptions: [{ value: 'true', label: 'Yes' }, { value: 'false', label: 'No' }] };
      return col;
    });
    const baseConfig = { ...base, columns: runtimeColumns };
    const effective = uiConfig ? uiPageConfigToTradeTableConfig<StrategyRow>('entry_strategies', uiConfig, baseConfig as any) : (baseConfig as any);
    const mergedColumns = (effective.columns as TradeColumnDef<StrategyRow>[]).map((col) => {
      const runtime = runtimeColumns.find((c) => c.id === col.id);
      return runtime ? { ...runtime, ...col, renderCell: runtime.renderCell ?? col.renderCell, filterOptions: runtime.filterOptions ?? col.filterOptions } : col;
    });
    const resolved = resolveTradeTableConfig<StrategyRow>({ ...effective, columns: mergedColumns } as any);
    return resolved;
  }, [uiConfig]);

  useEffect(() => {
    setColumnVisibility((prev) => {
      const next: Record<string, boolean> = {};
      for (const col of tableConfig.columns) next[col.id] = prev[col.id] ?? col.visible;
      for (const col of tableConfig.columns) if (col.required) next[col.id] = true;
      return next;
    });
    setSort((prev) => prev ?? tableConfig.defaultSort ?? null);
    setPageSize((prev) => (tableConfig.allowedPageSizes.includes(prev) ? prev : tableConfig.defaultPageSize));
  }, [tableConfig]);

  const visibleColumns = useMemo(() => {
    return tableConfig.columns
      .filter((c) => !c.tableHidden)
      .filter((c) => columnVisibility[c.id] !== false)
      .sort((a, b) => a.position - b.position);
  }, [tableConfig.columns, columnVisibility]);
  const filterableColumns = useMemo(() => getFilterableColumns({ ...tableConfig, columns: tableConfig.columns.map((c) => ({ ...c, visible: columnVisibility[c.id] !== false })) } as any), [tableConfig, columnVisibility]);

  const filteredRows = useMemo(() => applyTradeFilters(filteredByHoldings, filters, tableConfig.columns as any), [filteredByHoldings, filters, tableConfig.columns]);
  const sortedRows = useMemo(() => applyTradeSort(filteredRows, sort, tableConfig.columns as any), [filteredRows, sort, tableConfig.columns]);
  const pagedRows = useMemo(() => sortedRows.slice(page * pageSize, page * pageSize + pageSize), [sortedRows, page, pageSize]);

  useEffect(() => { setPage(0); }, [filters, sort, pageSize, includeHoldings]);
  useEffect(() => { setPage((p) => Math.min(p, Math.max(0, Math.ceil(sortedRows.length / pageSize) - 1))); }, [sortedRows.length, pageSize]);

  const fetchStrategies = useCallback(async () => {
    if (!sessionId) return;
    setLoading(true);
    setError('');
    try {
      const data = await api.listEntryStrategies();
      setStrategies(data.strategies || []);
      if (data.strategies?.length) void fetchCmp(data.strategies.map((s: EntryStrategySummary) => s.symbol));
    } catch (err) { setError(err instanceof Error ? err.message : 'Failed to fetch strategies'); }
    finally { setLoading(false); }
  }, [sessionId]);

  const fetchHoldings = useCallback(async () => {
    if (!sessionId) return;
    setHoldingsLoading(true);
    try {
      const data = await api.getHoldings(sessionId);
      setHoldingsSymbols(new Set((data.holdings || []).map((h: any) => h.symbol)));
    } catch (err) { console.error('Failed to fetch holdings:', err); }
    finally { setHoldingsLoading(false); }
  }, [sessionId]);

  const fetchCmp = useCallback(async (symbols: string[]) => {
    if (symbols.length === 0) return;
    try { const response = await api.getCmp(symbols); setCmpData(response.prices); } catch { /* best effort */ }
  }, []);

  useEffect(() => { if (sessionReady) { void fetchStrategies(); void fetchHoldings(); } }, [sessionReady, fetchStrategies, fetchHoldings]);

  const handleSelectAll = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.checked) setSelected(sortedRows.map((s) => s.symbol));
    else setSelected([]);
  };
  const handleSelectOne = (symbol: string) => setSelected((prev) => prev.includes(symbol) ? prev.filter((s) => s !== symbol) : [...prev, symbol]);
  const handleClearSelection = () => setSelected([]);

  const handleDeleteSelected = async () => { if (selected.length > 0) setDeleteDialogOpen(true); };
  const handleDeleteConfirm = async () => {
    setDeleteDialogOpen(false); setDeleting(true); setError('');
    try {
      const result = await api.bulkDeleteEntryStrategies(selected);
      setSuccess(`Deleted ${result.deleted_count} strateg${result.deleted_count === 1 ? 'y' : 'ies'}`);
      if (result.not_found?.length > 0) setError(`Not found: ${result.not_found.join(', ')}`);
      setSelected([]); await fetchStrategies();
    } catch (err) { setError(err instanceof Error ? err.message : 'Failed to delete strategies'); }
    finally { setDeleting(false); }
  };

  const handleDownloadTemplate = async () => {
    try {
      const headers = 'Symbol,Allocated,Entry1,Entry2,Entry3\n';
      const sampleRows = 'BEL,30000,386.5,375,369\n';
      const blob = new Blob([headers + sampleRows], { type: 'text/csv' });
      const url = window.URL.createObjectURL(blob); const a = document.createElement('a');
      a.href = url; a.download = 'entry_strategy_template.csv'; document.body.appendChild(a); a.click();
      window.URL.revokeObjectURL(url); document.body.removeChild(a);
    } catch (err) { setError(err instanceof Error ? err.message : 'Failed to download template'); }
  };

  const handleDownloadStrategies = async () => {
    try {
      await api.downloadStrategiesCSV();
    } catch (err) { setError(err instanceof Error ? err.message : 'Failed to download strategies'); }
  };

  const handleFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]; if (!file) return;
    if (!file.name.endsWith('.csv')) { setError('Please select a CSV file'); return; }
    setUploading(true); setError(''); setSuccess('');
    try {
      const result = await api.uploadEntryStrategyCSV(file);
      const errorCount = result.errors.length;
      let msg = `Upload complete: ${result.created_count} created, ${result.updated_count} updated`;
      if (errorCount > 0) msg += `. ${errorCount} error${errorCount === 1 ? '' : 's'}`;
      setSuccess(msg);
      if (errorCount > 0) setError(`Some rows had errors: ${result.errors.join(', ')}`);
      await fetchStrategies();
    } catch (err) { setError(err instanceof Error ? err.message : 'Upload failed'); }
    finally { setUploading(false); setFileInputKey((k) => k + 1); }
  };

  const handleOpenRevisionModal = () => { if (selected.length > 0) setRevisionModalOpen(true); };
  const handleRevisionModalClose = () => setRevisionModalOpen(false);
  const handleRevisionApplied = async () => {
    setRevisionModalOpen(false);
    setSelected([]);
    await fetchStrategies();
  };

  const handleEvaluateAll = async () => {
    if (strategies.length === 0) return; setEvaluating(true); setError(''); setMoreAnchor(null);
    try {
      const results = await api.evaluateAllStrategies();
      setSuccess(`Evaluated ${results.length} strategies`);
      await fetchStrategies();
    } catch (err) { setError(err instanceof Error ? err.message : 'Failed to evaluate strategies'); }
    finally { setEvaluating(false); }
  };

  const handleCellSave = useCallback(async (symbol: string, field: string, value: number) => {
    const cellKey = `${symbol}:${field}`;
    setCellStatus((prev) => ({ ...prev, [cellKey]: 'saving' }));
    setCellErrors((prev) => ({ ...prev, [cellKey]: '' }));
    try {
      const result = await api.updateEntryStrategyField(symbol, { [field]: value } as any);
      setStrategies((prev) => prev.map((s) => s.symbol === symbol ? { ...s, [field]: value, updated_at: result.updated_at } : s));
      setCellStatus((prev) => ({ ...prev, [cellKey]: 'saved' }));
      setTimeout(() => setCellStatus((prev) => ({ ...prev, [cellKey]: 'idle' })), 2000);
    } catch (err) {
      setCellStatus((prev) => ({ ...prev, [cellKey]: 'error' }));
      setCellErrors((prev) => ({ ...prev, [cellKey]: err instanceof Error ? err.message : 'Save failed' }));
    }
  }, []);

  const handleOpenEdit = (strategy: EntryStrategySummary) => { setEditError(''); setEditingStrategy(strategy); };
  const handleCloseEdit = () => { if (editSaving) return; setEditingStrategy(null); setEditError(''); };
  const handleMobileSave = async (symbol: string, updates: { allocated: number | null; entry1: number | null; entry2: number | null; entry3: number | null; }) => {
    setEditSaving(true); setEditError('');
    try {
      const result = await api.updateEntryStrategyField(symbol, updates as any);
      setStrategies((prev) => prev.map((s) => s.symbol === symbol ? { ...s, ...updates, updated_at: result.updated_at } : s));
      setEditingStrategy(null);
    } catch (err) { setEditError(err instanceof Error ? err.message : 'Failed to update strategy'); }
    finally { setEditSaving(false); }
  };

  const handleViewHistory = async (strategy: EntryStrategySummary) => {
    setHistoryDialogOpen(true); setHistoryLoading(true); setHistoryError(''); setHistoryVersions([]); setHistorySymbol(strategy.symbol);
    try { const data = await api.getVersionHistory(strategy.symbol); setHistoryVersions(data.versions || []); }
    catch (err) { setHistoryError(err instanceof Error ? err.message : 'Failed to load version history'); }
    finally { setHistoryLoading(false); }
  };
  const handleCloseHistory = () => { if (historyLoading) return; setHistoryDialogOpen(false); setHistoryError(''); setHistoryVersions([]); setHistorySymbol(''); };
  const handleOpenFullDetailFromHistory = (symbol: string) => { if (!symbol) return; setHistoryDialogOpen(false); navigate(`/entry-strategies/${encodeURIComponent(symbol)}`); };

  const isAllSelected = sortedRows.length > 0 && selected.length === sortedRows.length;
  const isIndeterminate = selected.length > 0 && selected.length < sortedRows.length;
  const hasActiveFilters = filters.length > 0;

  const summaryItems = useMemo(() => {
    const total = strategies.length;
    const reviewDue = strategies.filter((s) => s.review_status === 'REVIEW_REQUIRED').length;
    const lastUpdated = strategies.reduce<string | null>((acc, s) => (!acc || (s.updated_at && s.updated_at > acc) ? s.updated_at : acc), null);
    return [
      { label: 'Total Strategies', value: total },
      { label: 'Review Due', value: reviewDue, tone: reviewDue > 0 ? 'warning' : 'default' } as const,
      { label: 'Last Updated', value: lastUpdated ? formatDate(lastUpdated) : '-' },
    ];
  }, [strategies]);

  const toggleSort = (field: string) => {
    const col = tableConfig.columns.find((c) => c.id === field);
    if (!col?.sortable) return;
    setSort((prev) => {
      if (!prev || prev.field !== field) return { field, direction: 'asc' };
      if (prev.direction === 'asc') return { field, direction: 'desc' };
      return tableConfig.defaultSort?.field === field ? { field, direction: 'asc' } : null;
    });
  };

  const renderDesktopTable = () => (
    <Paper variant="outlined">
      <TableContainer sx={{ overflowX: 'auto' }}>
        <Table size={tableConfig.density === 'compact' ? 'small' : 'medium'} stickyHeader>
          <TableHead>
            <TableRow>
              {tableConfig.selectionEnabled && (
                <TableCell padding="checkbox">
                  <Checkbox indeterminate={isIndeterminate} checked={isAllSelected} onChange={handleSelectAll} inputProps={{ 'aria-label': 'Select all strategies' }} />
                </TableCell>
              )}
              {visibleColumns.map((col) => (
                <TableCell key={col.id} align={col.alignment === 'right' ? 'right' : 'left'} style={col.width ? { width: col.width } : undefined}>
                  {col.sortable ? (
                    <TableSortLabel active={sort?.field === col.id} direction={sort?.field === col.id ? sort.direction : 'asc'} onClick={() => toggleSort(col.id)}>
                      {col.label}
                    </TableSortLabel>
                  ) : col.label}
                </TableCell>
              ))}
            </TableRow>
          </TableHead>
          <TableBody>
            {pagedRows.map((strategy) => (
              <TableRow key={strategy.symbol} hover selected={selected.includes(strategy.symbol)}>
                {tableConfig.selectionEnabled && (
                  <TableCell padding="checkbox">
                    <Checkbox checked={selected.includes(strategy.symbol)} onChange={() => handleSelectOne(strategy.symbol)} inputProps={{ 'aria-label': `Select ${strategy.symbol}` }} />
                  </TableCell>
                )}
                {visibleColumns.map((col) => {
                  const align = col.alignment === 'right' ? 'right' : 'left';
                  if (col.id === 'symbol') return <TableCell key={col.id} align={align}><Typography variant="body2" sx={{ fontWeight: 500 }}>{strategy.symbol}</Typography></TableCell>;
                  if (col.id === 'cmp') return <TableCell key={col.id} align={align}>{formatPrice(strategy.cmp)}</TableCell>;
                  if (col.id === 'delta_pct') {
                    const delta = strategy.delta_pct;
                    if (delta == null) return <TableCell key={col.id} align={align}>-</TableCell>;
                    const color = delta > 5 ? 'success.main' : delta >= 0 ? 'warning.main' : 'error.main';
                    return <TableCell key={col.id} align={align}><Typography variant="body2" sx={{ color, fontWeight: 600 }}>{delta > 0 ? '+' : ''}{delta.toFixed(2)}%</Typography></TableCell>;
                  }
                  if (col.id === 'allocated') return <TableCell key={col.id} align={align}><InlineEditCell value={strategy.allocated} format={formatAllocation} parse={parseNumericInput} onSave={(v) => handleCellSave(strategy.symbol, 'allocated', v)} status={cellStatus[`${strategy.symbol}:allocated`] || 'idle'} errorMessage={cellErrors[`${strategy.symbol}:allocated`]} /></TableCell>;
                  if (col.id === 'entry1') return <TableCell key={col.id} align={align}><InlineEditCell value={strategy.entry1} format={formatPrice} parse={parseNumericInput} onSave={(v) => handleCellSave(strategy.symbol, 'entry1', v)} status={cellStatus[`${strategy.symbol}:entry1`] || 'idle'} errorMessage={cellErrors[`${strategy.symbol}:entry1`]} /></TableCell>;
                  if (col.id === 'entry2') return <TableCell key={col.id} align={align}><InlineEditCell value={strategy.entry2} format={formatPrice} parse={parseNumericInput} onSave={(v) => handleCellSave(strategy.symbol, 'entry2', v)} status={cellStatus[`${strategy.symbol}:entry2`] || 'idle'} errorMessage={cellErrors[`${strategy.symbol}:entry2`]} /></TableCell>;
                  if (col.id === 'entry3') return <TableCell key={col.id} align={align}><InlineEditCell value={strategy.entry3} format={formatPrice} parse={parseNumericInput} onSave={(v) => handleCellSave(strategy.symbol, 'entry3', v)} status={cellStatus[`${strategy.symbol}:entry3`] || 'idle'} errorMessage={cellErrors[`${strategy.symbol}:entry3`]} /></TableCell>;
                  if (col.id === 'swing_eligible') return <TableCell key={col.id} align={align}>{strategy.swing_eligible == null ? '-' : (<Tooltip title={strategy.swing_reasons?.length ? strategy.swing_reasons.join('\n') : strategy.swing_avg_volume != null ? `Vol: ${strategy.swing_avg_volume.toLocaleString()} | ATR%: ${(strategy.swing_atr_percent ?? 0).toFixed(2)}% | Range%: ${(strategy.swing_range_percent ?? 0).toFixed(2)}%` : "Click 'Evaluate All' for swing analysis details"} arrow><Chip label={strategy.swing_eligible ? 'Yes' : 'No'} size="small" color={strategy.swing_eligible ? 'success' : 'default'} variant={strategy.swing_eligible ? 'filled' : 'outlined'} /></Tooltip>)}</TableCell>;
                  if (col.id === 'review_status') return <TableCell key={col.id} align={align}>{strategy.review_status ? <Chip label={strategy.review_status.replace(/_/g, ' ')} size="small" color={strategy.review_status === 'ACTIVE' ? 'success' : strategy.review_status === 'REVIEW_REQUIRED' ? 'warning' : 'error'} /> : '-'}</TableCell>;
                  if (col.id === 'updated_at') return <TableCell key={col.id} align={align}><Typography variant="body2" color="text.secondary">{strategy.updated_at ? new Date(strategy.updated_at).toLocaleDateString() : '-'}</Typography></TableCell>;
                  return <TableCell key={col.id} align={align}>{String((strategy as any)[col.id] ?? '-')}</TableCell>;
                })}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
      <TablePagination
        component="div"
        count={sortedRows.length}
        page={page}
        onPageChange={(_, p) => setPage(p)}
        rowsPerPage={pageSize}
        onRowsPerPageChange={(e) => { setPageSize(parseInt(e.target.value, 10)); setPage(0); }}
        rowsPerPageOptions={tableConfig.allowedPageSizes}
      />
    </Paper>
  );

  const renderMobile = () => (
    <Box>
      {sortedRows.length === 0 ? (
        <Paper sx={{ p: 3, textAlign: 'center' }}>
          <Typography variant="body1" color="text.secondary">No strategies match the current filters.</Typography>
        </Paper>
      ) : (
        pagedRows.map((strategy) => (
          <MobileEntryStrategyCard
            key={strategy.symbol}
            strategy={strategy}
            cmp={strategy.cmp}
            delta={strategy.delta_pct}
            primaryFields={tableConfig.mobilePrimaryFields}
            detailFields={tableConfig.mobileDetailFields}
            onEdit={handleOpenEdit}
            onOpenDetail={(symbol) => navigate(`/entry-strategies/${encodeURIComponent(symbol)}`)}
            onViewHistory={handleViewHistory}
          />
        ))
      )}
      <TablePagination
        component="div"
        count={sortedRows.length}
        page={page}
        onPageChange={(_, p) => setPage(p)}
        rowsPerPage={pageSize}
        onRowsPerPageChange={(e) => { setPageSize(parseInt(e.target.value, 10)); setPage(0); }}
        rowsPerPageOptions={tableConfig.allowedPageSizes}
      />
    </Box>
  );

  return (
    <TradePageLayout
      header={
        <ResponsivePageHeader
          title="Entry Strategies"
          recordCount={strategies.length}
          primaryAction={<Button variant="contained" startIcon={<EditIcon />} onClick={handleOpenRevisionModal} disabled={selected.length === 0}>Revise Entries</Button>}
          secondaryActions={[
            ...(!isMobile ? [{ label: 'Upload CSV', onClick: () => document.getElementById('es-csv-upload')?.click(), icon: <UploadIcon />, disabled: uploading }] : []),
            { label: 'Download CSV', onClick: () => void handleDownloadStrategies(), icon: <DownloadIcon /> },
            ...(!isMobile ? [{ label: 'Download Template', onClick: () => void handleDownloadTemplate(), icon: <DownloadIcon /> }] : []),
            { label: evaluating ? 'Evaluating...' : 'Evaluate All', onClick: () => void handleEvaluateAll(), icon: <EvaluateIcon />, disabled: evaluating || strategies.length === 0 },
          ]}
        />
      }
      summary={<TradeSummaryStrip ariaLabel="Entry strategies summary" items={summaryItems as any} />}
    >
      <input id="es-csv-upload" key={fileInputKey} type="file" accept=".csv" hidden onChange={handleFileChange} disabled={uploading} />

      {error && <TradeStatusAlert kind="critical" message={error} onClose={() => setError('')} sx={{ mb: 2 }} />}
      {success && <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccess('')}>{success}</Alert>}

      <Paper sx={{ p: 1.5, mb: 2 }}>
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
          <FormControlLabel control={<Switch checked={includeHoldings} onChange={(e) => setIncludeHoldings(e.target.checked)} color="primary" />} label="Include Holding Symbols" />
          <Box sx={{ flexGrow: 1 }} />
          <Tooltip title="Refresh strategies">
            <IconButton onClick={() => { void fetchStrategies(); void fetchHoldings(); }} disabled={loading} aria-label="Refresh strategies">
              {loading ? <CircularProgress size={20} /> : <RefreshIcon />}
            </IconButton>
          </Tooltip>
        </Box>
      </Paper>

      <TradeTableToolbar
        config={tableConfig as any}
        search=""
        onSearchChange={() => {}}
        activeFilterCount={filters.length}
        onClearFilters={() => setFilters([])}
        onOpenMobileFilters={() => setMobileFiltersOpen(true)}
        columnVisibility={columnVisibility}
        onColumnVisibilityChange={(id, visible) => setColumnVisibility((prev) => ({ ...prev, [id]: visible }))}
        onResetColumns={() => {
          const next: Record<string, boolean> = {};
          for (const col of tableConfig.columns) next[col.id] = col.visible;
          setColumnVisibility(next);
        }}
        mobile={isMobile}
      />

      {tableConfig.selectionEnabled && (
        <TradeSelectionToolbar
          selectedIds={selected}
          actions={[
            { label: 'Revise Entries', onClick: () => handleOpenRevisionModal(), icon: <EditIcon />, variant: 'contained', color: 'primary' },
            { label: deleting ? 'Deleting...' : 'Delete', onClick: () => void handleDeleteSelected(), icon: <DeleteIcon />, variant: 'outlined', color: 'error', disabled: deleting },
          ]}
          onClearSelection={handleClearSelection}
        />
      )}

      {loading || holdingsLoading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}><CircularProgress /></Box>
      ) : !sessionReady ? (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <Typography variant="body1" color="text.secondary">
            {!sessionId ? 'No active session. Open Broker Accounts to prepare a trading session.'
              : sessionReadiness === 'ERROR' ? sessionMessage || 'Unable to prepare trading session. Retry.'
                : sessionReadiness === 'INITIALIZING' ? 'Preparing trading session...'
                  : sessionReadiness === 'LOADING' ? 'Loading session data...'
                    : sessionReadiness === 'CONNECTED' ? 'Broker connected. Preparing trading session.'
                      : 'Preparing trading session...'}
          </Typography>
          {sessionReadiness === 'ERROR' && <Button size="small" sx={{ mt: 1 }} onClick={() => void retrySession()}>Retry</Button>}
        </Paper>
      ) : strategies.length === 0 ? (
        <Paper sx={{ p: 4, textAlign: 'center' }}><Typography variant="body1" color="text.secondary">No entry strategies found. Upload a CSV file to get started.</Typography></Paper>
      ) : sortedRows.length === 0 ? (
        <Paper sx={{ p: 4, textAlign: 'center' }}><Typography variant="body1" color="text.secondary">{hasActiveFilters ? 'No strategies match the current filters.' : (includeHoldings ? 'No entry strategies match the current filter.' : 'All entry strategy symbols are currently in holdings. Toggle "Include Holding Symbols" to show them.')}</Typography></Paper>
      ) : isMobile ? renderMobile() : renderDesktopTable()}

      <TradeMobileFilterDialog<StrategyRow>
        open={mobileFiltersOpen}
        onClose={() => setMobileFiltersOpen(false)}
        columns={filterableColumns as any}
        rows={filteredByHoldings}
        filters={filters}
        onApply={(next) => { setFilters(next); setMobileFiltersOpen(false); }}
        onClear={() => { setFilters([]); setMobileFiltersOpen(false); }}
      />

      {revisionModalOpen && (
        <BulkRevisionModal open={revisionModalOpen} onClose={handleRevisionModalClose} selectedSymbols={selected} strategies={strategies} onApply={() => { void handleRevisionApplied(); }} />
      )}

      <Dialog open={deleteDialogOpen} onClose={() => setDeleteDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Delete Entry Strategies</DialogTitle>
        <DialogContent>
          <Alert severity="warning" sx={{ mb: 2 }}>You are about to delete <strong>{selected.length}</strong> strategy(ies). Entry levels and allocations will be lost.</Alert>
          <TableContainer>
            <Table size="small">
              <TableHead><TableRow><TableCell>Symbol</TableCell><TableCell>Exchange</TableCell><TableCell>Allocation</TableCell></TableRow></TableHead>
              <TableBody>
                {selected.slice(0, 10).map((symbol) => {
                  const s = strategies.find((st) => st.symbol === symbol); if (!s) return null;
                  return <TableRow key={symbol}><TableCell>{s.symbol}</TableCell><TableCell>{s.exchange}</TableCell><TableCell>₹{(s.allocated ?? 0).toLocaleString()}</TableCell></TableRow>;
                })}
                {selected.length > 10 && <TableRow><TableCell colSpan={3}>...and {selected.length - 10} more</TableCell></TableRow>}
              </TableBody>
            </Table>
          </TableContainer>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteDialogOpen(false)} disabled={deleting}>Cancel</Button>
          <Button onClick={handleDeleteConfirm} variant="contained" color="error" disabled={deleting}>{deleting ? 'Deleting...' : `Delete ${selected.length} Strategy(ies)`}</Button>
        </DialogActions>
      </Dialog>

      <MobileStrategyEditDialog open={editingStrategy !== null} strategy={editingStrategy} saving={editSaving} errorMessage={editError} onClose={handleCloseEdit} onSave={async (values) => { if (editingStrategy) await handleMobileSave(editingStrategy.symbol, values as any); }} />
      <ResponsiveDialog open={historyDialogOpen} onClose={handleCloseHistory} maxWidth="sm" fullWidth>
        <DialogTitle>Version History - {historySymbol}</DialogTitle>
        <DialogContent dividers>
          <MobileVersionHistory versions={historyVersions} currentAllocation={strategies.find((s) => s.symbol === historySymbol)?.allocated ?? null} loading={historyLoading} error={historyError} onOpenFullDetail={() => handleOpenFullDetailFromHistory(historySymbol)} />
        </DialogContent>
        <DialogActions><Button onClick={handleCloseHistory}>Close</Button></DialogActions>
      </ResponsiveDialog>
    </TradePageLayout>
  );
}
