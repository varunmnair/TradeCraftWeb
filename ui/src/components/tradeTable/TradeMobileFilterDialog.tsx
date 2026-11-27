import { useEffect, useMemo, useState } from 'react';
import {
  Box,
  Button,
  Checkbox,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  InputLabel,
  ListItemText,
  MenuItem,
  Select,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import type { GridValidRowModel } from '@mui/x-data-grid';
import { ResponsiveDialog } from '../ResponsiveDialog';
import { getAllowedOperators } from './config';
import { getColumnValue } from './tableState';
import type { TradeColumnDef, TradeFilterOperator, TradeFilterRule } from './types';

interface TradeMobileFilterDialogProps<T extends GridValidRowModel> {
  open: boolean;
  onClose: () => void;
  columns: TradeColumnDef<T>[];
  rows: T[];
  filters: TradeFilterRule[];
  onApply: (filters: TradeFilterRule[]) => void;
  onClear: () => void;
}

type Draft = {
  operator: TradeFilterOperator;
  value: string;
  valueTo: string;
  values: string[];
};

function ruleToDraft(rule: TradeFilterRule | undefined, column: TradeColumnDef<any>): Draft {
  const operator = rule?.operator && getAllowedOperators(column.dataType).includes(rule.operator)
    ? rule.operator
    : getAllowedOperators(column.dataType)[0];
  return {
    operator,
    value: rule?.value == null ? '' : String(rule.value),
    valueTo: rule?.valueTo == null ? '' : String(rule.valueTo),
    values: (rule?.values ?? []).map(String),
  };
}

function draftToRule(columnId: string, column: TradeColumnDef<any>, draft: Draft): TradeFilterRule | null {
  const op = draft.operator;
  if (!getAllowedOperators(column.dataType).includes(op)) return null;

  if (column.dataType === 'text') {
    if (!draft.value.trim()) return null;
    return { columnId, operator: op, value: draft.value.trim() };
  }
  if (column.dataType === 'number') {
    if (op === 'between') {
      if (draft.value === '' && draft.valueTo === '') return null;
      return {
        columnId,
        operator: op,
        value: draft.value === '' ? null : Number(draft.value),
        valueTo: draft.valueTo === '' ? null : Number(draft.valueTo),
      };
    }
    if (draft.value === '') return null;
    return { columnId, operator: op, value: Number(draft.value) };
  }
  if (column.dataType === 'date') {
    if (op === 'between') {
      if (!draft.value && !draft.valueTo) return null;
      return { columnId, operator: op, value: draft.value || null, valueTo: draft.valueTo || null };
    }
    if (!draft.value) return null;
    return { columnId, operator: op, value: draft.value };
  }
  if (column.dataType === 'boolean') {
    if (draft.value !== 'true' && draft.value !== 'false') return null;
    return { columnId, operator: 'is', value: draft.value === 'true' };
  }
  if (column.dataType === 'categorical') {
    if (draft.values.length === 0) return null;
    return { columnId, operator: 'in', values: draft.values };
  }
  return null;
}

export function TradeMobileFilterDialog<T extends GridValidRowModel>({
  open,
  onClose,
  columns,
  rows,
  filters,
  onApply,
  onClear,
}: TradeMobileFilterDialogProps<T>) {
  const filterable = useMemo(() => columns.filter((c) => c.filterable && !c.tableHidden), [columns]);
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});

  useEffect(() => {
    if (!open) return;
    const next: Record<string, Draft> = {};
    for (const col of filterable) {
      next[col.id] = ruleToDraft(filters.find((f) => f.columnId === col.id), col);
    }
    setDrafts(next);
  }, [open, filterable, filters]);

  const categoricalOptions = useMemo(() => {
    const map = new Map<string, Array<{ label: string; value: string }>>();
    for (const col of filterable) {
      if (col.dataType !== 'categorical') continue;
      if (col.filterOptions?.length) {
        map.set(col.id, col.filterOptions.map((o) => ({ label: o.label, value: String(o.value) })));
        continue;
      }
      const values = Array.from(
        new Set(
          rows
            .map((row) => getColumnValue(row, col))
            .filter((v) => v != null && v !== '')
            .map((v) => String(v)),
        ),
      ).sort((a, b) => a.localeCompare(b));
      map.set(col.id, values.map((v) => ({ label: v, value: v })));
    }
    return map;
  }, [filterable, rows]);

  const setDraft = (columnId: string, patch: Partial<Draft>) => {
    setDrafts((prev) => ({ ...prev, [columnId]: { ...prev[columnId], ...patch } }));
  };

  const handleApply = () => {
    const next: TradeFilterRule[] = [];
    for (const col of filterable) {
      const draft = drafts[col.id];
      if (!draft) continue;
      const rule = draftToRule(col.id, col, draft);
      if (rule) next.push(rule);
    }
    onApply(next);
    onClose();
  };

  const handleClear = () => {
    onClear();
    onClose();
  };

  return (
    <ResponsiveDialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>Filters</DialogTitle>
      <DialogContent dividers>
        <Stack spacing={2} sx={{ mt: 0.5 }}>
          {filterable.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              No filters are available for this table.
            </Typography>
          ) : (
            filterable.map((col) => {
              const draft = drafts[col.id] ?? ruleToDraft(undefined, col);
              const operators = getAllowedOperators(col.dataType);
              return (
                <Box key={col.id} sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                  <Typography variant="subtitle2">{col.label}</Typography>
                  {operators.length > 1 ? (
                    <FormControl size="small" fullWidth>
                      <InputLabel id={`filter-op-${col.id}`}>Operator</InputLabel>
                      <Select
                        labelId={`filter-op-${col.id}`}
                        label="Operator"
                        value={draft.operator}
                        onChange={(e) => setDraft(col.id, { operator: e.target.value as TradeFilterOperator })}
                      >
                        {operators.map((op) => (
                          <MenuItem key={op} value={op}>
                            {op === 'gt' ? 'Greater than' : op === 'lt' ? 'Less than' : op === 'in' ? 'Includes' : op === 'is' ? 'Is' : op.charAt(0).toUpperCase() + op.slice(1)}
                          </MenuItem>
                        ))}
                      </Select>
                    </FormControl>
                  ) : null}

                  {col.dataType === 'text' ? (
                    <TextField
                      size="small"
                      fullWidth
                      label="Value"
                      value={draft.value}
                      onChange={(e) => setDraft(col.id, { value: e.target.value })}
                    />
                  ) : null}

                  {col.dataType === 'number' ? (
                    <Box sx={{ display: 'flex', gap: 1, flexDirection: { xs: 'column', sm: 'row' } }}>
                      <TextField
                        size="small"
                        fullWidth
                        type="number"
                        label={draft.operator === 'between' ? 'From' : 'Value'}
                        value={draft.value}
                        onChange={(e) => setDraft(col.id, { value: e.target.value })}
                      />
                      {draft.operator === 'between' ? (
                        <TextField
                          size="small"
                          fullWidth
                          type="number"
                          label="To"
                          value={draft.valueTo}
                          onChange={(e) => setDraft(col.id, { valueTo: e.target.value })}
                        />
                      ) : null}
                    </Box>
                  ) : null}

                  {col.dataType === 'date' ? (
                    <Box sx={{ display: 'flex', gap: 1, flexDirection: { xs: 'column', sm: 'row' } }}>
                      <TextField
                        size="small"
                        fullWidth
                        type="date"
                        label={draft.operator === 'between' ? 'From' : 'Date'}
                        InputLabelProps={{ shrink: true }}
                        value={draft.value}
                        onChange={(e) => setDraft(col.id, { value: e.target.value })}
                      />
                      {draft.operator === 'between' ? (
                        <TextField
                          size="small"
                          fullWidth
                          type="date"
                          label="To"
                          InputLabelProps={{ shrink: true }}
                          value={draft.valueTo}
                          onChange={(e) => setDraft(col.id, { valueTo: e.target.value })}
                        />
                      ) : null}
                    </Box>
                  ) : null}

                  {col.dataType === 'boolean' ? (
                    <FormControl size="small" fullWidth>
                      <InputLabel id={`filter-bool-${col.id}`}>Value</InputLabel>
                      <Select
                        labelId={`filter-bool-${col.id}`}
                        label="Value"
                        value={draft.value}
                        onChange={(e) => setDraft(col.id, { value: String(e.target.value) })}
                      >
                        <MenuItem value="">Any</MenuItem>
                        <MenuItem value="true">Yes</MenuItem>
                        <MenuItem value="false">No</MenuItem>
                      </Select>
                    </FormControl>
                  ) : null}

                  {col.dataType === 'categorical' ? (
                    <FormControl size="small" fullWidth>
                      <InputLabel id={`filter-cat-${col.id}`}>Values</InputLabel>
                      <Select
                        labelId={`filter-cat-${col.id}`}
                        label="Values"
                        multiple
                        value={draft.values}
                        onChange={(e) => {
                          const value = e.target.value;
                          setDraft(col.id, { values: typeof value === 'string' ? value.split(',') : value });
                        }}
                        renderValue={(selected) => (selected as string[]).join(', ')}
                      >
                        {(categoricalOptions.get(col.id) ?? []).map((option) => (
                          <MenuItem key={option.value} value={option.value}>
                            <Checkbox checked={draft.values.includes(option.value)} size="small" />
                            <ListItemText primary={option.label} />
                          </MenuItem>
                        ))}
                      </Select>
                    </FormControl>
                  ) : null}
                </Box>
              );
            })
          )}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClear} color="inherit">
          Clear
        </Button>
        <Button onClick={onClose}>Cancel</Button>
        <Button onClick={handleApply} variant="contained">
          Apply
        </Button>
      </DialogActions>
    </ResponsiveDialog>
  );
}