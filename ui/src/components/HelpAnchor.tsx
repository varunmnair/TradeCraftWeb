import { IconButton, Tooltip } from '@mui/material';
import { Info as InfoIcon } from '@mui/icons-material';

const HELP_ANCHOR_ENABLED = false;

interface HelpAnchorProps {
  helpId: string;
  label?: string;
}

export function HelpAnchor({ helpId, label }: HelpAnchorProps) {
  if (!HELP_ANCHOR_ENABLED) {
    return null;
  }

  return (
    <Tooltip title={label || `Help: ${helpId}`}>
      <IconButton size="small" color="primary">
        <InfoIcon fontSize="small" />
      </IconButton>
    </Tooltip>
  );
}
