import { useEffect, useMemo, useState } from 'react';
import { Box, Button, Paper, Typography } from '@mui/material';
import {
  DataGrid,
  GridFooterContainer,
  GridPagination,
  type GridColDef,
  type GridPaginationModel,
  type GridRowSelectionModel,
  type GridSortModel,
  type GridValidRowModel,
} from '@mui/x-data-grid';
import { useTheme } from '@mui/material/styles';
import useMediaQuery from '@mui/material/useMediaQuery';
import { TradeEmptyState } from '../TradeEmptyState';
import { TradeErrorState } from '../TradeErrorState';
import { TradeLoadingState } from '../TradeLoadingState';
import { getFilterableColumns, getVisibleOrderedColumns } from './config';
import { formatMissing } from './formatters';
import { useTradeTableState } from './tableState';
import { TradeMobileFilterDialog } from './TradeMobileFilterDialog';
import { TradeSelectionToolbar } from './TradeSelectionToolbar';
import { TradeTableToolbar } from './TradeTableToolbar';
import type { TradeSelectionAction, TradeTableConfig } from './types';

interface TradeDataTableProps<T extends GridValidRowModel> {
  config: TradeTableConfig<T>;
  rows: T[];
  getRowId: (row: T) => string | number;
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
  emptyTitle?: string;
  emptyDescription?: string;
  /** Optional search field override ignored if config.searchEnabled is false. */
  selectionActions?: TradeSelectionAction[];
  /** Mobile card renderer. When provided, used below sm breakpoint. */
  renderMobileCard?: (row: T, selected: boolean, toggleSelect: () => void) => React.ReactNode;
  /** Optional extra toolbar content (page-specific controls). */
  toolbarExtra?: React.ReactNode;
  /** Called when selected IDs change. */
  onSelectionChange?: (ids: Array<string | number>) => void;
  /** Disable selection for specific rows. */
  isRowSelectable?: (row: T) => boolean;
  height?: number | string;
}

export function TradeDataTable<T extends GridValidRowModel>({
  config,
  rows,
  getRowId,
  loading = false,
  error = null,
  onRetry,
  emptyTitle = 'No records available',
  emptyDescription,
  selectionActions = [],
  renderMobileCard,
  toolbarExtra,
  onSelectionChange,
  isRowSelectable,
  height = 560,
}: TradeDataTableProps<T>) {
  const theme = useTheme();
  const mobile = useMediaQuery(theme.breakpoints.down('sm'));
  const [mobileFiltersOpen, setMobileFiltersOpen] = useState(false);

  const table = useTradeTableState({ config, rows, getRowId });
  const { config: resolved } = table;

  const visibleColumns = useMemo(
    () => getVisibleOrderedColumns(resolved).filter((c) => table.columnVisibility[c.id] !== false),
    [resolved, table.columnVisibility],
  );

  const gridColumns = useMemo<GridColDef<T>[]>(() => {
    return visibleColumns.map((col) => ({
      field: col.id,
      headerName: col.label,
      width: col.width,
      minWidth: col.minWidth ?? 90,
      flex: col.flex,
      sortable: col.sortable,
      filterable: false, // framework uses shared filter UI
      align: col.alignment ?? (col.dataType === 'number' ? 'right' : 'left'),
      headerAlign: col.alignment ?? (col.dataType === 'number' ? 'right' : 'left'),
      valueGetter: col.valueGetter ? (_value, row) => col.valueGetter!(row) : undefined,
      renderCell: col.renderCell
        ? (params) => col.renderCell!(params.row as T)
        : col.formatValue
          ? (params) => col.formatValue!(params.value, params.row as T)
          : col.dataType === 'number' || col.dataType === 'date' || col.dataType === 'boolean'
            ? (params) => (params.value == null || params.value === '' ? formatMissing(params.value) : params.value)
            : undefined,
    }));
  }, [visibleColumns]);

  const sortModel: GridSortModel = useMemo(
    () => (table.sort ? [{ field: table.sort.field, sort: table.sort.direction }] : []),
    [table.sort],
  );

  const handleSortModelChange = (model: GridSortModel) => {
    const next = model[0];
    if (!next?.field || !next.sort) {
      table.setSort(resolved.defaultSort);
      table.setPage(0);
      return;
    }
    const col = resolved.columns.find((c) => c.id === next.field);
    if (!col?.sortable) return;
    table.setSort({ field: next.field, direction: next.sort });
    table.setPage(0);
  };

  const pageCount = Math.max(1, Math.ceil(table.sortedRows.length / table.pageSize));
  const safePage = Math.min(table.page, pageCount - 1);

  useEffect(() => {
    if (safePage !== table.page) {
      table.setPage(safePage);
    }
  }, [safePage, table.page, table.setPage]);

  const paginationModel: GridPaginationModel = { page: safePage, pageSize: table.pageSize };

  const pagedRows = useMemo(
    () =>
      table.sortedRows.slice(
        safePage * table.pageSize,
        safePage * table.pageSize + table.pageSize,
      ),
    [table.sortedRows, safePage, table.pageSize],
  );

  const handlePaginationModelChange = (model: GridPaginationModel) => {
    if (model.pageSize !== table.pageSize) {
      table.setPageSize(model.pageSize);
      return;
    }
    if (model.page !== safePage) table.setPage(model.page);
  };

  const setSelection = (ids: Array<string | number>) => {
    table.setSelectedIds(ids);
    onSelectionChange?.(ids);
  };

  const handleSelectionChange = (model: GridRowSelectionModel) => {
    const ids = Array.isArray(model) ? model : [];
    setSelection(ids as Array<string | number>);
  };

  const activeFilters = table.filters;
  const filterableColumns = getFilterableColumns(resolved);

  const emptyState = (
    <TradeEmptyState
      title={activeFilters.length > 0 || table.search ? 'No records match the selected filters' : emptyTitle}
      description={
        activeFilters.length > 0 || table.search
          ? 'Try adjusting or clearing filters to see more results.'
          : emptyDescription
      }
    />
  );

  const mobileCards = mobile && renderMobileCard ? (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
      {table.sortedRows.length === 0 ? (
        <Paper variant="outlined">{emptyState}</Paper>
      ) : (
        pagedRows.map((row) => {
          const id = getRowId(row);
          const selected = table.selectedIds.includes(id);
          const toggleSelect = () => {
            if (isRowSelectable && !isRowSelectable(row)) return;
            const next = selected
              ? table.selectedIds.filter((x) => x !== id)
              : [...table.selectedIds, id];
            setSelection(next);
          };
          return <Box key={String(id)}>{renderMobileCard(row, selected, toggleSelect)}</Box>;
        })
      )}
    </Box>
  ) : null;

  return (
    <Box sx={{ width: '100%', minWidth: 0 }}>
      <TradeTableToolbar
        config={resolved}
        search={table.search}
        onSearchChange={table.setSearch}
        activeFilterCount={table.activeFilterCount}
        onClearFilters={table.clearFilters}
        onOpenMobileFilters={() => setMobileFiltersOpen(true)}
        columnVisibility={table.columnVisibility}
        onColumnVisibilityChange={table.setColumnVisible}
        onResetColumns={table.resetColumns}
        mobile={mobile}
      />
      {toolbarExtra}

      {resolved.selectionEnabled ? (
        <TradeSelectionToolbar
          selectedIds={table.selectedIds}
          actions={selectionActions}
          onClearSelection={() => setSelection([])}
        />
      ) : null}

      {error ? (
        <TradeErrorState message={error} onRetry={onRetry} />
      ) : loading ? (
        <TradeLoadingState message="Loading records…" />
      ) : mobile && renderMobileCard ? (
        mobileCards
      ) : (
        <Paper variant="outlined" sx={{ height, width: '100%', overflow: 'hidden' }}>
          <DataGrid
            rows={pagedRows}
            columns={gridColumns}
            getRowId={getRowId}
            loading={loading}
            sortModel={sortModel}
            onSortModelChange={handleSortModelChange}
            sortingMode="server"
            filterMode="server"
            paginationModel={paginationModel}
            onPaginationModelChange={handlePaginationModelChange}
            pageSizeOptions={resolved.allowedPageSizes}
            paginationMode="server"
            rowCount={table.sortedRows.length}
            checkboxSelection={resolved.selectionEnabled}
            disableRowSelectionOnClick
            rowSelectionModel={table.selectedIds as GridRowSelectionModel}
            onRowSelectionModelChange={handleSelectionChange}
            isRowSelectable={isRowSelectable ? (params) => isRowSelectable(params.row as T) : undefined}
            density={resolved.density}
            disableColumnFilter
            disableColumnMenu={false}
            hideFooterSelectedRowCount={!resolved.selectionEnabled}
            slots={{
              noRowsOverlay: () => emptyState,
              footer: () => (
                <GridFooterContainer
                  sx={{
                    justifyContent: 'space-between',
                    px: 1.5,
                    gap: 1,
                    flexWrap: 'wrap',
                  }}
                >
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap', py: 0.5 }}>
                    <Typography variant="caption" color="text.secondary">
                      Total records: {table.sortedRows.length}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Page {safePage + 1} of {pageCount}
                    </Typography>
                  </Box>
                  <GridPagination />
                </GridFooterContainer>
              ),
            }}
            sx={{
              border: 0,
              '& .MuiDataGrid-columnHeaders': { minHeight: 40, maxHeight: 40, lineHeight: '40px' },
              '& .MuiDataGrid-columnHeader': { minHeight: 40, maxHeight: 40 },
              '& .MuiDataGrid-cell': { py: 0.5 },
              '& .MuiDataGrid-columnSeparator': { opacity: 0.2 },
              '& .MuiDataGrid-virtualScroller': { minHeight: 120 },
              fontVariantNumeric: 'tabular-nums',
            }}
          />
        </Paper>
      )}

      {mobile && renderMobileCard && !loading && !error && table.sortedRows.length > 0 ? (
        <Box sx={{ mt: 1.5, display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
          <Typography variant="caption" color="text.secondary">
            Total records: {table.sortedRows.length} · Page {safePage + 1} of {pageCount} · {table.pageSize}/page
          </Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Button size="small" disabled={safePage === 0} onClick={() => table.setPage(safePage - 1)}>Previous</Button>
            <Button
              size="small"
              disabled={safePage + 1 >= pageCount}
              onClick={() => table.setPage(safePage + 1)}
            >
              Next
            </Button>
          </Box>
        </Box>
      ) : null}

      <TradeMobileFilterDialog
        open={mobileFiltersOpen}
        onClose={() => setMobileFiltersOpen(false)}
        columns={filterableColumns}
        rows={rows}
        filters={activeFilters}
        onApply={(next) => {
          table.setFilters(next);
          table.setPage(0);
        }}
        onClear={table.clearFilters}
      />
    </Box>
  );
}