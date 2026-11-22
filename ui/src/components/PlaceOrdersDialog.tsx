import React, { useEffect, useMemo, useState } from 'react';
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  DialogActions,
  DialogContent,
  DialogTitle,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
  useMediaQuery,
  useTheme,
} from '@mui/material';
import {
  CheckCircle as CheckIcon,
  Error as ErrorIcon,
  SkipNext as SkipIcon,
} from '@mui/icons-material';
import { NormalizedCandidate, PlaceOrderResult } from '../types';
import { ResponsiveDialog } from './ResponsiveDialog';
import {
  candidateStrategyColor,
  candidateStrategyLabel,
  fmtCurrency,
  getActualOrderValue,
  getLevelLabel,
} from './candidates/candidateDisplay';

// Keep the desktop table labels/colors identical to the previous implementation.
const strategyLabel = candidateStrategyLabel;
const strategyColor = candidateStrategyColor;

function fmt(value: number | null | undefined, decimals = 2): string {
  if (value == null) return '-';
  return value.toLocaleString('en-IN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
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

function MobileDetailRow({ label, value }: { label: string; value: string }) {
  return (
    <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 2, py: 0.45 }}>
      <Typography variant="body2" color="text.secondary" sx={{ flexShrink: 0 }}>
        {label}
      </Typography>
      <Typography variant="body2" fontWeight={700} sx={{ textAlign: 'right', minWidth: 0 }}>
        {value}
      </Typography>
    </Box>
  );
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
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const [confirmOpen, setConfirmOpen] = useState(false);
  const step = results ? 'results' : 'review';

  useEffect(() => {
    if (!open || results) setConfirmOpen(false);
  }, [open, results]);

  const reviewData = useMemo(() => {
    return candidates.filter(
      (c) => selected.includes(c.symbol) && c.is_selectable && c.side === 'BUY'
    );
  }, [candidates, selected]);

  const reviewSummary = useMemo(() => {
    const mleCount = reviewData.filter((c) => c.strategy_type === 'MULTI_LEVEL').length;
    const daCount = reviewData.filter((c) => c.strategy_type === 'DYNAMIC_AVERAGING').length;
    const totalCapital = reviewData.reduce((sum, c) => sum + getActualOrderValue(c), 0);
    return { mleCount, daCount, totalCapital };
  }, [reviewData]);

  const resultSummary = useMemo(() => {
    if (!results) return null;
    const successful = results.filter((r) => r.status === 'Success').length;
    const failed = results.filter((r) => r.status === 'Fail').length;
    const skipped = Math.max(results.length - successful - failed, 0);
    const capitalSubmitted = results
      .filter((r) => r.status === 'Success')
      .reduce((sum, r) => sum + r.amount, 0);
    return { successful, failed, skipped, capitalSubmitted };
  }, [results]);

  const handleReviewPlace = () => {
    if (placing || reviewData.length === 0) return;
    if (isMobile) {
      setConfirmOpen(true);
    } else {
      onConfirm();
    }
  };

  const handleConfirmedPlace = () => {
    if (placing) return;
    setConfirmOpen(false);
    onConfirm();
  };

  const handleDialogClose = () => {
    if (placing) return;
    setConfirmOpen(false);
    onClose();
  };

  const renderMobileReview = () => (
    <>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
        Review {reviewData.length} order(s) before placing:
      </Typography>
      <Box
        sx={{
          display: 'flex',
          gap: 1,
          flexWrap: 'wrap',
          mb: 2,
        }}
      >
        <Chip label={`${reviewData.length} Orders`} size="small" />
        <Chip label={`${reviewSummary.mleCount} MLE`} size="small" color="primary" variant="outlined" />
        <Chip label={`${reviewSummary.daCount} DA`} size="small" color="secondary" variant="outlined" />
        <Chip
          label={`Total ${fmtCurrency(reviewSummary.totalCapital)}`}
          size="small"
          color="success"
          variant="outlined"
        />
      </Box>

      {reviewData.map((candidate) => (
        <Box
          key={`${candidate.symbol}-${candidate.strategy_type}-${candidate.level_or_leg}`}
          sx={{ border: 1, borderColor: 'divider', borderRadius: 1, p: 1.5, mb: 1.5 }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
            <Typography variant="subtitle1" fontWeight={800}>
              {candidate.symbol}
            </Typography>
            <Chip
              label={candidateStrategyLabel[candidate.strategy_type] ?? candidate.strategy_type}
              size="small"
              color={candidateStrategyColor[candidate.strategy_type] ?? 'default'}
              variant="outlined"
            />
            <Typography variant="caption" color="text.secondary">
              {getLevelLabel(candidate)}
            </Typography>
          </Box>
          <Box sx={{ mt: 1 }}>
            <MobileDetailRow label="Quantity" value={fmt(candidate.qty, 0)} />
            <MobileDetailRow label="Trigger Price" value={fmtCurrency(candidate.trigger_price)} />
            <MobileDetailRow label="Order Price" value={fmtCurrency(candidate.order_price)} />
            <MobileDetailRow
              label="Order Value"
              value={fmtCurrency(getActualOrderValue(candidate))}
            />
          </Box>
        </Box>
      ))}
    </>
  );

  const renderMobileResults = () => (
    <>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
        Order Placement Results
      </Typography>
      <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 2 }}>
        <Chip label={`${results!.length} Orders Selected`} size="small" />
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
        {resultSummary!.skipped > 0 && (
          <Chip
            label={`${resultSummary!.skipped} Skipped`}
            size="small"
            color="default"
            variant="outlined"
          />
        )}
      </Box>

      {results!.map((result) => {
        const isSuccess = result.status === 'Success';
        const isFailed = result.status === 'Fail';
        const statusLabel = isSuccess
          ? 'SUCCESS'
          : isFailed
            ? 'FAILED'
            : (result.status || 'SKIPPED').toUpperCase();
        return (
          <Box
            key={`${result.symbol}-${result.strategy_type}`}
            sx={{ border: 1, borderColor: 'divider', borderRadius: 1, p: 1.5, mb: 1.5 }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
              <Typography variant="subtitle1" fontWeight={800}>
                {result.symbol}
              </Typography>
              <Chip
                label={candidateStrategyLabel[result.strategy_type] ?? result.strategy_type}
                size="small"
                color={candidateStrategyColor[result.strategy_type] ?? 'default'}
                variant="outlined"
              />
              <Chip
                label={statusLabel}
                size="small"
                color={isSuccess ? 'success' : isFailed ? 'error' : 'default'}
              />
            </Box>
            <Box sx={{ mt: 1 }}>
              <MobileDetailRow label="Quantity" value={fmt(result.qty, 0)} />
              <MobileDetailRow label="Trigger Price" value={fmtCurrency(result.trigger_price)} />
              <MobileDetailRow label="Order Price" value={fmtCurrency(result.order_price)} />
              <MobileDetailRow label="Amount" value={fmtCurrency(result.amount)} />
            </Box>
            <Typography
              variant="body2"
              color={isFailed ? 'error' : 'text.secondary'}
              sx={{ mt: 1, whiteSpace: 'normal', wordBreak: 'break-word' }}
            >
              {result.remarks || result.status}
            </Typography>
          </Box>
        );
      })}
    </>
  );

  return (
    <>
      <ResponsiveDialog
        open={open}
        onClose={handleDialogClose}
        maxWidth="md"
        fullWidth
        PaperProps={{ sx: { m: { sm: 2 } } }}
      >
        <DialogTitle>{step === 'review' ? 'Review Orders' : 'Placement Results'}</DialogTitle>
        <DialogContent dividers>
          {isMobile ? (
            step === 'review' ? renderMobileReview() : renderMobileResults()
          ) : step === 'review' ? (
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
                            {r.status === 'Success' ? 'Placed' : r.remarks || r.status}
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
        <DialogActions
          sx={{
            position: { xs: 'sticky', sm: 'static' },
            bottom: 0,
            bgcolor: 'background.paper',
            borderTop: '1px solid',
            borderColor: 'divider',
            p: 1.5,
          }}
        >
          {step === 'review' ? (
            <>
              <Button onClick={handleDialogClose} disabled={placing}>
                Cancel
              </Button>
              <Button
                onClick={handleReviewPlace}
                variant="contained"
                color="success"
                disabled={placing || reviewData.length === 0}
                startIcon={placing ? <CircularProgress size={16} /> : undefined}
              >
                {placing ? 'Placing...' : 'Place Orders'}
              </Button>
            </>
          ) : (
            <Button onClick={handleDialogClose} variant="contained" autoFocus>
              Close
            </Button>
          )}
        </DialogActions>
      </ResponsiveDialog>

      <ResponsiveDialog
        open={confirmOpen && isMobile}
        onClose={placing ? undefined : () => setConfirmOpen(false)}
        fullScreenOnMobile={false}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle>Confirm Order Placement</DialogTitle>
        <DialogContent dividers>
          <Typography variant="body1" sx={{ mb: 1 }}>
            Place {reviewData.length} order(s) with your broker?
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Total capital required: {fmtCurrency(reviewSummary.totalCapital)}
          </Typography>
          <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1.5 }}>
            This action creates GTT orders. Failed orders will be reported and will not be retried
            automatically.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmOpen(false)} disabled={placing}>
            Cancel
          </Button>
          <Button
            onClick={handleConfirmedPlace}
            variant="contained"
            color="success"
            disabled={placing}
            startIcon={placing ? <CircularProgress size={16} /> : undefined}
          >
            {placing ? 'Placing...' : 'Confirm Place Orders'}
          </Button>
        </DialogActions>
      </ResponsiveDialog>
    </>
  );
}