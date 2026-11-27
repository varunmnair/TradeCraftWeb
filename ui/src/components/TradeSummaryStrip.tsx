import { Box, Paper, Typography } from '@mui/material';
import type { ReactNode } from 'react';
import { designTokens } from '../theme';

export type TradeSummaryTone = 'default' | 'success' | 'warning' | 'error' | 'info';

export interface TradeSummaryItem {
  label: ReactNode;
  value?: ReactNode;
  tone?: TradeSummaryTone;
  /** Optional icon rendered before the label/value. */
  icon?: ReactNode;
}

interface TradeSummaryStripProps {
  items: TradeSummaryItem[];
  /** Accessible label for the summary region. */
  ariaLabel?: string;
}

const TONE_COLOR: Record<TradeSummaryTone, string> = {
  default: designTokens.color.textPrimary,
  success: designTokens.color.success,
  warning: designTokens.color.warning,
  error: designTokens.color.error,
  info: designTokens.color.info,
};

/** Compact, responsive summary strip for counts, totals, and status indicators. */
export function TradeSummaryStrip({
  items,
  ariaLabel = 'Page summary',
}: TradeSummaryStripProps) {
  if (items.length === 0) return null;

  return (
    <Paper
      variant="outlined"
      aria-label={ariaLabel}
      sx={{
        px: { xs: 1.5, sm: 2 },
        py: 1,
        mb: 2,
        backgroundColor: designTokens.color.surfaceSubtle,
        borderColor: designTokens.color.border,
      }}
    >
      <Box
        sx={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          gap: { xs: 1, sm: 1.5 },
          rowGap: 0.75,
        }}
      >
        {items.map((item, index) => {
          const color = TONE_COLOR[item.tone ?? 'default'];
          return (
            <Box
              key={index}
              sx={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 0.5,
                minWidth: 0,
                maxWidth: '100%',
              }}
            >
              {item.icon ? (
                <Box sx={{ color, display: 'inline-flex', '& svg': { fontSize: 16 } }}>
                  {item.icon}
                </Box>
              ) : null}
              <Typography
                variant="body2"
                component="span"
                sx={{ color, fontWeight: item.value !== undefined ? 500 : 400, whiteSpace: 'nowrap' }}
              >
                {item.label}
                {item.value !== undefined ? ': ' : ''}
                {item.value !== undefined ? (
                  <Box component="span" sx={{ fontWeight: 700 }}>
                    {item.value}
                  </Box>
                ) : null}
              </Typography>
              {index < items.length - 1 ? (
                <Box
                  component="span"
                  aria-hidden="true"
                  sx={{ color: 'text.disabled', ml: { xs: 0.25, sm: 0.5 }, display: { xs: 'none', sm: 'inline' } }}
                >
                  |
                </Box>
              ) : null}
            </Box>
          );
        })}
      </Box>
    </Paper>
  );
}