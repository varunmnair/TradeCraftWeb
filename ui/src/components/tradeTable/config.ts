import type { GridValidRowModel } from '@mui/x-data-grid';
import type {
  TradeColumnDataType,
  TradeColumnDef,
  TradeFilterOperator,
  TradeSortState,
  TradeTableConfig,
  TradeTableResolvedConfig,
} from './types';

export const DEFAULT_PAGE_SIZES = [25, 50, 100] as const;
export const DEFAULT_PAGE_SIZE = 25;
export const DEFAULT_DENSITY: TradeTableResolvedConfig['density'] = 'compact';

const OPERATORS_BY_TYPE: Record<TradeColumnDataType, TradeFilterOperator[]> = {
  text: ['contains', 'equals'],
  number: ['gt', 'lt', 'between'],
  date: ['before', 'after', 'between'],
  boolean: ['is'],
  categorical: ['in'],
};

export function getAllowedOperators(dataType: TradeColumnDataType): TradeFilterOperator[] {
  return OPERATORS_BY_TYPE[dataType];
}

export function canSortColumn(column: Pick<TradeColumnDef, 'sortable' | 'id'>): boolean {
  return Boolean(column.sortable);
}

export function canFilterColumn(column: Pick<TradeColumnDef, 'filterable' | 'id'>): boolean {
  return Boolean(column.filterable);
}

export function isFilterOperatorAllowed(
  dataType: TradeColumnDataType,
  operator: TradeFilterOperator,
): boolean {
  return getAllowedOperators(dataType).includes(operator);
}

function normalizePageSizes(sizes: number[] | undefined): number[] {
  const input = sizes && sizes.length > 0 ? sizes : [...DEFAULT_PAGE_SIZES];
  const valid = Array.from(
    new Set(input.filter((size) => Number.isInteger(size) && size > 0)),
  ).sort((a, b) => a - b);
  return valid.length > 0 ? valid : [...DEFAULT_PAGE_SIZES];
}

function normalizeDefaultPageSize(defaultPageSize: number | undefined, allowed: number[]): number {
  if (defaultPageSize && allowed.includes(defaultPageSize)) return defaultPageSize;
  if (allowed.includes(DEFAULT_PAGE_SIZE)) return DEFAULT_PAGE_SIZE;
  return allowed[0];
}

function normalizeColumns<T extends GridValidRowModel>(
  columns: TradeColumnDef<T>[],
): TradeColumnDef<T>[] {
  const seen = new Set<string>();
  const normalized: TradeColumnDef<T>[] = [];

  for (const col of columns) {
    if (!col.id || seen.has(col.id)) continue;
    seen.add(col.id);
    const required = Boolean(col.required);
    normalized.push({
      ...col,
      visible: required ? true : Boolean(col.visible),
      sortable: Boolean(col.sortable),
      filterable: Boolean(col.filterable),
      position: Number.isFinite(col.position) ? col.position : normalized.length,
      alignment:
        col.alignment ?? (col.dataType === 'number' ? 'right' : 'left'),
      minWidth: col.minWidth ?? (col.width ? undefined : 90),
    });
  }

  normalized.sort((a, b) => {
    if (a.position !== b.position) return a.position - b.position;
    return a.id.localeCompare(b.id);
  });

  return normalized.map((col, index) => ({ ...col, position: index }));
}

function normalizeSort<T extends GridValidRowModel>(
  sort: TradeSortState | null | undefined,
  columns: TradeColumnDef<T>[],
): TradeSortState | null {
  if (!sort?.field) return null;
  const column = columns.find((col) => col.id === sort.field);
  if (!column || !canSortColumn(column)) return null;
  if (sort.direction !== 'asc' && sort.direction !== 'desc') return null;
  return { field: sort.field, direction: sort.direction };
}

function normalizeFieldList<T extends GridValidRowModel>(
  fieldIds: string[] | undefined,
  columns: TradeColumnDef<T>[],
  key: 'mobilePrimary' | 'mobileDetail',
): string[] {
  const validIds = new Set(columns.map((col) => col.id));
  const fromConfig = (fieldIds ?? []).filter((id) => validIds.has(id));
  if (fromConfig.length > 0) return Array.from(new Set(fromConfig));
  const fromColumns = columns.filter((col) => col[key]).map((col) => col.id);
  return Array.from(new Set(fromColumns));
}

export function resolveTradeTableConfig<T extends GridValidRowModel>(
  config: TradeTableConfig<T>,
): TradeTableResolvedConfig<T> {
  const columns = normalizeColumns(config.columns ?? []);
  const allowedPageSizes = normalizePageSizes(config.allowedPageSizes);
  const defaultPageSize = normalizeDefaultPageSize(config.defaultPageSize, allowedPageSizes);
  const searchEnabled = Boolean(config.searchEnabled && config.searchField);
  const searchField =
    searchEnabled && config.searchField && columns.some((c) => c.id === config.searchField)
      ? config.searchField
      : undefined;

  const mobilePrimaryFields = normalizeFieldList(config.mobilePrimaryFields, columns, 'mobilePrimary');
  const mobileDetailFields = normalizeFieldList(config.mobileDetailFields, columns, 'mobileDetail').filter(
    (id) => !mobilePrimaryFields.includes(id),
  );

  return {
    pageId: config.pageId,
    columns,
    searchEnabled: Boolean(searchEnabled && searchField),
    searchField,
    defaultSort: normalizeSort(config.defaultSort, columns),
    defaultPageSize,
    allowedPageSizes,
    density: config.density ?? DEFAULT_DENSITY,
    selectionEnabled: Boolean(config.selectionEnabled),
    mobilePrimaryFields,
    mobileDetailFields,
  };
}

export function getVisibleOrderedColumns<T extends GridValidRowModel>(
  config: TradeTableResolvedConfig<T>,
): TradeColumnDef<T>[] {
  return config.columns.filter((col) => col.visible && !col.tableHidden);
}

export function getFilterableColumns<T extends GridValidRowModel>(
  config: TradeTableResolvedConfig<T>,
): TradeColumnDef<T>[] {
  return config.columns.filter((col) => col.filterable && !col.tableHidden);
}

export function getSortableColumns<T extends GridValidRowModel>(
  config: TradeTableResolvedConfig<T>,
): TradeColumnDef<T>[] {
  return config.columns.filter((col) => col.sortable && !col.tableHidden);
}