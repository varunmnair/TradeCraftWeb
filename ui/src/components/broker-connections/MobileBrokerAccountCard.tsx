import { memo, useState } from 'react';
import type { MouseEvent } from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  IconButton,
  Menu,
  MenuItem,
  Tooltip,
  Typography,
} from '@mui/material';
import {
  Add as AddIcon,
  Check as CheckIcon,
  Cloud as ZerodhaIcon,
  CloudDone as UpstoxIcon,
  Delete as DeleteIcon,
  Error as ErrorIcon,
  MoreVert as MoreIcon,
  Refresh as RefreshIcon,
  StopCircle as EndSessionIcon,
  Warning as WarningIcon,
} from '@mui/icons-material';

export interface MobileBrokerAccountCardProps {
  broker: 'upstox' | 'zerodha';
  accountId: string;
  connectionLabel: string;
  connectionTone: 'default' | 'warning' | 'success';
  tradingStatus: string;
  dataStatus: string;
  lastRefresh: string;
  connecting: boolean;
  refreshing: boolean;
  hasSession: boolean;
  onPrimary: () => void;
  onRefreshStatus: () => void;
  onEndSession: () => void;
  onReconnect: () => void;
  onDisconnect: () => void;
}

function MobileBrokerAccountCardBase({
  broker,
  accountId,
  connectionLabel,
  connectionTone,
  tradingStatus,
  dataStatus,
  lastRefresh,
  connecting,
  refreshing,
  hasSession,
  onPrimary,
  onRefreshStatus,
  onEndSession,
  onReconnect,
  onDisconnect,
}: MobileBrokerAccountCardProps) {
  const [menuAnchor, setMenuAnchor] = useState<HTMLElement | null>(null);
  const isUpstox = broker === 'upstox';
  const connected = connectionTone === 'success';

  const openMenu = (event: MouseEvent<HTMLElement>) => setMenuAnchor(event.currentTarget);
  const closeMenu = () => setMenuAnchor(null);

  const runAction = (action: () => void) => {
    closeMenu();
    action();
  };

  return (
    <Card sx={{ mb: 1.5, overflow: 'hidden' }}>
      <CardContent sx={{ p: 1.75, '&:last-child': { pb: 1.75 } }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, minWidth: 0 }}>
          {isUpstox ? (
            <UpstoxIcon color="primary" fontSize="small" />
          ) : (
            <ZerodhaIcon fontSize="small" sx={{ color: '#283195' }} />
          )}
          <Typography variant="subtitle1" fontWeight={800} sx={{ minWidth: 0 }}>
            {isUpstox ? 'Upstox' : 'Zerodha'}
          </Typography>
          <Box sx={{ flex: 1, minWidth: 0 }} />
          <Chip
            label={connectionLabel}
            size="small"
            color={connectionTone}
            icon={
              connectionTone === 'success' ? (
                <CheckIcon />
              ) : connectionTone === 'warning' ? (
                <WarningIcon />
              ) : (
                <ErrorIcon />
              )
            }
          />
          <Tooltip title="More actions">
            <IconButton size="small" onClick={openMenu} aria-label="More broker account actions">
              <MoreIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>

        <Menu
          anchorEl={menuAnchor}
          open={Boolean(menuAnchor)}
          onClose={closeMenu}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
          transformOrigin={{ vertical: 'top', horizontal: 'right' }}
        >
          <MenuItem onClick={() => runAction(onRefreshStatus)} disabled={refreshing}>
            <RefreshIcon fontSize="small" sx={{ mr: 1 }} />
            Refresh status
          </MenuItem>
          {connected && (
            <MenuItem onClick={() => runAction(onReconnect)} disabled={connecting}>
              <AddIcon fontSize="small" sx={{ mr: 1 }} />
              Reconnect broker
            </MenuItem>
          )}
          {hasSession && (
            <MenuItem onClick={() => runAction(onEndSession)}>
              <EndSessionIcon fontSize="small" sx={{ mr: 1 }} />
              End session
            </MenuItem>
          )}
          {connected && (
            <MenuItem onClick={() => runAction(onDisconnect)} disabled={connecting}>
              <DeleteIcon fontSize="small" sx={{ mr: 1 }} />
              Disconnect broker
            </MenuItem>
          )}
        </Menu>

        <Box sx={{ display: 'grid', gap: 0.5, mt: 1.5 }}>
          <Typography variant="body2" color="text.secondary">
            Account:{' '}
            <Box component="span" sx={{ color: 'text.primary', fontWeight: 600 }}>
              {accountId}
            </Box>
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Trading:{' '}
            <Box component="span" sx={{ color: 'text.primary', fontWeight: 600 }}>
              {tradingStatus}
            </Box>
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Data:{' '}
            <Box component="span" sx={{ color: 'text.primary', fontWeight: 600 }}>
              {dataStatus}
            </Box>
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Last refresh:{' '}
            <Box component="span" sx={{ color: 'text.primary', fontWeight: 600 }}>
              {lastRefresh}
            </Box>
          </Typography>
        </Box>

        <Button
          variant={connected ? 'outlined' : 'contained'}
          startIcon={connected ? <RefreshIcon /> : <AddIcon />}
          onClick={onPrimary}
          disabled={connecting || refreshing}
          fullWidth
          sx={{ minHeight: 44, mt: 2, textTransform: 'none' }}
        >
          {connecting
            ? 'Connecting…'
            : refreshing
              ? 'Refreshing…'
              : connected
                ? 'Refresh'
                : 'Connect'}
        </Button>
      </CardContent>
    </Card>
  );
}

export const MobileBrokerAccountCard = memo(MobileBrokerAccountCardBase);
