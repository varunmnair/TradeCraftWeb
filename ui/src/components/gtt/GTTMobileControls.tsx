import {
  Box,
  Button,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  TextField,
} from '@mui/material';
import { Refresh as RefreshIcon } from '@mui/icons-material';
import type { GttSideFilter, GttStatusFilter } from './gttDisplay';

interface GTTMobileControlsProps {
  sideFilter: GttSideFilter;
  statusFilter: GttStatusFilter;
  varianceThreshold: number | '';
  varianceFilterType: 'gt' | 'lt';
  loading: boolean;
  onSideFilter: (value: GttSideFilter) => void;
  onStatusFilter: (value: GttStatusFilter) => void;
  onVarianceThreshold: (value: number | '') => void;
  onVarianceFilterType: (value: 'gt' | 'lt') => void;
  onRefresh: () => void;
}

export function GTTMobileControls({
  sideFilter,
  statusFilter,
  varianceThreshold,
  varianceFilterType,
  loading,
  onSideFilter,
  onStatusFilter,
  onVarianceThreshold,
  onVarianceFilterType,
  onRefresh,
}: GTTMobileControlsProps) {
  return (
    <Box sx={{ display: 'grid', gap: 1.25, mb: 2 }}>
      <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
        <Button
          variant="outlined"
          onClick={onRefresh}
          disabled={loading}
          sx={{ minWidth: 52, minHeight: 40, px: 1 }}
          aria-label="Refresh GTT orders"
        >
          <RefreshIcon fontSize="small" />
        </Button>
      </Box>

      <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 1 }}>
        <FormControl size="small" fullWidth>
          <InputLabel>Side</InputLabel>
          <Select
            value={sideFilter}
            label="Side"
            onChange={(event) => onSideFilter(event.target.value as GttSideFilter)}
          >
            <MenuItem value="all">All</MenuItem>
            <MenuItem value="BUY">BUY</MenuItem>
            <MenuItem value="SELL">SELL</MenuItem>
          </Select>
        </FormControl>
        <FormControl size="small" fullWidth>
          <InputLabel>Status</InputLabel>
          <Select
            value={statusFilter}
            label="Status"
            onChange={(event) => onStatusFilter(event.target.value as GttStatusFilter)}
          >
            <MenuItem value="all">All</MenuItem>
            <MenuItem value="active">Active</MenuItem>
            <MenuItem value="other">Other</MenuItem>
          </Select>
        </FormControl>
      </Box>

      <Box sx={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) 92px', gap: 1 }}>
        <TextField
          size="small"
          fullWidth
          type="number"
          label="Variance %"
          value={varianceThreshold}
          onChange={(event) =>
            onVarianceThreshold(event.target.value === '' ? '' : Number(event.target.value))
          }
        />
        <Button
          size="small"
          variant={varianceFilterType === 'gt' ? 'contained' : 'outlined'}
          onClick={() => onVarianceFilterType(varianceFilterType === 'gt' ? 'lt' : 'gt')}
          sx={{ minHeight: 40 }}
        >
          {varianceFilterType === 'gt' ? '≥' : '<'}
        </Button>
      </Box>
    </Box>
  );
}
