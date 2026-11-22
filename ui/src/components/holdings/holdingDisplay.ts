import type { ChipProps } from '@mui/material/Chip';
import type { AgeReason, HoldingsRow } from '../../types';

/** Display-only helpers shared by the desktop grid and mobile holding cards. */
export const AGE_REASON_MESSAGES: Record<Exclude<AgeReason, null>, string> = {
  order_history_not_fetched: 'Order history not uploaded. Upload CSV to calculate age.',
  no_trades_for_symbol: 'No trade records found for this symbol.',
  no_buy_trades: 'Only sell trades found — no buy history to calculate age from.',
  buy_trades_beyond_400_days: 'Oldest buy is >400 days old. Age capped at 400 days.',
  trade_qty_mismatch: '',
};

export const NOT_CALCULATED_TOOLTIP = "Click 'Calculate Trend' to compute";

export function formatPlainNumber(value: number | null | undefined, decimals = 2): string {
  if (value === null || value === undefined) return '-';
  return value.toFixed(decimals);
}

export function formatCurrency(
  value: number | null | undefined,
  decimals = 2,
): string {
  if (value === null || value === undefined) return '-';
  return `₹${value.toLocaleString('en-IN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })}`;
}

export function formatProfit(value: number | null | undefined): string {
  if (value === null || value === undefined) return '-';
  return `${value < 0 ? '-' : ''}₹${Math.abs(value).toFixed(0)}`;
}

export function formatProfitPct(value: number | null | undefined): string {
  if (value === null || value === undefined) return '-';
  return `${value.toFixed(1)}%`;
}

export function getSignalColor(
  action: string | null | undefined,
): NonNullable<ChipProps['color']> {
  if (action === 'HOLD') return 'success';
  if (action === 'WATCH' || action === 'REDUCE') return 'warning';
  return 'error';
}

export function getSignalVariant(
  action: string | null | undefined,
): 'filled' | 'outlined' {
  return action === 'REDUCE' ? 'outlined' : 'filled';
}

export function getWroiTrendColor(trend: string | null | undefined): string {
  if (trend === 'STRONG_UP') return '#1b5e20';
  if (trend === 'UP') return '#2e7d32';
  if (trend === 'NEUTRAL') return '#e65100';
  return '#c62828';
}

export function getExitScoreStyle(score: number | null | undefined) {
  if (score === null || score === undefined) {
    return { backgroundColor: 'transparent', color: 'text.secondary' };
  }
  if (score >= 80) {
    return { backgroundColor: 'rgba(76, 175, 80, 0.15)', color: '#1b5e20' };
  }
  if (score >= 60) {
    return { backgroundColor: 'rgba(255, 193, 7, 0.15)', color: '#e65100' };
  }
  if (score >= 40) {
    return { backgroundColor: 'rgba(255, 152, 0, 0.15)', color: '#bf360c' };
  }
  return { backgroundColor: 'rgba(244, 67, 54, 0.15)', color: '#b71c1c' };
}

export function getAgeTooltipText(holding: HoldingsRow): string {
  const reason = holding.age_reason;
  if (!reason) return '';
  let text = AGE_REASON_MESSAGES[reason] || reason;
  if (reason === 'trade_qty_mismatch') {
    if (!holding.age_trade_qty) {
      text = `No trade records found (holding: ${holding.age_holding_qty ?? '?'} shares)`;
    } else {
      text = `Trade qty (${holding.age_trade_qty}) ≠ Holding qty (${holding.age_holding_qty ?? '?'})`;
    }
  }
  return text;
}