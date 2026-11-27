import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  IconButton,
  LinearProgress,
  Menu,
  MenuItem,
  ListItemIcon,
  ListItemText,
  Paper,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import {
  CloudSync as SyncIcon,
  InfoOutlined,
  MoreVert as MoreVertIcon,
  Refresh as RefreshIcon,
  Upload as UploadIcon,
} from '@mui/icons-material';
import { api } from '../api/client';
import { useSession } from '../context/SessionContext';
import type { HoldingsRow, OrderHistoryStatus, Trade, WroiScore } from '../types';
import { AGE_REASON_MESSAGES, NOT_CALCULATED_TOOLTIP } from '../components/holdings/holdingDisplay';
import { MobileHoldingCard } from '../components/holdings/MobileHoldingCard';
import { ResponsivePageHeader } from '../components/ResponsivePageHeader';
import { TradePageLayout } from '../components/TradePageLayout';
import { TradeStatusAlert } from '../components/TradeStatusAlert';
import { TradeSummaryStrip } from '../components/TradeSummaryStrip';
import { TradeDataTable } from '../components/tradeTable/TradeDataTable';
import type { TradeColumnDef } from '../components/tradeTable/types';
import { tradeTableRegistry } from '../config/tradeTableRegistry';
import { uiPageConfigToTradeTableConfig, useUiPageConfig } from '../hooks/useUiPageConfig';

const UnpopulatedIcon = () => (
  <Tooltip title={NOT_CALCULATED_TOOLTIP} arrow>
    <InfoOutlined sx={{ fontSize: 16, color: '#999', cursor: 'help' }} />
  </Tooltip>
);

type HoldingDisplayRow = HoldingsRow & { id: string | number; wroi_trend?: string | null };

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
  const [symbolSearch, setSymbolSearch] = useState('');
  const [trades, setTrades] = useState<Trade[]>([]);
  const [searchingTrades, setSearchingTrades] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [wroiTrends, setWroiTrends] = useState<Record<string, string> | null>(null);
  const [scores, setScores] = useState<Record<string, WroiScore> | null>(null);
  const [computingWroiTrend, setComputingWroiTrend] = useState(false);
  const [actionMenuAnchorEl, setActionMenuAnchorEl] = useState<HTMLElement | null>(null);
  const [orderHistoryExpanded, setOrderHistoryExpanded] = useState(false);

  const { config: uiConfig } = useUiPageConfig('holdings');

  const fetchHoldings = useCallback(async () => {
    if (!sessionId) return;
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
    setHoldings([]);
    setTrades([]);
    setWroiTrends(null);
    setScores(null);
    setOrderHistory(null);
    setError('');
    setSearchError(null);
    if (sessionId) {
      void fetchHoldings();
      api.getOrderHistoryStatus(sessionId).then(setOrderHistory).catch(() => setOrderHistory(null));
    }
  }, [sessionId, fetchHoldings]);

  const handleComputeWroiTrend = async () => {
    if (!sessionId) return;
    setComputingWroiTrend(true);
    try {
      const result = await api.computeWroiTrend(sessionId);
      setWroiTrends(result.wroi_trends);
      setScores(result.scores);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to compute trend and scores');
    } finally {
      setComputingWroiTrend(false);
    }
  };

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

  const handleFetchOrderHistory = async () => {
    if (!sessionId) return;
    setFetchingOrderHistory(true);
    setError('');
    try {
      const result = await api.fetchOrderHistory(sessionId, orderHistoryDays);
      setOrderHistory(result);
      void fetchHoldings();
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
      void fetchHoldings();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to upload order history');
    } finally {
      setUploadingOrderHistory(false);
    }
    event.target.value = '';
  };

  const formatDateRange = (from: string, to: string) => {
    const fromDate = new Date(from);
    const toDate = new Date(to);
    const format = (d: Date) => d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    return `${format(fromDate)} - ${format(toDate)}`;
  };

  const broker = sessionInfo?.broker || 'upstox';
  const isUpstox = broker === 'upstox';

  const displayHoldings = useMemo<HoldingDisplayRow[]>(
    () =>
      holdings.map((item) => ({
        ...item,
        id: (item as any).id ?? item.symbol,
        wroi_trend: wroiTrends?.[item.symbol] ?? 'NA',
        ...(scores?.[item.symbol] || {}),
      })) as HoldingDisplayRow[],
    [holdings, wroiTrends, scores],
  );

  const summary = useMemo(() => {
    const totalHoldings = displayHoldings.length;
    const totalInvested = displayHoldings.reduce((sum, h) => sum + (h.invested || 0), 0);
    const totalProfit = displayHoldings.reduce((sum, h) => sum + (h.profit || 0), 0);
    const breakCount = displayHoldings.filter((h) => h.exit_action === 'BREAK').length;
    return { totalHoldings, totalInvested, totalProfit, breakCount };
  }, [displayHoldings]);

  const tableConfig = useMemo(() => {
    const base = tradeTableRegistry.holdings.config;
    const runtimeColumns: TradeColumnDef<HoldingDisplayRow>[] = (base.columns as TradeColumnDef<HoldingDisplayRow>[]).map((col) => {
      if (col.id === 'symbol') {
        return { ...col, required: true };
      }
      if (col.id === 'exit_action') {
        return {
          ...col,
          filterOptions: ['HOLD', 'WATCH', 'REDUCE', 'EXIT', 'BREAK'].map((v) => ({ value: v, label: v })),
          renderCell: (row: HoldingDisplayRow) => {
            if (wroiTrends == null) return <UnpopulatedIcon />;
            const action = row.exit_action;
            if (!action) return <span style={{ color: '#999' }}>-</span>;
            if (action === 'BREAK') {
              const breakPrice = row.thesis_break_price;
              const cmp = row.last_price;
              const breakPct = row.thesis_break_pct;
              const breakLines: string[] = [];
              if (breakPrice != null) breakLines.push(`Thesis Break Price: ₹${breakPrice}`);
              if (cmp != null) breakLines.push(`CMP: ₹${cmp.toFixed(2)}`);
              if (breakPct != null) breakLines.push(`% below break: ${breakPct.toFixed(2)}%`);
              breakLines.push('', 'Automation Paused – Manual Review Required');
              return (
                <Tooltip title={breakLines.join('\n')} arrow>
                  <Chip label="BREAK" size="small" color="error" variant="outlined" />
                </Tooltip>
              );
            }
            const color = action === 'HOLD' ? 'success' : action === 'WATCH' ? 'warning' : action === 'REDUCE' ? 'warning' : 'error';
            const ema = (row as any).ema_score;
            const vol = (row as any).volume_score;
            const wroi = (row as any).wroi_score;
            const total = (row as any).exit_score;
            const breakdown = [ema != null ? `EMA: ${ema}/50` : 'EMA: --', vol != null ? `Volume: ${vol}/30` : 'Volume: --', wroi != null ? `WROI: ${wroi}/20` : 'WROI: --'].join(' • ');
            const summaryText = total != null ? `Total: ${total}/100 → ${action}` : '';
            return (
              <Tooltip title={`${breakdown}${summaryText ? `\n${summaryText}` : ''}`} arrow>
                <Chip label={action} size="small" color={color as any} variant={action === 'REDUCE' ? 'outlined' : 'filled'} />
              </Tooltip>
            );
          },
        };
      }
      if (col.id === 'weighted_roi') return { ...col, formatValue: (v: unknown) => (v != null ? Number(v).toFixed(4) : '-') };
      if (col.id === 'wroi_trend') {
        return {
          ...col,
          filterOptions: ['STRONG_UP', 'UP', 'NEUTRAL', 'DOWN', 'NA'].map((v) => ({ value: v, label: v.replace('_', ' ') })),
          renderCell: (row: HoldingDisplayRow) => {
            if (wroiTrends == null) return <UnpopulatedIcon />;
            const val = row.wroi_trend;
            if (!val || val === 'NA') return <span style={{ color: '#999' }}>-</span>;
            const color = val === 'STRONG_UP' ? '#1b5e20' : val === 'UP' ? '#2e7d32' : val === 'NEUTRAL' ? '#e65100' : '#c62828';
            return <span style={{ color, fontWeight: 600 }}>{String(val).replace('_', ' ')}</span>;
          },
        };
      }
      if (col.id === 'profit') return { ...col, formatValue: (v: unknown) => (v != null ? Number(v).toFixed(0) : '-') };
      if (col.id === 'profit_pct') return { ...col, formatValue: (v: unknown) => (v != null ? Number(v).toFixed(1) : '-') };
      if (col.id === 'profit_per_day') return { ...col, formatValue: (v: unknown) => (v != null ? Number(v).toFixed(1) : '-') };
      if (col.id === 'age') {
        return {
          ...col,
          renderCell: (row: HoldingDisplayRow) => {
            if (row.age === null && row.age_reason) {
              let tooltipText = AGE_REASON_MESSAGES[row.age_reason] || row.age_reason;
              if (row.age_reason === 'trade_qty_mismatch') {
                if (!row.age_trade_qty || row.age_trade_qty === 0) {
                  tooltipText = `No trade records found (holding: ${row.age_holding_qty ?? '?'} shares)`;
                } else {
                  tooltipText = `Trade qty (${row.age_trade_qty}) ≠ Holding qty (${row.age_holding_qty ?? '?'})`;
                }
              }
              return (
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 0.5, width: '100%' }}>
                  <span style={{ color: '#999' }}>-</span>
                  <Tooltip title={tooltipText} arrow>
                    <InfoOutlined sx={{ fontSize: 16, color: '#999', cursor: 'help' }} />
                  </Tooltip>
                </Box>
              );
            }
            return row.age ?? '-';
          },
        };
      }
      if (col.id === 'invested') return { ...col, formatValue: (v: unknown) => (v != null ? Number(v).toFixed(0) : '-') };
      if (col.id === 'average_price') return { ...col, formatValue: (v: unknown) => (v != null ? Number(v).toFixed(1) : '-') };
      if (col.id === 'last_price') return { ...col, formatValue: (v: unknown) => (v != null ? Number(v).toFixed(2) : '-') };
      if (col.id === 'quality') {
        const qualityOptions = Array.from(new Set(holdings.map((h) => h.quality).filter(Boolean))) as string[];
        return { ...col, filterOptions: qualityOptions.map((v) => ({ value: v, label: v })) };
      }
      if (col.id === 'exit_score') {
        return {
          ...col,
          renderCell: (row: HoldingDisplayRow) => {
            if (wroiTrends == null) return <UnpopulatedIcon />;
            const score = (row as any).exit_score;
            if (score == null) return <span style={{ color: '#999' }}>-</span>;
            const bg = score >= 80 ? 'rgba(76, 175, 80, 0.15)' : score >= 60 ? 'rgba(255, 193, 7, 0.15)' : score >= 40 ? 'rgba(255, 152, 0, 0.15)' : 'rgba(244, 67, 54, 0.15)';
            const fg = score >= 80 ? '#1b5e20' : score >= 60 ? '#e65100' : score >= 40 ? '#bf360c' : '#b71c1c';
            return <Box sx={{ backgroundColor: bg, color: fg, fontWeight: 600, width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>{score}</Box>;
          },
        };
      }
      return col;
    });

    const baseConfig = { ...base, columns: runtimeColumns };
    const effective = uiConfig ? uiPageConfigToTradeTableConfig<HoldingDisplayRow>('holdings', uiConfig, baseConfig as any) : (baseConfig as any);
    const mergedColumns = (effective.columns as TradeColumnDef<HoldingDisplayRow>[]).map((col) => {
      const runtime = runtimeColumns.find((c) => c.id === col.id);
      return runtime ? { ...runtime, ...col, renderCell: runtime.renderCell ?? col.renderCell, formatValue: runtime.formatValue ?? col.formatValue, filterOptions: runtime.filterOptions ?? col.filterOptions } : col;
    });
    return { ...effective, columns: mergedColumns };
  }, [uiConfig, wroiTrends, holdings]);

  const renderOrderHistorySummary = () => (
    <Typography variant="body2" color="text.secondary">
      Order History:
      {orderHistory?.available ? (
        <>
          {' '}{orderHistory.trade_count} trades • {orderHistory.symbol_count} symbols
          {orderHistory.date_from && orderHistory.date_to && <> • {formatDateRange(orderHistory.date_from, orderHistory.date_to)}</>}
        </>
      ) : (
        <span> Not fetched</span>
      )}
    </Typography>
  );

  const renderOrderHistoryMeta = () => (
    <>
      {orderHistory?.source && <Chip label={orderHistory.source === 'upstox_api' ? 'Upstox' : 'Zerodha CSV'} size="small" sx={{ height: 20, fontSize: '0.7rem' }} />}
      {orderHistory?.fetched_at && <Typography variant="caption" color="text.secondary">Updated on: {new Date(orderHistory.fetched_at).toLocaleDateString()}</Typography>}
    </>
  );

  const renderOrderHistoryControls = () => (
    <>
      <TextField type="number" size="small" value={orderHistoryDays} onChange={(e) => setOrderHistoryDays(Math.max(1, parseInt(e.target.value) || 100))} sx={{ width: 70 }} inputProps={{ min: 1, style: { padding: '4px 8px' } }} />
      {isUpstox ? (
        <Button variant="contained" size="small" startIcon={fetchingOrderHistory ? <CircularProgress size={16} color="inherit" /> : <SyncIcon />} onClick={handleFetchOrderHistory} disabled={fetchingOrderHistory}>
          {fetchingOrderHistory ? 'Fetching...' : 'Fetch'}
        </Button>
      ) : (
        <Button variant="contained" component="label" size="small" startIcon={uploadingOrderHistory ? <CircularProgress size={16} color="inherit" /> : <UploadIcon />} disabled={uploadingOrderHistory}>
          {uploadingOrderHistory ? 'Uploading...' : 'Upload'}
          <input type="file" accept=".csv" hidden onChange={handleUploadOrderHistory} />
        </Button>
      )}
      <TextField size="small" placeholder="Symbol" value={symbolSearch} onChange={(e) => setSymbolSearch(e.target.value.toUpperCase())} onKeyDown={(e) => e.key === 'Enter' && void handleSearchTrades()} sx={{ width: 120 }} inputProps={{ style: { padding: '4px 8px' } }} />
      <Button variant="outlined" size="small" onClick={() => void handleSearchTrades()} disabled={searchingTrades || !symbolSearch.trim()}>
        {searchingTrades ? '...' : 'Search'}
      </Button>
    </>
  );

  if (!sessionId) {
    return (
      <TradePageLayout header={<ResponsivePageHeader title="Holdings" />}>
        <Alert severity="warning">No active session. Please start a session from the Sessions page first.</Alert>
      </TradePageLayout>
    );
  }

  return (
    <TradePageLayout
      header={
        <ResponsivePageHeader
          title="Holdings"
          recordCount={displayHoldings.length}
          primaryAction={<Button variant="contained" startIcon={<RefreshIcon />} onClick={() => void fetchHoldings()} disabled={loading}>Refresh</Button>}
          secondaryActions={[
            { label: computingWroiTrend ? 'Computing...' : 'Calculate Trend', onClick: () => void handleComputeWroiTrend(), icon: <SyncIcon />, disabled: computingWroiTrend },
          ]}
        />
      }
      summary={
        !loading ? (
          <TradeSummaryStrip
            ariaLabel="Holdings summary"
            items={[
              { label: 'Total Holdings', value: summary.totalHoldings },
              { label: 'Total Invested', value: `₹${summary.totalInvested.toFixed(0)}` },
              { label: 'Total P/L', value: `${summary.totalProfit >= 0 ? '+' : ''}₹${summary.totalProfit.toFixed(0)}`, tone: summary.totalProfit >= 0 ? 'success' : 'error' },
              { label: 'BREAK', value: summary.breakCount, tone: summary.breakCount > 0 ? 'error' : 'default' },
            ]}
          />
        ) : undefined
      }
    >
      {error && <TradeStatusAlert kind="critical" message={error} onClose={() => setError('')} sx={{ mb: 2 }} />}
      {!orderHistory?.available && <TradeStatusAlert kind="persistent" severity="warning" message="Order history is incomplete. Age/WROI calculations may be unreliable until order history is fetched or uploaded." sx={{ mb: 2 }} />}
      {lastUpdated && <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>Last updated: {lastUpdated.toLocaleTimeString()}</Typography>}

      <Paper sx={{ p: 1.5, mb: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
          <Box sx={{ display: { xs: 'flex', sm: 'none' }, alignItems: 'center', justifyContent: 'space-between', gap: 1, width: '100%' }}>
            <Typography variant="body2" color="text.secondary" sx={{ minWidth: 0 }}>
              Order History:{orderHistory?.available ? ` ${orderHistory.trade_count} trades` : ' Not fetched'}
            </Typography>
            <Button size="small" onClick={() => setOrderHistoryExpanded((v) => !v)}>{orderHistoryExpanded ? 'Hide Details' : 'View Details'}</Button>
          </Box>
          <Box sx={{ display: { xs: 'none', sm: 'flex' }, alignItems: 'center', gap: 1, flexWrap: 'wrap', width: '100%' }}>
            {renderOrderHistorySummary()}
            {renderOrderHistoryMeta()}
            <Box sx={{ flex: 1 }} />
            {renderOrderHistoryControls()}
          </Box>
          {orderHistoryExpanded && (
            <Box sx={{ display: { xs: 'flex', sm: 'none' }, flexDirection: 'column', alignItems: 'stretch', gap: 1, width: '100%', pt: 1, borderTop: '1px solid', borderColor: 'divider' }}>
              <Typography variant="caption" color="text.secondary">
                {orderHistory?.available ? `${orderHistory.symbol_count} symbols${orderHistory.date_from && orderHistory.date_to ? ` • ${formatDateRange(orderHistory.date_from, orderHistory.date_to)}` : ''}` : 'No order history details available'}
              </Typography>
              {renderOrderHistoryMeta()}
              {renderOrderHistoryControls()}
            </Box>
          )}
        </Box>
        {fetchingOrderHistory && <LinearProgress sx={{ mt: 1 }} />}
        {searchError && <Alert severity="error" sx={{ mt: 1 }} onClose={() => setSearchError(null)}>{searchError}</Alert>}
        {(trades.length > 0 || (symbolSearch && trades.length === 0 && !searchingTrades)) && (
          <Box sx={{ mt: 2, pt: 2, borderTop: '1px solid #eee' }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
              <Typography variant="body2" color="text.secondary">
                {trades.length > 0 ? `${trades.length} trade${trades.length !== 1 ? 's' : ''} for ${symbolSearch}` : `No trades for ${symbolSearch}${orderHistory?.available ? ' in fetched history' : ''}`}
              </Typography>
              <Button size="small" onClick={() => { setSymbolSearch(''); setTrades([]); }} sx={{ minWidth: 'auto', p: 0.5 }}>✕</Button>
            </Box>
            {trades.length > 0 && (
              <Box sx={{ maxHeight: 200, overflow: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
                  <thead><tr style={{ backgroundColor: '#f5f5f5' }}>
                    <th style={{ padding: '6px', textAlign: 'left', borderBottom: '1px solid #ddd' }}>Date</th>
                    <th style={{ padding: '6px', textAlign: 'left', borderBottom: '1px solid #ddd' }}>Side</th>
                    <th style={{ padding: '6px', textAlign: 'right', borderBottom: '1px solid #ddd' }}>Qty</th>
                    <th style={{ padding: '6px', textAlign: 'right', borderBottom: '1px solid #ddd' }}>Price</th>
                    <th style={{ padding: '6px', textAlign: 'right', borderBottom: '1px solid #ddd' }}>Value</th>
                  </tr></thead>
                  <tbody>
                    {trades.map((trade, index) => (
                      <tr key={index} style={{ borderBottom: '1px solid #eee' }}>
                        <td style={{ padding: '6px' }}>{trade.trade_date || '-'}</td>
                        <td style={{ padding: '6px', color: trade.side === 'BUY' ? 'green' : 'red' }}>{trade.side}</td>
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

      {orderHistory?.skipped_symbols && orderHistory.skipped_symbols.length > 0 && (
        <Alert severity="warning" sx={{ mb: 2 }}>Skipped symbols (invalid data): {orderHistory.skipped_symbols.join(', ')}</Alert>
      )}
      {orderHistory?.errors && orderHistory.errors.length > 0 && (
        <Alert severity="info" sx={{ mb: 2 }}>
          Upload notes: {orderHistory.errors.slice(0, 5).join('; ')}{orderHistory.errors.length > 5 && ` (+${orderHistory.errors.length - 5} more)`}
        </Alert>
      )}

      <TradeDataTable<HoldingDisplayRow>
        config={tableConfig as any}
        rows={displayHoldings}
        getRowId={(row) => (row.id ?? row.symbol) as string | number}
        loading={loading}
        error={null}
        onRetry={() => void fetchHoldings()}
        emptyTitle="No holdings data"
        emptyDescription='No holdings data. Click "Refresh" to fetch holdings from your broker.'
        renderMobileCard={(row) => (
          <MobileHoldingCard
            holding={row as any}
            trendsPopulated={wroiTrends != null}
            primaryFields={tableConfig.mobilePrimaryFields}
            detailFields={tableConfig.mobileDetailFields}
          />
        )}
      />

      <Menu anchorEl={actionMenuAnchorEl} open={Boolean(actionMenuAnchorEl)} onClose={() => setActionMenuAnchorEl(null)}>
        <MenuItem onClick={() => { setActionMenuAnchorEl(null); void handleComputeWroiTrend(); }} disabled={computingWroiTrend}>
          <ListItemIcon><SyncIcon fontSize="small" /></ListItemIcon>
          <ListItemText primary={computingWroiTrend ? 'Computing...' : 'Calculate Trend'} />
        </MenuItem>
      </Menu>
    </TradePageLayout>
  );
}
