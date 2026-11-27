import { Box, Typography } from '@mui/material';
import type { ReactNode } from 'react';

interface TradeEmptyStateProps {
  title: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
  icon?: ReactNode;
}

/** Reusable empty state with consistent spacing and optional action. */
export function TradeEmptyState({ title, description, action, icon }: TradeEmptyStateProps) {
  return (
    <Box
      sx={{
        py: 5,
        px: 2,
        textAlign: 'center',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 1,
      }}
    >
      {icon ? (
        <Box sx={{ color: 'text.secondary', '& svg': { fontSize: 40 } }}>{icon}</Box>
      ) : null}
      <Typography variant="h6" sx={{ fontSize: '1rem', fontWeight: 600 }}>
        {title}
      </Typography>
      {description ? (
        <Typography variant="body2" color="text.secondary" sx={{ maxWidth: 560 }}>
          {description}
        </Typography>
      ) : null}
      {action ? <Box sx={{ mt: 1 }}>{action}</Box> : null}
    </Box>
  );
}