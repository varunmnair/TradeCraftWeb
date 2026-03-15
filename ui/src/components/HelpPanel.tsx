import { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  IconButton,
  Box,
  Typography,
  CircularProgress,
} from '@mui/material';
import { Close as CloseIcon } from '@mui/icons-material';
import ReactMarkdown from 'react-markdown';
import { getHelpContent, HelpId } from '../help/helpRegistry';

interface HelpPanelProps {
  open: boolean;
  onClose: () => void;
  helpId?: HelpId;
}

export function HelpPanel({ open, onClose, helpId = 'app' }: HelpPanelProps) {
  const [loading, setLoading] = useState(false);
  const entry = getHelpContent(helpId);

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="md"
      fullWidth
      PaperProps={{
        sx: { maxHeight: '80vh' },
      }}
    >
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', pb: 1 }}>
        <Typography variant="h6" component="div">
          {entry.title}
        </Typography>
        <IconButton onClick={onClose} size="small">
          <CloseIcon />
        </IconButton>
      </DialogTitle>
      <DialogContent dividers>
        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
            <CircularProgress />
          </Box>
        ) : (
          <Box sx={{ typography: 'body1' }}>
            <ReactMarkdown>{entry.content}</ReactMarkdown>
          </Box>
        )}
      </DialogContent>
    </Dialog>
  );
}
