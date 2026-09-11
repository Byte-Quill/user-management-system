import { useEffect, useRef } from "react";

/**
 * Live-region announcer for async UI events (uploads, decisions, resets).
 * Screen-reader users get the same "saved / uploaded / decided" feedback that
 * sighted users get from toasts — professional apps never leave async events
 * silent for assistive tech.
 */
export function useAnnouncer() {
  const liveRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const el = document.createElement("div");
    el.setAttribute("role", "status");
    el.setAttribute("aria-live", "polite");
    el.className = "sr-only";
    document.body.appendChild(el);
    liveRef.current = el;
    return () => {
      el.remove();
      liveRef.current = null;
    };
  }, []);

  const announce = (message: string) => {
    const el = liveRef.current;
    if (!el) return;
    el.textContent = "";
    window.setTimeout(() => {
      el.textContent = message;
    }, 30);
  };

  return announce;
}
