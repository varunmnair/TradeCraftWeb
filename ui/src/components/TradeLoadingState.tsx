import { Box, CircularProgress, Typography } from '@mui/material';
import type { ReactNode } from 'react';

interface TradeLoadingStateProps {
  message?: ReactNode;
  compact?: boolean;
}

/** Reusable loading indicator with a short progress message. */
export function TradeLoadingState({
  message = 'Loading…',
  compact = false,
}: TradeLoadingStateProps) {
  return (
    <Box
      role="status"
      aria-live="polite"
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 1.5,
        py: compact ? 2 : 5,
        px: 2,
        minHeight: compact ? undefined : 160,
      }}
    >
      <CircularProgress size={compact ? 24 : 36} />
      {message ? (
        <Typography variant="body2" color="text.secondary">
          {message}
        </Typography>
      ) : null}
    </Box>
  );
}