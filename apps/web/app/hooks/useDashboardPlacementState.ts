import { useCallback, useRef, useState } from "react";
import type { BuildingPlacement } from "../types";
import { commitPlacementState } from "../utils/placementStateCommit";

/** All writers synchronize live canonical placements before scheduling a render. */
export function useDashboardPlacementState() {
  const [buildingPlacements, publishPlacements] = useState<BuildingPlacement[]>([]);
  const buildingPlacementsRef = useRef<BuildingPlacement[]>([]);
  const setBuildingPlacements = useCallback((update: BuildingPlacement[] | ((previous: BuildingPlacement[]) => BuildingPlacement[])) => {
    commitPlacementState(buildingPlacementsRef, update, publishPlacements);
  }, []);
  return { buildingPlacements, buildingPlacementsRef, setBuildingPlacements };
}
