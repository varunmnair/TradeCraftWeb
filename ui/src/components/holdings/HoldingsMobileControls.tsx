import { useState } from 'react';
import type { MouseEvent } from 'react';
import {
  Button,
  Divider,
  FormControl,
  InputLabel,
  ListItemText,
  Menu,
  MenuItem,
  Select,
  Typography,
} from '@mui/material';
import { FilterList as FilterIcon, Sort as SortIcon } from '@mui/icons-material';
import type { GridSortModel } from '@mui/x-data-grid';
import { ResponsiveToolbar } from '../ResponsiveToolbar';

export interface HoldingsMobileFilters {
  signal: string;
  quality: string;
  performance: 'ALL' | 'PROFIT' | 'LOSS';
}

export const INITIAL_HOLDINGS_FILTERS: HoldingsMobileFilters = {
  signal: 'ALL',
  quality: 'ALL',
  performance: 'ALL',
};

const SORT_FIELDS = [
  { field: 'symbol', label: 'Symbol' },
  { field: 'profit', label: 'Profit' },
  { field: 'profit_pct', label: 'Profit %' },
  { field: 'invested', label: 'Invested' },
  { field: 'weighted_roi', label: 'WROI' },
  { field: 'exit_score', label: 'Exit Score' },
] as const;

const SIGNAL_OPTIONS = ['ALL', 'HOLD', 'WATCH', 'REDUCE', 'EXIT', 'BREAK'];
const PERFORMANCE_OPTIONS: Array<{ value: HoldingsMobileFilters['performance']; label: string }> = [
  { value: 'ALL', label: 'All' },
  { value: 'PROFIT', label: 'Profit' },
  { value: 'LOSS', label: 'Loss' },
];

interface HoldingsMobileControlsProps {
  sortModel: GridSortModel;
  onSortChange: (model: GridSortModel) => void;
  filters: HoldingsMobileFilters;
  onFiltersChange: (filters: HoldingsMobileFilters) => void;
  qualityOptions: string[];
}

export function HoldingsMobileControls({
  sortModel,
  onSortChange,
  filters,
  onFiltersChange,
  qualityOptions,
}: HoldingsMobileControlsProps) {
  const [sortAnchorEl, setSortAnchorEl] = useState<HTMLElement | null>(null);
  const [filterAnchorEl, setFilterAnchorEl] = useState<HTMLElement | null>(null);

  const currentSort = sortModel[0] ?? { field: 'weighted_roi', sort: 'desc' as const };
  const currentSortLabel =
    SORT_FIELDS.find((field) => field.field === currentSort.field)?.label ?? 'WROI';
  const activeFilterCount = [
    filters.signal !== 'ALL',
    filters.quality !== 'ALL',
    filters.performance !== 'ALL',
  ].filter(Boolean).length;

  const handleSortOpen = (event: MouseEvent<HTMLElement>) => {
    setSortAnchorEl(event.currentTarget);
  };

  const handleFilterOpen = (event: MouseEvent<HTMLElement>) => {
    setFilterAnchorEl(event.currentTarget);
  };

  const handleSortField = (field: string) => {
    onSortChange([{ field, sort: currentSort.sort ?? 'desc' }]);
    setSortAnchorEl(null);
  };

  const handleToggleDirection = () => {
    onSortChange([
      { field: currentSort.field, sort: currentSort.sort === 'asc' ? 'desc' : 'asc' },
    ]);
    setSortAnchorEl(null);
  };

  const handleFilterChange = (patch: Partial<HoldingsMobileFilters>) => {
    onFiltersChange({ ...filters, ...patch });
  };

  return (
    <>
      <ResponsiveToolbar sx={{ mb: 1.5, gap: 1 }}>
        <Button
          size="small"
          variant="outlined"
          startIcon={<SortIcon />}
          onClick={handleSortOpen}
          sx={{ flex: 1, minWidth: 0, textTransform: 'none' }}
        >
          Sort: {currentSortLabel} {currentSort.sort === 'asc' ? '↑' : '↓'}
        </Button>
        <Button
          size="small"
          variant="outlined"
          startIcon={<FilterIcon />}
          onClick={handleFilterOpen}
          sx={{ flex: 1, minWidth: 0, textTransform: 'none' }}
        >
          Filter{activeFilterCount ? ` (${activeFilterCount})` : ''}
        </Button>
      </ResponsiveToolbar>

      <Menu
        anchorEl={sortAnchorEl}
        open={Boolean(sortAnchorEl)}
        onClose={() => setSortAnchorEl(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
        transformOrigin={{ vertical: 'top', horizontal: 'left' }}
      >
        <MenuItem onClick={handleToggleDirection}>
          <ListItemText
            primary={`Direction: ${currentSort.sort === 'asc' ? 'Ascending' : 'Descending'}`}
            secondary="Tap to toggle"
          />
        </MenuItem>
        <Divider />
        {SORT_FIELDS.map((field) => (
          <MenuItem
            key={field.field}
            selected={currentSort.field === field.field}
            onClick={() => handleSortField(field.field)}
          >
            <ListItemText primary={field.label} />
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
          Filter Holdings
        </Typography>
        <FormControl fullWidth size="small" sx={{ mb: 1.5 }}>
          <InputLabel id="holding-filter-signal-label">Signal</InputLabel>
          <Select
            labelId="holding-filter-signal-label"
            label="Signal"
            value={filters.signal}
            onChange={(event) => handleFilterChange({ signal: event.target.value })}
          >
            {SIGNAL_OPTIONS.map((option) => (
              <MenuItem key={option} value={option}>
                {option === 'ALL' ? 'All signals' : option}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <FormControl fullWidth size="small" sx={{ mb: 1.5 }}>
          <InputLabel id="holding-filter-quality-label">Quality</InputLabel>
          <Select
            labelId="holding-filter-quality-label"
            label="Quality"
            value={filters.quality}
            onChange={(event) => handleFilterChange({ quality: event.target.value })}
          >
            <MenuItem value="ALL">All qualities</MenuItem>
            {qualityOptions.map((option) => (
              <MenuItem key={option} value={option}>
                {option}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <FormControl fullWidth size="small" sx={{ mb: 2 }}>
          <InputLabel id="holding-filter-performance-label">Profit / Loss</InputLabel>
          <Select
            labelId="holding-filter-performance-label"
            label="Profit / Loss"
            value={filters.performance}
            onChange={(event) =>
              handleFilterChange({
                performance: event.target.value as HoldingsMobileFilters['performance'],
              })
            }
          >
            {PERFORMANCE_OPTIONS.map((option) => (
              <MenuItem key={option.value} value={option.value}>
                {option.label}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <Button
          fullWidth
          size="small"
          onClick={() => {
            onFiltersChange(INITIAL_HOLDINGS_FILTERS);
            setFilterAnchorEl(null);
          }}
        >
          Reset Filters
        </Button>
      </Menu>
    </>
  );
}