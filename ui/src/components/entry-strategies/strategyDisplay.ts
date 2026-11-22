import type { EntryStrategySummary } from '../../types';

export interface StrategyFormValues {
  allocated: number | null;
  entry1: number | null;
  entry2: number | null;
  entry3: number | null;
}

export type StrategyFormErrors = Partial<Record<keyof StrategyFormValues, string>>;

export function formatAllocation(value: number | null | undefined): string {
  if (value === null || value === undefined) return '-';
  return `₹${value.toLocaleString()}`;
}

export function formatPrice(value: number | null | undefined): string {
  if (value === null || value === undefined) return '-';
  return `₹${value.toFixed(2)}`;
}

export function parseNumericInput(input: string): number | null {
  const cleaned = input.replace(/[₹,\s]/g, '');
  if (!cleaned) return null;
  const value = Number(cleaned);
  return Number.isFinite(value) ? value : null;
}

export function getDeltaColor(delta: number | null): string {
  if (delta === null) return 'text.secondary';
  if (delta > 5) return 'success.main';
  if (delta >= 0) return 'warning.main';
  return 'error.main';
}

export function getReviewStatusColor(status: string | null | undefined):
  | 'success'
  | 'warning'
  | 'error' {
  if (status === 'ACTIVE') return 'success';
  if (status === 'REVIEW_REQUIRED') return 'warning';
  return 'error';
}

export function getReviewStatusLabel(status: string | null | undefined): string {
  if (!status) return '-';
  return status.replace(/_/g, ' ');
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return '-';
  return new Date(value).toLocaleDateString();
}

/** Mirrors the backend inline-update descending sort for display after a save. */
export function sortEntryValues(
  entry1: number | null,
  entry2: number | null,
  entry3: number | null,
): Pick<StrategyFormValues, 'entry1' | 'entry2' | 'entry3'> {
  const values = [entry1, entry2, entry3]
    .filter((value): value is number => value != null)
    .sort((a, b) => b - a);
  return {
    entry1: values[0] ?? entry1,
    entry2: values[1] ?? entry2,
    entry3: values[2] ?? entry3,
  };
}

export function validateStrategyForm(values: StrategyFormValues): StrategyFormErrors {
  const errors: StrategyFormErrors = {};
  if (values.allocated === null || values.allocated <= 0) {
    errors.allocated = 'Allocation must be greater than 0';
  }
  if (values.entry1 === null || values.entry1 <= 0) {
    errors.entry1 = 'Entry 1 must be greater than 0';
  }
  if (values.entry2 !== null && values.entry2 <= 0) {
    errors.entry2 = 'Entry 2 must be greater than 0';
  }
  if (values.entry3 !== null && values.entry3 <= 0) {
    errors.entry3 = 'Entry 3 must be greater than 0';
  }
  if (values.entry1 !== null && values.entry2 !== null && values.entry2 >= values.entry1) {
    errors.entry2 = 'Entry 2 must be lower than Entry 1';
  }
  if (values.entry2 !== null && values.entry3 !== null && values.entry3 >= values.entry2) {
    errors.entry3 = 'Entry 3 must be lower than Entry 2';
  }
  return errors;
}

export function getSwingFailureReasons(strategy: EntryStrategySummary): string[] {
  return strategy.swing_reasons ?? [];
}