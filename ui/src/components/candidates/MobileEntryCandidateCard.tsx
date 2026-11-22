import { memo, useMemo, useState } from 'react';
import {
  Box,
  Button,
  Checkbox,
  Chip,
  Divider,
  Typography,
} from '@mui/material';
import type { NormalizedCandidate } from '../../types';
import {
  candidateStatusColor,
  candidateStrategyColor,
  candidateStrategyLabel,
  fmt,
  fmtCurrency,
  getDeltaPercent,
  formatDelta,
  getLevelLabel,
} from './candidateDisplay';

interface MobileEntryCandidateCardProps {
  candidate: NormalizedCandidate;
  hasActiveOrder: boolean;
  selected: boolean;
  disabled: boolean;
  onToggle: (symbol: string) => void;
}

function toNumber(value: unknown): number | null {
  if (typeof value === 'number') return Number.isFinite(value) ? value : null;
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value.replace(/[₹,\s]/g, ''));
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function currency(value: unknown): string {
  const number = toNumber(value);
  return number == null ? '-' : fmtCurrency(number);
}

function count(value: unknown): string {
  const number = toNumber(value);
  return number == null ? '-' : fmt(number, 0);
}

function percent(value: unknown, signed = false): string {
  const number = toNumber(value);
  if (number == null) return '-';
  const prefix = signed && number > 0 ? '+' : '';
  return `${prefix}${number.toFixed(2)}%`;
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <Box sx={{ minWidth: 0 }}>
      <Typography variant="caption" color="text.secondary" display="block">
        {label}
      </Typography>
      <Typography
        variant="body2"
        noWrap
        title={value}
        sx={{ fontWeight: 700, fontSize: '0.875rem' }}
      >
        {value}
      </Typography>
    </Box>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <Box
      sx={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'flex-start',
        gap: 2,
        py: 0.6,
        borderBottom: '1px solid',
        borderColor: 'divider',
      }}
    >
      <Typography variant="body2" color="text.secondary" sx={{ flexShrink: 0 }}>
        {label}
      </Typography>
      <Typography
        variant="body2"
        sx={{ fontWeight: 600, textAlign: 'right', minWidth: 0, whiteSpace: 'normal' }}
      >
        {value}
      </Typography>
    </Box>
  );
}

function MobileEntryCandidateCardBase({
  candidate,
  hasActiveOrder,
  selected,
  disabled,
  onToggle,
}: MobileEntryCandidateCardProps) {
  const [expanded, setExpanded] = useState(false);
  const selectable = candidate.is_selectable && !hasActiveOrder;
  const delta = getDeltaPercent(candidate.cmp, candidate.additional_details?.level_price as number ?? null);

  const detailRows = useMemo(() => {
    const details = candidate.additional_details ?? {};
    const rows: Array<[string, string]> = [];
    const push = (label: string, value: string) => {
      if (value && value !== '-') rows.push([label, value]);
    };
    const text = (value: unknown) =>
      typeof value === 'string' && value.trim() ? value : '-';

    if (candidate.strategy_type === 'DYNAMIC_AVERAGING') {
      push('Average holding price', currency(details.avg_price));
      push('Drop from average %', percent(details.drop_from_avg_pct, true));
      push('Market regime', text(details.regime));
      push('Reversal offset %', percent(details.trigger_offset_pct));
      push('DA capacity', currency(details.da_capacity));
      push('Expected benefit', currency(details.expected_benefit));
      push('Estimated cost', currency(details.estimated_cost));
      push('Net benefit', currency(details.net_benefit));
      push('Order price', currency(details.order_price ?? candidate.order_price));
    } else {
      push('Entry level', getLevelLabel(candidate));
      push('Entry level price', currency(details.level_price));
      push('Order price', currency(details.order_price ?? candidate.order_price));
      push('Trigger price', currency(details.trigger_price ?? candidate.trigger_price));
      push('Current holding', count(details.current_holding_qty));
      push('Allocation', currency(details.allocation ?? candidate.allocation));
      push('Allocation used', percent(details.allocation_used_percent));
    }
    push('Candidate reason', candidate.reason_message || '-');
    return rows;
  }, [candidate]);

  return (
    <Box
      component="article"
      sx={{
        border: 1,
        borderColor: selected ? 'primary.main' : 'divider',
        borderRadius: 1,
        bgcolor: 'background.paper',
        mb: 1.5,
        overflow: 'hidden',
      }}
    >
      <Box sx={{ p: 1.5 }}>
        <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1, minWidth: 0 }}>
          <Checkbox
            checked={selected}
            onChange={() => onToggle(candidate.symbol)}
            disabled={!selectable || disabled}
            inputProps={{ 'aria-label': `Select ${candidate.symbol}` }}
            sx={{ mt: -0.5, ml: -0.5 }}
          />
          <Box sx={{ minWidth: 0, flex: 1 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, flexWrap: 'wrap' }}>
              <Typography
                variant="subtitle1"
                noWrap
                title={candidate.symbol}
                sx={{ fontWeight: 800, letterSpacing: 0.3 }}
              >
                {candidate.symbol}
              </Typography>
              <Chip
                label={candidateStrategyLabel[candidate.strategy_type] ?? candidate.strategy_type}
                size="small"
                color={candidateStrategyColor[candidate.strategy_type] ?? 'default'}
                variant="outlined"
                sx={{ height: 22, fontSize: '0.7rem' }}
              />
              <Typography variant="caption" color="text.secondary" noWrap>
                {getLevelLabel(candidate)}
              </Typography>
            </Box>
            <Box sx={{ mt: 0.75 }}>
              <Chip
                label={
                  hasActiveOrder
                    ? 'Active Order'
                    : (candidate.status || '-').replace(/_/g, ' ')
                }
                size="small"
                color={hasActiveOrder ? 'default' : candidateStatusColor[candidate.status] ?? 'default'}
                sx={{ fontWeight: 700 }}
              />
            </Box>
          </Box>
        </Box>

        <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 1, mt: 1.5 }}>
          <Metric label="CMP" value={fmtCurrency(candidate.cmp)} />
          <Metric label="Trigger" value={fmtCurrency(candidate.trigger_price)} />
        </Box>
        <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 1, mt: 1 }}>
          <Metric label="Qty" value={candidate.qty != null ? fmt(candidate.qty, 0) : '-'} />
          <Metric label="Amount" value={fmtCurrency(candidate.amount)} />
        </Box>
        {delta != null && (
          <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1 }}>
            Δ vs entry: {formatDelta(delta)}
          </Typography>
        )}

        <Button
          fullWidth
          size="small"
          variant="text"
          onClick={() => setExpanded((value) => !value)}
          aria-expanded={expanded}
          sx={{ mt: 1, minHeight: 36 }}
        >
          {expanded ? 'Hide Details' : 'View Details'}
        </Button>
      </Box>

      {expanded && (
        <Box sx={{ px: 1.5, pb: 1.5 }}>
          <Divider sx={{ mb: 0.5 }} />
          {detailRows.length === 0 ? (
            <Typography variant="body2" color="text.secondary" sx={{ py: 1 }}>
              No additional details available.
            </Typography>
          ) : (
            detailRows.map(([label, value]) => (
              <DetailRow key={label} label={label} value={value} />
            ))
          )}
          {candidate.exchange && (
            <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1 }}>
              Exchange: {candidate.exchange}
            </Typography>
          )}
        </Box>
      )}
    </Box>
  );
}

export const MobileEntryCandidateCard = memo(MobileEntryCandidateCardBase);