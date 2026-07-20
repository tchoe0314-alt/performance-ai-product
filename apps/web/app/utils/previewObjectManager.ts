import type { BuildingPlacement } from "../types";
import { useCallback, useMemo } from "react";
import { getPreviewCadLayer } from "./previewCadObjectHelpers";
import { getPreviewObjectActionBlocker as resolvePreviewObjectActionBlocker } from "./previewCadObjectHelpers";

export type PreviewObjectManagerCounts = {
  total: number;
  visible: number;
  draft: number;
  generated: number;
};

export const buildPreviewObjectManagerRows = (items: BuildingPlacement[]) => {
  const rows = new Map<string, BuildingPlacement>();
  items.forEach((item) => {
    if (!rows.has(item.id)) rows.set(item.id, item);
  });
  return Array.from(rows.values()).sort((a, b) => {
    const aHidden = a.meta?.ui_hidden ? 1 : 0;
    const bHidden = b.meta?.ui_hidden ? 1 : 0;
    if (aHidden !== bHidden) return aHidden - bHidden;
    if (a.type === "site" && b.type !== "site") return -1;
    if (b.type === "site" && a.type !== "site") return 1;
    return (a.label || a.id).localeCompare(b.label || b.id);
  });
};

export const buildPreviewObjectManagerCounts = ({
  rows,
  hiddenCadLayers,
  getCadLayer,
}: {
  rows: BuildingPlacement[];
  hiddenCadLayers: string[];
  getCadLayer: (item: BuildingPlacement) => string;
}): PreviewObjectManagerCounts => ({
  total: rows.length,
  visible: rows.filter((item) => !item.meta?.ui_hidden && !hiddenCadLayers.includes(getCadLayer(item))).length,
  draft: rows.filter(
    (item) =>
      item.source === "manual_drawn" ||
      item.type === "custom" ||
      item.meta?.engineering_status === "draft_review_required",
  ).length,
  generated: rows.filter((item) => item.generated || item.source === "generated").length,
});

export function buildPreviewCadLayerOptions({
  buildingPlacements,
  cadEntityPreviewObjects,
  suggestedPlacements,
}: {
  buildingPlacements: BuildingPlacement[];
  cadEntityPreviewObjects: BuildingPlacement[];
  suggestedPlacements: BuildingPlacement[];
}) {
  const layers = new Set(["C-DRAFT", "C-SITE", "C-ROAD", "C-UTIL", "C-DRAIN", "C-BLDG", "C-SYMB", "C-ANNO"]);
  [...buildingPlacements, ...cadEntityPreviewObjects, ...suggestedPlacements].forEach((item) => {
    layers.add(getPreviewCadLayer(item));
  });
  return Array.from(layers).sort();
}

export function isPreviewObjectEditableSource({
  buildingPlacements,
  item,
  suggestedPlacements,
}: {
  buildingPlacements: BuildingPlacement[];
  item: BuildingPlacement;
  suggestedPlacements: BuildingPlacement[];
}) {
  return (
    buildingPlacements.some((candidate) => candidate.id === item.id) ||
    suggestedPlacements.some((candidate) => candidate.id === item.id)
  );
}

export function isPreviewCanonicalBuildingObject({
  buildingPlacements,
  item,
}: {
  buildingPlacements: BuildingPlacement[];
  item: BuildingPlacement;
}) {
  return buildingPlacements.some((candidate) => candidate.id === item.id);
}

export function usePreviewObjectManagerModel({
  buildingPlacements,
  cadEntityPreviewObjects,
  hiddenCadLayers,
  suggestedPlacements,
}: {
  buildingPlacements: BuildingPlacement[];
  cadEntityPreviewObjects: BuildingPlacement[];
  hiddenCadLayers: string[];
  suggestedPlacements: BuildingPlacement[];
}) {
  const cadLayerOptions = useMemo(
    () =>
      buildPreviewCadLayerOptions({
        buildingPlacements,
        cadEntityPreviewObjects,
        suggestedPlacements,
      }),
    [buildingPlacements, cadEntityPreviewObjects, suggestedPlacements],
  );
  const objectManagerRows = useMemo(
    () => buildPreviewObjectManagerRows([...buildingPlacements, ...cadEntityPreviewObjects, ...suggestedPlacements]),
    [buildingPlacements, cadEntityPreviewObjects, suggestedPlacements],
  );
  const objectManagerCounts = useMemo(
    () =>
      buildPreviewObjectManagerCounts({
        rows: objectManagerRows,
        hiddenCadLayers,
        getCadLayer: getPreviewCadLayer,
      }),
    [hiddenCadLayers, objectManagerRows],
  );
  const previewObjectEditableSource = useCallback(
    (item: BuildingPlacement) =>
      isPreviewObjectEditableSource({
        buildingPlacements,
        item,
        suggestedPlacements,
      }),
    [buildingPlacements, suggestedPlacements],
  );
  const getPreviewObjectActionBlocker = useCallback(
    (item: BuildingPlacement | null, action: "rename" | "style" | "type" | "hide" | "delete" | "focus") =>
      resolvePreviewObjectActionBlocker({
        item,
        action,
        isEditableSource: item ? previewObjectEditableSource(item) : false,
        isCanonicalBuilding: item
          ? isPreviewCanonicalBuildingObject({ buildingPlacements, item })
          : false,
      }),
    [buildingPlacements, previewObjectEditableSource],
  );

  return {
    cadLayerOptions,
    getPreviewObjectActionBlocker,
    objectManagerCounts,
    objectManagerRows,
    previewObjectEditableSource,
  };
}
