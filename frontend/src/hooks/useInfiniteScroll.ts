import { useEffect, useRef } from "react";

/**
 * Runs `callback` when a sentinel element scrolls into view — the mechanism
 * behind infinite-scroll rails, keeping pagination as a progressive
 * enhancement on top of the existing prev/next pager (never a replacement).
 */
interface InfiniteScrollOptions {
  onIntersect: () => void;
  enabled?: boolean;
  rootMargin?: string;
}

export function useInfiniteScroll({
  onIntersect,
  enabled = true,
  rootMargin = "320px",
}: InfiniteScrollOptions) {
  const sentinelRef = useRef<HTMLDivElement | null>(null);
  const callbackRef = useRef(onIntersect);
  callbackRef.current = onIntersect;

  useEffect(() => {
    const el = sentinelRef.current;
    if (!el || !enabled || typeof IntersectionObserver === "undefined") return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) callbackRef.current();
      },
      { rootMargin }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [enabled, rootMargin]);

  return sentinelRef;
}
