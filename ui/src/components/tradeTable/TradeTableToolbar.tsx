import {
  Clear as ClearIcon,
  FilterList as FilterListIcon,
  Search as SearchIcon,
  ViewColumn as ViewColumnIcon,
} from '@mui/icons-material';
import {
  Badge,
  Box,
  Button,
  Checkbox,
  IconButton,
  InputAdornment,
  ListItemText,
  Menu,
  MenuItem,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import { useState, type MouseEvent } from 'react';
import type { TradeTableResolvedConfig } from './types';

interface TradeTableToolbarProps {
  config: TradeTableResolvedConfig<any>;
  search: string;
  onSearchChange: (value: string) => void;
  activeFilterCount: number;
  onClearFilters: () => void;
  onOpenMobileFilters?: () => void;
  columnVisibility: Record<string, boolean>;
  onColumnVisibilityChange: (columnId: string, visible: boolean) => void;
  onResetColumns: () => void;
  /** Show mobile filters button instead of relying on column headers. */
  mobile?: boolean;
}

export function TradeTableToolbar({
  config,
  search,
  onSearchChange,
  activeFilterCount,
  onClearFilters,
  onOpenMobileFilters,
  columnVisibility,
  onColumnVisibilityChange,
  onResetColumns,
  mobile = false,
}: TradeTableToolbarProps) {
  const [columnsAnchor, setColumnsAnchor] = useState<HTMLElement | null>(null);

  const openColumnsMenu = (e: MouseEvent<HTMLElement>) => setColumnsAnchor(e.currentTarget);
  const closeColumnsMenu = () => setColumnsAnchor(null);

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: { xs: 'stretch', sm: 'center' },
        justifyContent: 'space-between',
        gap: 1,
        flexWrap: 'wrap',
        mb: 1.5,
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap', flex: 1, minWidth: 0 }}>
        {config.searchEnabled && config.searchField ? (
          <TextField
            size="small"
            placeholder="Search symbol"
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            inputProps={{ 'aria-label': 'Search table' }}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon fontSize="small" />
                </InputAdornment>
              ),
            }}
            sx={{ width: { xs: '100%', sm: 260 }, maxWidth: '100%' }}
          />
        ) : null}

        {onOpenMobileFilters ? (
          <Button
            variant="outlined"
            size="small"
            startIcon={
              <Badge color="primary" badgeContent={activeFilterCount} invisible={activeFilterCount === 0}>
                <FilterListIcon />
              </Badge>
            }
            onClick={onOpenMobileFilters}
            sx={{ minHeight: 40 }}
          >
            Filters
          </Button>
        ) : null}

        {activeFilterCount > 0 ? (
          <Box sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.75 }}>
            <Typography variant="body2" color="primary" sx={{ fontWeight: 500 }}>
              {activeFilterCount} Filter{activeFilterCount === 1 ? '' : 's'} Active
            </Typography>
            <Button
              size="small"
              color="inherit"
              startIcon={<ClearIcon />}
              onClick={onClearFilters}
            >
              Clear Filters
            </Button>
          </Box>
        ) : null}
      </Box>

      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
        <Tooltip title="Columns">
          <IconButton aria-label="Configure columns" onClick={openColumnsMenu} size="small" sx={{ minWidth: 40, minHeight: 40 }}>
            <ViewColumnIcon />
          </IconButton>
        </Tooltip>
        <Menu anchorEl={columnsAnchor} open={Boolean(columnsAnchor)} onClose={closeColumnsMenu}>
          {config.columns
            .filter((c) => !c.tableHidden)
            .map((col) => {
              const visible = columnVisibility[col.id] !== false;
              return (
                <MenuItem
                  key={col.id}
                  disabled={Boolean(col.required)}
                  onClick={() => onColumnVisibilityChange(col.id, !visible)}
                  dense
                >
                  <Checkbox checked={visible} size="small" />
                  <ListItemText primary={col.label} secondary={col.required ? 'Required' : undefined} />
                </MenuItem>
              );
            })}
          <MenuItem onClick={() => { onResetColumns(); closeColumnsMenu(); }} dense>
            <ListItemText primary="Reset columns" />
          </MenuItem>
        </Menu>
      </Box>
    </Box>
  );
}