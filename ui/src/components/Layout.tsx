import React, { useState, ReactNode } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  AppBar,
  Box,
  Drawer,
  IconButton,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Toolbar,
  Typography,
  Divider,
  Tooltip,
  Chip,
} from '@mui/material';
import {
  Menu as MenuIcon,
  Dashboard as DashboardIcon,
  AccountBalance as BrokerIcon,
  PlayCircle as SessionIcon,
  Assessment as HoldingsIcon,
  Assignment as PlanIcon,
  ShoppingCart as BuyIcon,
  Notifications as GttIcon,
  Work as JobsIcon,
  Logout as LogoutIcon,
  Help as HelpIcon,
  PowerSettingsNew as PowerIcon,
} from '@mui/icons-material';
import { useAuth } from '../context/AuthContext';
import { useSession } from '../context/SessionContext';
import { JobMonitor } from './JobMonitor';
import { AIChatPanel, AIFloatingButton } from './AIChatPanel';
import { HelpPanel } from './HelpPanel';

const DRAWER_WIDTH = 240;

interface LayoutProps {
  children: ReactNode;
}

const navItems = [
  { text: 'Dashboard', icon: <DashboardIcon />, path: '/dashboard' },
  { text: 'Brokers', icon: <BrokerIcon />, path: '/broker-connections' },
  { text: 'Sessions', icon: <SessionIcon />, path: '/sessions' },
  { text: 'Holdings', icon: <HoldingsIcon />, path: '/holdings' },
  { text: 'Entry Plans', icon: <BuyIcon />, path: '/entries' },
  { text: 'Entry Strategies', icon: <PlanIcon />, path: '/entry-strategies' },
  { text: 'Buy Orders', icon: <GttIcon />, path: '/gtt' },
  { text: 'Jobs', icon: <JobsIcon />, path: '/jobs' },
];

export default function Layout({ children }: LayoutProps) {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [aiPanelOpen, setAiPanelOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const { user, logout } = useAuth();
  const { sessionInfo } = useSession();
  const navigate = useNavigate();
  const location = useLocation();

  const handleDrawerToggle = () => {
    setDrawerOpen(!drawerOpen);
  };

  const handleNavigation = (path: string) => {
    navigate(path);
    setDrawerOpen(false);
  };

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const drawer = (
    <Box sx={{ width: DRAWER_WIDTH }}>
      <Toolbar>
        <Typography variant="h6" noWrap component="div">
          TradeCraftX
        </Typography>
      </Toolbar>
      <Divider />
      <List>
        {navItems.map((item) => (
          <ListItem key={item.text} disablePadding>
            <ListItemButton
              selected={location.pathname === item.path}
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

  return (
    <Box sx={{ display: 'flex' }}>
      <AppBar
        position="fixed"
        sx={{
          zIndex: (theme) => theme.zIndex.drawer + 1,
        }}
      >
        <Toolbar>
          <IconButton
            color="inherit"
            edge="start"
            onClick={handleDrawerToggle}
            sx={{ mr: 2, display: { sm: 'none' } }}
          >
            <MenuIcon />
          </IconButton>
          <Typography variant="h6" noWrap component="div" sx={{ flexGrow: 1 }}>
            TradeCraftX
          </Typography>
          {user && (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              {import.meta.env.VITE_DEMO_MODE === 'true' && (
                <Chip 
                  label="Demo Mode" 
                  size="small" 
                  color="warning"
                  sx={{ mr: 1 }}
                />
              )}
              {sessionInfo && (
                <Chip 
                  label={`${sessionInfo.broker.toUpperCase()} - ${sessionInfo.user_id}`} 
                  size="small" 
                  variant="outlined"
                  sx={{ mr: 1, color: 'white', borderColor: 'white' }}
                />
              )}
              <Tooltip title="Help">
                <IconButton color="inherit" onClick={() => setHelpOpen(true)}>
                  <HelpIcon />
                </IconButton>
              </Tooltip>
              <Typography variant="body2" sx={{ mr: 1 }}>
                {user.email}
              </Typography>
              <Tooltip title="Logout">
                <IconButton color="inherit" onClick={handleLogout} size="small">
                  <PowerIcon />
                </IconButton>
              </Tooltip>
            </Box>
          )}
        </Toolbar>
      </AppBar>
      <Box
        component="nav"
        sx={{ width: { sm: DRAWER_WIDTH }, flexShrink: { sm: 0 } }}
      >
        <Drawer
          variant="temporary"
          open={drawerOpen}
          onClose={handleDrawerToggle}
          ModalProps={{ keepMounted: true }}
          sx={{
            display: { xs: 'block', sm: 'none' },
            '& .MuiDrawer-paper': {
              boxSizing: 'border-box',
              width: DRAWER_WIDTH,
            },
          }}
        >
          {drawer}
        </Drawer>
        <Drawer
          variant="permanent"
          sx={{
            display: { xs: 'none', sm: 'block' },
            '& .MuiDrawer-paper': {
              boxSizing: 'border-box',
              width: DRAWER_WIDTH,
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
          p: 3,
          width: { sm: `calc(100% - ${DRAWER_WIDTH}px)` },
          mt: 8,
          mb: 10,
        }}
      >
        {children}
      </Box>
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
