import { Chip } from '@mui/material';
import type { ChipProps } from '@mui/material/Chip';
import {
  CheckCircleOutline as SuccessIcon,
  ErrorOutline as ErrorIcon,
  InfoOutlined as InfoIcon,
  RemoveCircleOutline as NeutralIcon,
  WarningAmberOutlined as WarningIcon,
} from '@mui/icons-material';
import type { ReactNode } from 'react';

export type TradeStatusTone = 'SUCCESS' | 'WARNING' | 'ERROR' | 'INFO' | 'NEUTRAL';

const STATUS_TONE_MAP: Record<string, TradeStatusTone> = {
  pending: 'WARNING',
  running: 'INFO',
  completed: 'SUCCESS',
  succeeded: 'NEUTRAL',
  failed: 'ERROR',
  success: 'SUCCESS',
  error: 'ERROR',
  warning: 'WARNING',
  info: 'INFO',
  default: 'NEUTRAL',
  neutral: 'NEUTRAL',
  ready: 'SUCCESS',
  active: 'INFO',
  inactive: 'NEUTRAL',
};

const TONE_CHIP_COLOR: Record<TradeStatusTone, NonNullable<ChipProps['color']>> = {
  SUCCESS: 'success',
  WARNING: 'warning',
  ERROR: 'error',
  INFO: 'info',
  NEUTRAL: 'default',
};

const TONE_ICON: Record<TradeStatusTone, ReactNode> = {
  SUCCESS: <SuccessIcon fontSize="small" />,
  WARNING: <WarningIcon fontSize="small" />,
  ERROR: <ErrorIcon fontSize="small" />,
  INFO: <InfoIcon fontSize="small" />,
  NEUTRAL: <NeutralIcon fontSize="small" />,
};

export function getTradeStatusTone(status: string): TradeStatusTone {
  return STATUS_TONE_MAP[status.toLowerCase()] ?? 'NEUTRAL';
}

interface StatusChipProps extends Omit<ChipProps, 'color' | 'label'> {
  status: string;
  label?: ReactNode;
  /** Override the inferred semantic tone. */
  tone?: TradeStatusTone;
  /** Show the semantic icon. Defaults to false for backward compatibility. */
  showIcon?: boolean;
}

/** Shared status presentation with one color/icon map for status indicators. */
export function StatusChip({
  status,
  label,
  tone,
  showIcon = false,
  size = 'small',
  ...props
}: StatusChipProps) {
  const resolvedTone = tone ?? getTradeStatusTone(status);
  return (
    <Chip
      label={label ?? status}
      color={TONE_CHIP_COLOR[resolvedTone]}
      icon={showIcon ? (TONE_ICON[resolvedTone] as any) : undefined}
      size={size}
      {...props}
    />
  );
}
