import React, { createContext, useContext, useState, useCallback, useRef, ReactNode } from 'react';
import { JobStatus } from '../types';
import { api } from '../api/client';

const POLL_INTERVAL_MS = 2000;

interface JobsContextType {
  // Track active polling jobs
  activeJobs: Map<number, JobStatus>;
  // Start polling a job
  trackJob: (jobId: number) => void;
  // Stop tracking a job
  untrackJob: (jobId: number) => void;
  // Get job status
  getJob: (jobId: number) => JobStatus | undefined;
}

const JobsContext = createContext<JobsContextType | undefined>(undefined);

export function JobsProvider({ children }: { children: ReactNode }) {
  const [activeJobs, setActiveJobs] = useState<Map<number, JobStatus>>(new Map());
  const intervalsRef = useRef<Map<number, ReturnType<typeof setInterval>>>(new Map());

  const pollJob = useCallback((jobId: number) => {
    const fetchJob = async () => {
      try {
        const response = await api.getJob(jobId);
        const job = response.job;
        
        setActiveJobs((prev) => {
          const newMap = new Map(prev);
          newMap.set(jobId, job);
          return newMap;
        });

        // Stop polling if terminal
        if (job.status === 'completed' || job.status === 'succeeded' || job.status === 'failed') {
          const interval = intervalsRef.current.get(jobId);
          if (interval) {
            clearInterval(interval);
            intervalsRef.current.delete(jobId);
          }
        }
      } catch {
        // Job might have been deleted, stop polling
        const interval = intervalsRef.current.get(jobId);
        if (interval) {
          clearInterval(interval);
          intervalsRef.current.delete(jobId);
        }
      }
    };

    // Initial fetch
    fetchJob();

    // Set up interval
    const interval = setInterval(fetchJob, POLL_INTERVAL_MS);
    intervalsRef.current.set(jobId, interval);
  }, []);

  const trackJob = useCallback((jobId: number) => {
    // Don't track if already tracking
    if (intervalsRef.current.has(jobId)) return;
    pollJob(jobId);
  }, [pollJob]);

  const untrackJob = useCallback((jobId: number) => {
    const interval = intervalsRef.current.get(jobId);
    if (interval) {
      clearInterval(interval);
      intervalsRef.current.delete(jobId);
    }
    setActiveJobs((prev) => {
      const newMap = new Map(prev);
      newMap.delete(jobId);
      return newMap;
    });
  }, []);

  const getJob = useCallback((jobId: number) => {
    return activeJobs.get(jobId);
  }, [activeJobs]);

  return (
    <JobsContext.Provider value={{ activeJobs, trackJob, untrackJob, getJob }}>
      {children}
    </JobsContext.Provider>
  );
}

export function useJobs() {
  const context = useContext(JobsContext);
  if (context === undefined) {
    throw new Error('useJobs must be used within a JobsProvider');
  }
  return context;
}

// Hook to track a specific job
export function useJob(jobId: number | null) {
  const { activeJobs, trackJob, untrackJob } = useJobs();
  const [localJob, setLocalJob] = useState<JobStatus | null>(null);
  
  const job = jobId ? activeJobs.get(jobId) || localJob : null;
  const isDone = job?.status === 'completed' || job?.status === 'succeeded' || job?.status === 'failed';
  const isError = job?.status === 'failed';

  React.useEffect(() => {
    if (jobId) {
      trackJob(jobId);
      // Also fetch directly to have immediate data
      api.getJob(jobId).then((response) => {
        setLocalJob(response.job);
      }).catch(() => {});
    }
    return () => {
      if (jobId) {
        untrackJob(jobId);
      }
    };
  }, [jobId, trackJob, untrackJob]);

  return { job, isDone, isError };
}

// Hook to start a job and track it
export function useStartJob() {
  const { trackJob } = useJobs();
  const [jobId, setJobId] = useState<number | null>(null);
  const { job, isDone, isError } = useJob(jobId);

  const start = useCallback((newJobId: number) => {
    setJobId(newJobId);
    trackJob(newJobId);
  }, [trackJob]);

  const reset = useCallback(() => {
    setJobId(null);
  }, []);

  return { jobId, start, job, isDone, isError, reset };
}
