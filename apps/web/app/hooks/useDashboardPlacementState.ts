import { useCallback, useRef, useState } from "react";
import type { BuildingPlacement } from "../types";
import { commitPlacementState } from "../utils/placementStateCommit";

/** All writers synchronize live canonical placements before scheduling a render. */
export function useDashboardPlacementState() {
  const [buildingPlacements, publishPlacements] = useState<BuildingPlacement[]>([]);
  const buildingPlacementsRef = useRef<BuildingPlacement[]>([]);
  const placementGuardRef=useRef<((before:BuildingPlacement[],after:BuildingPlacement[])=>BuildingPlacement[])|null>(null);
  const restoreBuildingPlacements=useCallback((update:BuildingPlacement[]|((previous:BuildingPlacement[])=>BuildingPlacement[]))=>{
    commitPlacementState(buildingPlacementsRef,update,publishPlacements);
  },[]);
  const setBuildingPlacements = useCallback((update: BuildingPlacement[] | ((previous: BuildingPlacement[]) => BuildingPlacement[])) => {
    commitPlacementState(buildingPlacementsRef, previous=>{
      const next=typeof update==="function"?update(previous):update;
      return placementGuardRef.current?.(previous,next)??next;
    }, publishPlacements);
  }, []);
  return { buildingPlacements, buildingPlacementsRef, setBuildingPlacements,restoreBuildingPlacements,placementGuardRef };
}
