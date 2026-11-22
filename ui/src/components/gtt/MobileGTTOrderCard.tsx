import { memo, useState } from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  Checkbox,
  Chip,
  Collapse,
  IconButton,
  Typography,
} from '@mui/material';
import {
  ExpandMore as ExpandIcon,
  Delete as DeleteIcon,
  Tune as NormalizeIcon,
} from '@mui/icons-material';
import type { GTTOrder } from './gttDisplay';
import {
  brokerLabel,
  formatCurrency,
  formatNumber,
  orderPrice,
  orderSide,
  orderStatus,
} from './gttDisplay';

interface MobileGTTOrderCardProps {
  order: GTTOrder;
  selected: boolean;
  duplicate: boolean;
  onToggleSelect: () => void;
  onDelete: () => void;
  onNormalize: () => void;
}

function MobileGTTOrderCardBase({
  order,
  selected,
  duplicate,
  onToggleSelect,
  onDelete,
  onNormalize,
}: MobileGTTOrderCardProps) {
  const [expanded, setExpanded] = useState(false);
  const side = orderSide(order);
  const status = orderStatus(order);

  return (
    <Card sx={{ mb: 1.5, overflow: 'hidden' }}>
      <CardContent sx={{ p: 1.5, '&:last-child': { pb: 1.5 } }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, minWidth: 0 }}>
          <Checkbox
            checked={selected}
            onChange={onToggleSelect}
            size="small"
            inputProps={{ 'aria-label': `Select ${order.Symbol}` }}
          />
          <Box sx={{ minWidth: 0, flex: 1 }}>
            <Typography variant="subtitle1" fontWeight={800} noWrap>
              {order.Symbol}
            </Typography>
            <Typography variant="caption" color="text.secondary" noWrap display="block">
              {order.Exchange} · {brokerLabel(order)}
            </Typography>
          </Box>
          <Chip label={side} size="small" color={side === 'SELL' ? 'error' : 'success'} />
          <Chip label={status} size="small" variant="outlined" />
          <IconButton
            size="small"
            onClick={() => setExpanded((value) => !value)}
            aria-label={expanded ? 'Collapse order details' : 'Expand order details'}
          >
            <ExpandIcon
              sx={{ transform: expanded ? 'rotate(180deg)' : 'none' }}
              fontSize="small"
            />
          </IconButton>
        </Box>

        <Box
          sx={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 1, mt: 1.5 }}
        >
          <Box>
            <Typography variant="caption" color="text.secondary" display="block">
              Trigger
            </Typography>
            <Typography variant="body2" fontWeight={700} noWrap>
              {formatNumber(order['Trigger Price'])}
            </Typography>
          </Box>
          <Box>
            <Typography variant="caption" color="text.secondary" display="block">
              Order Price
            </Typography>
            <Typography variant="body2" fontWeight={700} noWrap>
              {formatNumber(orderPrice(order))}
            </Typography>
          </Box>
          <Box>
            <Typography variant="caption" color="text.secondary" display="block">
              Qty
            </Typography>
            <Typography variant="body2" fontWeight={700} noWrap>
              {order.Qty}
            </Typography>
          </Box>
        </Box>

        {duplicate && <Chip label="DUPLICATE SYMBOL" size="small" color="warning" sx={{ mt: 1 }} />}

        <Collapse in={expanded} unmountOnExit>
          <Box sx={{ mt: 1.5, pt: 1.5, borderTop: 1, borderColor: 'divider' }}>
            <Typography variant="body2" color="text.secondary">
              GTT / Order ID:{' '}
              <Box component="span" sx={{ color: 'text.primary', fontWeight: 700 }}>
                {order['GTT ID'] || '-'}
              </Box>
            </Typography>
            <Typography variant="body2" color="text.secondary">
              CMP:{' '}
              <Box component="span" sx={{ color: 'text.primary', fontWeight: 700 }}>
                {formatNumber(order.LTP)}
              </Box>
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Variance:{' '}
              <Box component="span" sx={{ color: 'text.primary', fontWeight: 700 }}>
                {formatNumber(order['Variance (%)'])}%
              </Box>
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Order value:{' '}
              <Box component="span" sx={{ color: 'text.primary', fontWeight: 700 }}>
                {formatCurrency(order['Buy Amount'] ?? order.Qty * (orderPrice(order) || 0))}
              </Box>
            </Typography>
            <Box sx={{ display: 'flex', gap: 1, mt: 1.5 }}>
              <Button
                size="small"
                variant="outlined"
                color="error"
                startIcon={<DeleteIcon />}
                onClick={onDelete}
                fullWidth
                sx={{ minHeight: 40 }}
              >
                Delete
              </Button>
              <Button
                size="small"
                variant="outlined"
                color="info"
                startIcon={<NormalizeIcon />}
                onClick={onNormalize}
                fullWidth
                sx={{ minHeight: 40 }}
              >
                Normalize
              </Button>
            </Box>
          </Box>
        </Collapse>
      </CardContent>
    </Card>
  );
}

export const MobileGTTOrderCard = memo(MobileGTTOrderCardBase);
