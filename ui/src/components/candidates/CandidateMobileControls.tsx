import { useState } from 'react';
import type { MouseEvent } from 'react';
import {
  Box,
  Button,
  FormControl,
  IconButton,
  InputLabel,
  ListItemText,
  Menu,
  MenuItem,
  Paper,
  Select,
  Typography,
} from '@mui/material';
import {
  Clear as ClearIcon,
  FilterList as FilterIcon,
  Sort as SortIcon,
} from '@mui/icons-material';
import { ResponsiveToolbar } from '../ResponsiveToolbar';

export interface CandidateSort {
  field: 'symbol' | 'cmp' | 'amount' | 'status' | 'strategy';
  direction: 'asc' | 'desc';
}

export const INITIAL_CANDIDATE_SORT: CandidateSort = {
  field: 'symbol',
  direction: 'asc',
};

const STRATEGY_OPTIONS = [
  { value: 'ALL', label: 'All strategies' },
  { value: 'MULTI_LEVEL', label: 'Multi-Level Entry' },
  { value: 'DYNAMIC_AVERAGING', label: 'Dynamic Averaging' },
];

const STATUS_OPTIONS = [
  { value: 'ALL', label: 'All statuses' },
  { value: 'READY', label: 'Ready' },
  { value: 'WARNING', label: 'Warning' },
  { value: 'REVIEW', label: 'Review' },
  { value: 'SKIPPED', label: 'Skipped' },
];

const SORT_FIELDS: Array<{ field: CandidateSort['field']; label: string }> = [
  { field: 'symbol', label: 'Symbol' },
  { field: 'cmp', label: 'CMP' },
  { field: 'amount', label: 'Order Value' },
  { field: 'status', label: 'Status' },
  { field: 'strategy', label: 'Strategy' },
];

interface CandidateMobileControlsProps {
  strategyFilter: string;
  statusFilter: string;
  onStrategyFilterChange: (value: string) => void;
  onStatusFilterChange: (value: string) => void;
  sortBy: CandidateSort | null;
  onSort: (field: CandidateSort['field']) => void;
  onSelectReady: () => void;
  onClearSelection: () => void;
  onClearFilters: () => void;
  selectedCount: number;
  busy: boolean;
}

export function CandidateMobileControls({
  strategyFilter,
  statusFilter,
  onStrategyFilterChange,
  onStatusFilterChange,
  sortBy,
  onSort,
  onSelectReady,
  onClearSelection,
  onClearFilters,
  selectedCount,
  busy,
}: CandidateMobileControlsProps) {
  const [sortAnchorEl, setSortAnchorEl] = useState<HTMLElement | null>(null);
  const activeFilterCount = [
    strategyFilter !== 'ALL',
    statusFilter !== 'ALL',
  ].filter(Boolean).length;
  const currentSort = sortBy ?? INITIAL_CANDIDATE_SORT;
  const currentSortLabel =
    SORT_FIELDS.find((field) => field.field === currentSort.field)?.label ?? 'Symbol';

  return (
    <Box sx={{ mb: 2 }}>
      <Paper sx={{ p: 1.5 }}>
        <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 1 }}>
          <FormControl fullWidth size="small">
            <InputLabel id="candidate-strategy-filter-label">Strategy</InputLabel>
            <Select
              labelId="candidate-strategy-filter-label"
              label="Strategy"
              value={strategyFilter}
              onChange={(event) => onStrategyFilterChange(event.target.value)}
            >
              {STRATEGY_OPTIONS.map((option) => (
                <MenuItem key={option.value} value={option.value}>
                  {option.label}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <FormControl fullWidth size="small">
            <InputLabel id="candidate-status-filter-label">Status</InputLabel>
            <Select
              labelId="candidate-status-filter-label"
              label="Status"
              value={statusFilter}
              onChange={(event) => onStatusFilterChange(event.target.value)}
            >
              {STATUS_OPTIONS.map((option) => (
                <MenuItem key={option.value} value={option.value}>
                  {option.label}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Box>

        <ResponsiveToolbar sx={{ mt: 1.25, gap: 1 }}>
          <Button
            size="small"
            variant="outlined"
            startIcon={<SortIcon />}
            onClick={(event: MouseEvent<HTMLElement>) => setSortAnchorEl(event.currentTarget)}
            sx={{ flex: 1, minWidth: 0, textTransform: 'none' }}
          >
            Sort: {sortBy ? currentSortLabel : 'Default'}{' '}
            {sortBy ? (currentSort.direction === 'asc' ? '↑' : '↓') : ''}
          </Button>
          <Button
            size="small"
            variant="outlined"
            onClick={onSelectReady}
            disabled={busy}
            sx={{ flex: 1, minWidth: 0, textTransform: 'none' }}
          >
            Select Ready
          </Button>
          {selectedCount > 0 && (
            <IconButton size="small" aria-label="Clear selection" onClick={onClearSelection}>
              <ClearIcon />
            </IconButton>
          )}
          {activeFilterCount > 0 && (
            <Button
              size="small"
              startIcon={<FilterIcon />}
              onClick={onClearFilters}
              sx={{ textTransform: 'none' }}
            >
              Clear
            </Button>
          )}
        </ResponsiveToolbar>
      </Paper>

      <Menu
        anchorEl={sortAnchorEl}
        open={Boolean(sortAnchorEl)}
        onClose={() => setSortAnchorEl(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
        transformOrigin={{ vertical: 'top', horizontal: 'left' }}
      >
        {SORT_FIELDS.map((field) => (
          <MenuItem
            key={field.field}
            selected={sortBy?.field === field.field}
            onClick={() => {
              onSort(field.field);
              setSortAnchorEl(null);
            }}
          >
            <ListItemText
              primary={field.label}
              secondary={
                sortBy?.field === field.field
                  ? sortBy.direction === 'asc'
                    ? 'Ascending'
                    : 'Descending'
                  : undefined
              }
            />
          </MenuItem>
        ))}
      </Menu>
      {activeFilterCount > 0 && (
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.75 }}>
          Filters active. Clear to see all candidates.
        </Typography>
      )}
    </Box>
  );
}