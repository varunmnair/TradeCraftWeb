import React, { useState, useRef, useEffect } from 'react';
import { Box, TextField, Typography, CircularProgress } from '@mui/material';
import CheckIcon from '@mui/icons-material/Check';
import ErrorIcon from '@mui/icons-material/Warning';

export type CellStatus = 'idle' | 'saving' | 'saved' | 'error';

interface InlineEditCellProps {
  value: number | null;
  format: (v: number) => string;
  parse: (s: string) => number | null;
  onSave: (newValue: number) => Promise<void>;
  validate?: (v: number) => string | null;
  status: CellStatus;
  errorMessage?: string;
  emptyDisplay?: string;
}

export function InlineEditCell({
  value,
  format,
  parse,
  onSave,
  validate,
  status,
  errorMessage,
  emptyDisplay = '-',
}: InlineEditCellProps) {
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState(value?.toString() ?? '');
  const [localError, setLocalError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [editing]);

  const handleClick = () => {
    if (status === 'saving') return;
    setEditing(true);
    setEditValue(value?.toString() ?? '');
    setLocalError(null);
  };

  const handleSave = async () => {
    const parsed = parse(editValue);
    if (parsed === null || parsed === undefined) {
      setLocalError('Value must be a number');
      return;
    }
    if (parsed <= 0) {
      setLocalError('Value must be greater than 0');
      return;
    }
    if (validate) {
      const error = validate(parsed);
      if (error) {
        setLocalError(error);
        return;
      }
    }
    setLocalError(null);
    setEditing(false);
    await onSave(parsed);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSave();
    } else if (e.key === 'Escape') {
      setEditing(false);
      setLocalError(null);
    }
  };

  const handleBlur = () => {
    handleSave();
  };

  if (editing) {
    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', minWidth: 80 }}>
        <TextField
          size="small"
          type="text"
          value={editValue}
          onChange={(e) => setEditValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={handleBlur}
          inputRef={inputRef}
          error={!!localError}
          sx={{ minWidth: 80 }}
          inputProps={{
            style: { padding: '4px 8px', fontSize: '0.875rem' },
          }}
        />
        {localError && (
          <Typography variant="caption" color="error" sx={{ mt: 0.5 }}>
            {localError}
          </Typography>
        )}
      </Box>
    );
  }

  return (
    <Box
      onClick={handleClick}
      sx={{
        cursor: status === 'saving' ? 'default' : 'pointer',
        display: 'flex',
        alignItems: 'center',
        gap: 0.5,
        minHeight: 32,
        px: 0.5,
        borderRadius: 1,
        '&:hover': {
          backgroundColor: status === 'saving' ? 'transparent' : 'action.hover',
        },
      }}
    >
      <Typography variant="body2">
        {value != null ? format(value) : emptyDisplay}
      </Typography>
      {status === 'saving' && <CircularProgress size={14} />}
      {status === 'saved' && <CheckIcon sx={{ fontSize: 14, color: 'success.main' }} />}
      {status === 'error' && <ErrorIcon sx={{ fontSize: 14, color: 'error.main' }} />}
    </Box>
  );
}
