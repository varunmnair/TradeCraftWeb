import { useState, useCallback, useEffect, useRef } from 'react';
import { api } from '../api/client';

export type JobStatus = 'pending' | 'processing' | 'completed' | 'failed' | 'succeeded' | 'error';

interface JobResult {
  job_id: number;
  status: string;
  progress: number;
  result?: unknown;
  error?: {
    message: string;
    error_code?: string;
  };
}

interface UseJobRunnerOptions {
  onSuccess?: (job: JobResult) => void | Promise<void>;
  onError?: (error: string, job?: JobResult) => void;
  pollInterval?: number;
}

interface UseJobRunnerReturn {
  isRunning: boolean;
  isSuccess: boolean;
  isError: boolean;
  errorMessage: string | null;
  lastJobId: number | null;
  jobStatus: JobStatus | null;
  jobProgress: number;
  run: (startJobFn: () => Promise<{ job_id: number }>) => Promise<void>;
  reset: () => void;
}

const TERMINAL_STATUSES: JobStatus[] = ['completed', 'failed', 'succeeded', 'error'];

function normalizeStatus(status: string): JobStatus {
  const lower = status.toLowerCase();
  if (lower === 'succeeded' || lower === 'completed') return 'completed';
  if (lower === 'failed' || lower === 'error') return 'failed';
  if (lower === 'processing' || lower === 'pending') return lower as JobStatus;
  return 'pending';
}

export function useJobRunner(options: UseJobRunnerOptions = {}): UseJobRunnerReturn {
  const { onSuccess, onError, pollInterval = 2000 } = options;
  
  const [isRunning, setIsRunning] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  const [isError, setIsError] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [lastJobId, setLastJobId] = useState<number | null>(null);
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null);
  const [jobProgress, setJobProgress] = useState(0);
  
  const pollingRef = useRef<NodeJS.Timeout | null>(null);
  const optionsRef = useRef(options);
  optionsRef.current = options;

  const clearPolling = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  }, []);

  const reset = useCallback(() => {
    setIsRunning(false);
    setIsSuccess(false);
    setIsError(false);
    setErrorMessage(null);
    setJobStatus(null);
    setJobProgress(0);
    clearPolling();
  }, [clearPolling]);

  const pollJob = useCallback(async (jobId: number) => {
    try {
      const response = await api.getJob(jobId);
      const job = response.job;
      const status = normalizeStatus(job.status);
      
      setJobStatus(status);
      setJobProgress(job.progress || 0);
      
      if (TERMINAL_STATUSES.includes(status)) {
        clearPolling();
        setIsRunning(false);
        
        if (status === 'completed') {
          setIsSuccess(true);
          setIsError(false);
          setErrorMessage(null);
          if (optionsRef.current.onSuccess) {
            optionsRef.current.onSuccess(job as JobResult);
          }
        } else {
          setIsError(true);
          setIsSuccess(false);
          const errMsg = job.error?.message || 'Job failed';
          setErrorMessage(errMsg);
          if (optionsRef.current.onError) {
            optionsRef.current.onError(errMsg, job as JobResult);
          }
        }
      }
    } catch (err) {
      console.error('Polling error:', err);
      clearPolling();
      setIsRunning(false);
      setIsError(true);
      setErrorMessage('Failed to poll job status');
    }
  }, [clearPolling]);

  const run = useCallback(async (startJobFn: () => Promise<{ job_id: number }>) => {
    reset();
    setIsRunning(true);
    setErrorMessage(null);
    
    try {
      const response = await startJobFn();
      const jobId = response.job_id;
      setLastJobId(jobId);
      
      pollingRef.current = setInterval(() => pollJob(jobId), pollInterval);
      pollJob(jobId);
    } catch (err) {
      setIsRunning(false);
      setIsError(true);
      const errMsg = err instanceof Error ? err.message : 'Failed to start job';
      setErrorMessage(errMsg);
      if (optionsRef.current.onError) {
        optionsRef.current.onError(errMsg);
      }
    }
  }, [reset, pollJob, pollInterval]);

  useEffect(() => {
    return () => {
      clearPolling();
    };
  }, [clearPolling]);

  return {
    isRunning,
    isSuccess,
    isError,
    errorMessage,
    lastJobId,
    jobStatus,
    jobProgress,
    run,
    reset,
  };
}
