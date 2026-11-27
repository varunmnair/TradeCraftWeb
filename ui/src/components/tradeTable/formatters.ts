export const MISSING_VALUE = '—';

export function formatMissing(value: unknown): string {
  if (value == null || value === '') return MISSING_VALUE;
  return String(value);
}

export function formatCurrency(
  value: unknown,
  options?: { currency?: string; maximumFractionDigits?: number; minimumFractionDigits?: number },
): string {
  if (value == null || value === '') return MISSING_VALUE;
  const num = typeof value === 'number' ? value : Number(String(value).replace(/,/g, ''));
  if (!Number.isFinite(num)) return MISSING_VALUE;
  const currency = options?.currency ?? 'INR';
  const maximumFractionDigits = options?.maximumFractionDigits ?? 2;
  const minimumFractionDigits = options?.minimumFractionDigits ?? 0;
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency,
    maximumFractionDigits,
    minimumFractionDigits,
  }).format(num);
}

export function formatNumber(
  value: unknown,
  options?: Intl.NumberFormatOptions,
): string {
  if (value == null || value === '') return MISSING_VALUE;
  const num = typeof value === 'number' ? value : Number(String(value).replace(/,/g, ''));
  if (!Number.isFinite(num)) return MISSING_VALUE;
  return new Intl.NumberFormat('en-IN', options).format(num);
}

export function formatPercent(value: unknown, digits = 2): string {
  if (value == null || value === '') return MISSING_VALUE;
  const num = typeof value === 'number' ? value : Number(String(value).replace(/,/g, ''));
  if (!Number.isFinite(num)) return MISSING_VALUE;
  const sign = num > 0 ? '+' : '';
  return `${sign}${num.toFixed(digits)}%`;
}

export function formatDateValue(value: unknown): string {
  if (value == null || value === '') return MISSING_VALUE;
  const date = value instanceof Date ? value : new Date(String(value));
  if (Number.isNaN(date.getTime())) return MISSING_VALUE;
  return date.toLocaleDateString('en-IN', {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
  });
}

export function signedValueColor(value: unknown): 'success.main' | 'error.main' | 'text.primary' {
  const num = typeof value === 'number' ? value : Number(String(value).replace(/,/g, ''));
  if (!Number.isFinite(num) || num === 0) return 'text.primary';
  return num > 0 ? 'success.main' : 'error.main';
}