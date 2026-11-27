import { useCallback, useMemo, useState } from 'react';
import type { GridValidRowModel } from '@mui/x-data-grid';
import { getAllowedOperators, resolveTradeTableConfig } from './config';
import type {
  TradeColumnDef,
  TradeFilterRule,
  TradeSortState,
  TradeTableConfig,
  TradeTableResolvedConfig,
} from './types';

export function getColumnValue<T extends GridValidRowModel>(
  row: T,
  column: Pick<TradeColumnDef<T>, 'id' | 'valueGetter'>,
): unknown {
  if (column.valueGetter) return column.valueGetter(row);
  return (row as Record<string, unknown>)[column.id];
}

function normalizeText(value: unknown): string {
  if (value == null) return '';
  return String(value).trim().toLowerCase();
}

function toNumber(value: unknown): number | null {
  if (value == null || value === '') return null;
  const num = typeof value === 'number' ? value : Number(String(value).replace(/,/g, ''));
  return Number.isFinite(num) ? num : null;
}

function toTimestamp(value: unknown): number | null {
  if (value == null || value === '') return null;
  if (value instanceof Date) {
    const ts = value.getTime();
    return Number.isNaN(ts) ? null : ts;
  }
  if (typeof value === 'number') {
    return Number.isFinite(value) ? value : null;
  }
  const ts = Date.parse(String(value));
  return Number.isNaN(ts) ? null : ts;
}

function matchesRule<T extends GridValidRowModel>(row: T, column: TradeColumnDef<T>, rule: TradeFilterRule): boolean {
  if (!getAllowedOperators(column.dataType).includes(rule.operator)) return true;
  const raw = getColumnValue(row, column);

  switch (column.dataType) {
    case 'text': {
      const value = normalizeText(rule.value);
      if (!value) return true;
      const text = normalizeText(raw);
      if (rule.operator === 'equals') return text === value;
      return text.includes(value);
    }
    case 'number': {
      const num = toNumber(raw);
      if (rule.operator === 'between') {
        const min = toNumber(rule.value);
        const max = toNumber(rule.valueTo);
        if (min == null && max == null) return true;
        if (num == null) return false;
        if (min != null && num < min) return false;
        if (max != null && num > max) return false;
        return true;
      }
      const target = toNumber(rule.value);
      if (target == null) return true;
      if (num == null) return false;
      if (rule.operator === 'gt') return num > target;
      if (rule.operator === 'lt') return num < target;
      return true;
    }
    case 'date': {
      const ts = toTimestamp(raw);
      if (rule.operator === 'between') {
        const start = toTimestamp(rule.value);
        const end = toTimestamp(rule.valueTo);
        if (start == null && end == null) return true;
        if (ts == null) return false;
        if (start != null && ts < start) return false;
        if (end != null && ts > end + 24 * 60 * 60 * 1000 - 1) return false;
        return true;
      }
      const target = toTimestamp(rule.value);
      if (target == null) return true;
      if (ts == null) return false;
      if (rule.operator === 'before') return ts < target;
      if (rule.operator === 'after') return ts > target;
      return true;
    }
    case 'boolean': {
      if (rule.operator !== 'is' || typeof rule.value !== 'boolean') return true;
      if (typeof raw === 'boolean') return raw === rule.value;
      const text = normalizeText(raw);
      if (text === 'true' || text === 'yes' || text === '1') return rule.value === true;
      if (text === 'false' || text === 'no' || text === '0') return rule.value === false;
      return false;
    }
    case 'categorical': {
      if (rule.operator !== 'in') return true;
      const values = rule.values ?? [];
      if (values.length === 0) return true;
      const text = normalizeText(raw);
      return values.some((value) => normalizeText(value) === text);
    }
    default:
      return true;
  }
}

export function applyTradeFilters<T extends GridValidRowModel>(
  rows: T[],
  filters: TradeFilterRule[],
  columns: TradeColumnDef<T>[],
): T[] {
  if (filters.length === 0) return rows;
  const byId = new Map(columns.map((col) => [col.id, col]));
  const active = filters.filter((rule) => {
    const col = byId.get(rule.columnId);
    return Boolean(col && col.filterable);
  });
  if (active.length === 0) return rows;
  return rows.filter((row) =>
    active.every((rule) => {
      const col = byId.get(rule.columnId);
      return col ? matchesRule(row, col, rule) : true;
    }),
  );
}

export function applyTradeSearch<T extends GridValidRowModel>(
  rows: T[],
  search: string,
  config: TradeTableResolvedConfig<T>,
): T[] {
  if (!config.searchEnabled || !config.searchField) return rows;
  const q = normalizeText(search);
  if (!q) return rows;
  const col = config.columns.find((c) => c.id === config.searchField);
  if (!col) return rows;
  return rows.filter((row) => normalizeText(getColumnValue(row, col)).includes(q));
}

export function compareTradeValues(a: unknown, b: unknown, dataType: TradeColumnDef['dataType']): number {
  if (a == null && b == null) return 0;
  if (a == null) return 1; // missing last
  if (b == null) return -1;

  if (dataType === 'number') {
    const na = toNumber(a);
    const nb = toNumber(b);
    if (na == null && nb == null) return 0;
    if (na == null) return 1;
    if (nb == null) return -1;
    return na - nb;
  }
  if (dataType === 'date') {
    const ta = toTimestamp(a);
    const tb = toTimestamp(b);
    if (ta == null && tb == null) return 0;
    if (ta == null) return 1;
    if (tb == null) return -1;
    return ta - tb;
  }
  if (dataType === 'boolean') {
    const ba = a === true ? 1 : 0;
    const bb = b === true ? 1 : 0;
    return ba - bb;
  }
  return String(a).localeCompare(String(b), undefined, { numeric: true, sensitivity: 'base' });
}

export function applyTradeSort<T extends GridValidRowModel>(
  rows: T[],
  sort: TradeSortState | null,
  columns: TradeColumnDef<T>[],
): T[] {
  if (!sort?.field || !sort.direction) return rows;
  const column = columns.find((c) => c.id === sort.field);
  if (!column || !column.sortable) return rows;
  const dir = sort.direction === 'asc' ? 1 : -1;
  return [...rows].sort((a, b) => dir * compareTradeValues(getColumnValue(a, column), getColumnValue(b, column), column.dataType));
}

export interface UseTradeTableStateOptions<T extends GridValidRowModel> {
  config: TradeTableConfig<T>;
  rows: T[];
  getRowId: (row: T) => string | number;
}

export function useTradeTableState<T extends GridValidRowModel>({
  config,
  rows,
  getRowId,
}: UseTradeTableStateOptions<T>) {
  const resolved = useMemo(() => resolveTradeTableConfig(config), [config]);
  const [sort, setSort] = useState<TradeSortState | null>(resolved.defaultSort);
  const [filters, setFilters] = useState<TradeFilterRule[]>([]);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(resolved.defaultPageSize);
  const [selectedIds, setSelectedIds] = useState<Array<string | number>>([]);
  const [columnVisibility, setColumnVisibility] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(resolved.columns.map((c) => [c.id, c.visible])),
  );
  const [columnOrder, setColumnOrder] = useState<string[]>(() => resolved.columns.map((c) => c.id));

  const visibleColumnIds = useMemo(
    () => columnOrder.filter((id) => columnVisibility[id] !== false),
    [columnOrder, columnVisibility],
  );

  const searchedRows = useMemo(() => applyTradeSearch(rows, search, resolved), [rows, search, resolved]);
  const filteredRows = useMemo(
    () => applyTradeFilters(searchedRows, filters, resolved.columns),
    [searchedRows, filters, resolved.columns],
  );
  const sortedRows = useMemo(
    () => applyTradeSort(filteredRows, sort, resolved.columns),
    [filteredRows, sort, resolved.columns],
  );

  const activeFilterCount = filters.length;

  const toggleSort = useCallback(
    (field: string) => {
      const column = resolved.columns.find((c) => c.id === field);
      if (!column?.sortable) return;
      setSort((prev) => {
        if (!prev || prev.field !== field) return { field, direction: 'asc' };
        if (prev.direction === 'asc') return { field, direction: 'desc' };
        return resolved.defaultSort?.field === field ? { field, direction: 'asc' } : null;
      });
      setPage(0);
    },
    [resolved.columns, resolved.defaultSort],
  );

  const updateFilter = useCallback((rule: TradeFilterRule) => {
    setFilters((prev) => {
      const idx = prev.findIndex((r) => r.columnId === rule.columnId);
      if (idx === -1) return [...prev, rule];
      const next = [...prev];
      next[idx] = rule;
      return next;
    });
    setPage(0);
  }, []);

  const removeFilter = useCallback((columnId: string) => {
    setFilters((prev) => prev.filter((r) => r.columnId !== columnId));
    setPage(0);
  }, []);

  const clearFilters = useCallback(() => {
    setFilters([]);
    setPage(0);
  }, []);

  const setSearchValue = useCallback((value: string) => {
    setSearch(value);
    setPage(0);
  }, []);

  const setColumnVisible = useCallback((columnId: string, visible: boolean) => {
    setColumnVisibility((prev) => {
      const col = resolved.columns.find((c) => c.id === columnId);
      if (!col || (col.required && !visible)) return prev;
      return { ...prev, [columnId]: visible };
    });
  }, [resolved.columns]);

  const setColumnOrderSafe = useCallback((order: string[]) => {
    const known = new Set(resolved.columns.map((c) => c.id));
    const filtered = order.filter((id) => known.has(id));
    for (const col of resolved.columns) if (!filtered.includes(col.id)) filtered.push(col.id);
    setColumnOrder(filtered);
  }, [resolved.columns]);

  const resetColumns = useCallback(() => {
    setColumnVisibility(Object.fromEntries(resolved.columns.map((c) => [c.id, c.visible])));
    setColumnOrder(resolved.columns.map((c) => c.id));
  }, [resolved.columns]);

  // Reconcile selection when underlying data changes.
  const validIds = useMemo(() => new Set(rows.map(getRowId)), [rows, getRowId]);
  const reconciledSelectedIds = useMemo(
    () => selectedIds.filter((id) => validIds.has(id)),
    [selectedIds, validIds],
  );

  const clearSelection = useCallback(() => setSelectedIds([]), []);

  return {
    config: resolved,
    rows,
    searchedRows,
    filteredRows,
    sortedRows,
    sort,
    setSort,
    toggleSort,
    filters,
    setFilters,
    updateFilter,
    removeFilter,
    clearFilters,
    activeFilterCount,
    search,
    setSearch: setSearchValue,
    page,
    setPage,
    pageSize,
    setPageSize: (size: number) => {
      if (resolved.allowedPageSizes.includes(size)) {
        setPageSize(size);
        setPage(0);
      }
    },
    selectedIds: reconciledSelectedIds,
    setSelectedIds,
    clearSelection,
    columnVisibility,
    setColumnVisible,
    columnOrder,
    setColumnOrder: setColumnOrderSafe,
    visibleColumnIds,
    resetColumns,
  };
}