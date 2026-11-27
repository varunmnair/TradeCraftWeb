import type { GridValidRowModel } from '@mui/x-data-grid';
import type { ReactNode } from 'react';

export type TradeColumnDataType = 'text' | 'number' | 'date' | 'boolean' | 'categorical';

export type TradeColumnAlignment = 'left' | 'right' | 'center';

export type TradeTextFilterOperator = 'contains' | 'equals';
export type TradeNumberFilterOperator = 'gt' | 'lt' | 'between';
export type TradeDateFilterOperator = 'before' | 'after' | 'between';
export type TradeBooleanFilterOperator = 'is';
export type TradeCategoricalFilterOperator = 'in';

export type TradeFilterOperator =
  | TradeTextFilterOperator
  | TradeNumberFilterOperator
  | TradeDateFilterOperator
  | TradeBooleanFilterOperator
  | TradeCategoricalFilterOperator;

export interface TradeFilterRule {
  columnId: string;
  operator: TradeFilterOperator;
  /** Single value for most operators. */
  value?: string | number | boolean | null;
  /** Second value for between operators. */
  valueTo?: string | number | null;
  /** Values for categorical multi-select. */
  values?: Array<string | number | boolean>;
}

export interface TradeColumnDef<T extends GridValidRowModel = GridValidRowModel> {
  id: string;
  label: string;
  dataType: TradeColumnDataType;
  visible: boolean;
  sortable: boolean;
  filterable: boolean;
  position: number;
  width?: number;
  minWidth?: number;
  flex?: number;
  alignment?: TradeColumnAlignment;
  /** Required columns must remain available and cannot be hidden. */
  required?: boolean;
  /** Field shown prominently on mobile cards. */
  mobilePrimary?: boolean;
  /** Field shown in mobile detail/expanded area. */
  mobileDetail?: boolean;
  /** Categorical filter options; if omitted, options can be derived from data. */
  filterOptions?: Array<{ label: string; value: string | number | boolean }>;
  /** Custom display formatter. Must be presentation-only. */
  formatValue?: (value: unknown, row: T) => ReactNode;
  /** Raw value accessor when the field is not a direct row property. */
  valueGetter?: (row: T) => unknown;
  /** Disable selection for specific rows when selection is enabled. */
  selectable?: (row: T) => boolean;
  /** Render cell in DataGrid; use for existing specialized presentation. */
  renderCell?: (row: T) => ReactNode;
  /** Hide from DataGrid columns but keep in config/mobile metadata. */
  tableHidden?: boolean;
}

export interface TradeSortState {
  field: string;
  direction: 'asc' | 'desc';
}

export interface TradeTableConfig<T extends GridValidRowModel = GridValidRowModel> {
  pageId: string;
  columns: TradeColumnDef<T>[];
  searchEnabled?: boolean;
  searchField?: string;
  defaultSort?: TradeSortState | null;
  defaultPageSize?: number;
  allowedPageSizes?: number[];
  density?: 'compact' | 'standard' | 'comfortable';
  selectionEnabled?: boolean;
  mobilePrimaryFields?: string[];
  mobileDetailFields?: string[];
}

export interface TradeTableResolvedConfig<T extends GridValidRowModel = GridValidRowModel>
  extends Required<
    Pick<
      TradeTableConfig<T>,
      | 'pageId'
      | 'searchEnabled'
      | 'defaultPageSize'
      | 'allowedPageSizes'
      | 'density'
      | 'selectionEnabled'
      | 'mobilePrimaryFields'
      | 'mobileDetailFields'
    >
  > {
  columns: TradeColumnDef<T>[];
  searchField?: string;
  defaultSort: TradeSortState | null;
}

export interface TradePageTableRegistryEntry<T extends GridValidRowModel = GridValidRowModel> {
  pageId: string;
  config: TradeTableConfig<T>;
  /** Human description for maintainers/admin tooling. */
  description?: string;
}

export interface TradeSelectionAction {
  label: string;
  icon?: ReactNode;
  onClick: (selectedIds: Array<string | number>) => void;
  color?: 'primary' | 'secondary' | 'error' | 'warning' | 'info' | 'success' | 'inherit';
  variant?: 'text' | 'outlined' | 'contained';
  disabled?: boolean;
  /** Secondary actions may be moved to overflow on compact layouts. */
  priority?: 'primary' | 'secondary';
}

export interface TradeTableState {
  sort: TradeSortState | null;
  filters: TradeFilterRule[];
  search: string;
  visibleColumnIds: string[];
  columnOrder: string[];
  page: number;
  pageSize: number;
  selectedIds: Array<string | number>;
}