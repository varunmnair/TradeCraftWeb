import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Checkbox,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  FormControl,
  FormControlLabel,
  IconButton,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import {
  ArrowDownward as DownIcon,
  ArrowUpward as UpIcon,
  DragIndicator as DragIcon,
  RestartAlt as ResetIcon,
  Save as SaveIcon,
} from '@mui/icons-material';
import { api } from '../../api/client';
import { invalidateUiPageConfig, setCachedUiPageConfig } from '../../config/uiConfigCache';
import type { UiConfigPageSummary, UiConfigSort, UiPageConfig } from '../../types';

const PAGE_SIZE_OPTIONS = [25, 50, 100] as const;

function cloneConfig(config: UiPageConfig): UiPageConfig {
  return JSON.parse(JSON.stringify(config)) as UiPageConfig;
}

function normalizeConfig(config: UiPageConfig): UiPageConfig {
  const next = cloneConfig(config);
  next.columns = [...next.columns]
    .sort((a, b) => (a.position ?? 0) - (b.position ?? 0) || a.id.localeCompare(b.id))
    .map((c, idx) => ({ ...c, position: idx, visible: c.required ? true : c.visible }));
  const allowed = Array.from(new Set(next.allowedPageSizes.filter((s): s is 25 | 50 | 100 => PAGE_SIZE_OPTIONS.includes(s as 25 | 50 | 100)))).sort((a, b) => a - b);
  next.allowedPageSizes = allowed.length ? allowed : [25, 50, 100];
  if (!next.allowedPageSizes.includes(next.defaultPageSize)) next.defaultPageSize = next.allowedPageSizes[0];
  const ids = new Set(next.columns.map((c) => c.id));
  next.mobilePrimaryFields = next.mobilePrimaryFields.filter((id, i, arr) => ids.has(id) && arr.indexOf(id) === i);
  next.mobileDetailFields = next.mobileDetailFields.filter((id, i, arr) => ids.has(id) && arr.indexOf(id) === i && !next.mobilePrimaryFields.includes(id));
  for (const col of next.columns) {
    if (col.required && !next.mobilePrimaryFields.includes(col.id) && !next.mobileDetailFields.includes(col.id)) {
      next.mobilePrimaryFields.unshift(col.id);
    }
  }
  return next;
}

function configsEqual(a: UiPageConfig | null, b: UiPageConfig | null): boolean {
  return JSON.stringify(a) === JSON.stringify(b);
}

function toPayload(config: UiPageConfig) {
  return {
    pageId: config.pageId,
    searchEnabled: config.searchEnabled,
    searchField: config.searchField ?? null,
    defaultPageSize: config.defaultPageSize,
    allowedPageSizes: config.allowedPageSizes,
    density: config.density,
    selectionEnabled: config.selectionEnabled,
    defaultSort: config.defaultSort ?? null,
    mobilePrimaryFields: config.mobilePrimaryFields,
    mobileDetailFields: config.mobileDetailFields,
    columns: config.columns.map((c) => ({
      id: c.id,
      visible: c.visible,
      sortable: c.sortable,
      filterable: c.filterable,
      position: c.position,
    })),
  };
}

export default function UiConfigTab() {
  const [pages, setPages] = useState<UiConfigPageSummary[]>([]);
  const [selectedPageId, setSelectedPageId] = useState('');
  const [config, setConfig] = useState<UiPageConfig | null>(null);
  const [savedConfig, setSavedConfig] = useState<UiPageConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error' | 'info'; text: string } | null>(null);
  const [resetOpen, setResetOpen] = useState(false);
  const [pendingPageId, setPendingPageId] = useState<string | null>(null);
  const [dragId, setDragId] = useState<string | null>(null);

  const dirty = useMemo(() => !configsEqual(config, savedConfig), [config, savedConfig]);
  const selectedPage = pages.find((p) => p.page_id === selectedPageId);

  const loadPages = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.getUiConfigPages();
      setPages(res.pages);
      if (!selectedPageId && res.pages.length > 0) {
        setSelectedPageId(res.pages[0].page_id);
      }
    } catch (err) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : 'Failed to load UI config pages' });
    } finally {
      setLoading(false);
    }
  }, [selectedPageId]);

  const loadConfig = useCallback(async (pageId: string) => {
    if (!pageId) return;
    setLoading(true);
    try {
      const cfg = normalizeConfig(await api.getUiPageConfig(pageId));
      setConfig(cloneConfig(cfg));
      setSavedConfig(cloneConfig(cfg));
      setMessage(null);
    } catch (err) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : 'Failed to load page configuration' });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void loadPages(); }, [loadPages]);
  useEffect(() => { if (selectedPageId) void loadConfig(selectedPageId); }, [selectedPageId, loadConfig]);

  const updateConfig = (updater: (current: UiPageConfig) => UiPageConfig) => {
    setConfig((current) => (current ? normalizeConfig(updater(cloneConfig(current))) : current));
  };

  const handlePageChange = (nextPageId: string) => {
    if (nextPageId === selectedPageId) return;
    if (dirty) {
      setPendingPageId(nextPageId);
      return;
    }
    setSelectedPageId(nextPageId);
  };

  const confirmDiscard = () => {
    if (pendingPageId) {
      setSelectedPageId(pendingPageId);
      setPendingPageId(null);
    }
  };

  const moveColumn = (columnId: string, direction: -1 | 1) => {
    updateConfig((current) => {
      const cols = [...current.columns].sort((a, b) => a.position - b.position);
      const index = cols.findIndex((c) => c.id === columnId);
      const target = index + direction;
      if (index < 0 || target < 0 || target >= cols.length) return current;
      const [item] = cols.splice(index, 1);
      cols.splice(target, 0, item);
      current.columns = cols.map((c, i) => ({ ...c, position: i }));
      return current;
    });
  };

  const onDropColumn = (targetId: string) => {
    if (!dragId || dragId === targetId) return;
    updateConfig((current) => {
      const cols = [...current.columns].sort((a, b) => a.position - b.position);
      const from = cols.findIndex((c) => c.id === dragId);
      const to = cols.findIndex((c) => c.id === targetId);
      if (from < 0 || to < 0) return current;
      const [item] = cols.splice(from, 1);
      cols.splice(to, 0, item);
      current.columns = cols.map((c, i) => ({ ...c, position: i }));
      return current;
    });
    setDragId(null);
  };

  const handleSave = async () => {
    if (!config) return;
    setSaving(true);
    setMessage(null);
    try {
      const saved = normalizeConfig(await api.saveUiPageConfig(config.pageId, toPayload(config)));
      setConfig(cloneConfig(saved));
      setSavedConfig(cloneConfig(saved));
      setCachedUiPageConfig(saved.pageId, saved);
      invalidateUiPageConfig(saved.pageId);
      setCachedUiPageConfig(saved.pageId, saved);
      setMessage({ type: 'success', text: 'Configuration saved.' });
    } catch (err) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : 'Failed to save configuration' });
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async () => {
    if (!config) return;
    setSaving(true);
    setMessage(null);
    try {
      const reset = normalizeConfig(await api.resetUiPageConfig(config.pageId));
      setConfig(cloneConfig(reset));
      setSavedConfig(cloneConfig(reset));
      setCachedUiPageConfig(reset.pageId, reset);
      invalidateUiPageConfig(reset.pageId);
      setCachedUiPageConfig(reset.pageId, reset);
      setResetOpen(false);
      setMessage({ type: 'success', text: 'Configuration reset to defaults.' });
    } catch (err) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : 'Failed to reset configuration' });
    } finally {
      setSaving(false);
    }
  };

  if (loading && !config) {
    return <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}><CircularProgress /></Box>;
  }

  const sortedColumns = [...(config?.columns ?? [])].sort((a, b) => a.position - b.position);
  const sortableColumns = sortedColumns.filter((c) => c.sortable);

  return (
    <Paper sx={{ p: 3 }}>
      <Typography variant="h6" gutterBottom>UI Configuration</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Configure global table and mobile display settings. Changes apply to all users.
      </Typography>

      {message && <Alert severity={message.type} sx={{ mb: 2 }} onClose={() => setMessage(null)}>{message.text}</Alert>}

      <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} sx={{ mb: 3 }}>
        <FormControl size="small" sx={{ minWidth: 260 }}>
          <InputLabel id="ui-config-page-label">Configure Page</InputLabel>
          <Select
            labelId="ui-config-page-label"
            label="Configure Page"
            value={selectedPageId}
            onChange={(e) => handlePageChange(String(e.target.value))}
          >
            {pages.map((p) => <MenuItem key={p.page_id} value={p.page_id}>{p.label}</MenuItem>)}
          </Select>
        </FormControl>
        {dirty && <Alert severity="info" sx={{ py: 0, alignItems: 'center' }}>Unsaved changes</Alert>}
      </Stack>

      {config && (
        <>
          <Typography variant="subtitle1" sx={{ mb: 1 }}>Page Settings</Typography>
          <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} flexWrap="wrap" useFlexGap sx={{ mb: 3 }}>
            <FormControl size="small" sx={{ minWidth: 180 }}>
              <InputLabel id="density-label">Table Density</InputLabel>
              <Select labelId="density-label" label="Table Density" value={config.density}
                onChange={(e) => updateConfig((c) => ({ ...c, density: e.target.value as 'compact' | 'comfortable' }))}>
                <MenuItem value="compact">Compact</MenuItem>
                <MenuItem value="comfortable">Comfortable</MenuItem>
              </Select>
            </FormControl>

            <FormControl size="small" sx={{ minWidth: 180 }}>
              <InputLabel id="default-size-label">Default Page Size</InputLabel>
              <Select labelId="default-size-label" label="Default Page Size" value={config.defaultPageSize}
                onChange={(e) => updateConfig((c) => ({ ...c, defaultPageSize: Number(e.target.value) }))}>
                {config.allowedPageSizes.map((s) => <MenuItem key={s} value={s}>{s}</MenuItem>)}
              </Select>
            </FormControl>

            <FormControl size="small" sx={{ minWidth: 220 }}>
              <InputLabel id="allowed-sizes-label">Available Page Sizes</InputLabel>
              <Select
                labelId="allowed-sizes-label"
                label="Available Page Sizes"
                multiple
                value={config.allowedPageSizes}
                renderValue={(selected) => (selected as number[]).join(', ')}
                onChange={(e) => {
                  const value = e.target.value as number[];
                  updateConfig((c) => {
                    const allowed = PAGE_SIZE_OPTIONS.filter((s) => value.includes(s));
                    const nextAllowed = allowed.length ? allowed : [c.defaultPageSize];
                    return {
                      ...c,
                      allowedPageSizes: nextAllowed,
                      defaultPageSize: nextAllowed.includes(c.defaultPageSize) ? c.defaultPageSize : nextAllowed[0],
                    };
                  });
                }}
              >
                {PAGE_SIZE_OPTIONS.map((size) => (
                  <MenuItem key={size} value={size}>
                    <Checkbox checked={config.allowedPageSizes.includes(size)} />
                    {size}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <FormControl size="small" sx={{ minWidth: 220 }}>
              <InputLabel id="default-sort-label">Default Sort Column</InputLabel>
              <Select
                labelId="default-sort-label"
                label="Default Sort Column"
                value={config.defaultSort?.field ?? ''}
                onChange={(e) => {
                  const field = String(e.target.value);
                  updateConfig((c) => ({
                    ...c,
                    defaultSort: field ? { field, direction: c.defaultSort?.direction ?? 'asc' } : null,
                  }));
                }}
              >
                <MenuItem value="">None</MenuItem>
                {sortableColumns.map((c) => <MenuItem key={c.id} value={c.id}>{c.label ?? c.id}</MenuItem>)}
              </Select>
            </FormControl>

            <FormControl size="small" sx={{ minWidth: 160 }}>
              <InputLabel id="sort-dir-label">Sort Direction</InputLabel>
              <Select
                labelId="sort-dir-label"
                label="Sort Direction"
                value={config.defaultSort?.direction ?? 'asc'}
                disabled={!config.defaultSort?.field}
                onChange={(e) => updateConfig((c) => ({
                  ...c,
                  defaultSort: c.defaultSort ? { ...c.defaultSort, direction: e.target.value as UiConfigSort['direction'] } : c.defaultSort,
                }))}
              >
                <MenuItem value="asc">Ascending</MenuItem>
                <MenuItem value="desc">Descending</MenuItem>
              </Select>
            </FormControl>

            <FormControlLabel
              control={<Switch checked={config.selectionEnabled} disabled={!selectedPage?.selection_supported}
                onChange={(_, checked) => updateConfig((c) => ({ ...c, selectionEnabled: checked }))} />}
              label="Row Selection"
            />
            <FormControlLabel
              control={<Switch checked={config.searchEnabled} disabled={!selectedPage?.search_supported}
                onChange={(_, checked) => updateConfig((c) => ({ ...c, searchEnabled: checked, searchField: checked ? 'symbol' : null }))} />}
              label="Search Enabled"
            />
          </Stack>

          <Divider sx={{ my: 2 }} />
          <Typography variant="subtitle1" sx={{ mb: 1 }}>Column Settings</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
            Drag rows or use Move Up/Down to reorder. Required columns cannot be hidden.
          </Typography>
          <TableContainer sx={{ mb: 3 }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell width={70}>Order</TableCell>
                  <TableCell>Column Name</TableCell>
                  <TableCell align="center">Visible</TableCell>
                  <TableCell align="center">Sortable</TableCell>
                  <TableCell align="center">Filterable</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {sortedColumns.map((col, idx) => (
                  <TableRow
                    key={col.id}
                    draggable
                    onDragStart={() => setDragId(col.id)}
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={() => onDropColumn(col.id)}
                    onDragEnd={() => setDragId(null)}
                    sx={{ cursor: 'grab', opacity: dragId === col.id ? 0.5 : 1 }}
                  >
                    <TableCell>
                      <Stack direction="row" spacing={0} alignItems="center">
                        <DragIcon fontSize="small" color="action" />
                        <IconButton size="small" aria-label={`Move ${col.label} up`} onClick={() => moveColumn(col.id, -1)} disabled={idx === 0}><UpIcon fontSize="inherit" /></IconButton>
                        <IconButton size="small" aria-label={`Move ${col.label} down`} onClick={() => moveColumn(col.id, 1)} disabled={idx === sortedColumns.length - 1}><DownIcon fontSize="inherit" /></IconButton>
                      </Stack>
                    </TableCell>
                    <TableCell>{col.label ?? col.id}{col.required ? ' (Required)' : ''}</TableCell>
                    <TableCell align="center">
                      <Checkbox checked={col.visible} disabled={!!col.required}
                        onChange={(_, checked) => updateConfig((c) => ({ ...c, columns: c.columns.map((x) => x.id === col.id ? { ...x, visible: checked } : x) }))} />
                    </TableCell>
                    <TableCell align="center">
                      <Checkbox checked={col.sortable} disabled={col.sortableSupported === false}
                        onChange={(_, checked) => updateConfig((c) => ({ ...c, columns: c.columns.map((x) => x.id === col.id ? { ...x, sortable: checked } : x) }))} />
                    </TableCell>
                    <TableCell align="center">
                      <Checkbox checked={col.filterable} disabled={col.filterableSupported === false}
                        onChange={(_, checked) => updateConfig((c) => ({ ...c, columns: c.columns.map((x) => x.id === col.id ? { ...x, filterable: checked } : x) }))} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>

          <Divider sx={{ my: 2 }} />
          <Typography variant="subtitle1" sx={{ mb: 1 }}>Mobile Fields</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
            Primary fields appear on mobile cards; detail fields appear in expanded/secondary content. Required identity fields remain visible.
          </Typography>
          <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} sx={{ mb: 3 }}>
            <FormControl size="small" fullWidth>
              <InputLabel id="mobile-primary-label">Primary Fields</InputLabel>
              <Select
                labelId="mobile-primary-label"
                label="Primary Fields"
                multiple
                value={config.mobilePrimaryFields}
                renderValue={(selected) => (selected as string[]).map((id) => config.columns.find((c) => c.id === id)?.label ?? id).join(', ')}
                onChange={(e) => {
                  const value = e.target.value as string[];
                  updateConfig((c) => ({ ...c, mobilePrimaryFields: value, mobileDetailFields: c.mobileDetailFields.filter((id) => !value.includes(id)) }));
                }}
              >
                {sortedColumns.map((col) => (
                  <MenuItem key={col.id} value={col.id}>
                    <Checkbox checked={config.mobilePrimaryFields.includes(col.id)} />
                    {col.label ?? col.id}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <FormControl size="small" fullWidth>
              <InputLabel id="mobile-detail-label">Expanded Detail Fields</InputLabel>
              <Select
                labelId="mobile-detail-label"
                label="Expanded Detail Fields"
                multiple
                value={config.mobileDetailFields}
                renderValue={(selected) => (selected as string[]).map((id) => config.columns.find((c) => c.id === id)?.label ?? id).join(', ')}
                onChange={(e) => {
                  const value = e.target.value as string[];
                  updateConfig((c) => ({ ...c, mobileDetailFields: value.filter((id) => !c.mobilePrimaryFields.includes(id)) }));
                }}
              >
                {sortedColumns.filter((c) => !config.mobilePrimaryFields.includes(c.id)).map((col) => (
                  <MenuItem key={col.id} value={col.id}>
                    <Checkbox checked={config.mobileDetailFields.includes(col.id)} />
                    {col.label ?? col.id}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Stack>

          <Stack direction="row" spacing={2}>
            <Button variant="contained" startIcon={<SaveIcon />} onClick={() => void handleSave()} disabled={!dirty || saving}>
              {saving ? 'Saving...' : 'Save Configuration'}
            </Button>
            <Button variant="outlined" color="warning" startIcon={<ResetIcon />} onClick={() => setResetOpen(true)} disabled={saving}>
              Reset to Defaults
            </Button>
          </Stack>
        </>
      )}

      <Dialog open={!!pendingPageId} onClose={() => setPendingPageId(null)}>
        <DialogTitle>Discard unsaved changes?</DialogTitle>
        <DialogContent>
          <Typography>You have unsaved UI configuration changes. Discard them and switch pages?</Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPendingPageId(null)}>Cancel</Button>
          <Button color="warning" variant="contained" onClick={confirmDiscard}>Discard</Button>
        </DialogActions>
      </Dialog>

      <Dialog open={resetOpen} onClose={() => !saving && setResetOpen(false)}>
        <DialogTitle>Reset to Defaults</DialogTitle>
        <DialogContent>
          <Typography>
            This will restore the <strong>{selectedPage?.label ?? config?.pageId}</strong> page configuration to built-in defaults for all users.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setResetOpen(false)} disabled={saving}>Cancel</Button>
          <Button color="warning" variant="contained" onClick={() => void handleReset()} disabled={saving}>
            {saving ? 'Resetting...' : 'Reset to Defaults'}
          </Button>
        </DialogActions>
      </Dialog>
    </Paper>
  );
}