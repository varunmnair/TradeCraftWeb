import { memo, useState } from 'react';
import type { ReactNode } from 'react';
import {
  Box,
  CardActionArea,
  Chip,
  Divider,
  Tooltip,
  Typography,
} from '@mui/material';
import type { HoldingsRow } from '../../types';
import {
  formatCurrency,
  formatPlainNumber,
  formatProfit,
  formatProfitPct,
  getAgeTooltipText,
  getExitScoreStyle,
  getSignalColor,
  getSignalVariant,
  getWroiTrendColor,
  NOT_CALCULATED_TOOLTIP,
} from './holdingDisplay';

export type MobileHoldingRow = HoldingsRow & {
  id?: string | number;
  exchange?: string | null;
};

interface MobileHoldingCardProps {
  holding: MobileHoldingRow;
  trendsPopulated: boolean;
}

interface DetailRowProps {
  label: string;
  value: ReactNode;
  valueColor?: string;
}

function DetailRow({ label, value, valueColor }: DetailRowProps) {
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

interface MetricProps {
  label: string;
  value: string;
  color?: string;
}

function Metric({ label, value, color }: MetricProps) {
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

function BreakDetails({ holding }: { holding: MobileHoldingRow }) {
  return (
    <Box
      sx={{
        mt: 1.5,
        p: 1.25,
        borderRadius: 1,
        bgcolor: '#ffebee',
        border: '1px solid',
        borderColor: '#ffcdd2',
      }}
    >
      <Typography variant="subtitle2" color="error" sx={{ fontWeight: 700, mb: 0.5 }}>
        BREAK — Manual Review Required
      </Typography>
      <DetailRow label="Manual review reason" value="Thesis break detected" />
      <DetailRow label="Current market price" value={formatCurrency(holding.last_price)} />
      {holding.thesis_break_price != null && (
        <DetailRow
          label="Thesis break price"
          value={formatCurrency(holding.thesis_break_price)}
        />
      )}
      {holding.thesis_break_pct != null && (
        <DetailRow
          label="% below break"
          value={`${holding.thesis_break_pct.toFixed(2)}%`}
          valueColor="#b71c1c"
        />
      )}
      <Typography variant="caption" color="error" sx={{ display: 'block', mt: 1, fontWeight: 700 }}>
        Automation Paused – Manual Review Required
      </Typography>
    </Box>
  );
}

function MobileHoldingCardBase({ holding, trendsPopulated }: MobileHoldingCardProps) {
  const [expanded, setExpanded] = useState(false);
  const action = holding.exit_action;
  const isBreak = action === 'BREAK';
  const profitColor = (holding.profit ?? 0) >= 0 ? '#1b5e20' : '#c62828';
  const trend = holding.wroi_trend;
  const trendValue =
    !trendsPopulated || !trend || trend === 'NA' ? '-' : trend.replace('_', ' ');
  const trendColor = trendValue === '-' ? 'text.secondary' : getWroiTrendColor(trend);
  const ageValue =
    holding.age === null
      ? (
          <Tooltip title={getAgeTooltipText(holding) || '-'} arrow>
            <span style={{ color: '#999' }}>-</span>
          </Tooltip>
        )
      : holding.age;
  const exitScoreStyle = getExitScoreStyle(holding.exit_score);

  const signalChip = !trendsPopulated ? (
    <Tooltip title={NOT_CALCULATED_TOOLTIP} arrow>
      <Chip label="—" size="small" variant="outlined" sx={{ color: 'text.secondary' }} />
    </Tooltip>
  ) : !action ? (
    <Typography variant="body2" color="text.secondary">-</Typography>
  ) : (
    <Chip
      label={action}
      size="small"
      color={getSignalColor(action)}
      variant={getSignalVariant(action)}
      sx={
        isBreak
          ? { fontWeight: 800, letterSpacing: 0.3, boxShadow: 2 }
          : { fontWeight: 700 }
      }
    />
  );

  return (
    <Box
      component="article"
      sx={{
        border: 1,
        borderColor: isBreak ? 'error.main' : 'divider',
        borderRadius: 1,
        bgcolor: 'background.paper',
        mb: 1.5,
        overflow: 'hidden',
      }}
    >
      <CardActionArea
        onClick={() => setExpanded((value) => !value)}
        aria-expanded={expanded}
        sx={{ p: 1.5, '&:focus': { outline: 'none' } }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 1, minWidth: 0 }}>
          <Typography
            variant="subtitle1"
            noWrap
            title={holding.symbol}
            sx={{ fontWeight: 800, letterSpacing: 0.3, minWidth: 0 }}
          >
            {holding.symbol}
          </Typography>
          {signalChip}
        </Box>

        <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 1, mt: 1.5 }}>
          <Metric label="CMP" value={formatCurrency(holding.last_price)} />
          <Metric label="Profit" value={formatProfit(holding.profit)} color={profitColor} />
          <Metric
            label="Profit %"
            value={formatProfitPct(holding.profit_pct)}
            color={profitColor}
          />
        </Box>

        <Typography variant="body2" color="primary" sx={{ mt: 1.5, fontWeight: 700 }}>
          {expanded ? 'Hide Details' : 'View Details'}
        </Typography>
      </CardActionArea>

      {expanded && (
        <Box sx={{ px: 1.5, py: 1 }}>
          <Divider sx={{ mb: 0.5 }} />
          <DetailRow label="Exchange" value={holding.exchange || '-'} />
          <DetailRow label="Quantity" value={holding.quantity ?? '-'} />
          <DetailRow label="Average Price" value={formatPlainNumber(holding.average_price, 1)} />
          <DetailRow label="Invested" value={formatPlainNumber(holding.invested, 0)} />
          <DetailRow label="Profit" value={formatProfit(holding.profit)} valueColor={profitColor} />
          <DetailRow
            label="Profit %"
            value={formatProfitPct(holding.profit_pct)}
            valueColor={profitColor}
          />
          <DetailRow label="WROI" value={formatPlainNumber(holding.weighted_roi, 4)} />
          <DetailRow label="WROI Trend" value={trendValue} valueColor={trendColor} />
          <DetailRow
            label="Profit per Day"
            value={formatPlainNumber(holding.profit_per_day, 1)}
          />
          <DetailRow label="Age" value={ageValue} />
          <DetailRow label="Quality" value={holding.quality || '-'} />
          <Box
            sx={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              gap: 2,
              py: 0.75,
            }}
          >
            <Typography variant="body2" color="text.secondary">Exit Score</Typography>
            <Box
              sx={{
                minWidth: 44,
                px: 1,
                py: 0.25,
                borderRadius: 1,
                textAlign: 'center',
                fontWeight: 700,
                ...exitScoreStyle,
              }}
            >
              {holding.exit_score ?? '-'}
            </Box>
          </Box>

          {isBreak && <BreakDetails holding={holding} />}
        </Box>
      )}
    </Box>
  );
}

export const MobileHoldingCard = memo(MobileHoldingCardBase);
