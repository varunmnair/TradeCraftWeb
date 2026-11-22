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
 * Shell-level content wrapper. Desktop geometry (24px padding, 240px drawer
 * offset, 64px top offset, 80px bottom margin) is unchanged. On mobile the
 * bottom padding reserves room for the bottom navigation and safe area.
 */
export function ResponsivePageContainer({
  children,
  sx,
  className,
}: ResponsivePageContainerProps) {
  return (
    <Box
      component="main"
      className={className}
      sx={{
        flexGrow: 1,
        width: { sm: `calc(100% - ${layout.drawerWidth}px)` },
        p: layout.contentPadding,
        pb: { xs: mobileBottomSpacing.content, sm: layout.contentPadding.sm * 8 },
        mt: 8,
        mb: { xs: 0, sm: 10 },
        ...sx,
      }}
    >
      {children}
    </Box>
  );
}
