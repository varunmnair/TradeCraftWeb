import type { TradeTableConfig } from '../components/tradeTable/types';

export interface TradeTableRegistryEntry {
  pageId: string;
  description: string;
  config: TradeTableConfig;
}

/**
 * Static, serializable table configuration registry. Phase 3 will move
 * persistence/admin editing to the backend while keeping this shape compatible.
 */
export const tradeTableRegistry: Record<string, TradeTableRegistryEntry> = {
  jobs: {
    pageId: 'jobs',
    description: 'Background jobs list',
    config: {
      pageId: 'jobs',
      searchEnabled: false,
      defaultSort: { field: 'created_at', direction: 'desc' },
      defaultPageSize: 25,
      allowedPageSizes: [25, 50, 100],
      density: 'compact',
      selectionEnabled: true,
      mobilePrimaryFields: ['job_type', 'status'],
      mobileDetailFields: ['id', 'session_id', 'progress', 'created_at'],
      columns: [
        { id: 'id', label: 'ID', dataType: 'number', visible: true, sortable: true, filterable: true, position: 0, width: 90, alignment: 'right', mobilePrimary: false, mobileDetail: true },
        { id: 'job_type', label: 'Type', dataType: 'categorical', visible: true, sortable: true, filterable: true, position: 1, width: 180, mobilePrimary: true },
        { id: 'session_id', label: 'Session', dataType: 'text', visible: true, sortable: true, filterable: true, position: 2, minWidth: 160, mobileDetail: true },
        { id: 'status', label: 'Status', dataType: 'categorical', visible: true, sortable: true, filterable: true, position: 3, width: 140, mobilePrimary: true },
        { id: 'progress', label: 'Progress', dataType: 'number', visible: true, sortable: true, filterable: true, position: 4, width: 110, alignment: 'right', mobileDetail: true },
        { id: 'created_at', label: 'Created', dataType: 'date', visible: true, sortable: true, filterable: true, position: 5, minWidth: 180, mobileDetail: true },
      ],
    },
  },

  holdings: {
    pageId: 'holdings',
    description: 'Holdings analysis table',
    config: {
      pageId: 'holdings',
      searchEnabled: false,
      defaultSort: { field: 'weighted_roi', direction: 'desc' },
      defaultPageSize: 25,
      allowedPageSizes: [25, 50, 100],
      density: 'compact',
      selectionEnabled: false,
      mobilePrimaryFields: ['symbol', 'exit_action', 'profit_pct'],
      mobileDetailFields: ['quantity', 'average_price', 'last_price', 'invested', 'profit'],
      columns: [
        { id: 'symbol', label: 'Symbol', dataType: 'text', visible: true, sortable: true, filterable: true, position: 0, width: 120, required: true, mobilePrimary: true },
        { id: 'exit_action', label: 'Signal', dataType: 'categorical', visible: true, sortable: true, filterable: true, position: 1, width: 120, mobilePrimary: true },
        { id: 'weighted_roi', label: 'WTD ROI', dataType: 'number', visible: true, sortable: true, filterable: true, position: 2, width: 100, alignment: 'right' },
        { id: 'wroi_trend', label: 'Trend', dataType: 'categorical', visible: true, sortable: true, filterable: true, position: 3, width: 110 },
        { id: 'profit', label: 'Profit', dataType: 'number', visible: true, sortable: true, filterable: true, position: 4, width: 100, alignment: 'right', mobileDetail: true },
        { id: 'profit_pct', label: 'Profit%', dataType: 'number', visible: true, sortable: true, filterable: true, position: 5, width: 90, alignment: 'right', mobilePrimary: true },
        { id: 'profit_per_day', label: 'Pr/Day', dataType: 'number', visible: true, sortable: true, filterable: true, position: 6, width: 100, alignment: 'right' },
        { id: 'age', label: 'Age', dataType: 'number', visible: true, sortable: true, filterable: true, position: 7, width: 80, alignment: 'right' },
        { id: 'invested', label: 'Invested', dataType: 'number', visible: true, sortable: true, filterable: true, position: 8, width: 100, alignment: 'right', mobileDetail: true },
        { id: 'quantity', label: 'Qty', dataType: 'number', visible: true, sortable: true, filterable: true, position: 9, width: 70, alignment: 'right', mobileDetail: true },
        { id: 'average_price', label: 'Avg Price', dataType: 'number', visible: true, sortable: true, filterable: true, position: 10, width: 100, alignment: 'right', mobileDetail: true },
        { id: 'last_price', label: 'CMP', dataType: 'number', visible: true, sortable: true, filterable: true, position: 11, width: 90, alignment: 'right', mobileDetail: true },
        { id: 'quality', label: 'Quality', dataType: 'categorical', visible: true, sortable: true, filterable: true, position: 12, width: 90 },
        { id: 'exit_score', label: 'Score', dataType: 'number', visible: true, sortable: true, filterable: true, position: 13, width: 80, alignment: 'right' },
      ],
    },
  },
  entry_strategies: {
    pageId: 'entry_strategies',
    description: 'Entry strategies table',
    config: {
      pageId: 'entry_strategies',
      searchEnabled: false,
      defaultSort: null,
      defaultPageSize: 25,
      allowedPageSizes: [25, 50, 100],
      density: 'compact',
      selectionEnabled: true,
      mobilePrimaryFields: ['symbol', 'review_status', 'delta_pct'],
      mobileDetailFields: ['allocated', 'cmp', 'updated_at'],
      columns: [
        { id: 'symbol', label: 'Symbol', dataType: 'text', visible: true, sortable: true, filterable: true, position: 0, width: 120, required: true, mobilePrimary: true },
        { id: 'delta_pct', label: 'Delta %', dataType: 'number', visible: true, sortable: true, filterable: true, position: 1, width: 100, alignment: 'right' },
        { id: 'allocated', label: 'Allocation', dataType: 'number', visible: true, sortable: true, filterable: true, position: 2, width: 110, alignment: 'right', mobileDetail: true },
        { id: 'entry1', label: 'Entry 1', dataType: 'number', visible: true, sortable: true, filterable: true, position: 3, width: 100, alignment: 'right' },
        { id: 'entry2', label: 'Entry 2', dataType: 'number', visible: true, sortable: true, filterable: true, position: 4, width: 100, alignment: 'right' },
        { id: 'entry3', label: 'Entry 3', dataType: 'number', visible: true, sortable: true, filterable: true, position: 5, width: 100, alignment: 'right' },
        { id: 'swing_eligible', label: 'Swing', dataType: 'boolean', visible: true, sortable: true, filterable: true, position: 6, width: 90 },
        { id: 'review_status', label: 'Review Status', dataType: 'categorical', visible: true, sortable: true, filterable: true, position: 7, width: 140, mobilePrimary: true },
        { id: 'updated_at', label: 'Updated', dataType: 'date', visible: true, sortable: true, filterable: true, position: 8, width: 140, mobileDetail: true },
        { id: 'cmp', label: 'CMP', dataType: 'number', visible: true, sortable: true, filterable: true, position: 9, width: 100, alignment: 'right', mobileDetail: true },
      ],
    },
  },
  entry_candidates: {
    pageId: 'entry_candidates',
    description: 'Entry candidates review table',
    config: {
      pageId: 'entry_candidates',
      searchEnabled: false,
      defaultSort: null,
      defaultPageSize: 25,
      allowedPageSizes: [25, 50, 100],
      density: 'compact',
      selectionEnabled: true,
      mobilePrimaryFields: ['symbol', 'status', 'amount'],
      mobileDetailFields: ['strategy', 'cmp', 'trigger', 'qty'],
      columns: [
        { id: 'symbol', label: 'Symbol', dataType: 'text', visible: true, sortable: true, filterable: true, position: 0, width: 120, required: true, mobilePrimary: true },
        { id: 'strategy', label: 'Strategy', dataType: 'categorical', visible: true, sortable: true, filterable: true, position: 1, width: 120, mobileDetail: true },
        { id: 'signal', label: 'Signal', dataType: 'categorical', visible: true, sortable: true, filterable: true, position: 2, width: 110 },
        { id: 'cmp', label: 'CMP', dataType: 'number', visible: true, sortable: true, filterable: true, position: 3, width: 100, alignment: 'right', mobileDetail: true },
        { id: 'trigger', label: 'Trigger', dataType: 'number', visible: true, sortable: true, filterable: true, position: 4, width: 100, alignment: 'right', mobileDetail: true },
        { id: 'qty', label: 'Qty', dataType: 'number', visible: true, sortable: true, filterable: true, position: 5, width: 80, alignment: 'right', mobileDetail: true },
        { id: 'amount', label: 'Amount', dataType: 'number', visible: true, sortable: true, filterable: true, position: 6, width: 110, alignment: 'right', mobilePrimary: true },
        { id: 'delta_vs_entry', label: 'Δ vs Entry', dataType: 'number', visible: true, sortable: true, filterable: true, position: 7, width: 110, alignment: 'right' },
        { id: 'status', label: 'Status', dataType: 'categorical', visible: true, sortable: true, filterable: true, position: 8, width: 120, mobilePrimary: true },
      ],
    },
  },

  buy_orders: {
    pageId: 'buy_orders',
    description: 'Buy orders / GTT table',
    config: {
      pageId: 'buy_orders',
      searchEnabled: false,
      defaultSort: null,
      defaultPageSize: 25,
      allowedPageSizes: [25, 50, 100],
      density: 'compact',
      selectionEnabled: true,
      mobilePrimaryFields: ['Symbol', 'Status', 'Trigger Price'],
      mobileDetailFields: ['Qty', 'LTP', 'Variance (%)', 'Buy Amount'],
      columns: [
        { id: 'GTT ID', label: 'GTT ID', dataType: 'text', visible: true, sortable: true, filterable: true, position: 0, width: 100 },
        { id: 'Symbol', label: 'Symbol', dataType: 'text', visible: true, sortable: true, filterable: true, position: 1, width: 120, required: true, mobilePrimary: true },
        { id: 'Trigger Price', label: 'Trigger', dataType: 'number', visible: true, sortable: true, filterable: true, position: 2, width: 100, alignment: 'right', mobilePrimary: true },
        { id: 'LTP', label: 'CMP', dataType: 'number', visible: true, sortable: true, filterable: true, position: 3, width: 100, alignment: 'right', mobileDetail: true },
        { id: 'Variance (%)', label: 'Variance %', dataType: 'number', visible: true, sortable: true, filterable: true, position: 4, width: 110, alignment: 'right', mobileDetail: true },
        { id: 'Qty', label: 'Qty', dataType: 'number', visible: true, sortable: true, filterable: true, position: 5, width: 80, alignment: 'right', mobileDetail: true },
        { id: 'Buy Amount', label: 'Buy Amount', dataType: 'number', visible: true, sortable: true, filterable: true, position: 6, width: 120, alignment: 'right', mobileDetail: true },
        { id: 'Status', label: 'Status', dataType: 'categorical', visible: true, sortable: true, filterable: true, position: 7, width: 120, mobilePrimary: true },
      ],
    },
  },

  tableFrameworkDemo: {
    pageId: 'tableFrameworkDemo',
    description: 'Isolated Phase 2 framework validation table',
    config: {
      pageId: 'tableFrameworkDemo',
      searchEnabled: false,
      defaultSort: { field: 'symbol', direction: 'asc' },
      defaultPageSize: 25,
      allowedPageSizes: [25, 50, 100],
      density: 'compact',
      selectionEnabled: true,
      mobilePrimaryFields: ['symbol', 'status', 'pnl_pct'],
      mobileDetailFields: ['quantity', 'avg_price', 'last_price', 'updated_at'],
      columns: [
        { id: 'symbol', label: 'Symbol', dataType: 'text', visible: true, sortable: true, filterable: true, position: 0, width: 120, required: true, mobilePrimary: true },
        { id: 'status', label: 'Status', dataType: 'categorical', visible: true, sortable: true, filterable: true, position: 1, width: 130, mobilePrimary: true },
        { id: 'quantity', label: 'Qty', dataType: 'number', visible: true, sortable: true, filterable: true, position: 2, width: 90, alignment: 'right', mobileDetail: true },
        { id: 'avg_price', label: 'Avg Price', dataType: 'number', visible: true, sortable: true, filterable: true, position: 3, width: 120, alignment: 'right', mobileDetail: true },
        { id: 'last_price', label: 'LTP', dataType: 'number', visible: true, sortable: true, filterable: true, position: 4, width: 110, alignment: 'right', mobileDetail: true },
        { id: 'pnl_pct', label: 'P&L %', dataType: 'number', visible: true, sortable: true, filterable: true, position: 5, width: 110, alignment: 'right', mobilePrimary: true },
        { id: 'updated_at', label: 'Updated', dataType: 'date', visible: true, sortable: true, filterable: true, position: 6, minWidth: 160, mobileDetail: true },
        { id: 'active', label: 'Active', dataType: 'boolean', visible: false, sortable: true, filterable: true, position: 7, width: 100, mobileDetail: true },
      ],
    },
  },
};

export function getTradeTableRegistryEntry(pageId: string): TradeTableRegistryEntry | undefined {
  return tradeTableRegistry[pageId];
}