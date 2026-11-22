import { createTheme } from '@mui/material/styles';

/**
 * Shared layout and overlay values for the application shell.
 * These use MUI's default breakpoints (sm = 600px) and preserve the
 * existing desktop geometry.
 */
export const layout = {
  drawerWidth: 240,
  mobileNavHeight: 56,
  safeAreaBottom: 'env(safe-area-inset-bottom, 0px)',
  contentPadding: { xs: 2, sm: 3 },
} as const;

export const mobileBottomSpacing = {
  nav: `calc(${layout.mobileNavHeight}px + ${layout.safeAreaBottom})`,
  content: `calc(${layout.mobileNavHeight}px + 16px + ${layout.safeAreaBottom})`,
  fab: `calc(${layout.mobileNavHeight}px + 68px + ${layout.safeAreaBottom})`,
} as const;

/** Stacking order for shell overlays. Dialogs (MUI zIndex 1300+) stay above. */
export const overlayZIndex = {
  bottomNavigation: 1200,
  aiFab: 1210,
  jobMonitor: 1220,
  aiDrawer: 1300,
} as const;

/** Colors already used by the shell, centralized without changing values. */
export const appColors = {
  onPrimary: '#ffffff',
  jobRunning: '#e3f2fd',
  jobIdle: '#f5f5f5',
  jobFailed: '#ffebee',
  jobSuccess: '#e8f5e9',
} as const;

const fontFamily = '"Roboto", "Helvetica", "Arial", sans-serif';

export const appTypography = { fontFamily } as const;

export const theme = createTheme({
  palette: {
    mode: 'light',
  },
  typography: {
    fontFamily,
  },
  breakpoints: {
    values: { xs: 0, sm: 600, md: 900, lg: 1200, xl: 1536 },
  },
  spacing: 8,
});
