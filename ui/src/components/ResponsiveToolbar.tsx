import { Box } from '@mui/material';
import type { BoxProps } from '@mui/material/Box';
import type { ReactNode } from 'react';

interface ResponsiveToolbarProps extends Omit<BoxProps, 'children'> {
  children: ReactNode;
  /** Keep controls on one line (adds horizontal scrolling on mobile). */
  nowrap?: boolean;
}

/** Action bar that wraps on mobile and stays inline on desktop/laptop. */
export function ResponsiveToolbar({
  children,
  nowrap = false,
  sx,
  ...rest
}: ResponsiveToolbarProps) {
  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: 1,
        flexWrap: nowrap ? 'nowrap' : { xs: 'wrap', sm: 'nowrap' },
        overflowX: nowrap ? 'auto' : 'visible',
        ...sx,
      }}
      {...rest}
    >
      {children}
    </Box>
  );
}
