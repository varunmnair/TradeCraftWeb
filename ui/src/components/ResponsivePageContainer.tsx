import { Box } from '@mui/material';
import type { SxProps, Theme } from '@mui/material/styles';
import type { ReactNode } from 'react';
import { layout, mobileBottomSpacing } from '../theme';

interface ResponsivePageContainerProps {
  children: ReactNode;
  sx?: SxProps<Theme>;
  className?: string;
}

/**
 * Page content wrapper. Desktop geometry (24px padding, 80px bottom margin)
 * is preserved. On mobile the bottom padding reserves room for the bottom
 * navigation and safe area. Shell sizing/offset is owned by Layout.
 */
export function ResponsivePageContainer({
  children,
  sx,
  className,
}: ResponsivePageContainerProps) {
  return (
    <Box
      className={className}
      sx={{
        flexGrow: 1,
        p: layout.contentPadding,
        pb: { xs: mobileBottomSpacing.content, sm: layout.contentPadding.sm * 8 },
        mb: { xs: 0, sm: 10 },
        minWidth: 0,
        ...sx,
      }}
    >
      {children}
    </Box>
  );
}
