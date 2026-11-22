import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Typography,
} from '@mui/material';
import type { VersionItem } from '../../types';
import { formatAllocation, formatDate, formatPrice } from './strategyDisplay';

interface MobileVersionHistoryProps {
  versions: VersionItem[];
  currentAllocation: number | null;
  loading: boolean;
  error: string;
  onRestore?: (version: VersionItem) => void;
  onOpenFullDetail?: () => void;
}

export function MobileVersionHistory({
  versions,
  currentAllocation,
  loading,
  error,
  onRestore,
  onOpenFullDetail,
}: MobileVersionHistoryProps) {
  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return <Alert severity="error">{error}</Alert>;
  }

  if (versions.length === 0) {
    return <Alert severity="info">No version history available</Alert>;
  }

  return (
    <Box>
      {versions.map((version) => (
        <Box
          key={version.id}
          sx={{
            py: 1.25,
            borderBottom: '1px solid',
            borderColor: 'divider',
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 1 }}>
            <Typography variant="subtitle2" sx={{ fontWeight: 800 }}>
              v{version.version_no}
            </Typography>
            <Chip label={version.action} size="small" color="primary" variant="outlined" />
          </Box>
          <Typography variant="caption" color="text.secondary" display="block">
            {formatDate(version.created_at)}
          </Typography>
          <Typography variant="body2" sx={{ mt: 0.5, wordBreak: 'break-word' }}>
            Entries:{' '}
            {version.levels.length
              ? version.levels
                  .slice()
                  .sort((a, b) => a.level_no - b.level_no)
                  .map((level) => `E${level.level_no} ${formatPrice(level.price)}`)
                  .join('  •  ')
              : '-'}
          </Typography>
          <Typography variant="body2">
            Allocation: {formatAllocation(currentAllocation)} (current)
          </Typography>
          {version.changes_summary && (
            <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 0.5 }}>
              {version.changes_summary}
            </Typography>
          )}
          {(onRestore || onOpenFullDetail) && (
            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mt: 1 }}>
              {onRestore && (
                <Button size="small" onClick={() => onRestore(version)}>
                  Restore
                </Button>
              )}
              {onOpenFullDetail && (
                <Button size="small" onClick={onOpenFullDetail}>
                  Open full detail
                </Button>
              )}
            </Box>
          )}
        </Box>
      ))}
    </Box>
  );
}