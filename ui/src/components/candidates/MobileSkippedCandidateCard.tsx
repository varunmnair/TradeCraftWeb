import { memo, useState } from 'react';
import { Box, Button, Chip, Divider, Typography } from '@mui/material';
import type { SkippedCandidate } from '../../types';
import {
  candidateStrategyColor,
  candidateStrategyLabel,
  fmtCurrency,
} from './candidateDisplay';

interface MobileSkippedCandidateCardProps {
  skipped: SkippedCandidate;
}

function MobileSkippedCandidateCardBase({ skipped }: MobileSkippedCandidateCardProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <Box
      component="article"
      sx={{
        border: 1,
        borderColor: 'divider',
        borderRadius: 1,
        bgcolor: 'background.paper',
        mb: 1.5,
        overflow: 'hidden',
      }}
    >
      <Box sx={{ p: 1.5 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
          <Typography variant="subtitle1" sx={{ fontWeight: 800, letterSpacing: 0.3 }}>
            {skipped.symbol}
          </Typography>
          <Chip
            label={candidateStrategyLabel[skipped.strategy_type] ?? skipped.strategy_type}
            size="small"
            color={candidateStrategyColor[skipped.strategy_type] ?? 'default'}
            variant="outlined"
            sx={{ height: 22, fontSize: '0.7rem' }}
          />
        </Box>
        <Typography
          variant="body2"
          color="text.secondary"
          sx={{
            mt: 0.75,
            display: '-webkit-box',
            WebkitLineClamp: expanded ? 'unset' : 2,
            WebkitBoxOrient: 'vertical',
            overflow: 'hidden',
            whiteSpace: 'normal',
          }}
        >
          {skipped.reason_message}
        </Typography>
        <Button
          fullWidth
          size="small"
          onClick={() => setExpanded((value) => !value)}
          aria-expanded={expanded}
          sx={{ mt: 1, minHeight: 36 }}
        >
          {expanded ? 'Hide Details' : 'View Details'}
        </Button>
      </Box>

      {expanded && (
        <Box sx={{ px: 1.5, pb: 1.5 }}>
          <Divider sx={{ mb: 0.5 }} />
          <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 2, py: 0.6 }}>
            <Typography variant="body2" color="text.secondary">CMP</Typography>
            <Typography variant="body2" fontWeight={700}>{fmtCurrency(skipped.cmp)}</Typography>
          </Box>
          {skipped.level_or_leg && (
            <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 2, py: 0.6 }}>
              <Typography variant="body2" color="text.secondary">Entry / Leg</Typography>
              <Typography variant="body2" fontWeight={700}>{skipped.level_or_leg}</Typography>
            </Box>
          )}
          <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1 }}>
            Full reason
          </Typography>
          <Typography variant="body2" sx={{ whiteSpace: 'normal', wordBreak: 'break-word' }}>
            {skipped.reason_message}
          </Typography>
          {skipped.suggested_action && (
            <>
              <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1 }}>
                Suggested Action
              </Typography>
              <Typography variant="body2" sx={{ whiteSpace: 'normal' }}>
                {skipped.suggested_action}
              </Typography>
            </>
          )}
          {skipped.technical_details && (
            <>
              <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1 }}>
                Technical details
              </Typography>
              <Typography variant="caption" sx={{ whiteSpace: 'normal', wordBreak: 'break-word' }}>
                {skipped.technical_details}
              </Typography>
            </>
          )}
        </Box>
      )}
    </Box>
  );
}

export const MobileSkippedCandidateCard = memo(MobileSkippedCandidateCardBase);