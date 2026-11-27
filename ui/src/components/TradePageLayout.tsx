import { Box } from '@mui/material';
import type { SxProps, Theme } from '@mui/material/styles';
import type { ReactNode } from 'react';
import { designTokens } from '../theme';

interface TradePageLayoutProps {
  /** Page header region (title, description, actions). */
  header?: ReactNode;
  /** Summary/status region (counts, totals, status indicators). */
  summary?: ReactNode;
  /** Toolbar region (filters, search, view controls). */
  toolbar?: ReactNode;
  /** Main page content. */
  children?: ReactNode;
  /** Optional content rendered after main children. */
  footer?: ReactNode;
  sx?: SxProps<Theme>;
}

/**
 * Shared page template for TradeCraftWeb pages. Regions are optional so pages
 * can adopt the layout incrementally without forcing a single rigid structure.
 */
export function TradePageLayout({
  header,
  summary,
  toolbar,
  children,
  footer,
  sx,
}: TradePageLayoutProps) {
  const regionSx = { minWidth: 0, '& > *': { mb: '0 !important' } } as const;

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        gap: `${designTokens.spacing.pageGap}px`,
        minWidth: 0,
        ...sx,
      }}
    >
      {header ? <Box sx={regionSx}>{header}</Box> : null}
      {summary ? <Box sx={regionSx}>{summary}</Box> : null}
      {toolbar ? <Box sx={regionSx}>{toolbar}</Box> : null}
      {children ? <Box sx={{ minWidth: 0 }}>{children}</Box> : null}
      {footer ? <Box sx={regionSx}>{footer}</Box> : null}
    </Box>
  );
}