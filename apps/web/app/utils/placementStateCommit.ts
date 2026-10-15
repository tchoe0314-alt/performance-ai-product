import type { BuildingPlacement } from "../types";
import {validateObjectGroups} from "./siteObjectDefinition";

/** The ref is the live authority; React receives a presentation snapshot. */
export function commitPlacementState(
  live: { current: BuildingPlacement[] },
  update: BuildingPlacement[] | ((previous: BuildingPlacement[]) => BuildingPlacement[]),
  publish: (placements: BuildingPlacement[]) => void,
) {
  // Detached planning prevents a throwing/invalid updater from partially mutating live state.
  const previous=JSON.parse(JSON.stringify(live.current)) as BuildingPlacement[];
  const next = typeof update === "function" ? update(previous) : update;
  validateObjectGroups(next);
  live.current = next;
  publish(next);
}
