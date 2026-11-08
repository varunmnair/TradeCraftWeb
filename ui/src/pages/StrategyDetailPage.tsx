import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
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
  Chip,
  Card,
  CardContent,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  FormControl,
  FormControlLabel,
  Radio,
  RadioGroup,
  Checkbox,
  Tabs,
  Tab,
  TextField,
  Accordion,
  AccordionSummary,
  AccordionDetails,
} from '@mui/material';
import {
  ArrowBack as BackIcon,
  Refresh as RefreshIcon,
  AutoFixHigh as ReviseIcon,
  ExpandMore as ExpandMoreIcon,
} from '@mui/icons-material';
import { api } from '../api/client';
import { EntryStrategyFull, SuggestRevisionResponse, VersionItem, EvaluateStrategyResponse } from '../types';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;
  return (
    <div role="tabpanel" hidden={value !== index} {...other}>
      {value === index && <Box sx={{ pt: 2 }}>{children}</Box>}
    </div>
  );
}

export default function StrategyDetailPage() {
  const { symbol } = useParams<{ symbol: string }>();
  const navigate = useNavigate();
  const [strategy, setStrategy] = useState<EntryStrategyFull | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [tabValue, setTabValue] = useState(0);

  // Version history state
  const [versions, setVersions] = useState<VersionItem[]>([]);
  const [versionsLoading, setVersionsLoading] = useState(false);
  const [versionsError, setVersionsError] = useState('');
  const [restoreDialogOpen, setRestoreDialogOpen] = useState(false);
  const [selectedVersion, setSelectedVersion] = useState<VersionItem | null>(null);
  const [restoreLoading, setRestoreLoading] = useState(false);
  const [restoreSuccess, setRestoreSuccess] = useState('');
  const [restoreError, setRestoreError] = useState('');

  // Evaluate state
  const [evaluating, setEvaluating] = useState(false);
  const [evaluateResult, setEvaluateResult] = useState<EvaluateStrategyResponse | null>(null);

  // Revision modal state
  const [revisionModalOpen, setRevisionModalOpen] = useState(false);
  const [revisionLoading, setRevisionLoading] = useState(false);
  const [revisionError, setRevisionError] = useState('');
  const [revisionData, setRevisionData] = useState<SuggestRevisionResponse | null>(null);
  const [revisionStyle, setRevisionStyle] = useState<'conservative' | 'balanced' | 'aggressive'>('balanced');
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [advancedOverrides, setAdvancedOverrides] = useState({
    atrPeriod: 14,
    emaFast: 20,
    emaSlow: 50,
    lookback: 60,
    atrMultiplier: 1.0,
  });
  const [selectedLevels, setSelectedLevels] = useState<Set<number>>(new Set());
  const [applyLoading, setApplyLoading] = useState(false);
  const [applyError, setApplyError] = useState('');
  const [applySuccess, setApplySuccess] = useState('');

  useEffect(() => {
    if (symbol) {
      fetchStrategy();
    }
  }, [symbol]);

  useEffect(() => {
    if (tabValue === 1 && symbol) {
      fetchVersionHistory();
    }
  }, [tabValue, symbol]);

  const fetchStrategy = async () => {
    if (!symbol) return;
    setLoading(true);
    try {
      const data = await api.getEntryStrategy(decodeURIComponent(symbol));
      setStrategy(data);
      setError('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load strategy');
    } finally {
      setLoading(false);
    }
  };

  const fetchVersionHistory = async () => {
    if (!symbol) return;
    setVersionsLoading(true);
    setVersionsError('');
    try {
      const data = await api.getVersionHistory(decodeURIComponent(symbol));
      setVersions(data.versions);
    } catch (err) {
      setVersionsError(err instanceof Error ? err.message : 'Failed to load version history');
    } finally {
      setVersionsLoading(false);
    }
  };

  const handleRefresh = () => {
    fetchStrategy();
  };

  const handleEvaluate = async () => {
    if (!symbol) return;
    setEvaluating(true);
    setEvaluateResult(null);
    try {
      const result = await api.evaluateStrategy(decodeURIComponent(symbol));
      setEvaluateResult(result);
      fetchStrategy();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to evaluate strategy');
    } finally {
      setEvaluating(false);
    }
  };

  const handleBack = () => {
    navigate('/entry-strategies');
  };

  const handleOpenRevision = async () => {
    if (!symbol) return;
    setRevisionModalOpen(true);
    setRevisionError('');
    setRevisionData(null);
    setSelectedLevels(new Set());
    await fetchRevisionSuggestions();
  };

  const handleCloseRevision = () => {
    setRevisionModalOpen(false);
    setRevisionData(null);
    setSelectedLevels(new Set());
    setRevisionError('');
    setApplyError('');
    setApplySuccess('');
  };

  const handleStyleChange = async (style: string) => {
    setRevisionStyle(style as 'conservative' | 'balanced' | 'aggressive');
    setRevisionData(null);
    setSelectedLevels(new Set());
    await fetchRevisionSuggestions(style);
  };

  const fetchRevisionSuggestions = async (style?: string) => {
    if (!symbol) return;
    setRevisionLoading(true);
    setRevisionError('');
    try {
      const effectiveStyle = style || revisionStyle;
      const data = await api.suggestRevision(
        decodeURIComponent(symbol),
        effectiveStyle,
      );
      setRevisionData(data);
    } catch (err) {
      setRevisionError(err instanceof Error ? err.message : 'Failed to get suggestions');
    } finally {
      setRevisionLoading(false);
    }
  };

  const handleToggleLevel = (levelNo: number) => {
    const newSelected = new Set(selectedLevels);
    if (newSelected.has(levelNo)) {
      newSelected.delete(levelNo);
    } else {
      newSelected.add(levelNo);
    }
    setSelectedLevels(newSelected);
  };

  const handleApplyRevision = async () => {
    if (!symbol || selectedLevels.size === 0) return;
    setApplyLoading(true);
    setApplyError('');
    setApplySuccess('');
    try {
      const levelsToUpdate = Array.from(selectedLevels).map(levelNo => {
        const revision = revisionData?.revised_levels.find(r => r.level_no === levelNo);
        return {
          level_no: levelNo,
          new_price: revision?.suggested_price || 0,
        };
      });
      const result = await api.applyRevision(decodeURIComponent(symbol), levelsToUpdate);
      setApplySuccess(`Updated ${result.updated_levels.length} levels successfully`);
      setTimeout(() => {
        handleCloseRevision();
        fetchStrategy();
      }, 1500);
    } catch (err) {
      setApplyError(err instanceof Error ? err.message : 'Failed to apply revisions');
    } finally {
      setApplyLoading(false);
    }
  };

  const handleRestoreClick = (version: VersionItem) => {
    setSelectedVersion(version);
    setRestoreDialogOpen(true);
  };

  const handleConfirmRestore = async () => {
    if (!symbol || !selectedVersion) return;
    setRestoreLoading(true);
    setRestoreSuccess('');
    try {
      const result = await api.restoreVersion(decodeURIComponent(symbol), selectedVersion.id);
      setRestoreSuccess(`Restored to version ${result.restored_to_version}`);
      setTimeout(() => {
        setRestoreDialogOpen(false);
        setSelectedVersion(null);
        fetchVersionHistory();
        fetchStrategy();
      }, 1500);
    } catch (err) {
      setRestoreError(err instanceof Error ? err.message : 'Failed to restore version');
    } finally {
      setRestoreLoading(false);
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
          <Button startIcon={<BackIcon />} onClick={handleBack}>
            Back
          </Button>
        </Box>
        <Alert severity="error">{error}</Alert>
      </Box>
    );
  }

  if (!strategy) {
    return (
      <Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
          <Button startIcon={<BackIcon />} onClick={handleBack}>
            Back
          </Button>
        </Box>
        <Alert severity="warning">Strategy not found</Alert>
      </Box>
    );
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
        <Button startIcon={<BackIcon />} onClick={handleBack} variant="outlined">
          Back
        </Button>
        <Box sx={{ flexGrow: 1 }} />
        <Button startIcon={<ReviseIcon />} onClick={handleOpenRevision} variant="outlined">
          Revise Entries
        </Button>
        <Button
          variant="outlined"
          color="success"
          onClick={handleEvaluate}
          disabled={evaluating}
          startIcon={evaluating ? <CircularProgress size={20} /> : undefined}
        >
          {evaluating ? 'Evaluating...' : 'Evaluate'}
        </Button>
        <Button startIcon={<RefreshIcon />} onClick={handleRefresh} variant="outlined">
          Refresh
        </Button>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}

      {/* Symbol Header */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Typography variant="h4" component="h1">
            {strategy.symbol}
          </Typography>
          <Chip
            label={strategy.dynamic_averaging_enabled ? 'Dynamic Averaging Enabled' : 'Dynamic Averaging Disabled'}
            color={strategy.dynamic_averaging_enabled ? 'success' : 'default'}
          />
        </Box>
      </Paper>

      {/* Strategy Health */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          Strategy Health
        </Typography>
        <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 2 }}>
          <Box>
            <Typography variant="body2" color="text.secondary">Review Status</Typography>
            <Chip
              label={strategy.review_status ? strategy.review_status.replace(/_/g, ' ') : 'Not Evaluated'}
              size="small"
              color={
                strategy.review_status === 'ACTIVE'
                  ? 'success'
                  : strategy.review_status === 'REVIEW_REQUIRED'
                    ? 'warning'
                    : strategy.review_status === 'THESIS_BREAK'
                      ? 'error'
                      : 'default'
              }
              sx={{ mt: 0.5 }}
            />
          </Box>
          <Box>
            <Typography variant="body2" color="text.secondary">Swing Eligible</Typography>
            <Typography variant="body1">
              {strategy.swing_eligible == null ? 'Not Checked' : strategy.swing_eligible ? 'Yes' : 'No'}
            </Typography>
          </Box>
          <Box>
            <Typography variant="body2" color="text.secondary">Thesis Break Price</Typography>
            <Typography variant="body1">
              {strategy.thesis_break_price != null ? `₹${strategy.thesis_break_price.toFixed(2)}` : '-'}
            </Typography>
          </Box>
          <Box>
            <Typography variant="body2" color="text.secondary">Last Evaluated</Typography>
            <Typography variant="body1">
              {strategy.last_evaluated_at
                ? new Date(strategy.last_evaluated_at).toLocaleDateString()
                : '-'}
            </Typography>
          </Box>
          <Box>
            <Typography variant="body2" color="text.secondary">Last Revised</Typography>
            <Typography variant="body1">
              {strategy.last_entry_revision_at
                ? new Date(strategy.last_entry_revision_at).toLocaleDateString()
                : '-'}
            </Typography>
          </Box>
        </Box>
        {evaluateResult && (
          <Alert severity="info" sx={{ mt: 2 }} onClose={() => setEvaluateResult(null)}>
            {evaluateResult.reason}
          </Alert>
        )}
      </Paper>

      {/* Dynamic Averaging Intelligence Panel */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          Dynamic Averaging Intelligence
          <Chip
            label={strategy.dynamic_averaging_enabled ? 'DA Enabled' : 'DA Disabled'}
            color={strategy.dynamic_averaging_enabled ? 'success' : 'default'}
            size="small"
            sx={{ ml: 1 }}
          />
        </Typography>
        <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 2, mb: 2 }}>
          <Box>
            <Typography variant="body2" color="text.secondary">DA Status</Typography>
            <Chip
              label={strategy.da_status ? strategy.da_status.replace(/_/g, ' ') : 'Not Evaluated'}
              size="small"
              color={
                strategy.da_status === 'ELIGIBLE'
                  ? 'success'
                  : strategy.da_status === 'LOW_VOLUME'
                    ? 'warning'
                    : strategy.da_status === 'TRENDING'
                      ? 'info'
                      : strategy.da_status === 'THESIS_BREAK'
                        ? 'error'
                        : 'default'
              }
              sx={{ mt: 0.5 }}
            />
          </Box>
          <Box>
            <Typography variant="body2" color="text.secondary">DA Eligible</Typography>
            <Typography variant="body1">{strategy.da_eligible == null ? 'Not Checked' : strategy.da_eligible ? 'Yes' : 'No'}</Typography>
          </Box>
          <Box>
            <Typography variant="body2" color="text.secondary">Confidence Score</Typography>
            <Typography variant="body1">{strategy.da_confidence_score != null ? `${strategy.da_confidence_score}/100` : '-'}</Typography>
          </Box>
          <Box>
            <Typography variant="body2" color="text.secondary">Last Evaluated</Typography>
            <Typography variant="body1">{strategy.da_last_evaluated_at ? new Date(strategy.da_last_evaluated_at).toLocaleDateString() : '-'}</Typography>
          </Box>
        </Box>
        {strategy.da_notes && (
          <Box sx={{ mb: 2 }}>
            <Typography variant="body2" color="text.secondary">Notes</Typography>
            <Typography variant="body2">{strategy.da_notes}</Typography>
          </Box>
        )}
        <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
          <Button
            size="small"
            variant="outlined"
            color="success"
            onClick={handleEvaluate}
            disabled={evaluating}
            startIcon={evaluating ? <CircularProgress size={16} /> : undefined}
          >
            {evaluating ? 'Evaluating...' : 'Evaluate DA'}
          </Button>
        </Box>
      </Paper>

      {/* Tabs */}
      <Paper sx={{ mb: 3 }}>
        <Tabs value={tabValue} onChange={(_, v) => setTabValue(v)}>
          <Tab label="Entry Levels" />
          <Tab label="Version History" />
        </Tabs>

        <TabPanel value={tabValue} index={0}>
          {/* Entry Levels */}
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Entry Levels
            </Typography>
            <TableContainer>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>Level</TableCell>
                    <TableCell>Price</TableCell>
                    <TableCell>Status</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {strategy.levels.map((level) => (
                    <TableRow key={level.level_no}>
                      <TableCell>Level {level.level_no}</TableCell>
                      <TableCell>₹{level.price.toFixed(2)}</TableCell>
                      <TableCell>
                        <Chip
                          label={level.is_active ? 'Active' : 'Inactive'}
                          color={level.is_active ? 'success' : 'default'}
                          size="small"
                        />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Paper>
        </TabPanel>

        <TabPanel value={tabValue} index={1}>
          {/* Version History */}
          <Box sx={{ p: 3 }}>
            {versionsLoading ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
                <CircularProgress />
              </Box>
            ) : versionsError ? (
              <Alert severity="error">{versionsError}</Alert>
            ) : versions.length === 0 ? (
              <Alert severity="info">No version history available</Alert>
            ) : (
              <TableContainer>
                <Table>
                  <TableHead>
                    <TableRow>
                      <TableCell>Version</TableCell>
                      <TableCell>Action</TableCell>
                      <TableCell>Changes</TableCell>
                      <TableCell>Created At</TableCell>
                      <TableCell>Actions</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {versions.map((version) => (
                      <TableRow key={version.id}>
                        <TableCell>v{version.version_no}</TableCell>
                        <TableCell>
                          <Chip
                            label={version.action}
                            color={version.action === 'upload' ? 'primary' : version.action === 'revision' ? 'warning' : 'info'}
                            size="small"
                          />
                        </TableCell>
                        <TableCell>{version.changes_summary || '-'}</TableCell>
                        <TableCell>{new Date(version.created_at).toLocaleString()}</TableCell>
                        <TableCell>
                          <Button
                            size="small"
                            onClick={() => handleRestoreClick(version)}
                          >
                            Restore
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            )}
          </Box>
        </TabPanel>
      </Paper>

      {/* Metadata */}
      <Paper sx={{ p: 3 }}>
        <Typography variant="h6" gutterBottom>
          Metadata
        </Typography>
        <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 2 }}>
          <Box>
            <Typography variant="body2" color="text.secondary">
              Created At
            </Typography>
            <Typography variant="body1">
              {new Date(strategy.created_at).toLocaleString()}
            </Typography>
          </Box>
          <Box>
            <Typography variant="body2" color="text.secondary">
              Last Updated
            </Typography>
            <Typography variant="body1">
              {new Date(strategy.updated_at).toLocaleString()}
            </Typography>
          </Box>
        </Box>
      </Paper>

      {/* Revision Modal */}
      <Dialog open={revisionModalOpen} onClose={handleCloseRevision} maxWidth="md" fullWidth>
        <DialogTitle>
          Revise Entries - {strategy.symbol}
        </DialogTitle>
        <DialogContent>
          {revisionLoading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
              <CircularProgress />
            </Box>
          ) : revisionError ? (
            <Alert severity="error">{revisionError}</Alert>
          ) : revisionData ? (
            <Box>
              <Box sx={{ mb: 3 }}>
                <Typography variant="subtitle2" sx={{ mb: 1 }}>Revision Style</Typography>
                <RadioGroup
                  row
                  value={revisionStyle}
                  onChange={(e) => handleStyleChange(e.target.value)}
                  sx={{ mb: 2 }}
                >
                  <FormControlLabel value="conservative" control={<Radio size="small" />} label="Conservative" />
                  <FormControlLabel value="balanced" control={<Radio size="small" />} label="Balanced" />
                  <FormControlLabel value="aggressive" control={<Radio size="small" />} label="Aggressive" />
                </RadioGroup>

                <Accordion expanded={advancedOpen} onChange={() => setAdvancedOpen(!advancedOpen)} sx={{ mb: 2 }}>
                  <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                    <Typography variant="subtitle2">Advanced Settings</Typography>
                  </AccordionSummary>
                  <AccordionDetails>
                    <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                      <TextField
                        type="number"
                        label="ATR Period"
                        value={advancedOverrides.atrPeriod}
                        onChange={(e) => setAdvancedOverrides({ ...advancedOverrides, atrPeriod: Number(e.target.value) })}
                        size="small"
                        sx={{ width: 120 }}
                        inputProps={{ min: 5, max: 50 }}
                      />
                      <TextField
                        type="number"
                        label="EMA Fast"
                        value={advancedOverrides.emaFast}
                        onChange={(e) => setAdvancedOverrides({ ...advancedOverrides, emaFast: Number(e.target.value) })}
                        size="small"
                        sx={{ width: 120 }}
                        inputProps={{ min: 5, max: 50 }}
                      />
                      <TextField
                        type="number"
                        label="EMA Slow"
                        value={advancedOverrides.emaSlow}
                        onChange={(e) => setAdvancedOverrides({ ...advancedOverrides, emaSlow: Number(e.target.value) })}
                        size="small"
                        sx={{ width: 120 }}
                        inputProps={{ min: 20, max: 200 }}
                      />
                      <TextField
                        type="number"
                        label="Lookback Days"
                        value={advancedOverrides.lookback}
                        onChange={(e) => setAdvancedOverrides({ ...advancedOverrides, lookback: Number(e.target.value) })}
                        size="small"
                        sx={{ width: 140 }}
                        inputProps={{ min: 20, max: 200 }}
                      />
                      <TextField
                        type="number"
                        label="ATR Spacing Multiplier"
                        value={advancedOverrides.atrMultiplier}
                        onChange={(e) => setAdvancedOverrides({ ...advancedOverrides, atrMultiplier: Number(e.target.value) })}
                        size="small"
                        sx={{ width: 180 }}
                        inputProps={{ min: 0.1, max: 5.0, step: 0.05 }}
                      />
                    </Box>
                  </AccordionDetails>
                </Accordion>

                {revisionData.style && (
                  <Chip label={`Style: ${revisionData.style}`} size="small" sx={{ mb: 1 }} />
                )}
                {revisionData.cmp_price && (
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                    Current Market Price (CMP): ₹{revisionData.cmp_price.toFixed(2)}
                  </Typography>
                )}
              </Box>

              <TableContainer>
                <Table>
                  <TableHead>
                    <TableRow>
                      <TableCell>Select</TableCell>
                      <TableCell>Level</TableCell>
                      <TableCell>Original Price</TableCell>
                      <TableCell>Suggested Price</TableCell>
                      <TableCell>Change</TableCell>
                      <TableCell>Rationale</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {revisionData.revised_levels.map((level) => {
                      const change = ((level.suggested_price - level.original_price) / level.original_price * 100).toFixed(1);
                      const isPositive = level.suggested_price > level.original_price;
                      return (
                        <TableRow key={level.level_no}>
                          <TableCell>
                            <Checkbox
                              checked={selectedLevels.has(level.level_no)}
                              onChange={() => handleToggleLevel(level.level_no)}
                            />
                          </TableCell>
                          <TableCell>Level {level.level_no}</TableCell>
                          <TableCell>₹{level.original_price.toFixed(2)}</TableCell>
                          <TableCell>₹{level.suggested_price.toFixed(2)}</TableCell>
                          <TableCell>
                            <Chip
                              label={`${isPositive ? '+' : ''}${change}%`}
                              color={isPositive ? 'success' : 'error'}
                              size="small"
                            />
                          </TableCell>
                          <TableCell>{level.rationale}</TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </TableContainer>

              {applyError && (
                <Alert severity="error" sx={{ mt: 2 }} onClose={() => setApplyError('')}>
                  {applyError}
                </Alert>
              )}

              {applySuccess && (
                <Alert severity="success" sx={{ mt: 2 }}>
                  {applySuccess}
                </Alert>
              )}
            </Box>
          ) : (
            <Typography>No revision data available</Typography>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseRevision}>Cancel</Button>
          <Button
            onClick={handleApplyRevision}
            variant="contained"
            disabled={selectedLevels.size === 0 || applyLoading || !!applySuccess}
          >
            {applyLoading ? 'Applying...' : `Apply Selected (${selectedLevels.size})`}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Restore Version Dialog */}
      <Dialog open={restoreDialogOpen} onClose={() => setRestoreDialogOpen(false)}>
        <DialogTitle>Restore Version</DialogTitle>
        <DialogContent>
          {restoreSuccess ? (
            <Alert severity="success">{restoreSuccess}</Alert>
          ) : (
            <Typography>
              Are you sure you want to restore to version {selectedVersion?.version_no}?
              This will overwrite the current entry levels.
            </Typography>
          )}
          {restoreError && (
            <Alert severity="error" sx={{ mt: 2 }}>{restoreError}</Alert>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setRestoreDialogOpen(false)} disabled={!!restoreSuccess}>
            Cancel
          </Button>
          <Button
            onClick={handleConfirmRestore}
            variant="contained"
            color="warning"
            disabled={restoreLoading || !!restoreSuccess}
          >
            {restoreLoading ? 'Restoring...' : 'Restore'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
