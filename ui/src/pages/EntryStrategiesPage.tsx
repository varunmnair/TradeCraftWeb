import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Typography,
  Paper,
  Alert,
  CircularProgress,
  Button,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Checkbox,
  Toolbar,
  Typography as MuiTypography,
} from '@mui/material';
import {
  CloudUpload as UploadIcon,
  Download as DownloadIcon,
  Refresh as RefreshIcon,
  Delete as DeleteIcon,
} from '@mui/icons-material';
import { api } from '../api/client';
import { EntryStrategySummary } from '../types';
import { useSession } from '../context/SessionContext';

export default function EntryStrategiesPage() {
  const navigate = useNavigate();
  const { sessionId } = useSession();
  const [strategies, setStrategies] = useState<EntryStrategySummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [fileInputKey, setFileInputKey] = useState(0);
  const [selected, setSelected] = useState<string[]>([]);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    if (sessionId) {
      fetchStrategies();
    }
  }, [sessionId]);

  const fetchStrategies = async () => {
    if (!sessionId) {
      setError('No active session. Please start a session first.');
      return;
    }
    setLoading(true);
    try {
      const data = await api.listEntryStrategies(sessionId);
      setStrategies(data.strategies);
      setSelected([]);
      setError('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load strategies');
    } finally {
      setLoading(false);
    }
  };

  const handleSelectAll = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.checked) {
      setSelected(strategies.map(s => s.symbol));
    } else {
      setSelected([]);
    }
  };

  const handleSelectOne = (symbol: string) => {
    setSelected(prev => 
      prev.includes(symbol) 
        ? prev.filter(s => s !== symbol)
        : [...prev, symbol]
    );
  };

  const handleDeleteSelected = async () => {
    if (selected.length === 0) return;
    if (!sessionId) {
      setError('No active session. Please start a session first.');
      return;
    }
    
    if (!window.confirm(`Delete ${selected.length} selected strategy(ies)?`)) {
      return;
    }

    setDeleting(true);
    setError('');
    
    try {
      const result = await api.bulkDeleteEntryStrategies(selected, sessionId);
      setSuccess(`Deleted ${result.deleted_count} strategy(ies)`);
      if (result.not_found.length > 0) {
        setError(`Not found: ${result.not_found.join(', ')}`);
      }
      fetchStrategies();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete strategies');
    } finally {
      setDeleting(false);
    }
  };

  const handleFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    if (!sessionId) {
      setError('No active session. Please start a session first.');
      return;
    }

    setUploading(true);
    setError('');
    setSuccess('');

    try {
      const result = await api.uploadEntryStrategyCSV(file, sessionId);
      let msg = `Upload complete: ${result.created_count} created, ${result.updated_count} updated`;
      if (result.errors.length > 0) {
        msg += `. ${result.errors.length} errors`;
      }
      setSuccess(msg);
      fetchStrategies();
      setFileInputKey(prev => prev + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setUploading(false);
      if (event.target) {
        event.target.value = '';
      }
    }
  };

  const handleDownloadTemplate = async () => {
    try {
      const headers = 'Date,Raw Symbol,symbol,Allocated,Quality,exchange,entry1,entry2,entry3,DA Enabled,DA legs,DA E1 Buyback,DA E2 Buyback,DA E3 Buyback,DATriggerOffset,Last Updated\n';
      const sampleRows = 
        '03-Nov-25,544186,544186,30000,,BSE,175,165,159,Y,1,3,3,5,1,05-May-25\n' +
        '03-Oct-25,aadharhfc,AADHARHFC,30000,OK,NSE,510,500,492,Y,1,3,3,5,1,05-May-25\n' +
        '05-Sep-25,ACE,ACE,30000,Good,NSE,1040,982,955,Y,1,3,3,5,1,05-May-25';
      const blob = new Blob([headers + sampleRows], { type: 'text/csv' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'entry_strategy_template.csv';
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError('Failed to download template');
    }
  };

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Entry Strategies
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}

      {success && (
        <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccess('')}>
          {success}
        </Alert>
      )}

      <Paper sx={{ p: 2, mb: 2 }}>
        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
          <Button
            variant="contained"
            component="label"
            startIcon={uploading ? <CircularProgress size={20} color="inherit" /> : <UploadIcon />}
            disabled={uploading}
          >
            {uploading ? 'Uploading...' : 'Upload CSV (Sync)'}
            <input
              key={fileInputKey}
              type="file"
              accept=".csv"
              hidden
              onChange={handleFileChange}
              disabled={uploading}
            />
          </Button>

          <Button
            variant="outlined"
            startIcon={<DownloadIcon />}
            onClick={handleDownloadTemplate}
          >
            Download Template
          </Button>

          <Box sx={{ flexGrow: 1 }} />

          <Button
            variant="outlined"
            startIcon={<RefreshIcon />}
            onClick={fetchStrategies}
            disabled={loading}
          >
            Refresh
          </Button>
        </Box>
      </Paper>

      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
          <CircularProgress />
        </Box>
      ) : !sessionId ? (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <Typography variant="body1" color="text.secondary">
            No active session. Please start a session to view or manage entry strategies.
          </Typography>
        </Paper>
      ) : strategies.length === 0 ? (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <Typography variant="body1" color="text.secondary">
            No entry strategies found. Upload a CSV file to get started.
          </Typography>
        </Paper>
      ) : (
        <Paper>
          {selected.length > 0 && (
            <Toolbar sx={{ pl: 2, pr: 1, bgcolor: 'action.selected' }}>
              <MuiTypography sx={{ flex: '1 1 100%' }} color="inherit" variant="subtitle2">
                {selected.length} selected
              </MuiTypography>
              <Button
                color="error"
                startIcon={<DeleteIcon />}
                onClick={handleDeleteSelected}
                disabled={deleting}
              >
                {deleting ? 'Deleting...' : 'Delete'}
              </Button>
            </Toolbar>
          )}
          <TableContainer>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell padding="checkbox">
                    <Checkbox
                      indeterminate={selected.length > 0 && selected.length < strategies.length}
                      checked={strategies.length > 0 && selected.length === strategies.length}
                      onChange={handleSelectAll}
                    />
                  </TableCell>
                  <TableCell>Symbol</TableCell>
                  <TableCell>Allocated</TableCell>
                  <TableCell>Quality</TableCell>
                  <TableCell>Exchange</TableCell>
                  <TableCell>Entry1</TableCell>
                  <TableCell>Entry2</TableCell>
                  <TableCell>Entry3</TableCell>
                  <TableCell>DA</TableCell>
                  <TableCell>DA Legs</TableCell>
                  <TableCell>DA E1</TableCell>
                  <TableCell>DA E2</TableCell>
                  <TableCell>DA E3</TableCell>
                    <TableCell>DA Offset</TableCell>
                    <TableCell>Updated</TableCell>
                    <TableCell>Action</TableCell>
                  </TableRow>
              </TableHead>
              <TableBody>
                {strategies.map((strategy) => (
                  <TableRow
                    key={strategy.symbol}
                    hover
                    selected={selected.includes(strategy.symbol)}
                    sx={{ cursor: 'pointer' }}
                  >
                    <TableCell padding="checkbox" onClick={(e) => e.stopPropagation()}>
                      <Checkbox
                        checked={selected.includes(strategy.symbol)}
                        onChange={() => handleSelectOne(strategy.symbol)}
                      />
                    </TableCell>
                    <TableCell>
                      {new Date(strategy.updated_at).toLocaleDateString()}
                    </TableCell>
                    <TableCell onClick={(e) => e.stopPropagation()}>
                      <Button
                        size="small"
                        variant="outlined"
                        onClick={() => navigate(`/entry-strategies/${encodeURIComponent(strategy.symbol)}`)}
                      >
                        Revise
                      </Button>
                    </TableCell>
                  </TableRow>
              ))}
            </TableBody>
          </Table>
          </TableContainer>
        </Paper>
      )}
    </Box>
  );
}
