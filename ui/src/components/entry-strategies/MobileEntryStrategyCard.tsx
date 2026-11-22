import { memo, useState } from 'react';
import type { ReactNode } from 'react';
import {
  Box,
  Button,
  CardActionArea,
  Chip,
  Divider,
  Typography,
} from '@mui/material';
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
}

interface ValueRowProps {
  label: string;
  value: ReactNode;
  valueColor?: string;
}

function ValueRow({ label, value, valueColor }: ValueRowProps) {
  return (
    <Box
      sx={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'flex-start',
        gap: 2,
        py: 0.55,
        borderBottom: '1px solid',
        borderColor: 'divider',
      }}
    >
      <Typography variant="body2" color="text.secondary" sx={{ flexShrink: 0 }}>
        {label}
      </Typography>
      <Typography
        variant="body2"
        sx={{ fontWeight: 600, textAlign: 'right', minWidth: 0, color: valueColor }}
      >
        {value}
      </Typography>
    </Box>
  );
}

function Metric({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <Box sx={{ minWidth: 0 }}>
      <Typography variant="caption" color="text.secondary" display="block">
        {label}
      </Typography>
      <Typography
        variant="body2"
        noWrap
        title={value}
        sx={{ fontWeight: 700, fontSize: '0.875rem', color }}
      >
        {value}
      </Typography>
    </Box>
  );
}

function MobileEntryStrategyCardBase({
  strategy,
  cmp,
  delta,
  onEdit,
  onOpenDetail,
  onViewHistory,
}: MobileEntryStrategyCardProps) {
  const [expanded, setExpanded] = useState(false);
  const [swingOpen, setSwingOpen] = useState(false);
  const reviewColor = getReviewStatusColor(strategy.review_status);
  const reasons = getSwingFailureReasons(strategy);
  const deltaText = delta === null ? '-' : `${delta > 0 ? '+' : ''}${delta.toFixed(2)}%`;

  return (
    <Box
      component="article"
      sx={{
        border: 1,
        borderColor: 'divider',
        borderRadius: 1,
        bgcolor: 'background.paper',
        mb: 1.5,
        overflow: 'hidden',
      }}
    >
      <CardActionArea
        onClick={() => setExpanded((value) => !value)}
        aria-expanded={expanded}
        aria-label={`Toggle details for ${strategy.symbol}`}
        sx={{ p: 1.5, '&:focus': { outline: 'none' } }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 1, minWidth: 0 }}>
          <Typography
            variant="subtitle1"
            noWrap
            title={strategy.symbol}
            sx={{ fontWeight: 800, letterSpacing: 0.3, minWidth: 0 }}
          >
            {strategy.symbol}
          </Typography>
          {strategy.review_status ? (
            <Chip
              label={getReviewStatusLabel(strategy.review_status)}
              size="small"
              color={reviewColor}
              sx={{ fontWeight: 700, flexShrink: 0 }}
            />
          ) : (
            <Typography variant="body2" color="text.secondary">
              -
            </Typography>
          )}
        </Box>

        <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 1, mt: 1.5 }}>
          <Metric label="CMP" value={cmp == null ? '-' : formatPrice(cmp)} />
          <Metric label="Allocation" value={formatAllocation(strategy.allocated)} />
        </Box>

        <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 1, mt: 1.5 }}>
          <Metric label="Entry 1" value={formatPrice(strategy.entry1)} />
          <Metric label="Entry 2" value={formatPrice(strategy.entry2)} />
          <Metric label="Entry 3" value={formatPrice(strategy.entry3)} />
        </Box>

        <Box
          sx={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            gap: 2,
            mt: 1.5,
          }}
        >
          <Typography variant="caption" color="text.secondary">
            Variance
          </Typography>
          <Typography variant="body2" sx={{ fontWeight: 800, color: getDeltaColor(delta) }}>
            {deltaText}
          </Typography>
        </Box>
      </CardActionArea>

      <Box sx={{ display: 'flex', gap: 1, px: 1.5, pb: 1.5 }}>
        <Button size="small" variant="outlined" onClick={() => setExpanded((value) => !value)} sx={{ flex: 1 }}>
          {expanded ? 'Hide Details' : 'Details'}
        </Button>
        <Button
          size="small"
          variant="contained"
          onClick={() => onEdit(strategy)}
          sx={{ flex: 1 }}
        >
          Edit
        </Button>
      </Box>

      {expanded && (
        <Box sx={{ px: 1.5, pb: 1.5 }}>
          <Divider sx={{ mb: 0.5 }} />
          <ValueRow label="Exchange" value={strategy.exchange || '-'} />
          <ValueRow label="Quality" value={strategy.quality || '-'} />
          <ValueRow label="Review Status" value={getReviewStatusLabel(strategy.review_status)} />
          <ValueRow label="Last Updated" value={formatDate(strategy.updated_at)} />
          {strategy.thesis_break_price != null && (
            <ValueRow label="Thesis Break Price" value={formatPrice(strategy.thesis_break_price)} />
          )}

          <Box
            sx={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              gap: 1,
              py: 0.75,
              borderBottom: '1px solid',
              borderColor: 'divider',
            }}
          >
            <Typography variant="body2" color="text.secondary">
              Swing Eligibility
            </Typography>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
              <Chip
                label={strategy.swing_eligible == null ? '-' : strategy.swing_eligible ? 'Yes' : 'No'}
                size="small"
                color={strategy.swing_eligible ? 'success' : 'default'}
                variant={strategy.swing_eligible ? 'filled' : 'outlined'}
              />
              <Button size="small" onClick={() => setSwingOpen((value) => !value)}>
                {swingOpen ? 'Hide' : 'Why?'}
              </Button>
            </Box>
          </Box>

          {swingOpen && (
            <Box sx={{ py: 1, pl: 1 }}>
              <Typography variant="caption" color="text.secondary" display="block">
                Average Volume:{' '}
                {strategy.swing_avg_volume != null
                  ? strategy.swing_avg_volume.toLocaleString()
                  : '-'}
              </Typography>
              <Typography variant="caption" color="text.secondary" display="block">
                ATR %:{' '}
                {strategy.swing_atr_percent != null
                  ? `${strategy.swing_atr_percent.toFixed(2)}%`
                  : '-'}
              </Typography>
              <Typography variant="caption" color="text.secondary" display="block">
                Trading Range %:{' '}
                {strategy.swing_range_percent != null
                  ? `${strategy.swing_range_percent.toFixed(2)}%`
                  : '-'}
              </Typography>
              <Typography variant="caption" color="text.secondary" display="block">
                Decision:{' '}
                {strategy.swing_eligible == null
                  ? 'Not checked'
                  : strategy.swing_eligible
                    ? 'Eligible'
                    : 'Not eligible'}
              </Typography>
              <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 0.5 }}>
                {reasons.length
                  ? `Failure reasons: ${reasons.join('; ')}`
                  : strategy.swing_avg_volume == null
                    ? "Click 'Evaluate All' for swing analysis details"
                    : 'No failure reasons reported'}
              </Typography>
            </Box>
          )}

          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mt: 1.5 }}>
            <Button size="small" variant="text" onClick={() => onOpenDetail(strategy.symbol)}>
              Full Details
            </Button>
            <Button size="small" variant="text" onClick={() => onViewHistory(strategy)}>
              Version History
            </Button>
          </Box>
        </Box>
      )}
    </Box>
  );
}

export const MobileEntryStrategyCard = memo(MobileEntryStrategyCardBase);