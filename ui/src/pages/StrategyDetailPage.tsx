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
  InputLabel,
  Select,
  MenuItem,
  Checkbox,
  Tabs,
  Tab,
  TextField,
} from '@mui/material';
import {
  ArrowBack as BackIcon,
  Refresh as RefreshIcon,
  AutoFixHigh as ReviseIcon,
} from '@mui/icons-material';
import { api } from '../api/client';
import { EntryStrategyFull, SuggestRevisionResponse, VersionItem } from '../types';
import { useSession } from '../context/SessionContext';

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
  const { sessionId } = useSession();
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

  // Revision modal state
  const [revisionModalOpen, setRevisionModalOpen] = useState(false);
  const [revisionLoading, setRevisionLoading] = useState(false);
  const [revisionError, setRevisionError] = useState('');
  const [revisionData, setRevisionData] = useState<SuggestRevisionResponse | null>(null);
  const [revisionMethod, setRevisionMethod] = useState('align_to_cmp');
  const [pctAdjustment, setPctAdjustment] = useState<number>(5);
  const [selectedLevels, setSelectedLevels] = useState<Set<number>>(new Set());
  const [applyLoading, setApplyLoading] = useState(false);
  const [applyError, setApplyError] = useState('');
  const [applySuccess, setApplySuccess] = useState('');

  useEffect(() => {
    if (symbol && sessionId) {
      fetchStrategy();
    }
  }, [symbol, sessionId]);

  useEffect(() => {
    if (tabValue === 1 && symbol) {
      fetchVersionHistory();
    }
  }, [tabValue, symbol]);

  const fetchStrategy = async () => {
    if (!symbol || !sessionId) return;
    setLoading(true);
    try {
      const data = await api.getEntryStrategy(decodeURIComponent(symbol), sessionId);
      setStrategy(data);
      setError('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load strategy');
    } finally {
      setLoading(false);
    }
  };

  const fetchVersionHistory = async () => {
    if (!symbol || !sessionId) return;
    setVersionsLoading(true);
    setVersionsError('');
    try {
      const data = await api.getVersionHistory(decodeURIComponent(symbol), sessionId);
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

  const handleMethodChange = async (method: string) => {
    setRevisionMethod(method);
    setRevisionData(null);
    setSelectedLevels(new Set());
    await fetchRevisionSuggestions(method, pctAdjustment);
  };

  const handlePctAdjustmentChange = async (pct: number) => {
    setPctAdjustment(pct);
    setRevisionData(null);
    setSelectedLevels(new Set());
    await fetchRevisionSuggestions(revisionMethod, pct);
  };

  const fetchRevisionSuggestions = async (method?: string, pct?: number) => {
    if (!symbol || !sessionId) return;
    setRevisionLoading(true);
    setRevisionError('');
    try {
      const effectiveMethod = method || revisionMethod;
      const effectivePct = pct !== undefined ? pct : pctAdjustment;
      const data = await api.suggestRevision(
        decodeURIComponent(symbol), 
        sessionId, 
        effectiveMethod, 
        effectivePct
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
    if (!symbol || !sessionId || selectedLevels.size === 0) return;
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
      const result = await api.applyRevision(decodeURIComponent(symbol), sessionId, levelsToUpdate);
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
    if (!symbol || !sessionId || !selectedVersion) return;
    setRestoreLoading(true);
    setRestoreSuccess('');
    try {
      const result = await api.restoreVersion(decodeURIComponent(symbol), sessionId, selectedVersion.id);
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
          Revise Levels
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

      {/* Dynamic Averaging Rules */}
      {strategy.dynamic_averaging_enabled && (
        <Paper sx={{ p: 3, mb: 3 }}>
          <Typography variant="h6" gutterBottom>
            Dynamic Averaging Rules
          </Typography>
          {strategy.averaging_rules_summary ? (
            <Typography variant="body1" color="text.secondary">
              {strategy.averaging_rules_summary}
            </Typography>
          ) : strategy.averaging_rules_json ? (
            <Card variant="outlined">
              <CardContent>
                <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                  {JSON.stringify(JSON.parse(strategy.averaging_rules_json), null, 2)}
                </pre>
              </CardContent>
            </Card>
          ) : (
            <Typography variant="body2" color="text.secondary">
              No averaging rules configured
            </Typography>
          )}
        </Paper>
      )}

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
          Revise Entry Levels - {strategy.symbol}
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
                <FormControl fullWidth sx={{ mb: 2 }}>
                  <InputLabel>Revision Method</InputLabel>
                  <Select
                    value={revisionMethod}
                    label="Revision Method"
                    onChange={(e) => handleMethodChange(e.target.value)}
                  >
                    <MenuItem value="align_to_cmp">Align to CMP</MenuItem>
                    <MenuItem value="volatility_band">Volatility Band</MenuItem>
                    <MenuItem value="gap_fill">Gap Fill</MenuItem>
                    <MenuItem value="fixed_adjustment">Fixed Adjustment</MenuItem>
                  </Select>
                </FormControl>
                {revisionMethod === 'fixed_adjustment' && (
                  <TextField
                    type="number"
                    label="Adjustment %"
                    value={pctAdjustment}
                    onChange={(e) => handlePctAdjustmentChange(Number(e.target.value))}
                    size="small"
                    sx={{ width: 150 }}
                    inputProps={{ min: -50, max: 50 }}
                  />
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
