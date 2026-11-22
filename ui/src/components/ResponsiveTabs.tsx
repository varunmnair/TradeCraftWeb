import { Tabs, useMediaQuery, useTheme } from '@mui/material';
import type { TabsProps } from '@mui/material/Tabs';

/** Standard tabs on desktop/laptop, scrollable tabs on mobile. */
export function ResponsiveTabs(props: TabsProps) {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

  return (
    <Tabs
      variant={isMobile ? 'scrollable' : 'standard'}
      scrollButtons={isMobile ? 'auto' : false}
      {...props}
    />
  );
}
