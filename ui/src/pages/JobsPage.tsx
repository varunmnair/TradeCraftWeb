import React, { useEffect, useState } from 'react';
import {
  Box,
  Typography,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Alert,
  CircularProgress,
  Chip,
  IconButton,
  Drawer,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
} from '@mui/material';
import {
  Refresh as RefreshIcon,
  Close as CloseIcon,
  ContentCopy as CopyIcon,
  Visibility as ViewIcon,
} from '@mui/icons-material';
import { api } from '../api/client';
import { JobStatus } from '../types';

const statusColors: Record<string, 'default' | 'primary' | 'secondary' | 'error' | 'info' | 'success' | 'warning'> = {
  pending: 'warning',
  running: 'info',
  completed: 'success',
  failed: 'error',
};

export default function JobsPage() {
  const [jobs, setJobs] = useState<JobStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedJob, setSelectedJob] = useState<JobStatus | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);

  const fetchJobs = async () => {
    try {
      const data = await api.listJobs();
      setJobs(data.jobs);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load jobs');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchJobs();
    const interval = setInterval(fetchJobs, 10000);
    return () => clearInterval(interval);
  }, []);

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

  const formatJson = (obj: unknown): string => {
    return JSON.stringify(obj, null, 2);
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h4">Jobs</Typography>
        <Box>
          <IconButton onClick={fetchJobs}>
            <RefreshIcon />
          </IconButton>
        </Box>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}

      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>ID</TableCell>
              <TableCell>Type</TableCell>
              <TableCell>Session</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Progress</TableCell>
              <TableCell>Created</TableCell>
              <TableCell>Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {jobs.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} align="center">
                  No jobs yet
                </TableCell>
              </TableRow>
            ) : (
              jobs.map((job) => (
                <TableRow key={job.id}>
                  <TableCell>{job.id}</TableCell>
                  <TableCell>{job.job_type}</TableCell>
                  <TableCell>{job.session_id}</TableCell>
                  <TableCell>
                    <Chip label={job.status} color={statusColors[job.status] || 'default'} size="small" />
                  </TableCell>
                  <TableCell>{(job.progress * 100).toFixed(0)}%</TableCell>
                  <TableCell>{new Date(job.created_at).toLocaleString()}</TableCell>
                  <TableCell>
                    <IconButton size="small" onClick={() => handleViewJob(job)}>
                      <ViewIcon />
                    </IconButton>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>

      {/* Job Details Dialog */}
      <Dialog 
        open={detailOpen} 
        onClose={() => setDetailOpen(false)} 
        maxWidth="md" 
        fullWidth
      >
        <DialogTitle>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            Job Details (#{selectedJob?.id})
            <IconButton onClick={() => handleCopyJson(selectedJob)} size="small">
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
                <Chip 
                  label={selectedJob.status} 
                  color={statusColors[selectedJob.status] || 'default'} 
                  size="small" 
                />
                
                <Typography variant="body2" color="text.secondary">Progress:</Typography>
                <Typography variant="body2">{(selectedJob.progress * 100).toFixed(0)}%</Typography>
                
                <Typography variant="body2" color="text.secondary">Created:</Typography>
                <Typography variant="body2">{new Date(selectedJob.created_at).toLocaleString()}</Typography>
                
                <Typography variant="body2" color="text.secondary">Updated:</Typography>
                <Typography variant="body2">{new Date(selectedJob.updated_at).toLocaleString()}</Typography>
              </Box>

              {selectedJob.log && (
                <>
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>Log:</Typography>
                  <TextField
                    multiline
                    rows={10}
                    fullWidth
                    value={selectedJob.log}
                    InputProps={{ readOnly: true }}
                    variant="outlined"
                    size="small"
                  />
                </>
              )}

              <Box>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 0.5 }}>
                  Raw JSON:
                </Typography>
                <TextField
                  multiline
                  rows={15}
                  fullWidth
                  value={formatJson(selectedJob)}
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
          <Button onClick={() => handleCopyJson(selectedJob)} startIcon={<CopyIcon />}>
            Copy JSON
          </Button>
          <Button onClick={() => setDetailOpen(false)} variant="contained">
            Close
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
