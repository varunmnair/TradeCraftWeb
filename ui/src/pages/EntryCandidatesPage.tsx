import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
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
  Switch,
  FormControlLabel,
  IconButton,
  Tooltip,
  Collapse,
  useMediaQuery,
  useTheme,
} from '@mui/material';
import {
  Refresh as RefreshIcon,
  PlayArrow as GenerateIcon,
  ShoppingCart as PlaceIcon,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
  Warning as WarningIcon,
  CheckCircle as CheckIcon,
  Info as InfoIcon,
} from '@mui/icons-material';
import { api } from '../api/client';
import {
  CandidateGenerateResponse,
  NormalizedCandidate,
  SkippedCandidate,
  PlaceOrderResult,
} from '../types';
import { useSession } from '../context/SessionContext';
import { useJobs } from '../context/JobsContext';
import PlaceOrdersDialog from '../components/PlaceOrdersDialog';
import { MobileEntryCandidateCard } from '../components/candidates/MobileEntryCandidateCard';
import { MobileSkippedCandidateCard } from '../components/candidates/MobileSkippedCandidateCard';
import {
  CandidateMobileControls,
  type CandidateSort,
} from '../components/candidates/CandidateMobileControls';
import { MobileOrderActionBar } from '../components/candidates/MobileOrderActionBar';
import {
  candidateStatusColor as statusColor,
  candidateStrategyColor as strategyColor,
  candidateStrategyLabel as strategyLabel,
  canSelectCandidate,
  candidateKey,
  fmt,
  fmtCurrency,
  getActualOrderValue,
} from '../components/candidates/candidateDisplay';
import { newPlacementKey } from '../utils/placementIdempotency';
import { TradePageLayout } from '../components/TradePageLayout';
import { ResponsivePageHeader } from '../components/ResponsivePageHeader';
import { TradeTableToolbar } from '../components/tradeTable/TradeTableToolbar';
import { TradeMobileFilterDialog } from '../components/tradeTable/TradeMobileFilterDialog';
import { resolveTradeTableConfig, getFilterableColumns } from '../components/tradeTable/config';
import { applyTradeFilters, applyTradeSort } from '../components/tradeTable/tableState';
import type { TradeColumnDef, TradeFilterRule, TradeSortState } from '../components/tradeTable/types';
import { tradeTableRegistry } from '../config/tradeTableRegistry';
import { uiPageConfigToTradeTableConfig, useUiPageConfig } from '../hooks/useUiPageConfig';


function DeltaChip({ cmp, entry }: { cmp: number | null; entry: number | null }) {
  if (cmp == null || entry == null || entry === 0) return <Typography variant="body2" color="text.secondary">—</Typography>;
  const delta = ((cmp - entry) / entry) * 100;
  const color = delta >= 0 ? 'success' : 'error';
  return (
    <Chip
      size="small"
      label={`${delta >= 0 ? '+' : ''}${delta.toFixed(1)}%`}
      color={color}
      variant="outlined"
      sx={{ fontWeight: 600, minWidth: 64 }}
    />
  );
}

export default function EntryCandidatesPage() {
  const { sessionId } = useSession();
  const { trackJob } = useJobs();
  const [data, setData] = useState<CandidateGenerateResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState('');
  const [selected, setSelected] = useState<string[]>([]);
  const [reviewDialogOpen, setReviewDialogOpen] = useState(false);
  const [placing, setPlacing] = useState(false);
  const [placeResults, setPlaceResults] = useState<PlaceOrderResult[] | null>(null);
  const [skippedOpen, setSkippedOpen] = useState(false);
  const [existingOrderSymbols, setExistingOrderSymbols] = useState<Set<string>>(new Set());
  const [hideWithOrders, setHideWithOrders] = useState(false);
  const [strategyFilter, setStrategyFilter] = useState('ALL');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [sortBy, setSortBy] = useState<CandidateSort | null>(null);
  const placingRef = useRef(false);

  // Admin UI config integration
  const { config: uiConfig } = useUiPageConfig('entry_candidates');
  const [filters, setFilters] = useState<TradeFilterRule[]>([]);
  const [mobileFiltersOpen, setMobileFiltersOpen] = useState(false);
  const [columnVisibility, setColumnVisibility] = useState<Record<string, boolean>>({});

  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const busy = generating || placing || loading;

  const fetchCandidates = useCallback(async () => {
    if (!sessionId) return;
    setLoading(true);
    setError('');
    try {
      const result = await api.getLatestCandidates(sessionId);
      setData(result);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to load candidates';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    setData(null);
    setSelected([]);
    setExistingOrderSymbols(new Set());
    setError('');
    setPlaceResults(null);
    if (!sessionId) return;
    fetchCandidates();
    api.getGTTOrders(sessionId).then(resp => {
      const symbols = new Set<string>();
      for (const order of resp.orders) {
        const sym = ((order['Symbol'] as string) || '').toUpperCase();
        if (sym) symbols.add(sym);
      }
      setExistingOrderSymbols(symbols);
    }).catch(() => {});
  }, [sessionId, fetchCandidates]);

  const handleGenerate = async () => {
    if (!sessionId) return;
    setGenerating(true);
    setError('');
    try {
      const resp = await api.generateCandidates(sessionId);
      trackJob(resp.job_id);
      // Poll for result after a delay
      setTimeout(() => fetchCandidates(), 5000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to queue generation');
    } finally {
      setGenerating(false);
    }
  };

  const handleSelectAll = (checked: boolean) => {
    if (!data) return;
    if (checked) {
      setSelected(data.candidates.filter(c => c.is_selectable).map(c => c.symbol));
    } else {
      setSelected([]);
    }
  };

  const handleSelect = (symbol: string) => {
    const candidate = data?.candidates.find((item) => item.symbol === symbol);
    if (
      !candidate ||
      !canSelectCandidate(candidate, existingOrderSymbols.has(symbol.toUpperCase()))
    ) {
      return;
    }
    setSelected(prev =>
      prev.includes(symbol) ? prev.filter(s => s !== symbol) : [...prev, symbol]
    );
  };

  const handleSelectReady = () => {
    setSelected((previous) => {
      const next = new Set(previous);
      for (const candidate of visibleCandidates) {
        const hasOrder = existingOrderSymbols.has(candidate.symbol.toUpperCase());
        if (
          candidate.status === 'READY' &&
          canSelectCandidate(candidate, hasOrder)
        ) {
          next.add(candidate.symbol);
        }
      }
      return [...next];
    });
  };

  const handleSort = (field: string) => {
    const col = tableConfig.columns.find((c) => c.id === field);
    if (!col || !col.sortable) return;
    setSortBy((previous) => {
      if (previous?.field === field) {
        return { field: field as CandidateSort['field'], direction: previous.direction === 'asc' ? 'desc' : 'asc' };
      }
      return { field: field as CandidateSort['field'], direction: field === 'symbol' ? 'asc' : 'desc' };
    });
  };

  const handleClearMobileFilters = () => {
    setStrategyFilter('ALL');
    setStatusFilter('ALL');
  };

  const handleOpenReview = () => {
    setPlaceResults(null);
    setReviewDialogOpen(true);
  };

  const handleConfirmPlace = async () => {
    if (!sessionId || selected.length === 0 || placingRef.current) return;
    placingRef.current = true;
    setPlacing(true);
    try {
      const result = await api.placeCandidates(
        sessionId,
        selected,
        newPlacementKey('candidates'),
      );
      setPlaceResults(result.results);
      if (result.errors.length > 0) {
        setError(result.errors.join('; '));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to place orders');
    } finally {
      setPlacing(false);
      placingRef.current = false;
    }
  };

  const handleCloseDialog = () => {
    setReviewDialogOpen(false);
    setPlaceResults(null);
    setSelected([]);
    fetchCandidates();
  };

  const summary = data?.summary;
  const candidates = data?.candidates ?? [];
  const skipped = data?.skipped ?? [];

  const tableConfig = useMemo(() => {
    const base = tradeTableRegistry.entry_candidates.config;
    const runtimeColumns = (base.columns as TradeColumnDef<NormalizedCandidate>[]).map((col) => {
      if (col.id === 'symbol') return { ...col, required: true, valueGetter: (row: NormalizedCandidate) => row.symbol };
      if (col.id === 'strategy') return { ...col, valueGetter: (row: NormalizedCandidate) => row.strategy_type, filterOptions: [{ value: 'MULTI_LEVEL', label: 'Multi-Level Entry' }, { value: 'DYNAMIC_AVERAGING', label: 'Dynamic Averaging' }] };
      if (col.id === 'signal') return { ...col, valueGetter: (row: NormalizedCandidate) => row.signal ?? '' };
      if (col.id === 'cmp') return { ...col, valueGetter: (row: NormalizedCandidate) => row.cmp };
      if (col.id === 'trigger') return { ...col, valueGetter: (row: NormalizedCandidate) => row.trigger_price ?? row.order_price };
      if (col.id === 'qty') return { ...col, valueGetter: (row: NormalizedCandidate) => row.qty };
      if (col.id === 'amount') return { ...col, valueGetter: (row: NormalizedCandidate) => getActualOrderValue(row) };
      if (col.id === 'delta_vs_entry') return { ...col, valueGetter: (row: NormalizedCandidate) => {
        if (row.strategy_type === 'DYNAMIC_AVERAGING' && row.additional_details?.drop_from_avg_pct != null) return -(Number(row.additional_details.drop_from_avg_pct) || 0);
        const entry = (row.additional_details?.level_price as number | null | undefined) ?? null;
        if (row.cmp == null || entry == null || entry === 0) return null;
        return ((row.cmp - entry) / entry) * 100;
      } };
      if (col.id === 'status') return { ...col, valueGetter: (row: NormalizedCandidate) => row.status, filterOptions: [{ value: 'READY', label: 'Ready' }, { value: 'WARNING', label: 'Warning' }, { value: 'REVIEW', label: 'Review' }] };
      return col;
    });
    const baseConfig = { ...base, columns: runtimeColumns };
    const effective = uiConfig ? uiPageConfigToTradeTableConfig<any>('entry_candidates', uiConfig, baseConfig as any) : (baseConfig as any);
    const mergedColumns = (effective.columns as TradeColumnDef<any>[]).map((col) => {
      const runtime = runtimeColumns.find((c) => c.id === col.id);
      return runtime ? { ...runtime, ...col, renderCell: runtime.renderCell ?? col.renderCell, formatValue: runtime.formatValue ?? col.formatValue, filterOptions: runtime.filterOptions ?? col.filterOptions, valueGetter: runtime.valueGetter ?? col.valueGetter } : col;
    });
    return resolveTradeTableConfig<any>({ ...effective, columns: mergedColumns } as any);
  }, [uiConfig]);

  useEffect(() => {
    setColumnVisibility((prev) => {
      const next: Record<string, boolean> = {};
      for (const col of tableConfig.columns) next[col.id] = prev[col.id] ?? col.visible;
      for (const col of tableConfig.columns) if (col.required) next[col.id] = true;
      return next;
    });
    setSortBy((prev) => {
      if (prev) return prev;
      const ds = tableConfig.defaultSort;
      if (!ds) return null;
      const field = ds.field as CandidateSort['field'];
      if (['symbol', 'cmp', 'amount', 'status', 'strategy'].includes(field)) return { field, direction: ds.direction };
      return null;
    });
  }, [tableConfig]);

  const visibleColumns = useMemo(() => {
    return tableConfig.columns
      .filter((c) => columnVisibility[c.id] !== false)
      .sort((a, b) => a.position - b.position);
  }, [tableConfig.columns, columnVisibility]);
  const filterableColumns = useMemo(() => getFilterableColumns({ ...tableConfig, columns: tableConfig.columns.map((c) => ({ ...c, visible: columnVisibility[c.id] !== false })) } as any), [tableConfig, columnVisibility]);

  const filteredCandidates = useMemo(
    () =>
      hideWithOrders
        ? candidates.filter(c => !existingOrderSymbols.has(c.symbol.toUpperCase()))
        : candidates,
    [candidates, hideWithOrders, existingOrderSymbols],
  );

  const domainFilteredCandidates = useMemo(() => {
    let list = filteredCandidates.filter(
      c => strategyFilter === 'ALL' || c.strategy_type === strategyFilter,
    );
    if (statusFilter === 'SKIPPED') list = [];
    else if (statusFilter !== 'ALL') list = list.filter(c => c.status === statusFilter);
    return list;
  }, [filteredCandidates, strategyFilter, statusFilter]);

  const configSort: TradeSortState | null = useMemo(() => {
    if (!sortBy) return tableConfig.defaultSort ?? null;
    const col = tableConfig.columns.find((c) => c.id === sortBy.field);
    if (!col || !col.sortable) return tableConfig.defaultSort ?? null;
    return { field: sortBy.field, direction: sortBy.direction };
  }, [sortBy, tableConfig]);

  const configFilteredCandidates = useMemo(() => applyTradeFilters(domainFilteredCandidates as any, filters, tableConfig.columns as any) as NormalizedCandidate[], [domainFilteredCandidates, filters, tableConfig.columns]);
  const visibleCandidates = useMemo(() => applyTradeSort(configFilteredCandidates as any, configSort, tableConfig.columns as any) as NormalizedCandidate[], [configFilteredCandidates, configSort, tableConfig.columns]);

  const visibleSkipped = useMemo(() => {
    if (statusFilter !== 'ALL' && statusFilter !== 'SKIPPED') return [];
    return skipped.filter(
      s => strategyFilter === 'ALL' || s.strategy_type === strategyFilter,
    );
  }, [skipped, strategyFilter, statusFilter]);

  const selectableCount = visibleCandidates.filter(c => c.is_selectable && !existingOrderSymbols.has(c.symbol.toUpperCase())).length;

  const selectedOrderCandidates = useMemo(
    () =>
      candidates.filter(
        c =>
          selected.includes(c.symbol) &&
          c.is_selectable &&
          c.side === 'BUY' &&
          !existingOrderSymbols.has(c.symbol.toUpperCase()),
      ),
    [candidates, selected, existingOrderSymbols],
  );
  const selectedOrderTotal = useMemo(
    () => selectedOrderCandidates.reduce((sum, c) => sum + getActualOrderValue(c), 0),
    [selectedOrderCandidates],
  );

  return (
    <TradePageLayout
      sx={{ pb: { xs: selected.length > 0 ? '76px' : 0, sm: 0 } }}
      header={
        <ResponsivePageHeader
          title="Entry Candidates"
          primaryAction={
            <Button
              variant="contained"
              startIcon={generating ? <CircularProgress size={16} /> : <GenerateIcon />}
              onClick={handleGenerate}
              disabled={generating || !sessionId}
            >
              {generating ? 'Generating...' : 'Generate Candidates'}
            </Button>
          }
          actions={
            <Tooltip title="Refresh">
              <IconButton onClick={fetchCandidates} disabled={loading}>
                <RefreshIcon />
              </IconButton>
            </Tooltip>
          }
        />
      }
    >

      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>{error}</Alert>}

      {/* Summary Bar */}
      {summary && (
        <Paper
          sx={{
            p: 2,
            mb: 2,
            display: 'flex',
            gap: { xs: 1, sm: 3 },
            alignItems: 'center',
            flexWrap: { xs: 'wrap', sm: 'nowrap' },
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <InfoIcon fontSize="small" color="action" />
            <Typography variant="body2" color="text.secondary">
              Total
            </Typography>
            <Typography variant="body2" fontWeight={700}>{summary.total}</Typography>
          </Box>
          <Chip icon={<CheckIcon />} label={`${summary.ready} Ready`} size="small" color="success" variant="outlined" />
          <Chip icon={<WarningIcon />} label={`${summary.warning} Warning`} size="small" color="warning" variant="outlined" />
          {summary.review > 0 && (
            <Chip label={`${summary.review} Review`} size="small" color="info" variant="outlined" />
          )}
          {summary.skipped > 0 && (
            <Chip label={`${summary.skipped} Skipped`} size="small" color="default" variant="outlined" />
          )}
          <Box sx={{ flex: 1 }} />
          <Typography variant="body2" color="text.secondary">
            Capital required:{' '}
            <Typography component="span" variant="body2" fontWeight={700}>
              {fmtCurrency(summary.capital_required)}
            </Typography>
          </Typography>
          {data?.generated_at && (
            <Typography variant="caption" color="text.secondary">
              Generated {new Date(data.generated_at).toLocaleTimeString()}
            </Typography>
          )}
          <FormControlLabel
            control={
              <Switch
                size="small"
                checked={hideWithOrders}
                onChange={(e) => setHideWithOrders(e.target.checked)}
              />
            }
            label="Hide stocks with active orders"
            sx={{ ml: 1 }}
          />
        </Paper>
      )}

      {/* Toolbar */}
      {selected.length > 0 && (
        <Paper
          sx={{
            p: 1,
            mb: 2,
            display: { xs: 'none', sm: 'flex' },
            alignItems: 'center',
            gap: 1,
            bgcolor: 'grey.50',
          }}
        >
          <Typography variant="body2" sx={{ ml: 1 }}>
            {selected.length} selected
          </Typography>
          <Box sx={{ flex: 1 }} />
          <Button
            size="small"
            variant="contained"
            color="success"
            startIcon={<PlaceIcon />}
            onClick={handleOpenReview}
          >
            Place Orders
          </Button>
          <Button size="small" onClick={() => setSelected([])}>
            Clear
          </Button>
        </Paper>
      )}

      {isMobile && (
        <>
          <TradeTableToolbar
            config={tableConfig}
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
              for (const col of tableConfig.columns) if (col.required) next[col.id] = true;
              setColumnVisibility(next);
            }}
            mobile
          />
          <CandidateMobileControls
            strategyFilter={strategyFilter}
            statusFilter={statusFilter}
            onStrategyFilterChange={setStrategyFilter}
            onStatusFilterChange={setStatusFilter}
            sortBy={sortBy}
            onSort={handleSort}
            onSelectReady={handleSelectReady}
            onClearSelection={() => setSelected([])}
            onClearFilters={handleClearMobileFilters}
            selectedCount={selected.length}
            busy={busy}
            sortableFields={tableConfig.columns.filter((c) => c.sortable).map((c) => c.id)}
          />
        </>
      )}

      {/* Candidates Table */}
      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
          <CircularProgress />
        </Box>
      ) : visibleCandidates.length === 0 && visibleSkipped.length === 0 ? (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <Typography variant="body1" color="text.secondary">
            {hideWithOrders
              ? 'All candidates have active buy orders. Disable the filter to see them.'
              : strategyFilter !== 'ALL' || statusFilter !== 'ALL'
                ? 'No candidates match the current filters.'
                : 'No candidates generated yet. Click Generate Candidates to start.'}
          </Typography>
        </Paper>
      ) : isMobile ? (
        <Box>
          {visibleCandidates.map((candidate) => (
            <MobileEntryCandidateCard
              key={candidateKey(candidate)}
              candidate={candidate}
              hasActiveOrder={existingOrderSymbols.has(candidate.symbol.toUpperCase())}
              selected={selected.includes(candidate.symbol)}
              disabled={busy}
              onToggle={handleSelect}
            />
          ))}
          {visibleSkipped.length > 0 && (
            <Box sx={{ mt: 2 }}>
              <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1 }}>
                Skipped Symbols ({visibleSkipped.length})
              </Typography>
              {visibleSkipped.map((item) => (
                <MobileSkippedCandidateCard
                  key={`${item.symbol}-${item.reason_code}`}
                  skipped={item}
                />
              ))}
            </Box>
          )}
        </Box>
      ) : (
        <Paper sx={{ mb: 2 }}>
          <TradeTableToolbar
            config={tableConfig}
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
              for (const col of tableConfig.columns) if (col.required) next[col.id] = true;
              setColumnVisibility(next);
            }}
            mobile={false}
          />
          <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell padding="checkbox">
                  <Checkbox
                    checked={selected.length === selectableCount && selectableCount > 0}
                    indeterminate={selected.length > 0 && selected.length < selectableCount}
                    onChange={(e) => handleSelectAll(e.target.checked)}
                    disabled={selectableCount === 0}
                  />
                </TableCell>
                {visibleColumns.map((col) => {
                  const align = col.alignment ?? (col.dataType === 'number' ? 'right' : col.dataType === 'boolean' ? 'center' : 'left');
                  const sortable = col.sortable;
                  const active = sortBy?.field === col.id;
                  return (
                    <TableCell key={col.id} align={align} sortDirection={active ? sortBy?.direction : false} sx={{ width: col.width, minWidth: col.minWidth }}>
                      {sortable ? (
                        <TableSortLabel
                          active={active}
                          direction={active ? sortBy?.direction : 'asc'}
                          onClick={() => handleSort(col.id)}
                        >
                          {col.label}
                        </TableSortLabel>
                      ) : (
                        col.label
                      )}
                    </TableCell>
                  );
                })}
              </TableRow>
            </TableHead>
            <TableBody>
              {visibleCandidates.map((c) => {
                const isSelected = selected.includes(c.symbol);
                const hasOrder = existingOrderSymbols.has(c.symbol.toUpperCase());
                return (
                  <TableRow
                    key={c.symbol}
                    hover
                    selected={isSelected}
                    sx={{ opacity: c.is_selectable && !hasOrder ? 1 : 0.6 }}
                  >
                    <TableCell padding="checkbox">
                      <Checkbox
                        checked={isSelected}
                        onChange={() => handleSelect(c.symbol)}
                        disabled={!c.is_selectable || hasOrder}
                      />
                    </TableCell>
                    {visibleColumns.map((col) => {
                      const align = col.alignment ?? (col.dataType === 'number' ? 'right' : col.dataType === 'boolean' ? 'center' : 'left');
                      if (col.id === 'symbol') {
                        return (
                          <TableCell key={col.id} align={align}>
                            <Typography variant="body2" fontWeight={600}>{c.symbol}</Typography>
                            {c.exchange && <Typography variant="caption" color="text.secondary">{c.exchange}</Typography>}
                          </TableCell>
                        );
                      }
                      if (col.id === 'strategy') {
                        return (
                          <TableCell key={col.id} align={align}>
                            <Chip label={strategyLabel[c.strategy_type] ?? c.strategy_type} size="small" color={strategyColor[c.strategy_type] ?? 'default'} variant="outlined" />
                          </TableCell>
                        );
                      }
                      if (col.id === 'signal') {
                        return <TableCell key={col.id} align={align}><Typography variant="body2" fontWeight={600}>{c.signal ?? '\u2014'}</Typography></TableCell>;
                      }
                      if (col.id === 'cmp') {
                        return <TableCell key={col.id} align={align}><Typography variant="body2">{fmtCurrency(c.cmp)}</Typography></TableCell>;
                      }
                      if (col.id === 'trigger') {
                        return <TableCell key={col.id} align={align}><Typography variant="body2">{fmtCurrency(c.trigger_price)}</Typography></TableCell>;
                      }
                      if (col.id === 'qty') {
                        return <TableCell key={col.id} align={align}><Typography variant="body2">{c.qty}</Typography></TableCell>;
                      }
                      if (col.id === 'amount') {
                        return <TableCell key={col.id} align={align}><Typography variant="body2" fontWeight={600}>{fmtCurrency(getActualOrderValue(c))}</Typography></TableCell>;
                      }
                      if (col.id === 'delta_vs_entry') {
                        return (
                          <TableCell key={col.id} align={align}>
                            {c.strategy_type === 'DYNAMIC_AVERAGING' && c.additional_details?.drop_from_avg_pct != null ? (
                              <Chip size="small" label={`-${(c.additional_details.drop_from_avg_pct as number).toFixed(1)}%`} color="error" variant="outlined" sx={{ fontWeight: 600, minWidth: 64 }} />
                            ) : (
                              <DeltaChip cmp={c.cmp} entry={c.additional_details?.level_price as number ?? null} />
                            )}
                          </TableCell>
                        );
                      }
                      if (col.id === 'status') {
                        return (
                          <TableCell key={col.id} align={align}>
                            {hasOrder ? (
                              <Chip label="Active Order" size="small" color="default" variant="filled" sx={{ fontWeight: 600 }} />
                            ) : (
                              <>
                                <Chip label={c.status} size="small" color={statusColor[c.status] ?? 'default'} sx={{ fontWeight: 600 }} />
                                {(c.reason_message || c.strategy_type === 'DYNAMIC_AVERAGING') && (
                                  <Tooltip
                                    title={
                                      <Box sx={{ p: 0.5 }}>
                                        {c.reason_message && <Typography variant="body2" sx={{ mb: 1 }}>{c.reason_message}</Typography>}
                                        {c.strategy_type === 'DYNAMIC_AVERAGING' && c.additional_details && (
                                          <Box sx={{ fontSize: '0.8rem', lineHeight: 1.6 }}>
                                            <div><strong>Avg Price:</strong> {fmtCurrency(c.additional_details.avg_price as number ?? null)}</div>
                                            <div><strong>Drop from Avg %:</strong> {c.additional_details.drop_from_avg_pct != null ? `${(c.additional_details.drop_from_avg_pct as number).toFixed(1)}%` : '\u2014'}</div>
                                            <div><strong>Regime:</strong> {c.additional_details.regime as string ?? '\u2014'}</div>
                                            <div><strong>Offset %:</strong> {c.additional_details.trigger_offset_pct != null ? `${(c.additional_details.trigger_offset_pct as number).toFixed(2)}%` : '\u2014'}</div>
                                            <div><strong>DA Capacity:</strong> {fmtCurrency(c.additional_details.da_capacity as number ?? null)}</div>
                                            <div><strong>Expected Benefit:</strong> {fmtCurrency(c.additional_details.expected_benefit as number ?? null)}</div>
                                            <div><strong>Estimated Cost:</strong> {fmtCurrency(c.additional_details.estimated_cost as number ?? null)}</div>
                                            <div><strong>Net Benefit:</strong> {fmtCurrency(c.additional_details.net_benefit as number ?? null)}</div>
                                            <div><strong>Legs:</strong> {c.additional_details.total_legs as number ?? '\u2014'} / Max: {c.additional_details.total_legs as number ?? '\u2014'}</div>
                                          </Box>
                                        )}
                                      </Box>
                                    }
                                    arrow
                                    placement="left"
                                  >
                                    <IconButton size="small" sx={{ ml: 0.5 }}><InfoIcon fontSize="small" /></IconButton>
                                  </Tooltip>
                                )}
                              </>
                            )}
                          </TableCell>
                        );
                      }
                      const raw = (c as any)[col.id];
                      return <TableCell key={col.id} align={align}>{raw == null || raw === '' ? '\u2014' : String(raw)}</TableCell>;
                    })}

                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
          </TableContainer>
        </Paper>
      )}

      {/* Skipped Section */}
      {!isMobile && visibleSkipped.length > 0 && (
        <Paper sx={{ mt: 2 }}>
          <Box
            sx={{ display: 'flex', alignItems: 'center', cursor: 'pointer', p: 1.5 }}
            onClick={() => setSkippedOpen(!skippedOpen)}
          >
            <Typography variant="subtitle2" sx={{ flex: 1 }}>
              Skipped Symbols ({visibleSkipped.length})
            </Typography>
            <IconButton size="small">
              {skippedOpen ? <ExpandLessIcon /> : <ExpandMoreIcon />}
            </IconButton>
          </Box>
          <Collapse in={skippedOpen}>
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Symbol</TableCell>
                    <TableCell>Strategy</TableCell>
                    <TableCell>Reason</TableCell>
                    <TableCell>Suggested Action</TableCell>
                    <TableCell align="right">CMP</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {visibleSkipped.map((s) => (
                    <TableRow key={`${s.symbol}-${s.reason_code}`}>
                      <TableCell>
                        <Typography variant="body2" fontWeight={600}>{s.symbol}</Typography>
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={strategyLabel[s.strategy_type] ?? s.strategy_type}
                          size="small"
                          variant="outlined"
                        />
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2">{s.reason_message}</Typography>
                        {s.technical_details && (
                          <Typography variant="caption" color="text.secondary" display="block">
                            {s.technical_details}
                          </Typography>
                        )}
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" color="text.secondary">
                          {s.suggested_action}
                        </Typography>
                      </TableCell>
                      <TableCell align="right">
                        <Typography variant="body2">{fmtCurrency(s.cmp)}</Typography>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Collapse>
        </Paper>
      )}
      <MobileOrderActionBar
        count={selectedOrderCandidates.length}
        total={selectedOrderTotal}
        disabled={busy}
        onReview={handleOpenReview}
        onClear={() => setSelected([])}
      />

      <TradeMobileFilterDialog
        open={mobileFiltersOpen}
        onClose={() => setMobileFiltersOpen(false)}
        columns={filterableColumns}
        rows={domainFilteredCandidates as any}
        filters={filters}
        onApply={(next) => { setFilters(next); setMobileFiltersOpen(false); }}
        onClear={() => { setFilters([]); setMobileFiltersOpen(false); }}
      />

      {/* Place Orders Dialog */}
      <PlaceOrdersDialog
        open={reviewDialogOpen}
        onClose={handleCloseDialog}
        onConfirm={handleConfirmPlace}
        candidates={candidates}
        selected={selected}
        results={placeResults}
        placing={placing}
      />
    </TradePageLayout>
  );
}
