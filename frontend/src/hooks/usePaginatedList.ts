import { useCallback, useEffect, useRef, useState } from "react";
import type { Page } from "@/types";

export function usePaginatedList<T>(
  fetcher: (page: number) => Promise<Page<T>>,
  errorMessage = "Failed to load."
) {
  const [items, setItems] = useState<T[]>([]);
  const [count, setCount] = useState(0);
  const [hasNext, setHasNext] = useState(false);
  const [hasPrev, setHasPrev] = useState(false);
  const [pageNum, setPageNum] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const errorMessageRef = useRef(errorMessage);
  errorMessageRef.current = errorMessage;
  const requestIdRef = useRef(0);

  const load = useCallback(async (pageNumber: number) => {
    const requestId = ++requestIdRef.current;
    setLoading(true);
    setError("");
    try {
      const data = await fetcher(pageNumber);
      if (requestId !== requestIdRef.current) return;
      setItems(data.results);
      setCount(data.count);
      setHasNext(!!data.next);
      setHasPrev(!!data.previous);
    } catch {
      if (requestId !== requestIdRef.current) return;
      setError(errorMessageRef.current);
    } finally {
      if (requestId === requestIdRef.current) setLoading(false);
    }
  }, [fetcher]);

  useEffect(() => {
    void load(pageNum);
  }, [load, pageNum]);

  return { items, count, hasNext, hasPrev, pageNum, setPageNum, loading, error };
}
