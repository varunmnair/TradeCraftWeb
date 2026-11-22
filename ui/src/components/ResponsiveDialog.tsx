import { Dialog, useMediaQuery, useTheme } from '@mui/material';
import type { DialogProps } from '@mui/material/Dialog';
import type { SxProps, Theme } from '@mui/material/styles';

interface ResponsiveDialogProps extends Omit<DialogProps, 'fullScreen'> {
  /** Use a full-screen dialog below the sm breakpoint. Defaults to true. */
  fullScreenOnMobile?: boolean;
  paperSx?: SxProps<Theme>;
}

/** Standard modal on desktop/laptop, full-screen dialog on mobile. */
export function ResponsiveDialog({
  fullScreenOnMobile = true,
  paperSx,
  ...dialogProps
}: ResponsiveDialogProps) {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

  return (
    <Dialog
      {...dialogProps}
      fullScreen={fullScreenOnMobile && isMobile}
      PaperProps={{ ...dialogProps.PaperProps, sx: paperSx }}
    />
  );
}
