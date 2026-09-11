import { useEffect } from "react";

/**
 * Locks body scroll while a drawer/modal/overlay is open — the detail every
 * slide-over needs so the backdrop page never scrolls behind the panel.
 */
export function useBodyScrollLock(locked: boolean) {
  useEffect(() => {
    if (!locked) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previous;
    };
  }, [locked]);
}
