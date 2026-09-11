import { useEffect, useMemo, useState } from "react";

/**
 * Polling hook with visibility awareness + jittered backoff.
 * Professional live regions pause while the tab is hidden (no stale churn,
 * no thundering herd when the tab regains focus) and back off on repeated
 * fetch failures instead of hammering a struggling server.
 */
interface PollOptions<T> {
  fetcher: () => Promise<T>;
  intervalMs?: number;
  enabled?: boolean;
  maxBackoffMs?: number;
}

interface PollState<T> {
  data: T | null;
  error: string;
  loading: boolean;
  refreshing: boolean;
  ageMs: number | null;
  refresh: () => void;
}

export function usePolling<T>({
  fetcher,
  intervalMs = 15000,
  enabled = true,
  maxBackoffMs = 120000,
}: PollOptions<T>): PollState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [stamp, setStamp] = useState<number | null>(null);
  const [failures, setFailures] = useState(0);
  const [tick, setTick] = useState(0);

  const memoFetcher = useMemo(() => fetcher, [fetcher]);

  useEffect(() => {
    if (!enabled || document.hidden) return;
    const delay =
      failures === 0
        ? intervalMs
        : Math.min(maxBackoffMs, intervalMs * 2 ** Math.min(failures, 4));
    const timer = setTimeout(() => setTick((t) => t + 1), delay + Math.random() * 500);
    return () => {
      clearTimeout(timer);
    };
  }, [enabled, intervalMs, maxBackoffMs, failures, tick, data]);

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    const load = async (first: boolean) => {
      if (first) setLoading(true);
      else setRefreshing(true);
      try {
        const next = await memoFetcher();
        if (cancelled) return;
        setData(next);
        setError("");
        setFailures(0);
        setStamp(Date.now());
      } catch (err) {
        if (cancelled) return;
        setFailures((f) => f + 1);
        setError(err instanceof Error ? err.message : "Refresh failed.");
      } finally {
        if (!cancelled) {
          setLoading(false);
          setRefreshing(false);
        }
      }
    };
    void load(tick === 0 && data === null);
    const onVisible = () => {
      if (!document.hidden) setTick((t) => t + 1);
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      cancelled = true;
      document.removeEventListener("visibilitychange", onVisible);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, memoFetcher, tick]);

  return {
    data,
    error,
    loading,
    refreshing,
    ageMs: stamp === null ? null : Date.now() - stamp,
    refresh: () => setTick((t) => t + 1),
  };
}
