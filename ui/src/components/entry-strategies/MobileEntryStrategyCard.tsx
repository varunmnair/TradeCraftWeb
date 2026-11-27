import { memo, useState } from 'react';
import type { ReactNode } from 'react';
import { Box, Button, CardActionArea, Chip, Divider, Typography } from '@mui/material';
import type { EntryStrategySummary } from '../../types';
import {
  formatAllocation,
  formatDate,
  formatPrice,
  getDeltaColor,
  getReviewStatusColor,
  getReviewStatusLabel,
  getSwingFailureReasons,
} from './strategyDisplay';

interface MobileEntryStrategyCardProps {
  strategy: EntryStrategySummary;
  cmp: number | null;
  delta: number | null;
  onEdit: (strategy: EntryStrategySummary) => void;
  onOpenDetail: (symbol: string) => void;
  onViewHistory: (strategy: EntryStrategySummary) => void;
  primaryFields?: string[];
  detailFields?: string[];
}

interface ValueRowProps {
  label: string;
  value: ReactNode;
  valueColor?: string;
}

function ValueRow({ label, value, valueColor }: ValueRowProps) {
  return (
    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 2, py: 0.75 }}>
      <Typography variant="body2" color="text.secondary" sx={{ flexShrink: 0 }}>{label}</Typography>
      <Typography variant="body2" sx={{ fontWeight: 600, textAlign: 'right', minWidth: 0, color: valueColor }}>{value}</Typography>
    </Box>
  );
}

function Metric({ label, value, color }: { label: string; value: ReactNode; color?: string }) {
  return (
    <Box sx={{ minWidth: 0 }}>
      <Typography variant="caption" color="text.secondary" display="block">{label}</Typography>
      <Typography variant="body2" noWrap sx={{ fontWeight: 700, fontSize: '0.875rem', color }}>{value}</Typography>
    </Box>
  );
}

const DEFAULT_PRIMARY = ['symbol', 'review_status', 'cmp', 'delta_pct', 'allocated'];
const DEFAULT_DETAIL = ['entry1', 'entry2', 'entry3', 'swing_eligible', 'updated_at', 'actions'];

function MobileEntryStrategyCardBase({
  strategy,
  cmp,
  delta,
  onEdit,
  onOpenDetail,
  onViewHistory,
  primaryFields,
  detailFields,
}: MobileEntryStrategyCardProps) {
  const [expanded, setExpanded] = useState(false);
  const [swingOpen, setSwingOpen] = useState(false);
  const primary = primaryFields && primaryFields.length ? primaryFields : DEFAULT_PRIMARY;
  const detail = detailFields && detailFields.length ? detailFields : DEFAULT_DETAIL;
  const hasP = (id: string) => primary.includes(id);
  const hasD = (id: string) => detail.includes(id);
  const hasAny = (id: string) => hasP(id) || hasD(id);

  const reasons = getSwingFailureReasons(strategy);
  const reviewLabel = getReviewStatusLabel(strategy.review_status);
  const reviewColor = getReviewStatusColor(strategy.review_status);
  const deltaValue = delta == null ? '-' : `${delta > 0 ? '+' : ''}${delta.toFixed(2)}%`;
  const deltaColor = getDeltaColor(delta);

  const metricDefs: Record<string, { label: string; value: ReactNode; color?: string }> = {
    cmp: { label: 'CMP', value: formatPrice(cmp) },
    delta_pct: { label: 'Variance', value: deltaValue, color: deltaColor },
    allocated: { label: 'Allocation', value: formatAllocation(strategy.allocated) },
    entry1: { label: 'Entry 1', value: formatPrice(strategy.entry1) },
    entry2: { label: 'Entry 2', value: formatPrice(strategy.entry2) },
    entry3: { label: 'Entry 3', value: formatPrice(strategy.entry3) },
  };
  const primaryMetricIds = primary.filter((id) => metricDefs[id]).slice(0, 4);

  return (
    <Box component="article" sx={{ border: 1, borderColor: 'divider', borderRadius: 1, bgcolor: 'background.paper', mb: 1.5, overflow: 'hidden' }}>
      <CardActionArea onClick={() => setExpanded((v) => !v)} aria-expanded={expanded} aria-label={`${strategy.symbol} strategy details`} sx={{ p: 1.5 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 1, minWidth: 0 }}>
          <Typography variant="subtitle1" noWrap title={strategy.symbol} sx={{ fontWeight: 700, minWidth: 0 }}>{strategy.symbol}</Typography>
          <Chip label={reviewLabel} size="small" color={reviewColor} variant={strategy.review_status ? 'filled' : 'outlined'} sx={{ fontWeight: 600 }} />
        </Box>

        {primaryMetricIds.length > 0 && (
          <Box sx={{ display: 'grid', gridTemplateColumns: `repeat(${Math.max(1, primaryMetricIds.length)}, minmax(0, 1fr))`, gap: 1.25, mt: 1.5 }}>
            {primaryMetricIds.map((id) => <Metric key={id} label={metricDefs[id].label} value={metricDefs[id].value} color={metricDefs[id].color} />)}
          </Box>
        )}

        <Typography variant="body2" color="primary" sx={{ mt: 1.5, fontWeight: 600 }}>{expanded ? 'Hide Details' : 'View Details'}</Typography>
      </CardActionArea>

      {expanded && (
        <Box sx={{ px: 1.5, pb: 1.5 }}>
          <Divider sx={{ mb: 0.5 }} />
          {hasD('entry1') && <ValueRow label="Entry 1" value={formatPrice(strategy.entry1)} />}
          {hasD('entry2') && <ValueRow label="Entry 2" value={formatPrice(strategy.entry2)} />}
          {hasD('entry3') && <ValueRow label="Entry 3" value={formatPrice(strategy.entry3)} />}
          {hasD('allocated') && <ValueRow label="Allocation" value={formatAllocation(strategy.allocated)} />}
          {hasD('cmp') && <ValueRow label="CMP" value={formatPrice(cmp)} />}
          {hasD('delta_pct') && <ValueRow label="Variance" value={deltaValue} valueColor={deltaColor} />}
          {hasD('updated_at') && <ValueRow label="Updated" value={formatDate(strategy.updated_at)} />}
          {hasD('swing_eligible') && (
            <>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 2, py: 0.75 }}>
                <Typography variant="body2" color="text.secondary">Swing Eligibility</Typography>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                  <Chip label={strategy.swing_eligible == null ? 'Not checked' : strategy.swing_eligible ? 'Eligible' : 'Not eligible'} size="small" color={strategy.swing_eligible ? 'success' : strategy.swing_eligible == null ? 'default' : 'warning'} variant={strategy.swing_eligible ? 'filled' : 'outlined'} />
                  <Button size="small" onClick={() => setSwingOpen((v) => !v)}>{swingOpen ? 'Hide' : 'Why?'}</Button>
                </Box>
              </Box>
              {swingOpen && (
                <Box sx={{ py: 1, pl: 1 }}>
                  <Typography variant="caption" color="text.secondary" display="block">Average Volume: {strategy.swing_avg_volume != null ? strategy.swing_avg_volume.toLocaleString() : '-'}</Typography>
                  <Typography variant="caption" color="text.secondary" display="block">ATR %: {strategy.swing_atr_percent != null ? `${strategy.swing_atr_percent.toFixed(2)}%` : '-'}</Typography>
                  <Typography variant="caption" color="text.secondary" display="block">Trading Range %: {strategy.swing_range_percent != null ? `${strategy.swing_range_percent.toFixed(2)}%` : '-'}</Typography>
                  <Typography variant="caption" color="text.secondary" display="block">Decision: {strategy.swing_eligible == null ? 'Not checked' : strategy.swing_eligible ? 'Eligible' : 'Not eligible'}</Typography>
                  <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 0.5 }}>
                    {reasons.length ? `Failure reasons: ${reasons.join('; ')}` : strategy.swing_avg_volume == null ? "Click 'Evaluate All' for swing analysis details" : 'No failure reasons reported'}
                  </Typography>
                </Box>
              )}
            </>
          )}

          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mt: 1.5 }}>
            <Button size="small" variant="outlined" onClick={() => onEdit(strategy)}>Edit</Button>
            <Button size="small" variant="text" onClick={() => onOpenDetail(strategy.symbol)}>Full Details</Button>
            <Button size="small" variant="text" onClick={() => onViewHistory(strategy)}>Version History</Button>
          </Box>
        </Box>
      )}
    </Box>
  );
}

export const MobileEntryStrategyCard = memo(MobileEntryStrategyCardBase);
