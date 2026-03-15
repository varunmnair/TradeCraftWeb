import React, { useState, useMemo } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Box,
  Typography,
} from '@mui/material';
import { Search as SearchIcon } from '@mui/icons-material';

export interface SkippedItem {
  symbol?: string;
  Symbol?: string;
  skip_reason?: string;
  reason?: string;
  [key: string]: unknown;
}

interface SkippedItemsDialogProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  items: SkippedItem[];
}

export function SkippedItemsDialog({
  open,
  onClose,
  title = 'Skipped Items',
  items,
}: SkippedItemsDialogProps) {
  const [searchText, setSearchText] = useState('');

  const filteredItems = useMemo(() => {
    if (!searchText.trim()) return items;
    const lower = searchText.toLowerCase();
    return items.filter((item) => {
      const symbol = item.symbol || item.Symbol || '';
      const reason = item.skip_reason || item.reason || '';
      return (
        symbol.toLowerCase().includes(lower) ||
        reason.toLowerCase().includes(lower)
      );
    });
  }, [items, searchText]);

  const getSymbol = (item: SkippedItem) => item.symbol || item.Symbol || '-';
  const getReason = (item: SkippedItem) => item.skip_reason || item.reason || 'Unknown';

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>{title}</DialogTitle>
      <DialogContent>
        <Box sx={{ mb: 2 }}>
          <TextField
            size="small"
            placeholder="Search by symbol or reason..."
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            InputProps={{
              startAdornment: (
                <SearchIcon color="action" sx={{ mr: 1 }} />
              ),
            }}
            sx={{ width: 300 }}
          />
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
            Showing {filteredItems.length} of {items.length} items
          </Typography>
        </Box>

        {filteredItems.length > 0 ? (
          <TableContainer component={Paper} variant="outlined">
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell sx={{ fontWeight: 'bold' }}>Symbol</TableCell>
                  <TableCell sx={{ fontWeight: 'bold' }}>Reason</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {filteredItems.map((item, idx) => (
                  <TableRow key={idx}>
                    <TableCell>{getSymbol(item)}</TableCell>
                    <TableCell>{getReason(item)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        ) : (
          <Typography color="text.secondary">No items to display</Typography>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
}
