import type { CandidateStatus, NormalizedCandidate } from '../../types';

export const candidateStatusColor: Record<
  string,
  'success' | 'warning' | 'info' | 'error' | 'default'
> = {
  READY: 'success',
  WARNING: 'warning',
  REVIEW: 'info',
  SKIPPED: 'error',
};

export const candidateStrategyLabel: Record<string, string> = {
  MULTI_LEVEL: 'MLE',
  DYNAMIC_AVERAGING: 'DA',
  SIP: 'SIP',
};

export const candidateStrategyColor: Record<string, 'primary' | 'secondary' | 'default'> = {
  MULTI_LEVEL: 'primary',
  DYNAMIC_AVERAGING: 'secondary',
  SIP: 'default',
};

export function fmt(value: number | null | undefined, decimals = 2): string {
  if (value == null) return '-';
  return value.toLocaleString('en-IN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

export function fmtCurrency(value: number | null | undefined): string {
  if (value == null) return '-';
  return `₹${fmt(value, 0)}`;
}

/** Actual value used by the order review, derived from the backend order price and qty. */
export function getActualOrderValue(candidate: NormalizedCandidate): number {
  if (candidate.order_price != null) return candidate.qty * candidate.order_price;
  return candidate.amount;
}

export function candidateKey(candidate: NormalizedCandidate): string {
  return [candidate.symbol, candidate.strategy_type, candidate.level_or_leg]
    .filter(Boolean)
    .join('::');
}

export function canSelectCandidate(
  candidate: NormalizedCandidate,
  hasActiveOrder: boolean,
): boolean {
  return candidate.is_selectable && !hasActiveOrder;
}

export function getLevelLabel(candidate: NormalizedCandidate): string {
  return candidate.level_or_leg || '-';
}

export function getDeltaPercent(
  cmp: number | null,
  entry: number | null,
): number | null {
  if (cmp == null || entry == null || entry === 0) return null;
  return ((cmp - entry) / entry) * 100;
}

export function formatDelta(delta: number | null): string {
  if (delta == null) return '-';
  return `${delta >= 0 ? '+' : ''}${delta.toFixed(1)}%`;
}

export function isReady(candidate: NormalizedCandidate): boolean {
  return candidate.status === 'READY';
}

export function isStatus(status: CandidateStatus | string, filter: string): boolean {
  if (filter === 'ALL') return true;
  return status === filter;
}