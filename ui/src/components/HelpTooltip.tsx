import { ReactElement } from 'react';
import { Tooltip, TooltipProps } from '@mui/material';

interface HelpTooltipProps extends Omit<TooltipProps, 'children'> {
  children: ReactElement;
}

export function HelpTooltip({ children, ...props }: HelpTooltipProps) {
  return (
    <Tooltip {...props}>
      {children}
    </Tooltip>
  );
}
