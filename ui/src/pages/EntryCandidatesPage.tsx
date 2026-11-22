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
import { ResponsiveToolbar } from '../components/ResponsiveToolbar';
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
    fetchCandidates();
  }, [fetchCandidates]);

  useEffect(() => {
    if (!sessionId) return;
    api.getGTTOrders(sessionId).then(resp => {
      const symbols = new Set<string>();
      for (const order of resp.orders) {
        const sym = ((order['Symbol'] as string) || '').toUpperCase();
        if (sym) symbols.add(sym);
      }
      setExistingOrderSymbols(symbols);
    }).catch(() => {});
  }, [sessionId]);

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

  const handleSort = (field: CandidateSort['field']) => {
    setSortBy((previous) => {
      if (previous?.field === field) {
        return { field, direction: previous.direction === 'asc' ? 'desc' : 'asc' };
      }
      return { field, direction: field === 'symbol' ? 'asc' : 'desc' };
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
  const selectableCount = candidates.filter(c => c.is_selectable).length;

  const filteredCandidates = useMemo(
    () =>
      hideWithOrders
        ? candidates.filter(c => !existingOrderSymbols.has(c.symbol.toUpperCase()))
        : candidates,
    [candidates, hideWithOrders, existingOrderSymbols],
  );

  const visibleCandidates = useMemo(() => {
    let list = filteredCandidates.filter(
      c => strategyFilter === 'ALL' || c.strategy_type === strategyFilter,
    );
    if (statusFilter === 'SKIPPED') {
      list = [];
    } else if (statusFilter !== 'ALL') {
      list = list.filter(c => c.status === statusFilter);
    }
    if (!sortBy) return list;
    const sorted = [...list];
    sorted.sort((a, b) => {
      let result = 0;
      if (sortBy.field === 'symbol') {
        result = a.symbol.localeCompare(b.symbol);
      } else if (sortBy.field === 'cmp') {
        result = (a.cmp ?? -1) - (b.cmp ?? -1);
      } else if (sortBy.field === 'amount') {
        result = getActualOrderValue(a) - getActualOrderValue(b);
      } else if (sortBy.field === 'status') {
        result = a.status_severity - b.status_severity;
      } else if (sortBy.field === 'strategy') {
        result = (strategyLabel[a.strategy_type] ?? a.strategy_type).localeCompare(
          strategyLabel[b.strategy_type] ?? b.strategy_type,
        );
      }
      return sortBy.direction === 'asc' ? result : -result;
    });
    return sorted;
  }, [filteredCandidates, strategyFilter, statusFilter, sortBy]);

  const visibleSkipped = useMemo(() => {
    if (statusFilter !== 'ALL' && statusFilter !== 'SKIPPED') return [];
    return skipped.filter(
      s => strategyFilter === 'ALL' || s.strategy_type === strategyFilter,
    );
  }, [skipped, strategyFilter, statusFilter]);

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
    <Box sx={{ pb: { xs: selected.length > 0 ? '76px' : 0, sm: 0 } }}>
      <ResponsiveToolbar sx={{ alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
        <Typography variant="h5" fontWeight={700} sx={{ flexShrink: 0 }}>
          Entry Candidates
        </Typography>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button
            variant="contained"
            startIcon={generating ? <CircularProgress size={16} /> : <GenerateIcon />}
            onClick={handleGenerate}
            disabled={generating || !sessionId}
          >
            {generating ? 'Generating...' : 'Generate Candidates'}
          </Button>
          <Tooltip title="Refresh">
            <IconButton onClick={fetchCandidates} disabled={loading}>
              <RefreshIcon />
            </IconButton>
          </Tooltip>
        </Box>
      </ResponsiveToolbar>

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
        />
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
        <TableContainer component={Paper} sx={{ mb: 2 }}>
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
                <TableCell>Symbol</TableCell>
                <TableCell>Strategy</TableCell>
                <TableCell align="center">Signal</TableCell>
                <TableCell align="right">CMP</TableCell>
                <TableCell align="right">Trigger</TableCell>
                <TableCell align="right">Qty</TableCell>
                <TableCell align="right">Amount</TableCell>
                <TableCell align="center">Δ vs Entry</TableCell>
                <TableCell align="center">Status</TableCell>
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
                    <TableCell>
                      <Typography variant="body2" fontWeight={600}>
                        {c.symbol}
                      </Typography>
                      {c.exchange && (
                        <Typography variant="caption" color="text.secondary">{c.exchange}</Typography>
                      )}
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={strategyLabel[c.strategy_type] ?? c.strategy_type}
                        size="small"
                        color={strategyColor[c.strategy_type] ?? 'default'}
                        variant="outlined"
                      />
                    </TableCell>
                    <TableCell align="center">
                      <Typography variant="body2" fontWeight={600}>
                        {c.signal ?? '—'}
                      </Typography>
                    </TableCell>
                    <TableCell align="right">
                      <Typography variant="body2">{fmtCurrency(c.cmp)}</Typography>
                    </TableCell>
                    <TableCell align="right">
                      <Typography variant="body2">{fmtCurrency(c.trigger_price)}</Typography>
                    </TableCell>
                    <TableCell align="right">
                      <Typography variant="body2">{c.qty}</Typography>
                    </TableCell>
                    <TableCell align="right">
                      <Typography variant="body2" fontWeight={600}>
                        {fmtCurrency(c.amount)}
                      </Typography>
                    </TableCell>
                    <TableCell align="center">
                      {c.strategy_type === 'DYNAMIC_AVERAGING' && c.additional_details?.drop_from_avg_pct != null ? (
                        <Chip
                          size="small"
                          label={`-${(c.additional_details.drop_from_avg_pct as number).toFixed(1)}%`}
                          color="error"
                          variant="outlined"
                          sx={{ fontWeight: 600, minWidth: 64 }}
                        />
                      ) : (
                        <DeltaChip cmp={c.cmp} entry={c.additional_details?.level_price as number ?? null} />
                      )}
                    </TableCell>
                    <TableCell align="center">
                      {hasOrder ? (
                        <Chip label="Active Order" size="small" color="default" variant="filled" sx={{ fontWeight: 600 }} />
                      ) : (
                        <>
                          <Chip
                            label={c.status}
                            size="small"
                            color={statusColor[c.status] ?? 'default'}
                            sx={{ fontWeight: 600 }}
                          />
                          {(c.reason_message || c.strategy_type === 'DYNAMIC_AVERAGING') && (
                            <Tooltip
                              title={
                                <Box sx={{ p: 0.5 }}>
                                  {c.reason_message && (
                                    <Typography variant="body2" sx={{ mb: 1 }}>
                                      {c.reason_message}
                                    </Typography>
                                  )}
                                  {c.strategy_type === 'DYNAMIC_AVERAGING' && c.additional_details && (
                                    <Box sx={{ fontSize: '0.8rem', lineHeight: 1.6 }}>
                                      <div><strong>Avg Price:</strong> {fmtCurrency(c.additional_details.avg_price as number ?? null)}</div>
                                      <div><strong>Drop from Avg %:</strong> {c.additional_details.drop_from_avg_pct != null ? `${(c.additional_details.drop_from_avg_pct as number).toFixed(1)}%` : '—'}</div>
                                      <div><strong>Regime:</strong> {c.additional_details.regime as string ?? '—'}</div>
                                      <div><strong>Offset %:</strong> {c.additional_details.trigger_offset_pct != null ? `${(c.additional_details.trigger_offset_pct as number).toFixed(2)}%` : '—'}</div>
                                      <div><strong>DA Capacity:</strong> {fmtCurrency(c.additional_details.da_capacity as number ?? null)}</div>
                                      <div><strong>Expected Benefit:</strong> {fmtCurrency(c.additional_details.expected_benefit as number ?? null)}</div>
                                      <div><strong>Estimated Cost:</strong> {fmtCurrency(c.additional_details.estimated_cost as number ?? null)}</div>
                                      <div><strong>Net Benefit:</strong> {fmtCurrency(c.additional_details.net_benefit as number ?? null)}</div>
                                      <div><strong>Legs:</strong> {c.additional_details.total_legs as number ?? '—'} / Max: {c.additional_details.total_legs as number ?? '—'}</div>
                                    </Box>
                                  )}
                                </Box>
                              }
                              arrow
                              placement="left"
                            >
                              <IconButton size="small" sx={{ ml: 0.5 }}>
                                <InfoIcon fontSize="small" />
                              </IconButton>
                            </Tooltip>
                          )}
                        </>
                      )}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </TableContainer>
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
    </Box>
  );
}
