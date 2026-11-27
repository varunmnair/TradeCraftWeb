import { alpha, createTheme } from '@mui/material/styles';

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

/**
 * Phase 1 design tokens. Values preserve the existing MUI light/default visual
 * identity while giving shared components a single source of truth.
 */
export const designTokens = {
  color: {
    primary: '#1976d2',
    primaryLight: '#42a5f5',
    primaryDark: '#1565c0',
    secondary: '#9c27b0',
    success: '#2e7d32',
    warning: '#ed6c02',
    error: '#d32f2f',
    info: '#0288d1',
    neutral: '#616161',
    textPrimary: 'rgba(0, 0, 0, 0.87)',
    textSecondary: 'rgba(0, 0, 0, 0.6)',
    backgroundDefault: '#ffffff',
    backgroundPaper: '#ffffff',
    surfaceSubtle: '#f7f9fc',
    border: 'rgba(0, 0, 0, 0.12)',
  },
  typography: {
    fontFamily: '"Roboto", "Helvetica", "Arial", sans-serif',
    pageTitleSize: '1.5rem',
    pageTitleWeight: 500,
    sectionTitleSize: '1rem',
    bodySize: '0.875rem',
    captionSize: '0.75rem',
  },
  spacing: {
    pageGap: 16,
    sectionGap: 12,
    controlGap: 8,
  },
  radius: {
    surface: 8,
    control: 8,
    chip: 16,
  },
  control: {
    buttonMinHeight: 36,
    touchMinHeight: 44,
  },
  status: {
    success: { color: '#2e7d32', background: '#e8f5e9' },
    warning: { color: '#ed6c02', background: '#fff3e0' },
    error: { color: '#d32f2f', background: '#ffebee' },
    info: { color: '#0288d1', background: '#e3f2fd' },
    neutral: { color: '#616161', background: '#f5f5f5' },
  },
} as const;

/** Backward-compatible shell colors used by existing shell components. */
export const appColors = {
  onPrimary: '#ffffff',
  jobRunning: designTokens.status.info.background,
  jobIdle: designTokens.status.neutral.background,
  jobFailed: designTokens.status.error.background,
  jobSuccess: designTokens.status.success.background,
} as const;

export const appTypography = { fontFamily: designTokens.typography.fontFamily } as const;

export const theme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: designTokens.color.primary,
      light: designTokens.color.primaryLight,
      dark: designTokens.color.primaryDark,
      contrastText: '#ffffff',
    },
    secondary: {
      main: designTokens.color.secondary,
    },
    success: { main: designTokens.color.success },
    warning: { main: designTokens.color.warning },
    error: { main: designTokens.color.error },
    info: { main: designTokens.color.info },
    text: {
      primary: designTokens.color.textPrimary,
      secondary: designTokens.color.textSecondary,
    },
    background: {
      default: designTokens.color.backgroundDefault,
      paper: designTokens.color.backgroundPaper,
    },
    divider: designTokens.color.border,
  },
  typography: {
    fontFamily: designTokens.typography.fontFamily,
    h5: {
      fontSize: designTokens.typography.pageTitleSize,
      fontWeight: designTokens.typography.pageTitleWeight,
      lineHeight: 1.3,
    },
    body2: {
      fontSize: designTokens.typography.bodySize,
    },
    caption: {
      fontSize: designTokens.typography.captionSize,
    },
  },
  shape: {
    borderRadius: designTokens.radius.surface,
  },
  breakpoints: {
    values: { xs: 0, sm: 600, md: 900, lg: 1200, xl: 1536 },
  },
  spacing: 8,
  components: {
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: 'none',
        },
      },
    },
  },
});
