import { MoreVert as MoreVertIcon } from '@mui/icons-material';
import {
  Box,
  Chip,
  IconButton,
  Menu,
  MenuItem,
  Tooltip,
  Typography,
  useMediaQuery,
  useTheme,
} from '@mui/material';
import type { SxProps, Theme } from '@mui/material/styles';
import { useState, type MouseEvent, type ReactNode } from 'react';

export interface PageHeaderAction {
  label: string;
  onClick: () => void;
  icon?: ReactNode;
  disabled?: boolean;
  color?: 'inherit' | 'primary' | 'secondary' | 'success' | 'error' | 'info' | 'warning';
}

interface ResponsivePageHeaderProps {
  title: ReactNode;
  description?: ReactNode;
  /** Optional record/count indicator shown beside the title. */
  recordCount?: ReactNode;
  /** Primary page action. Rendered prominently in the header. */
  primaryAction?: ReactNode;
  /** Secondary actions. On compact layouts, these collapse into an overflow menu. */
  secondaryActions?: PageHeaderAction[];
  /** Backward-compatible action slot. Prefer primaryAction/secondaryActions for new pages. */
  actions?: ReactNode;
  sx?: SxProps<Theme>;
}

/** Page heading with actions that stack on mobile and sit inline on desktop. */
export function ResponsivePageHeader({
  title,
  description,
  recordCount,
  primaryAction,
  secondaryActions = [],
  actions,
  sx,
}: ResponsivePageHeaderProps) {
  const theme = useTheme();
  const compact = useMediaQuery(theme.breakpoints.down('sm'));
  const [menuAnchor, setMenuAnchor] = useState<HTMLElement | null>(null);

  const hasStructuredActions = Boolean(primaryAction) || secondaryActions.length > 0;
  const inlineSecondary = compact
    ? []
    : secondaryActions.filter((action) => Boolean(action.icon));
  const overflowSecondary = compact
    ? secondaryActions
    : secondaryActions.filter((action) => !action.icon);
  const showOverflow = overflowSecondary.length > 0;

  const handleMenuOpen = (event: MouseEvent<HTMLElement>) => setMenuAnchor(event.currentTarget);
  const handleMenuClose = () => setMenuAnchor(null);

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: { xs: 'column', sm: 'row' },
        alignItems: { xs: 'stretch', sm: 'flex-start' },
        justifyContent: 'space-between',
        gap: { xs: 1.5, sm: 2 },
        mb: 2,
        ...sx,
      }}
    >
      <Box sx={{ minWidth: 0, flex: 1 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, minWidth: 0 }}>
          <Typography
            variant="h5"
            component="h1"
            noWrap
            sx={{ minWidth: 0, fontSize: { xs: '1.25rem', sm: '1.5rem' } }}
          >
            {title}
          </Typography>
          {recordCount !== undefined && recordCount !== null && recordCount !== '' ? (
            <Chip
              label={recordCount}
              size="small"
              variant="outlined"
              sx={{ flexShrink: 0, maxWidth: '100%' }}
            />
          ) : null}
        </Box>
        {description && (
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
            {description}
          </Typography>
        )}
      </Box>

      {(hasStructuredActions || actions) && (
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 1,
            flexWrap: 'wrap',
            justifyContent: { xs: 'flex-start', sm: 'flex-end' },
            minWidth: 0,
          }}
        >
          {primaryAction}
          {!compact &&
            inlineSecondary.map((action) => (
              <Tooltip key={action.label} title={action.label}>
                <span>
                  <IconButton
                    aria-label={action.label}
                    onClick={action.onClick}
                    disabled={action.disabled}
                    color={action.color}
                    size="small"
                    sx={{ minWidth: 44, minHeight: 44 }}
                  >
                    {action.icon}
                  </IconButton>
                </span>
              </Tooltip>
            ))}
          {actions}
          {showOverflow && (
            <>
              <IconButton
                aria-label="More actions"
                onClick={handleMenuOpen}
                size="small"
                sx={{ minWidth: 44, minHeight: 44 }}
              >
                <MoreVertIcon />
              </IconButton>
              <Menu
                anchorEl={menuAnchor}
                open={Boolean(menuAnchor)}
                onClose={handleMenuClose}
                anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
                transformOrigin={{ vertical: 'top', horizontal: 'right' }}
              >
                {overflowSecondary.map((action) => (
                  <MenuItem
                    key={action.label}
                    disabled={action.disabled}
                    onClick={() => {
                      handleMenuClose();
                      action.onClick();
                    }}
                  >
                    {action.icon ? (
                      <Box component="span" sx={{ mr: 1, display: 'inline-flex' }}>
                        {action.icon}
                      </Box>
                    ) : null}
                    {action.label}
                  </MenuItem>
                ))}
              </Menu>
            </>
          )}
        </Box>
      )}
    </Box>
  );
}
