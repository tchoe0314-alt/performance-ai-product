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
  const selectedIds = [activePlacementId, ...selectedObjectIds].filter(Boolean);
  const selectedBuilding = buildingPlacements.find((item) => selectedIds.includes(item.id)) ?? null;
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
