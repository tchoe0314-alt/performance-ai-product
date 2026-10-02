import type { BuildingPlacement } from "../types";

/** The ref is the live authority; React receives a presentation snapshot. */
export function commitPlacementState(
  live: { current: BuildingPlacement[] },
  update: BuildingPlacement[] | ((previous: BuildingPlacement[]) => BuildingPlacement[]),
  publish: (placements: BuildingPlacement[]) => void,
) {
  const next = typeof update === "function" ? update(live.current) : update;
  live.current = next;
  publish(next);
}
