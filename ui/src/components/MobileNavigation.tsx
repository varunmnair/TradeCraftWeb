import { useState } from 'react';
import type { MouseEvent } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  BottomNavigation,
  BottomNavigationAction,
  Box,
  Divider,
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
} from '@mui/material';
import {
  AccountBalance as BrokerIcon,
  AdminPanelSettings as AdminIcon,
  Assessment as HoldingsIcon,
  Assignment as PlanIcon,
  Checklist as EntriesIcon,
  Dashboard as HomeIcon,
  Help as HelpIcon,
  MoreHoriz as MoreIcon,
  ShoppingCart as OrdersIcon,
  Work as JobsIcon,
} from '@mui/icons-material';
import { useAuth } from '../context/AuthContext';
import { layout, overlayZIndex } from '../theme';

interface MobileNavigationProps {
  onHelp: () => void;
}

const primaryItems = [
  { label: 'Home', path: '/dashboard', icon: <HomeIcon /> },
  { label: 'Holdings', path: '/holdings', icon: <HoldingsIcon /> },
  { label: 'Entries', path: '/entry-candidates', icon: <EntriesIcon /> },
  { label: 'Orders', path: '/gtt', icon: <OrdersIcon /> },
];

export function MobileNavigation({ onHelp }: MobileNavigationProps) {
  const [moreAnchorEl, setMoreAnchorEl] = useState<HTMLElement | null>(null);
  const { user } = useAuth();
  const { pathname } = useLocation();
  const navigate = useNavigate();

  const isActive = (path: string) =>
    pathname === path || pathname.startsWith(`${path}/`);

  const primaryIndex = primaryItems.findIndex((item) => isActive(item.path));
  const selected = primaryIndex >= 0 ? primaryIndex : primaryItems.length;
  const isAdmin = user?.role === 'admin';

  const handleOpenMore = (event: MouseEvent<HTMLElement>) => {
    setMoreAnchorEl(event.currentTarget);
  };

  const handleCloseMore = () => {
    setMoreAnchorEl(null);
  };

  const handleNavigate = (path: string) => {
    navigate(path);
    handleCloseMore();
  };

  const handleHelp = () => {
    onHelp();
    handleCloseMore();
  };

  return (
    <Box
      sx={{
        display: { xs: 'block', sm: 'none' },
        position: 'fixed',
        bottom: 0,
        left: 0,
        right: 0,
        zIndex: overlayZIndex.bottomNavigation,
        bgcolor: 'background.paper',
        borderTop: 1,
        borderColor: 'divider',
        pb: layout.safeAreaBottom,
      }}
    >
      <BottomNavigation
        value={selected}
        showLabels
        onChange={(_, value: number) => {
          if (value < primaryItems.length) {
            navigate(primaryItems[value].path);
          }
        }}
        sx={{
          height: layout.mobileNavHeight,
          bgcolor: 'transparent',
          '& .MuiBottomNavigationAction-root': {
            minWidth: 0,
            maxWidth: 'none',
            px: 0.5,
            py: 0.5,
          },
        }}
      >
        {primaryItems.map((item) => (
          <BottomNavigationAction
            key={item.path}
            label={item.label}
            icon={item.icon}
          />
        ))}
        <BottomNavigationAction
          label="More"
          icon={<MoreIcon />}
          onClick={handleOpenMore}
        />
      </BottomNavigation>

      <Menu
        anchorEl={moreAnchorEl}
        open={Boolean(moreAnchorEl)}
        onClose={handleCloseMore}
        anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
        transformOrigin={{ vertical: 'bottom', horizontal: 'center' }}
        PaperProps={{ sx: { minWidth: 210, mb: 1 } }}
      >
        <MenuItem onClick={() => handleNavigate('/entry-strategies')}>
          <ListItemIcon>
            <PlanIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText primary="Entry Strategies" />
        </MenuItem>
        <MenuItem onClick={() => handleNavigate('/broker-connections')}>
          <ListItemIcon>
            <BrokerIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText primary="Broker Accounts" />
        </MenuItem>
        <MenuItem onClick={() => handleNavigate('/jobs')}>
          <ListItemIcon>
            <JobsIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText primary="Jobs" />
        </MenuItem>
        <Divider />
        <MenuItem onClick={handleHelp}>
          <ListItemIcon>
            <HelpIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText primary="Help" />
        </MenuItem>
        {isAdmin && (
          <MenuItem onClick={() => handleNavigate('/admin')}>
            <ListItemIcon>
              <AdminIcon fontSize="small" />
            </ListItemIcon>
            <ListItemText primary="Administration" />
          </MenuItem>
        )}
      </Menu>
    </Box>
  );
}
