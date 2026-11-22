import { useState } from 'react';
import type { MouseEvent } from 'react';
import {
  Box,
  Button,
  Divider,
  FormControl,
  IconButton,
  InputAdornment,
  InputLabel,
  ListItemText,
  Menu,
  MenuItem,
  Select,
  TextField,
  Typography,
} from '@mui/material';
import {
  Clear as ClearIcon,
  FilterList as FilterIcon,
  Search as SearchIcon,
  Sort as SortIcon,
} from '@mui/icons-material';
import { ResponsiveToolbar } from '../ResponsiveToolbar';

export interface EntryStrategyFilters {
  reviewStatus: string;
  swingEligibility: string;
  reviewDue: string;
}

export const INITIAL_ENTRY_STRATEGY_FILTERS: EntryStrategyFilters = {
  reviewStatus: 'ALL',
  swingEligibility: 'ALL',
  reviewDue: 'ALL',
};

export interface StrategySort {
  field: string;
  direction: 'asc' | 'desc';
}

const SORT_FIELDS = [
  { field: 'symbol', label: 'Symbol' },
  { field: 'allocated', label: 'Allocation' },
  { field: 'cmp', label: 'CMP' },
  { field: 'delta', label: 'Variance' },
  { field: 'updated', label: 'Updated On' },
] as const;

const REVIEW_STATUS_OPTIONS = [
  { value: 'ALL', label: 'All statuses' },
  { value: 'ACTIVE', label: 'ACTIVE' },
  { value: 'REVIEW_REQUIRED', label: 'REVIEW REQUIRED' },
  { value: 'NONE', label: 'Not evaluated' },
];

const SWING_OPTIONS = [
  { value: 'ALL', label: 'All' },
  { value: 'YES', label: 'Yes' },
  { value: 'NO', label: 'No' },
  { value: 'NONE', label: 'Not checked' },
];

const REVIEW_DUE_OPTIONS = [
  { value: 'ALL', label: 'All' },
  { value: 'YES', label: 'Review due' },
  { value: 'NO', label: 'Not due' },
];

interface EntryStrategiesMobileControlsProps {
  search: string;
  onSearchChange: (value: string) => void;
  sortBy: StrategySort | null;
  onSort: (field: string) => void;
  filters: EntryStrategyFilters;
  onFiltersChange: (filters: EntryStrategyFilters) => void;
  onClearFilters: () => void;
}

export function EntryStrategiesMobileControls({
  search,
  onSearchChange,
  sortBy,
  onSort,
  filters,
  onFiltersChange,
  onClearFilters,
}: EntryStrategiesMobileControlsProps) {
  const [sortAnchorEl, setSortAnchorEl] = useState<HTMLElement | null>(null);
  const [filterAnchorEl, setFilterAnchorEl] = useState<HTMLElement | null>(null);

  const currentSort = sortBy ?? { field: 'updated', direction: 'desc' as const };
  const currentSortLabel =
    SORT_FIELDS.find((field) => field.field === currentSort.field)?.label ?? 'Updated On';
  const activeFilterCount = [
    filters.reviewStatus !== 'ALL',
    filters.swingEligibility !== 'ALL',
    filters.reviewDue !== 'ALL',
  ].filter(Boolean).length;

  const handleFilterChange = (patch: Partial<EntryStrategyFilters>) => {
    onFiltersChange({ ...filters, ...patch });
  };

  return (
    <Box sx={{ mb: 2 }}>
      <TextField
        fullWidth
        size="small"
        placeholder="Search by symbol"
        value={search}
        onChange={(event) => onSearchChange(event.target.value)}
        inputProps={{ 'aria-label': 'Search strategies by symbol' }}
        InputProps={{
          startAdornment: (
            <InputAdornment position="start">
              <SearchIcon fontSize="small" />
            </InputAdornment>
          ),
          endAdornment: search ? (
            <InputAdornment position="end">
              <IconButton
                size="small"
                aria-label="Clear search"
                onClick={() => onSearchChange('')}
              >
                <ClearIcon fontSize="small" />
              </IconButton>
            </InputAdornment>
          ) : undefined,
        }}
      />

      <ResponsiveToolbar sx={{ mt: 1, gap: 1 }}>
        <Button
          size="small"
          variant="outlined"
          startIcon={<SortIcon />}
          onClick={(event: MouseEvent<HTMLElement>) => setSortAnchorEl(event.currentTarget)}
          sx={{ flex: 1, minWidth: 0, textTransform: 'none' }}
        >
          Sort: {sortBy ? currentSortLabel : 'None'}{' '}
          {sortBy ? (currentSort.direction === 'asc' ? '↑' : '↓') : ''}
        </Button>
        <Button
          size="small"
          variant="outlined"
          startIcon={<FilterIcon />}
          onClick={(event: MouseEvent<HTMLElement>) => setFilterAnchorEl(event.currentTarget)}
          sx={{ flex: 1, minWidth: 0, textTransform: 'none' }}
        >
          Filter{activeFilterCount ? ` (${activeFilterCount})` : ''}
        </Button>
        {activeFilterCount > 0 && (
          <Button size="small" onClick={onClearFilters} sx={{ textTransform: 'none' }}>
            Clear
          </Button>
        )}
      </ResponsiveToolbar>

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
            selected={currentSort.field === field.field}
            onClick={() => {
              onSort(field.field);
              setSortAnchorEl(null);
            }}
          >
            <ListItemText
              primary={field.label}
              secondary={
                currentSort.field === field.field
                  ? currentSort.direction === 'asc'
                    ? 'Ascending'
                    : 'Descending'
                  : undefined
              }
            />
          </MenuItem>
        ))}
      </Menu>

      <Menu
        anchorEl={filterAnchorEl}
        open={Boolean(filterAnchorEl)}
        onClose={() => setFilterAnchorEl(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
        transformOrigin={{ vertical: 'top', horizontal: 'right' }}
        PaperProps={{ sx: { width: 280, maxWidth: 'calc(100vw - 32px)', p: 2 } }}
      >
        <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1.5 }}>
          Filter Strategies
        </Typography>
        <FormControl fullWidth size="small" sx={{ mb: 1.5 }}>
          <InputLabel id="strategy-filter-review-label">Review Status</InputLabel>
          <Select
            labelId="strategy-filter-review-label"
            label="Review Status"
            value={filters.reviewStatus}
            onChange={(event) => handleFilterChange({ reviewStatus: event.target.value })}
          >
            {REVIEW_STATUS_OPTIONS.map((option) => (
              <MenuItem key={option.value} value={option.value}>
                {option.label}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <FormControl fullWidth size="small" sx={{ mb: 1.5 }}>
          <InputLabel id="strategy-filter-swing-label">Swing Eligibility</InputLabel>
          <Select
            labelId="strategy-filter-swing-label"
            label="Swing Eligibility"
            value={filters.swingEligibility}
            onChange={(event) => handleFilterChange({ swingEligibility: event.target.value })}
          >
            {SWING_OPTIONS.map((option) => (
              <MenuItem key={option.value} value={option.value}>
                {option.label}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <FormControl fullWidth size="small" sx={{ mb: 2 }}>
          <InputLabel id="strategy-filter-due-label">Review Due</InputLabel>
          <Select
            labelId="strategy-filter-due-label"
            label="Review Due"
            value={filters.reviewDue}
            onChange={(event) => handleFilterChange({ reviewDue: event.target.value })}
          >
            {REVIEW_DUE_OPTIONS.map((option) => (
              <MenuItem key={option.value} value={option.value}>
                {option.label}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <Divider sx={{ mb: 1.5 }} />
        <Button fullWidth size="small" onClick={onClearFilters}>
          Clear Filters
        </Button>
      </Menu>
    </Box>
  );
}