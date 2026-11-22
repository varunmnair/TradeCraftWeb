import { Box, Button, Typography } from '@mui/material';
import { ShoppingCart as PlaceIcon } from '@mui/icons-material';
import { layout, overlayZIndex } from '../../theme';
import { fmtCurrency } from './candidateDisplay';

interface MobileOrderActionBarProps {
  count: number;
  total: number;
  disabled: boolean;
  onReview: () => void;
  onClear: () => void;
}

export function MobileOrderActionBar({
  count,
  total,
  disabled,
  onReview,
  onClear,
}: MobileOrderActionBarProps) {
  if (count === 0) return null;

  return (
    <Box
      sx={{
        position: 'fixed',
        left: 16,
        right: 80,
        bottom: `calc(${layout.mobileNavHeight}px + 8px + ${layout.safeAreaBottom})`,
        zIndex: overlayZIndex.bottomNavigation - 10,
        display: { xs: 'flex', sm: 'none' },
        alignItems: 'center',
        gap: 1,
        minHeight: 60,
        boxSizing: 'border-box',
        px: 1.25,
        py: 0.75,
        borderRadius: 2,
        bgcolor: 'background.paper',
        border: 1,
        borderColor: 'divider',
        boxShadow: 6,
      }}
    >
      <Box sx={{ minWidth: 0, flex: 1 }}>
        <Typography variant="body2" fontWeight={800} noWrap>
          {count} {count === 1 ? 'Order' : 'Orders'} Selected
        </Typography>
        <Typography variant="caption" color="text.secondary" noWrap display="block">
          Total: {fmtCurrency(total)}
        </Typography>
      </Box>
      <Button
        size="small"
        variant="contained"
        startIcon={<PlaceIcon />}
        onClick={onReview}
        disabled={disabled}
        sx={{ minHeight: 40, px: 1.25, textTransform: 'none', whiteSpace: 'nowrap' }}
      >
        Review
      </Button>
      <Button size="small" onClick={onClear} disabled={disabled} sx={{ minHeight: 40, px: 0.75 }}>
        Clear
      </Button>
    </Box>
  );
}