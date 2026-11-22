import { Chip } from '@mui/material';
import type { ChipProps } from '@mui/material/Chip';
import type { ReactNode } from 'react';

const STATUS_COLORS: Record<string, NonNullable<ChipProps['color']>> = {
  pending: 'warning',
  running: 'info',
  completed: 'success',
  succeeded: 'default',
  failed: 'error',
  success: 'success',
  error: 'error',
  warning: 'warning',
  info: 'info',
  default: 'default',
};

interface StatusChipProps extends Omit<ChipProps, 'color' | 'label'> {
  status: string;
  label?: ReactNode;
}

/** Shared status presentation with one color map for all shell indicators. */
export function StatusChip({
  status,
  label,
  size = 'small',
  ...props
}: StatusChipProps) {
  return (
    <Chip
      label={label ?? status}
      color={STATUS_COLORS[status.toLowerCase()] ?? 'default'}
      size={size}
      {...props}
    />
  );
}
