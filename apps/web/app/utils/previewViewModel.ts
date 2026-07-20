import type { BuildingPlacement } from "../types";
import type { SiteSize } from "./geometryTransforms";

export function buildPreviewCurrentSiteSize(lotWidth: number, lotHeight: number): SiteSize {
  return { width: Math.max(lotWidth, 1), height: Math.max(lotHeight, 1) };
}

export function isAiRealismProviderConfigured(search?: string) {
  const effectiveSearch = search ?? (typeof window !== "undefined" ? window.location.search : "");
  if (effectiveSearch) {
    const params = new URLSearchParams(effectiveSearch);
    if (params.get("aiRealismProvider") === "mock") return true;
  }
  return Boolean(process.env.NEXT_PUBLIC_CIVORA_AI_REALISM_PROVIDER?.trim());
}

export function findPreviewHoveredObject({
  hoveredObjectId,
  buildingPlacements,
  cadEntityPreviewObjects,
  suggestedPlacements,
}: {
  hoveredObjectId: string | null;
  buildingPlacements: BuildingPlacement[];
  cadEntityPreviewObjects: BuildingPlacement[];
  suggestedPlacements: BuildingPlacement[];
}) {
  return (
    [...buildingPlacements, ...cadEntityPreviewObjects, ...suggestedPlacements].find(
      (item) => item.id === hoveredObjectId && item.type !== "site",
    ) ?? null
  );
}

export function findPreviewSelectedObject({
  selectedBuildingId,
  managedObjectId,
  hoveredObjectId,
  selectedObjectIds,
  cadSelectionSet,
  buildingPlacements,
  cadEntityPreviewObjects,
  suggestedPlacements,
}: {
  selectedBuildingId?: string | null;
  managedObjectId: string | null;
  hoveredObjectId: string | null;
  selectedObjectIds: string[];
  cadSelectionSet: string[];
  buildingPlacements: BuildingPlacement[];
  cadEntityPreviewObjects: BuildingPlacement[];
  suggestedPlacements: BuildingPlacement[];
}) {
  const selectedIds = [
    selectedBuildingId,
    managedObjectId,
    hoveredObjectId,
    ...selectedObjectIds,
    ...cadSelectionSet,
  ].filter((id): id is string => Boolean(id));
  return (
    [...buildingPlacements, ...cadEntityPreviewObjects, ...suggestedPlacements].find(
      (item) => selectedIds.includes(item.id) && item.type !== "site",
    ) ?? null
  );
}

export function resolvePreviewSelectedDeletableObject({
  selectedObject,
  buildingPlacements,
}: {
  selectedObject: BuildingPlacement | null;
  buildingPlacements: BuildingPlacement[];
}) {
  return selectedObject &&
    !selectedObject.locked &&
    selectedObject.type !== "site" &&
    buildingPlacements.some((item) => item.id === selectedObject.id)
    ? selectedObject
    : null;
}

export function buildPreviewParkingAccessPoints(buildingPlacements: BuildingPlacement[]) {
  return buildingPlacements
    .filter((item) => item.type === "entrance" || item.type === "road" || item.type === "driveway")
    .map((item) => ({ x: (item.x ?? 0) + item.w / 2, y: (item.y ?? 0) + item.d / 2 }));
}
