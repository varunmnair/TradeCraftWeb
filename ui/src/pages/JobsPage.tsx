import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  TextField,
  Typography,
} from '@mui/material';
import { ContentCopy as CopyIcon, Refresh as RefreshIcon, Visibility as ViewIcon } from '@mui/icons-material';
import { api } from '../api/client';
import { JobStatus } from '../types';
import { ResponsivePageHeader } from '../components/ResponsivePageHeader';
import { StatusChip } from '../components/StatusChip';
import { TradePageLayout } from '../components/TradePageLayout';
import { TradeStatusAlert } from '../components/TradeStatusAlert';
import { TradeSummaryStrip } from '../components/TradeSummaryStrip';
import { TradeDataTable } from '../components/tradeTable/TradeDataTable';
import type { TradeColumnDef, TradeSelectionAction } from '../components/tradeTable/types';
import { tradeTableRegistry } from '../config/tradeTableRegistry';
import { uiPageConfigToTradeTableConfig, useUiPageConfig } from '../hooks/useUiPageConfig';

export default function JobsPage() {
  const [jobs, setJobs] = useState<JobStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedJob, setSelectedJob] = useState<JobStatus | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);

  const fetchJobs = useCallback(async () => {
    try {
      const data = await api.listJobs();
      setJobs(data.jobs);
      setError('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load jobs');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchJobs();
    const interval = setInterval(() => void fetchJobs(), 10000);
    return () => clearInterval(interval);
  }, [fetchJobs]);

  const handleViewJob = async (job: JobStatus) => {
    try {
      const response = await api.getJob(job.id);
      setSelectedJob(response.job);
      setDetailOpen(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load job details');
    }
  };

  const handleCopyJson = (obj: unknown) => {
    navigator.clipboard.writeText(JSON.stringify(obj, null, 2));
  };

  const runningCount = jobs.filter((j) => j.status === 'pending' || j.status === 'running').length;
  const failedCount = jobs.filter((j) => j.status === 'failed').length;
  const completedCount = jobs.filter((j) => j.status === 'completed' || j.status === 'succeeded').length;

  const { config: uiConfig } = useUiPageConfig('jobs');

  const tableConfig = useMemo(() => {
    const runtimeBaseColumns: TradeColumnDef<JobStatus>[] = (tradeTableRegistry.jobs.config.columns as TradeColumnDef<JobStatus>[]).map((col) => {
      if (col.id === 'status') {
        return {
          ...col,
          filterOptions: [
            { value: 'pending', label: 'Pending' },
            { value: 'running', label: 'Running' },
            { value: 'completed', label: 'Completed' },
            { value: 'succeeded', label: 'Succeeded' },
            { value: 'failed', label: 'Failed' },
            { value: 'cancelled', label: 'Cancelled' },
          ],
          renderCell: (row: JobStatus) => <StatusChip status={row.status} />,
        };
      }
      if (col.id === 'progress') {
        return {
          ...col,
          formatValue: (value: unknown) => `${((Number(value) || 0) * 100).toFixed(0)}%`,
        };
      }
      if (col.id === 'created_at') {
        return {
          ...col,
          formatValue: (value: unknown) => (value ? new Date(String(value)).toLocaleString() : '-'),
        };
      }
      return col;
    });

    const actionColumn: TradeColumnDef<JobStatus> = {
      id: 'actions',
      label: 'Actions',
      dataType: 'text',
      visible: true,
      sortable: false,
      filterable: false,
      position: 99,
      width: 100,
      alignment: 'center',
      renderCell: (row: JobStatus) => (
        <IconButton size="small" onClick={() => void handleViewJob(row)} aria-label="View job details">
          <ViewIcon fontSize="small" />
        </IconButton>
      ),
    };

    const baseConfig = {
      ...tradeTableRegistry.jobs.config,
      columns: [...runtimeBaseColumns, actionColumn],
    };

    const effective = uiConfig
      ? uiPageConfigToTradeTableConfig('jobs', uiConfig, baseConfig)
      : baseConfig;

    const mergedColumns = (effective.columns as TradeColumnDef<JobStatus>[]).map((col) => {
      const runtime = baseConfig.columns.find((c) => c.id === col.id);
      return runtime
        ? {
            ...runtime,
            ...col,
            renderCell: runtime.renderCell ?? col.renderCell,
            formatValue: runtime.formatValue ?? col.formatValue,
            filterOptions: runtime.filterOptions ?? col.filterOptions,
          }
        : col;
    });

    const hasActions = mergedColumns.some((c) => c.id === 'actions');
    return {
      ...effective,
      columns: hasActions ? mergedColumns : [...mergedColumns, actionColumn],
    };
  }, [uiConfig]);

  const selectionActions = useMemo<TradeSelectionAction[]>(
    () => [
      {
        label: 'Copy IDs',
        onClick: (ids) => navigator.clipboard.writeText(ids.join(', ')),
        variant: 'outlined',
        priority: 'primary',
      },
    ],
    [],
  );

  return (
    <TradePageLayout
      header={
        <ResponsivePageHeader
          title="Jobs"
          description="Background job status and history"
          recordCount={jobs.length}
          secondaryActions={[
            {
              label: 'Refresh jobs',
              onClick: () => void fetchJobs(),
              icon: <RefreshIcon />,
            },
          ]}
        />
      }
      summary={
        !loading ? (
          <TradeSummaryStrip
            ariaLabel="Jobs summary"
            items={[
              { label: 'Total', value: jobs.length },
              { label: 'Running', value: runningCount, tone: runningCount > 0 ? 'info' : 'default' },
              { label: 'Completed', value: completedCount, tone: 'success' },
              { label: 'Failed', value: failedCount, tone: failedCount > 0 ? 'error' : 'default' },
            ]}
          />
        ) : undefined
      }
    >
      {error ? (
        <TradeStatusAlert kind="critical" message={error} onClose={() => setError('')} sx={{ mb: 2 }} />
      ) : null}

      <TradeDataTable<JobStatus>
        config={tableConfig}
        rows={jobs}
        getRowId={(row) => row.id}
        loading={loading}
        error={null}
        emptyTitle="No jobs yet"
        emptyDescription="Background jobs will appear here when you generate plans, refresh data, or run other tasks."
        selectionActions={selectionActions}
        renderMobileCard={(row, selected, toggleSelect) => (
          <Box
            onClick={toggleSelect}
            sx={{
              border: '1px solid',
              borderColor: selected ? 'primary.main' : 'divider',
              borderRadius: 1,
              p: 1.5,
              bgcolor: selected ? 'action.selected' : 'background.paper',
            }}
          >
            <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 1, mb: 0.5 }}>
              <Typography variant="subtitle2">{row.job_type}</Typography>
              <StatusChip status={row.status} />
            </Box>
            <Typography variant="body2" color="text.secondary">ID: {row.id} · {(row.progress * 100).toFixed(0)}%</Typography>
            <Typography variant="body2" color="text.secondary">{new Date(row.created_at).toLocaleString()}</Typography>
            <Button size="small" onClick={(e) => { e.stopPropagation(); void handleViewJob(row); }} sx={{ mt: 0.5, px: 0 }}>
              View details
            </Button>
          </Box>
        )}
      />

      <Dialog open={detailOpen} onClose={() => setDetailOpen(false)} maxWidth="md" fullWidth>
        <DialogTitle>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            Job Details (#{selectedJob?.id})
            <IconButton onClick={() => handleCopyJson(selectedJob)} size="small" aria-label="Copy job JSON">
              <CopyIcon />
            </IconButton>
          </Box>
        </DialogTitle>
        <DialogContent dividers>
          {selectedJob && (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <Box sx={{ display: 'grid', gridTemplateColumns: '150px 1fr', gap: 1 }}>
                <Typography variant="body2" color="text.secondary">ID:</Typography>
                <Typography variant="body2">{selectedJob.id}</Typography>
                <Typography variant="body2" color="text.secondary">Type:</Typography>
                <Typography variant="body2">{selectedJob.job_type}</Typography>
                <Typography variant="body2" color="text.secondary">Session:</Typography>
                <Typography variant="body2">{selectedJob.session_id}</Typography>
                <Typography variant="body2" color="text.secondary">Status:</Typography>
                <Box><StatusChip status={selectedJob.status} /></Box>
                <Typography variant="body2" color="text.secondary">Progress:</Typography>
                <Typography variant="body2">{((selectedJob.progress || 0) * 100).toFixed(0)}%</Typography>
                <Typography variant="body2" color="text.secondary">Created:</Typography>
                <Typography variant="body2">{new Date(selectedJob.created_at).toLocaleString()}</Typography>
                <Typography variant="body2" color="text.secondary">Updated:</Typography>
                <Typography variant="body2">{new Date(selectedJob.updated_at).toLocaleString()}</Typography>
              </Box>
              {selectedJob.log && (
                <>
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>Log:</Typography>
                  <TextField multiline rows={10} fullWidth value={selectedJob.log} InputProps={{ readOnly: true }} variant="outlined" size="small" />
                </>
              )}
              <Box>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 0.5 }}>Raw JSON:</Typography>
                <TextField
                  multiline
                  rows={15}
                  fullWidth
                  value={JSON.stringify(selectedJob, null, 2)}
                  InputProps={{ readOnly: true }}
                  variant="outlined"
                  size="small"
                  sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}
                />
              </Box>
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => handleCopyJson(selectedJob)} startIcon={<CopyIcon />}>Copy JSON</Button>
          <Button onClick={() => setDetailOpen(false)} variant="contained">Close</Button>
        </DialogActions>
      </Dialog>
    </TradePageLayout>
  );
}