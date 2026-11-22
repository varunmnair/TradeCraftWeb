import { Box, Typography } from '@mui/material';
import type { SxProps, Theme } from '@mui/material/styles';
import type { ReactNode } from 'react';

interface ResponsivePageHeaderProps {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  sx?: SxProps<Theme>;
}

/** Page heading with actions that stack on mobile and sit inline on desktop. */
export function ResponsivePageHeader({
  title,
  description,
  actions,
  sx,
}: ResponsivePageHeaderProps) {
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: { xs: 'column', sm: 'row' },
        alignItems: { xs: 'stretch', sm: 'center' },
        justifyContent: 'space-between',
        gap: 2,
        mb: 2,
        ...sx,
      }}
    >
      <Box sx={{ minWidth: 0 }}>
        <Typography variant="h5" component="h1" noWrap>
          {title}
        </Typography>
        {description && (
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
            {description}
          </Typography>
        )}
      </Box>
      {actions && (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
          {actions}
        </Box>
      )}
    </Box>
  );
}
