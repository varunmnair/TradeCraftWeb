import { useEffect, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  DialogActions,
  DialogContent,
  DialogTitle,
  TextField,
} from '@mui/material';
import { ResponsiveDialog } from '../ResponsiveDialog';
import type { EntryStrategySummary } from '../../types';
import {
  parseNumericInput,
  validateStrategyForm,
  type StrategyFormErrors,
  type StrategyFormValues,
} from './strategyDisplay';

interface MobileStrategyEditDialogProps {
  open: boolean;
  strategy: EntryStrategySummary | null;
  saving: boolean;
  errorMessage: string;
  onClose: () => void;
  onSave: (values: StrategyFormValues) => Promise<void>;
}

const toInput = (value: number | null) => (value == null ? '' : String(value));

export function MobileStrategyEditDialog({
  open,
  strategy,
  saving,
  errorMessage,
  onClose,
  onSave,
}: MobileStrategyEditDialogProps) {
  const [form, setForm] = useState({
    allocated: '',
    entry1: '',
    entry2: '',
    entry3: '',
  });
  const [errors, setErrors] = useState<StrategyFormErrors>({});

  useEffect(() => {
    if (!open || !strategy) return;
    setForm({
      allocated: toInput(strategy.allocated),
      entry1: toInput(strategy.entry1),
      entry2: toInput(strategy.entry2),
      entry3: toInput(strategy.entry3),
    });
    setErrors({});
  }, [open, strategy]);

  const handleChange = (field: keyof typeof form, value: string) => {
    setForm((previous) => ({ ...previous, [field]: value }));
    setErrors((previous) => ({ ...previous, [field]: undefined }));
  };

  const handleSave = async () => {
    if (saving) return;
    const values: StrategyFormValues = {
      allocated: parseNumericInput(form.allocated),
      entry1: parseNumericInput(form.entry1),
      entry2: parseNumericInput(form.entry2),
      entry3: parseNumericInput(form.entry3),
    };
    const nextErrors = validateStrategyForm(values);
    if (Object.keys(nextErrors).length > 0) {
      setErrors(nextErrors);
      return;
    }
    setErrors({});
    await onSave(values);
  };

  const numericProps = { inputMode: 'decimal' as const, step: 'any' };

  return (
    <ResponsiveDialog
      open={open}
      onClose={saving ? undefined : onClose}
      maxWidth="xs"
      fullWidth
      PaperProps={{ sx: { m: { sm: 2 } } }}
    >
      <DialogTitle>Edit {strategy?.symbol ?? 'Strategy'}</DialogTitle>
      <DialogContent dividers>
        {errorMessage && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {errorMessage}
          </Alert>
        )}
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 0.5 }}>
          <TextField
            label="Symbol"
            value={strategy?.symbol ?? ''}
            fullWidth
            InputProps={{ readOnly: true }}
            size="small"
          />
          <TextField
            label="Allocation"
            type="number"
            value={form.allocated}
            onChange={(event) => handleChange('allocated', event.target.value)}
            error={Boolean(errors.allocated)}
            helperText={errors.allocated || ' '}
            fullWidth
            size="small"
            inputProps={{ ...numericProps, min: 0 }}
          />
          <TextField
            label="Entry 1"
            type="number"
            value={form.entry1}
            onChange={(event) => handleChange('entry1', event.target.value)}
            error={Boolean(errors.entry1)}
            helperText={errors.entry1 || ' '}
            fullWidth
            size="small"
            inputProps={{ ...numericProps, min: 0 }}
          />
          <TextField
            label="Entry 2 (optional)"
            type="number"
            value={form.entry2}
            onChange={(event) => handleChange('entry2', event.target.value)}
            error={Boolean(errors.entry2)}
            helperText={errors.entry2 || ' '}
            fullWidth
            size="small"
            inputProps={{ ...numericProps, min: 0 }}
          />
          <TextField
            label="Entry 3 (optional)"
            type="number"
            value={form.entry3}
            onChange={(event) => handleChange('entry3', event.target.value)}
            error={Boolean(errors.entry3)}
            helperText={errors.entry3 || ' '}
            fullWidth
            size="small"
            inputProps={{ ...numericProps, min: 0 }}
          />
        </Box>
      </DialogContent>
      <DialogActions
        sx={{
          position: { xs: 'sticky', sm: 'static' },
          bottom: 0,
          bgcolor: 'background.paper',
          borderTop: '1px solid',
          borderColor: 'divider',
          p: 1.5,
        }}
      >
        <Button onClick={onClose} disabled={saving} fullWidth={false}>
          Cancel
        </Button>
        <Button onClick={handleSave} variant="contained" disabled={saving} fullWidth={false}>
          {saving ? 'Saving...' : 'Save'}
        </Button>
      </DialogActions>
    </ResponsiveDialog>
  );
}