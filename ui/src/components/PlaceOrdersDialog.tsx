import React, { useMemo } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Box,
  Chip,
  CircularProgress,
} from '@mui/material';
import {
  CheckCircle as CheckIcon,
  Error as ErrorIcon,
  SkipNext as SkipIcon,
} from '@mui/icons-material';
import { NormalizedCandidate, PlaceOrderResult } from '../types';

const strategyLabel: Record<string, string> = {
  MULTI_LEVEL: 'MLE',
  DYNAMIC_AVERAGING: 'DA',
  SIP: 'SIP',
};

const strategyColor: Record<string, 'primary' | 'secondary' | 'default'> = {
  MULTI_LEVEL: 'primary',
  DYNAMIC_AVERAGING: 'secondary',
  SIP: 'default',
};

function fmt(value: number | null | undefined, decimals = 2): string {
  if (value == null) return '—';
  return value.toLocaleString('en-IN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

function fmtCurrency(value: number | null | undefined): string {
  if (value == null) return '—';
  return `₹${fmt(value, 0)}`;
}

interface PlaceOrdersDialogProps {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  candidates: NormalizedCandidate[];
  selected: string[];
  results: PlaceOrderResult[] | null;
  placing: boolean;
}

export default function PlaceOrdersDialog({
  open,
  onClose,
  onConfirm,
  candidates,
  selected,
  results,
  placing,
}: PlaceOrdersDialogProps) {
  const step = results ? 'results' : 'review';

  const reviewData = useMemo(() => {
    return candidates.filter(
      (c) => selected.includes(c.symbol) && c.is_selectable && c.side === 'BUY'
    );
  }, [candidates, selected]);

  const reviewSummary = useMemo(() => {
    const mleCount = reviewData.filter((c) => c.strategy_type === 'MULTI_LEVEL').length;
    const daCount = reviewData.filter((c) => c.strategy_type === 'DYNAMIC_AVERAGING').length;
    const totalCapital = reviewData.reduce((sum, c) => sum + (c.amount || 0), 0);
    return { mleCount, daCount, totalCapital };
  }, [reviewData]);

  const resultSummary = useMemo(() => {
    if (!results) return null;
    const successful = results.filter((r) => r.status === 'Success').length;
    const failed = results.filter((r) => r.status === 'Fail').length;
    const capitalSubmitted = results
      .filter((r) => r.status === 'Success')
      .reduce((sum, r) => sum + r.amount, 0);
    return { successful, failed, capitalSubmitted };
  }, [results]);

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>
        {step === 'review' ? 'Review Orders' : 'Placement Results'}
      </DialogTitle>
      <DialogContent dividers>
        {step === 'review' ? (
          <>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Review {reviewData.length} order(s) before placing:
            </Typography>
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Symbol</TableCell>
                    <TableCell>Strategy</TableCell>
                    <TableCell align="right">Qty</TableCell>
                    <TableCell align="right">Order Price</TableCell>
                    <TableCell align="right">Trigger Price</TableCell>
                    <TableCell align="right">Amount</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {reviewData.map((c) => (
                    <TableRow key={c.symbol}>
                      <TableCell>
                        <Typography variant="body2" fontWeight={600}>
                          {c.symbol}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={strategyLabel[c.strategy_type] ?? c.strategy_type}
                          size="small"
                          color={strategyColor[c.strategy_type] ?? 'default'}
                          variant="outlined"
                        />
                      </TableCell>
                      <TableCell align="right">{c.qty}</TableCell>
                      <TableCell align="right">{fmtCurrency(c.order_price)}</TableCell>
                      <TableCell align="right">{fmtCurrency(c.trigger_price)}</TableCell>
                      <TableCell align="right">
                        <Typography fontWeight={600}>{fmtCurrency(c.amount)}</Typography>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
            <Box
              sx={{
                mt: 2,
                display: 'flex',
                gap: 2,
                alignItems: 'center',
                flexWrap: 'wrap',
              }}
            >
              <Chip label={`${reviewData.length} Orders`} size="small" />
              {reviewSummary.mleCount > 0 && (
                <Chip
                  label={`${reviewSummary.mleCount} MLE`}
                  size="small"
                  color="primary"
                  variant="outlined"
                />
              )}
              {reviewSummary.daCount > 0 && (
                <Chip
                  label={`${reviewSummary.daCount} DA`}
                  size="small"
                  color="secondary"
                  variant="outlined"
                />
              )}
              <Box sx={{ flex: 1 }} />
              <Typography variant="body2" color="text.secondary">
                Total capital:{' '}
                <Typography component="span" variant="body2" fontWeight={700}>
                  {fmtCurrency(reviewSummary.totalCapital)}
                </Typography>
              </Typography>
            </Box>
          </>
        ) : (
          <>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Placement results:
            </Typography>
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell width={48} />
                    <TableCell>Symbol</TableCell>
                    <TableCell align="right">Qty</TableCell>
                    <TableCell align="right">Trigger Price</TableCell>
                    <TableCell align="right">Order Price</TableCell>
                    <TableCell>Remarks</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {results!.map((r) => (
                    <TableRow key={r.symbol}>
                      <TableCell>
                        {r.status === 'Success' ? (
                          <CheckIcon fontSize="small" color="success" />
                        ) : r.status === 'Fail' ? (
                          <ErrorIcon fontSize="small" color="error" />
                        ) : (
                          <SkipIcon fontSize="small" color="disabled" />
                        )}
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" fontWeight={600}>
                          {r.symbol}
                        </Typography>
                        <Chip
                          label={strategyLabel[r.strategy_type] ?? r.strategy_type}
                          size="small"
                          color={strategyColor[r.strategy_type] ?? 'default'}
                          variant="outlined"
                          sx={{ mt: 0.5 }}
                        />
                      </TableCell>
                      <TableCell align="right">{r.qty}</TableCell>
                      <TableCell align="right">{fmtCurrency(r.trigger_price)}</TableCell>
                      <TableCell align="right">{fmtCurrency(r.order_price)}</TableCell>
                      <TableCell>
                        <Typography
                          variant="body2"
                          color={r.status === 'Fail' ? 'error' : 'text.secondary'}
                        >
                          {r.status === 'Success'
                            ? 'Placed'
                            : r.remarks || r.status}
                        </Typography>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
            <Box
              sx={{
                mt: 2,
                display: 'flex',
                gap: 2,
                alignItems: 'center',
                flexWrap: 'wrap',
              }}
            >
              <Chip label={`${results!.length} Selected`} size="small" />
              <Chip
                label={`${resultSummary!.successful} Successful`}
                size="small"
                color="success"
                variant="outlined"
              />
              {resultSummary!.failed > 0 && (
                <Chip
                  label={`${resultSummary!.failed} Failed`}
                  size="small"
                  color="error"
                  variant="outlined"
                />
              )}
              <Box sx={{ flex: 1 }} />
              <Typography variant="body2" color="text.secondary">
                Capital submitted:{' '}
                <Typography component="span" variant="body2" fontWeight={700}>
                  {fmtCurrency(resultSummary!.capitalSubmitted)}
                </Typography>
              </Typography>
            </Box>
          </>
        )}
      </DialogContent>
      <DialogActions>
        {step === 'review' ? (
          <>
            <Button onClick={onClose} disabled={placing}>
              Cancel
            </Button>
            <Button
              onClick={onConfirm}
              variant="contained"
              color="success"
              disabled={placing || reviewData.length === 0}
              startIcon={placing ? <CircularProgress size={16} /> : undefined}
            >
              {placing ? 'Placing...' : 'Place Orders'}
            </Button>
          </>
        ) : (
          <Button onClick={onClose} variant="contained" autoFocus>
            Close
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
}
