import { useState } from 'react';
import type { MouseEvent, ReactNode } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  Alert,
  AppBar,
  Box,
  Button,
  Chip,
  Divider,
  Drawer,
  IconButton,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
  Toolbar,
  Tooltip,
  Typography,
} from '@mui/material';
import {
  AccountBalance as BrokerIcon,
  AdminPanelSettings as AdminIcon,
  Assessment as HoldingsIcon,
  Assignment as PlanIcon,
  Checklist as CandidatesIcon,
  Dashboard as DashboardIcon,
  Help as HelpIcon,
  Logout as LogoutIcon,
  MoreVert as MoreVertIcon,
  Notifications as GttIcon,
  PowerSettingsNew as PowerIcon,
  Work as JobsIcon,
} from '@mui/icons-material';
import { useAuth } from '../context/AuthContext';
import { useSession } from '../context/SessionContext';
import { useBrokerSessionOrchestrator } from '../context/BrokerSessionContext';
import { JobMonitor } from './JobMonitor';
import { AIChatPanel, AIFloatingButton } from './AIChatPanel';
import { HelpPanel } from './HelpPanel';
import { MobileNavigation } from './MobileNavigation';
import { ResponsivePageContainer } from './ResponsivePageContainer';
import { appColors, layout } from '../theme';

interface LayoutProps {
  children: ReactNode;
}

const navItems = [
  { text: 'Dashboard', icon: <DashboardIcon />, path: '/dashboard' },
  { text: 'Broker Accounts', icon: <BrokerIcon />, path: '/broker-connections' },
  { text: 'Holdings', icon: <HoldingsIcon />, path: '/holdings' },
  { text: 'Entry Strategies', icon: <PlanIcon />, path: '/entry-strategies' },
  { text: 'Entry Candidates', icon: <CandidatesIcon />, path: '/entry-candidates' },
  { text: 'Buy Orders', icon: <GttIcon />, path: '/gtt' },
  { text: 'Jobs', icon: <JobsIcon />, path: '/jobs' },
  { text: 'Administration', icon: <AdminIcon />, path: '/admin', adminOnly: true },
];

const isRouteActive = (pathname: string, basePath: string) =>
  pathname === basePath || pathname.startsWith(`${basePath}/`);

export default function Layout({ children }: LayoutProps) {
  const [aiPanelOpen, setAiPanelOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const [accountMenuAnchorEl, setAccountMenuAnchorEl] = useState<HTMLElement | null>(
    null,
  );
  const { user, logout } = useAuth();
  const { sessionInfo, sessionExpiredMessage, clearSessionExpired } = useSession();
  const {
    status: sessionStatus,
    message: sessionMessage,
    brokerConnected,
    retry: retrySession,
  } = useBrokerSessionOrchestrator();
  const navigate = useNavigate();
  const location = useLocation();
  const isBrokerAccountsPage = location.pathname === '/broker-connections';

  const handleNavigation = (path: string) => {
    navigate(path);
  };

  const handleLogout = async () => {
    setAccountMenuAnchorEl(null);
    await logout();
    navigate('/login');
  };

  const handleOpenAccountMenu = (event: MouseEvent<HTMLElement>) => {
    setAccountMenuAnchorEl(event.currentTarget);
  };

  const handleCloseAccountMenu = () => {
    setAccountMenuAnchorEl(null);
  };

  const drawer = (
    <Box sx={{ width: layout.drawerWidth }}>
      <Toolbar>
        <Typography variant="h6" noWrap component="div">
          TradeCraftX
        </Typography>
      </Toolbar>
      <Divider />
      <List>
        {navItems
          .filter((item) => !item.adminOnly || (user && user.role === 'admin'))
          .map((item) => (
            <ListItem key={item.text} disablePadding>
              <ListItemButton
                selected={isRouteActive(location.pathname, item.path)}
                onClick={() => handleNavigation(item.path)}
              >
                <ListItemIcon>{item.icon}</ListItemIcon>
                <ListItemText primary={item.text} />
              </ListItemButton>
            </ListItem>
          ))}
      </List>
      <Divider />
      <List>
        <ListItem disablePadding>
          <ListItemButton onClick={handleLogout}>
            <ListItemIcon>
              <LogoutIcon />
            </ListItemIcon>
            <ListItemText primary="Logout" />
          </ListItemButton>
        </ListItem>
      </List>
    </Box>
  );

  const sessionChipSx = {
    mr: { xs: 0, sm: 1 },
    color: appColors.onPrimary,
    borderColor: appColors.onPrimary,
    maxWidth: { xs: 120, sm: 'none' },
    '& .MuiChip-label': {
      overflow: 'hidden',
      textOverflow: 'ellipsis',
      whiteSpace: 'nowrap',
    },
  };

  const readinessChipLabel =
    sessionStatus === 'READY' && sessionInfo
      ? `${sessionInfo.broker.toUpperCase()} - ${sessionInfo.user_id}`
      : sessionStatus === 'INITIALIZING'
        ? 'Starting session…'
        : sessionStatus === 'LOADING'
          ? 'Loading session…'
          : sessionStatus === 'ERROR'
            ? 'Session setup issue'
            : 'No broker session';

  return (
    <Box sx={{ display: 'flex' }}>
      <AppBar
        position="fixed"
        sx={{
          zIndex: (theme) => theme.zIndex.drawer + 1,
        }}
      >
        <Toolbar>
          <Typography
            variant="h6"
            noWrap
            component="div"
            sx={{ flexGrow: 1, fontSize: { xs: '1.1rem', sm: '1.25rem' } }}
          >
            TradeCraftX
          </Typography>
          {user && (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: { xs: 0.5, sm: 1 } }}>
              {import.meta.env.VITE_DEMO_MODE === 'true' && (
                <Chip
                  label="Demo Mode"
                  size="small"
                  color="warning"
                  sx={{ display: { xs: 'none', sm: 'inline-flex' }, mr: 1 }}
                />
              )}
              <Chip
                label={readinessChipLabel}
                size="small"
                variant="outlined"
                sx={{
                  ...sessionChipSx,
                  display: { xs: 'inline-flex', sm: 'inline-flex' },
                }}
              />
              <Tooltip title="Help">
                <IconButton color="inherit" onClick={() => setHelpOpen(true)}>
                  <HelpIcon />
                </IconButton>
              </Tooltip>
              <Box sx={{ display: { xs: 'none', sm: 'flex' }, alignItems: 'center' }}>
                <Typography variant="body2" sx={{ mr: 1 }}>
                  {user.email}
                </Typography>
                <Tooltip title="Logout">
                  <IconButton color="inherit" onClick={handleLogout} size="small">
                    <PowerIcon />
                  </IconButton>
                </Tooltip>
              </Box>
              <Box sx={{ display: { xs: 'flex', sm: 'none' } }}>
                <IconButton
                  color="inherit"
                  aria-label="Account menu"
                  onClick={handleOpenAccountMenu}
                >
                  <MoreVertIcon />
                </IconButton>
                <Menu
                  anchorEl={accountMenuAnchorEl}
                  open={Boolean(accountMenuAnchorEl)}
                  onClose={handleCloseAccountMenu}
                  anchorOrigin={{ vertical: 'top', horizontal: 'right' }}
                  transformOrigin={{ vertical: 'top', horizontal: 'right' }}
                >
                  <MenuItem disabled>
                    <Typography variant="body2">{user.email}</Typography>
                  </MenuItem>
                  <Divider />
                  <MenuItem onClick={handleLogout}>
                    <ListItemIcon>
                      <PowerIcon fontSize="small" />
                    </ListItemIcon>
                    <ListItemText primary="Logout" />
                  </MenuItem>
                </Menu>
              </Box>
            </Box>
          )}
        </Toolbar>
      </AppBar>

      <Box
        component="nav"
        sx={{ width: { sm: layout.drawerWidth }, flexShrink: { sm: 0 } }}
      >
        <Drawer
          variant="permanent"
          sx={{
            display: { xs: 'none', sm: 'block' },
            '& .MuiDrawer-paper': {
              boxSizing: 'border-box',
              width: layout.drawerWidth,
            },
          }}
          open
        >
          {drawer}
        </Drawer>
      </Box>

      <Box
        component="main"
        sx={{
          flexGrow: 1,
          width: { sm: `calc(100% - ${layout.drawerWidth}px)` },
          mt: 8,
          minWidth: 0,
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {sessionExpiredMessage && (
          <Alert
            severity="warning"
            sx={{ mx: { xs: 2, sm: 3 }, mt: 2 }}
            action={
              <Button
                color="inherit"
                size="small"
                onClick={() => {
                  clearSessionExpired();
                  navigate('/broker-connections');
                }}
              >
                Reconnect
              </Button>
            }
          >
            Trading session expired. Reconnect your broker session before placing orders.
          </Alert>
        )}

        {!isBrokerAccountsPage && sessionStatus === 'ERROR' && sessionMessage && (
          <Alert
            severity={brokerConnected ? 'warning' : 'info'}
            sx={{ mx: { xs: 2, sm: 3 }, mt: 2 }}
            action={
              <Button
                color="inherit"
                size="small"
                onClick={() => {
                  if (brokerConnected) {
                    void retrySession();
                  } else {
                    navigate('/broker-connections');
                  }
                }}
              >
                {brokerConnected ? 'Retry' : 'Connect Broker'}
              </Button>
            }
          >
            {sessionMessage}
          </Alert>
        )}

        <ResponsivePageContainer>{children}</ResponsivePageContainer>
      </Box>

      <MobileNavigation onHelp={() => setHelpOpen(true)} />
      <JobMonitor />
      <AIFloatingButton onClick={() => setAiPanelOpen(true)} />
      <AIChatPanel
        open={aiPanelOpen}
        onClose={() => setAiPanelOpen(false)}
        pageContext={{ page: location.pathname }}
      />
      <HelpPanel open={helpOpen} onClose={() => setHelpOpen(false)} helpId="app" />
    </Box>
  );
}
