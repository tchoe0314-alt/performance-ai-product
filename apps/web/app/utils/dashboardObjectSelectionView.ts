import type { BuildingPlacement, SiteObjectType } from "../types";
import {
  buildObjectManagerLayerRows,
  buildObjectManagerTypes,
  getDraftObjectMeasurement,
  summarizeDraftObjectMeasurements,
} from "./objectGeometry";

type BuildDashboardObjectSelectionViewOptions = {
  buildingPlacements: BuildingPlacement[];
  activePlacementId?: string | null;
  selectedObjectIds: string[];
};

export function buildDashboardObjectSelectionView({
  buildingPlacements,
  activePlacementId,
  selectedObjectIds,
}: BuildDashboardObjectSelectionViewOptions) {
  // The explicit inspector target must outrank older bulk selections. Finding
  // against the combined set lets whichever object happens to occur first in
  // the array masquerade as the active object (and edits then hit the wrong
  // geometry).
  const selectedBuilding = (
    (activePlacementId ? buildingPlacements.find((item) => item.id === activePlacementId) : undefined) ??
    buildingPlacements.find((item) => selectedObjectIds.includes(item.id))
  ) ?? null;
  const selectedObjectSet = new Set(selectedObjectIds);
  const selectedObjectRows = buildingPlacements.filter((item) => selectedObjectSet.has(item.id));
  const selectedObjectMeasurements = selectedObjectRows.map(getDraftObjectMeasurement);
  return {
    selectedBuilding,
    selectedObjectSet,
    selectedObjectRows,
    selectedObjectMeasurements,
    selectedObjectMeasurementSummary: summarizeDraftObjectMeasurements(selectedObjectMeasurements),
    hiddenObjectCount: buildingPlacements.filter((item) => Boolean(item.meta?.ui_hidden)).length,
    objectManagerTypes: buildObjectManagerTypes(buildingPlacements) as SiteObjectType[],
    objectManagerLayerRows: buildObjectManagerLayerRows(buildingPlacements),
  };
}
