import { Box, Button, Typography } from '@mui/material';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import type { ReactNode } from 'react';

interface TradeErrorStateProps {
  title?: ReactNode;
  message: ReactNode;
  onRetry?: () => void;
  retryLabel?: string;
}

/** Reusable error state with user-friendly explanation and optional retry. */
export function TradeErrorState({
  title = 'Something went wrong',
  message,
  onRetry,
  retryLabel = 'Retry',
}: TradeErrorStateProps) {
  return (
    <Box
      role="alert"
      sx={{
        py: 4,
        px: 2,
        textAlign: 'center',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 1,
      }}
    >
      <ErrorOutlineIcon color="error" sx={{ fontSize: 36 }} />
      <Typography variant="h6" sx={{ fontSize: '1rem', fontWeight: 600 }}>
        {title}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ maxWidth: 560 }}>
        {message}
      </Typography>
      {onRetry ? (
        <Button variant="outlined" onClick={onRetry} sx={{ mt: 1 }}>
          {retryLabel}
        </Button>
      ) : null}
    </Box>
  );
}