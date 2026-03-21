import { useState, useEffect } from 'react';
import { api } from '../api/client';

interface CmpSnapshot {
  data: Record<string, number>;
  missing: string[];
  trade_date: string;
  as_of_ts: string | null;
}

export function useCmpSnapshot(symbols: string[], enabled: boolean = true) {
  const [cmpData, setCmpData] = useState<CmpSnapshot | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!enabled || symbols.length === 0) {
      setCmpData(null);
      return;
    }

    let cancelled = false;

    const fetchCmp = async () => {
      setLoading(true);
      setError(null);
      try {
        const result = await api.getCmp(symbols);
        if (!cancelled) {
          setCmpData(result);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to fetch CMP');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    fetchCmp();

    return () => {
      cancelled = true;
    };
  }, [symbols.join(','), enabled]);

  return { cmpData, loading, error };
}