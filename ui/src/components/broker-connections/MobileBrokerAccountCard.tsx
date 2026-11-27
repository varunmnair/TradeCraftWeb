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
  Select,
  Typography,
} from '@mui/material';
import {
  Add as AddIcon,
  Check as CheckIcon,
  Cloud as ZerodhaIcon,
  CloudDone as UpstoxIcon,
  Delete as DeleteIcon,
  MoreVert as MoreIcon,
  Refresh as RefreshIcon,
  StopCircle as EndSessionIcon,
  Warning as WarningIcon,
} from '@mui/icons-material';

export type BrokerCardStatus =
  | 'NOT_CONNECTED'
  | 'CONNECTING'
  | 'READY'
  | 'ATTENTION_REQUIRED';

export interface BrokerAccountOption {
  connectionId: number;
  brokerUserId: string;
}

export interface BrokerAccountCardProps {
  broker: 'upstox' | 'zerodha';
  status: BrokerCardStatus;
  statusLabel: string;
  detail: string | null;
  accounts: BrokerAccountOption[];
  selectedConnectionId: number | null;
  accountId: string | null;
  sessionInfo: { holdings: string; lastRefreshed: string } | null;
  primaryLabel: string;
  primaryDisabled: boolean;
  busy: boolean;
  hasSession: boolean;
  canManage: boolean;
  onSelectAccount: (connectionId: number) => void;
  onPrimary: () => void;
  onRefreshStatus: () => void;
  onEndSession: () => void;
  onReconnect: () => void;
  onDisconnect: () => void;
}

const STATUS_COLORS: Record<BrokerCardStatus, 'default' | 'info' | 'success' | 'warning'> = {
  NOT_CONNECTED: 'default',
  CONNECTING: 'info',
  READY: 'success',
  ATTENTION_REQUIRED: 'warning',
};

function BrokerAccountCardBase({
  broker,
  status,
  statusLabel,
  detail,
  accounts,
  selectedConnectionId,
  accountId,
  sessionInfo,
  primaryLabel,
  primaryDisabled,
  busy,
  hasSession,
  canManage,
  onSelectAccount,
  onPrimary,
  onRefreshStatus,
  onEndSession,
  onReconnect,
  onDisconnect,
}: BrokerAccountCardProps) {
  const [menuAnchor, setMenuAnchor] = useState<HTMLElement | null>(null);
  const isUpstox = broker === 'upstox';
  const needsSelection = accounts.length > 1 && selectedConnectionId === null;

  const openMenu = (event: MouseEvent<HTMLElement>) => setMenuAnchor(event.currentTarget);
  const closeMenu = () => setMenuAnchor(null);
  const runAction = (action: () => void) => {
    closeMenu();
    action();
  };

  return (
    <Card sx={{ minWidth: 0, overflow: 'hidden' }}>
      <CardContent sx={{ p: { xs: 1.75, sm: 2 }, '&:last-child': { pb: { xs: 1.75, sm: 2 } } }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, minWidth: 0, flexWrap: 'wrap' }}>
          {isUpstox ? (
            <UpstoxIcon color="primary" />
          ) : (
            <ZerodhaIcon sx={{ color: '#283195' }} />
          )}
          <Typography variant="subtitle1" fontWeight={800} noWrap>
            {isUpstox ? 'Upstox' : 'Zerodha'}
          </Typography>
          <Chip
            label={statusLabel}
            size="small"
            color={STATUS_COLORS[status]}
            icon={
              status === 'READY' ? (
                <CheckIcon />
              ) : status === 'ATTENTION_REQUIRED' ? (
                <WarningIcon />
              ) : undefined
            }
          />
          <Box sx={{ flex: 1, minWidth: 0 }} />
          <IconButton size="small" onClick={openMenu} aria-label={`More ${broker} actions`}>
            <MoreIcon fontSize="small" />
          </IconButton>
        </Box>

        <Menu
          anchorEl={menuAnchor}
          open={Boolean(menuAnchor)}
          onClose={closeMenu}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
          transformOrigin={{ vertical: 'top', horizontal: 'right' }}
        >
          <MenuItem onClick={() => runAction(onRefreshStatus)}>Refresh status</MenuItem>
          {canManage && (
            <MenuItem onClick={() => runAction(onReconnect)} disabled={busy}>
              Reconnect
            </MenuItem>
          )}
          {hasSession && (
            <MenuItem onClick={() => runAction(onEndSession)}>End session</MenuItem>
          )}
          {canManage && (
            <MenuItem onClick={() => runAction(onDisconnect)} disabled={busy}>
              Disconnect
            </MenuItem>
          )}
        </Menu>

        {detail && (
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
            {detail}
          </Typography>
        )}

        {needsSelection && (
          <Box sx={{ mt: 1.5, maxWidth: 320 }}>
            <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 0.5 }}>
              Account
            </Typography>
            <Select
              value=""
              displayEmpty
              fullWidth
              size="small"
              renderValue={() => 'Select account'}
              onChange={(event) => onSelectAccount(Number(event.target.value))}
              inputProps={{ 'aria-label': `Select ${broker} account` }}
            >
              {accounts.map((account) => (
                <MenuItem key={account.connectionId} value={account.connectionId}>
                  {account.brokerUserId}
                </MenuItem>
              ))}
            </Select>
          </Box>
        )}

        {accountId && (
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1.5 }}>
            Account:{' '}
            <Box component="span" sx={{ color: 'text.primary', fontWeight: 600 }}>
              {accountId}
            </Box>
          </Typography>
        )}

        {sessionInfo && (
          <Box
            sx={{
              display: 'flex',
              flexWrap: 'wrap',
              gap: { xs: 0.5, sm: 3 },
              mt: 1,
              '& .MuiTypography-root': { fontSize: 14 },
            }}
          >
            <Typography variant="body2" color="text.secondary">
              Holdings:{' '}
              <Box component="span" sx={{ color: 'text.primary', fontWeight: 600 }}>
                {sessionInfo.holdings}
              </Box>
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Last refreshed:{' '}
              <Box component="span" sx={{ color: 'text.primary', fontWeight: 600 }}>
                {sessionInfo.lastRefreshed}
              </Box>
            </Typography>
          </Box>
        )}

        <Button
          variant={status === 'READY' ? 'outlined' : 'contained'}
          size="large"
          startIcon={status === 'READY' ? <RefreshIcon /> : <AddIcon />}
          onClick={onPrimary}
          disabled={busy || primaryDisabled}
          sx={{ mt: 2, minHeight: 44, textTransform: 'none', width: { xs: '100%', sm: 'auto' } }}
        >
          {primaryLabel}
        </Button>
      </CardContent>
    </Card>
  );
}

export const BrokerAccountCard = memo(BrokerAccountCardBase);

/** Kept for compatibility with existing imports. */
export const MobileBrokerAccountCard = BrokerAccountCard;
