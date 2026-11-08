import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Box,
  Typography,
  CircularProgress,
  Alert,
} from '@mui/material';
import { api } from '../api/client';
import { DAConfig } from '../types';

interface DASettingsModalProps {
  open: boolean;
  onClose: () => void;
}

export function DASettingsModal({ open, onClose }: DASettingsModalProps) {
  const [config, setConfig] = useState<DAConfig | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  useEffect(() => {
    if (open) {
      fetchConfig();
    }
  }, [open]);

  const fetchConfig = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await api.getDAConfig();
      setConfig(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load config');
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (field: keyof DAConfig, value: number) => {
    if (!config) return;
    setConfig({ ...config, [field]: value });
  };

  const handleSave = async () => {
    if (!config) return;
    setSaving(true);
    setError('');
    setSuccess('');
    try {
      const result = await api.updateDAConfig(config);
      setConfig(result);
      setSuccess('Settings saved');
      setTimeout(() => onClose(), 1000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>Dynamic Averaging Settings</DialogTitle>
      <DialogContent>
        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
            <CircularProgress />
          </Box>
        ) : config ? (
          <Box sx={{ pt: 1, display: 'flex', flexDirection: 'column', gap: 2 }}>
            <TextField
              label="Minimum DA Net Profit (₹)"
              type="number"
              size="small"
              value={config.minimum_da_net_profit}
              onChange={(e) => handleChange('minimum_da_net_profit', Number(e.target.value))}
            />
            <TextField
              label="Default Sell Offset (%)"
              type="number"
              size="small"
              inputProps={{ step: 0.1 }}
              value={config.default_sell_offset * 100}
              onChange={(e) => handleChange('default_sell_offset', Number(e.target.value) / 100)}
            />
            <TextField
              label="Minimum Volume Threshold"
              type="number"
              size="small"
              value={config.minimum_volume_threshold}
              onChange={(e) => handleChange('minimum_volume_threshold', Number(e.target.value))}
            />
            <TextField
              label="Range Analysis Days"
              type="number"
              size="small"
              value={config.da_range_analysis_days}
              onChange={(e) => handleChange('da_range_analysis_days', Number(e.target.value))}
            />
            <Typography variant="subtitle2" sx={{ mt: 1 }}>Quantity Percentages by Confidence</Typography>
            <Box sx={{ display: 'flex', gap: 2 }}>
              <TextField
                label="High Confidence %"
                type="number"
                size="small"
                value={config.high_confidence_qty_pct}
                onChange={(e) => handleChange('high_confidence_qty_pct', Number(e.target.value))}
                sx={{ width: 140 }}
              />
              <TextField
                label="Medium Confidence %"
                type="number"
                size="small"
                value={config.medium_confidence_qty_pct}
                onChange={(e) => handleChange('medium_confidence_qty_pct', Number(e.target.value))}
                sx={{ width: 140 }}
              />
              <TextField
                label="Low Confidence %"
                type="number"
                size="small"
                value={config.low_confidence_qty_pct}
                onChange={(e) => handleChange('low_confidence_qty_pct', Number(e.target.value))}
                sx={{ width: 140 }}
              />
            </Box>
          </Box>
        ) : null}
        {error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}
        {success && <Alert severity="success" sx={{ mt: 2 }}>{success}</Alert>}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="contained" onClick={handleSave} disabled={saving || !config}>
          {saving ? <CircularProgress size={20} /> : 'Save'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
