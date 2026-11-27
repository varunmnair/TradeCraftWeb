import { Alert, AlertTitle, Box } from '@mui/material';
import type { AlertProps } from '@mui/material/Alert';
import type { ReactNode } from 'react';

export type TradeStatusKind = 'persistent' | 'actionable' | 'critical' | 'temporary';

const KIND_SEVERITY: Record<TradeStatusKind, NonNullable<AlertProps['severity']>> = {
  persistent: 'info',
  actionable: 'warning',
  critical: 'error',
  temporary: 'success',
};

interface TradeStatusAlertProps extends Omit<AlertProps, 'severity' | 'title'> {
  kind: TradeStatusKind;
  severity?: AlertProps['severity'];
  title?: ReactNode;
  message: ReactNode;
  /** Action area for Retry/Reconnect/other follow-up. */
  action?: ReactNode;
}

/**
 * Shared status presentation for page-level messages. Use persistent for
 * non-blocking context, actionable for warnings requiring user attention,
 * critical for blocking errors, and temporary for short success feedback.
 */
export function TradeStatusAlert({
  kind,
  severity,
  title,
  message,
  action,
  sx,
  ...props
}: TradeStatusAlertProps) {
  const resolvedSeverity = severity ?? KIND_SEVERITY[kind];
  return (
    <Alert
      severity={resolvedSeverity}
      action={action}
      sx={{ alignItems: 'flex-start', ...sx }}
      {...props}
    >
      {title ? <AlertTitle>{title}</AlertTitle> : null}
      <Box component="div" sx={{ wordBreak: 'break-word' }}>
        {message}
      </Box>
    </Alert>
  );
}