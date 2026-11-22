import React from 'react';
import { Box, Paper, Typography, LinearProgress, IconButton, Collapse, List, ListItem, ListItemText, ListItemSecondaryAction } from '@mui/material';
import { ExpandMore as ExpandMoreIcon, ExpandLess as ExpandLessIcon, Close as CloseIcon, ContentCopy as CopyIcon } from '@mui/icons-material';
import { useJobs } from '../context/JobsContext';
import { JobStatus } from '../types';
import { StatusChip } from './StatusChip';
import { appColors, mobileBottomSpacing, overlayZIndex } from '../theme';

interface JobMonitorProps {
  onJobClick?: (job: JobStatus) => void;
}

export function JobMonitor({ onJobClick }: JobMonitorProps) {
  const { activeJobs, untrackJob } = useJobs();
  const [expanded, setExpanded] = React.useState(true);

  const jobs = Array.from(activeJobs.values());
  const runningJobs = jobs.filter(j => j.status === 'pending' || j.status === 'running');
  const doneJobs = jobs.filter(j => j.status === 'completed' || j.status === 'succeeded' || j.status === 'failed');

  if (jobs.length === 0) return null;

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  return (
    <Paper 
      sx={{ 
        position: 'fixed',
        bottom: { xs: mobileBottomSpacing.nav, sm: 0 },
        left: 0,
        right: 0,
        zIndex: overlayZIndex.jobMonitor,
        maxHeight: expanded ? { xs: '45vh', sm: 400 } : 60,
        overflow: 'hidden',
        borderRadius: 0,
        boxShadow: 3,
      }}
    >
      {/* Header */}
      <Box 
        sx={{ 
          p: 1, 
          px: 2, 
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: { xs: 'wrap', sm: 'nowrap' },
          bgcolor: runningJobs.length > 0 ? appColors.jobRunning : appColors.jobIdle,
          cursor: 'pointer',
        }}
        onClick={() => setExpanded(!expanded)}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: { xs: 'wrap', sm: 'nowrap' }, minWidth: 0 }}>
          <Typography variant="subtitle2">
            {runningJobs.length > 0
              ? `Running Jobs (${runningJobs.length})`
              : `Jobs (${doneJobs.length} completed/failed)`
            }
          </Typography>
          {runningJobs.map(job => (
            <StatusChip
              key={job.id}
              status={job.status}
              label={`#${job.id}: ${job.job_type}`}
            />
          ))}
        </Box>
        {expanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
      </Box>

      {/* Job List */}
      <Collapse in={expanded}>
        <List dense sx={{ maxHeight: { xs: '30vh', sm: 300 }, overflow: 'auto', p: 0 }}>
          {jobs.map((job) => (
            <ListItem 
              key={job.id}
              sx={{ 
                borderBottom: '1px solid #eee',
                bgcolor: job.status === 'failed'
                  ? appColors.jobFailed
                  : (job.status === 'completed' || job.status === 'succeeded')
                    ? appColors.jobSuccess
                    : 'transparent'
              }}
              onClick={() => onJobClick?.(job)}
            >
              <ListItemText
                primary={
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <StatusChip status={job.status} />
                    <Typography variant="body2">
                      {job.job_type} (#{job.id})
                    </Typography>
                  </Box>
                }
                secondary={
                  <Box>
                    {job.status === 'running' && (
                      <LinearProgress 
                        variant="determinate" 
                        value={(job.progress || 0) * 100} 
                        sx={{ mb: 0.5 }}
                      />
                    )}
                    <Typography variant="caption" color="text.secondary">
                      {job.log && job.log.split('\n').slice(-2).join('\n')}
                    </Typography>
                  </Box>
                }
              />
              <ListItemSecondaryAction>
                <IconButton 
                  size="small" 
                  onClick={(e) => {
                    e.stopPropagation();
                    handleCopy(JSON.stringify(job, null, 2));
                  }}
                >
                  <CopyIcon fontSize="small" />
                </IconButton>
                <IconButton 
                  size="small" 
                  onClick={(e) => {
                    e.stopPropagation();
                    untrackJob(job.id);
                  }}
                >
                  <CloseIcon fontSize="small" />
                </IconButton>
              </ListItemSecondaryAction>
            </ListItem>
          ))}
        </List>
      </Collapse>
    </Paper>
  );
}
