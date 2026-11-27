import { MoreVert as MoreVertIcon } from '@mui/icons-material';
import { Box, Button, IconButton, Menu, MenuItem, Paper, Typography } from '@mui/material';
import { useState, type MouseEvent } from 'react';
import type { TradeSelectionAction } from './types';

interface TradeSelectionToolbarProps {
  selectedIds: Array<string | number>;
  actions: TradeSelectionAction[];
  onClearSelection: () => void;
}

export function TradeSelectionToolbar({
  selectedIds,
  actions,
  onClearSelection,
}: TradeSelectionToolbarProps) {
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const count = selectedIds.length;
  if (count === 0) return null;

  const primary = actions.filter((a) => a.priority !== 'secondary');
  const secondary = actions.filter((a) => a.priority === 'secondary');

  const openMenu = (e: MouseEvent<HTMLElement>) => setAnchor(e.currentTarget);
  const closeMenu = () => setAnchor(null);

  return (
    <Paper
      variant="outlined"
      sx={{
        mb: 1.5,
        px: 1.5,
        py: 1,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 1,
        flexWrap: 'wrap',
      }}
    >
      <Typography variant="body2" sx={{ fontWeight: 600 }}>
        {count} selected
      </Typography>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
        {primary.map((action) => (
          <Button
            key={action.label}
            variant={action.variant ?? 'outlined'}
            color={action.color ?? 'primary'}
            size="small"
            startIcon={action.icon}
            disabled={action.disabled}
            onClick={() => action.onClick(selectedIds)}
          >
            {action.label}
          </Button>
        ))}
        {secondary.length > 0 ? (
          <>
            <IconButton aria-label="More selection actions" size="small" onClick={openMenu}>
              <MoreVertIcon />
            </IconButton>
            <Menu anchorEl={anchor} open={Boolean(anchor)} onClose={closeMenu}>
              {secondary.map((action) => (
                <MenuItem
                  key={action.label}
                  disabled={action.disabled}
                  onClick={() => {
                    closeMenu();
                    action.onClick(selectedIds);
                  }}
                >
                  {action.label}
                </MenuItem>
              ))}
            </Menu>
          </>
        ) : null}
        <Button size="small" color="inherit" onClick={onClearSelection}>
          Clear Selection
        </Button>
      </Box>
    </Paper>
  );
}