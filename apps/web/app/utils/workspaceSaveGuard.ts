import type { BuildingPlacement } from "../types";

/** Capture at action time, before any await, rather than when a worker later starts. */
export function captureWorkspaceSaveGuard(
  generationRef: { current: number },
  placementsRef: { current: BuildingPlacement[] },
  isLatest: () => boolean = () => true,
) {
  const generation = generationRef.current;
  const snapshot = JSON.stringify(placementsRef.current);
  return () => generationRef.current === generation &&
    JSON.stringify(placementsRef.current) === snapshot && isLatest();
}
