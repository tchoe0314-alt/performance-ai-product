import { useSyncExternalStore } from "react";

const queryText = "(max-width: 1023px)";
function subscribe(onChange: () => void) {
  const query = window.matchMedia(queryText);
  query.addEventListener("change", onChange);
  return () => query.removeEventListener("change", onChange);
}
const snapshot = () => window.matchMedia(queryText).matches;
const serverSnapshot = () => false;

/** Matches the workspace drawer breakpoint without a hydration mismatch. */
export function useCompactViewport() {
  return useSyncExternalStore(subscribe, snapshot, serverSnapshot);
}
