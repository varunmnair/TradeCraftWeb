export interface GTTOrder {
  id?: string | number;
  'GTT ID': string;
  Symbol: string;
  Exchange: string;
  'Trigger Price': number;
  LTP: number | null;
  'Variance (%)': number | null;
  Qty: number;
  'Buy Amount': number | null;
  cmp_available?: boolean;
  Side?: string;
  'Order Status'?: string;
  'Order Price'?: number | null;
  Broker?: string;
}

export type GttSideFilter = 'all' | 'BUY' | 'SELL';
export type GttStatusFilter = 'all' | 'active' | 'other';

export function orderSide(order: GTTOrder): string {
  return String(order.Side || 'BUY').toUpperCase();
}

export function orderStatus(order: GTTOrder): string {
  return String(order['Order Status'] || 'active').toLowerCase();
}

export function orderPrice(order: GTTOrder): number | null {
  if (order['Order Price'] !== undefined && order['Order Price'] !== null) {
    return order['Order Price'];
  }
  return order['Trigger Price'];
}

export function orderValue(order: GTTOrder): number | null {
  if (order['Buy Amount'] !== undefined && order['Buy Amount'] !== null) {
    return order['Buy Amount'];
  }
  const qty = order.Qty;
  const price = orderPrice(order);
  return qty && price ? qty * price : null;
}

export function brokerLabel(order: GTTOrder): string {
  return order.Broker || 'Active session';
}

export function formatNumber(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return 'N/A';
  return value.toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function formatCurrency(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return 'N/A';
  return `₹${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}
