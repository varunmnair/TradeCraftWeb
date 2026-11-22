import { Box, Button, Typography } from '@mui/material';
import { Delete as DeleteIcon, Tune as NormalizeIcon } from '@mui/icons-material';
import { layout, overlayZIndex } from '../../theme';

interface GTTMobileActionBarProps {
  count: number;
  disabled: boolean;
  onDelete: () => void;
  onNormalize: () => void;
  onClear: () => void;
}

export function GTTMobileActionBar({
  count,
  disabled,
  onDelete,
  onNormalize,
  onClear,
}: GTTMobileActionBarProps) {
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
        gap: 0.75,
        minHeight: 60,
        boxSizing: 'border-box',
        px: 1,
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
          {count} selected
        </Typography>
      </Box>
      <Button
        size="small"
        variant="contained"
        color="error"
        startIcon={<DeleteIcon />}
        onClick={onDelete}
        disabled={disabled}
        sx={{ minHeight: 40, px: 1, textTransform: 'none', whiteSpace: 'nowrap' }}
      >
        Delete
      </Button>
      <Button
        size="small"
        variant="outlined"
        color="info"
        startIcon={<NormalizeIcon />}
        onClick={onNormalize}
        disabled={disabled}
        sx={{ minHeight: 40, px: 1, textTransform: 'none', whiteSpace: 'nowrap' }}
      >
        Adjust
      </Button>
      <Button size="small" onClick={onClear} disabled={disabled} sx={{ minHeight: 40, px: 0.5 }}>
        Clear
      </Button>
    </Box>
  );
}
