import type { BuildingPlacement } from "../types";
import type { EngineeringSystemKey } from "./workflowConstants";

type StateSetter<T> = (value: T | ((prev: T) => T)) => void;
type LotBounds = { x: number; y: number; w: number; h: number };
type BuildDefaultPolyline = (bounds: { x: number; y: number; w: number; d: number }) => Array<[number, number]>;
type SystemsImpactedByPlacement = (target?: Partial<BuildingPlacement> | null) => EngineeringSystemKey[];

export type DashboardPlacementActions = {
  askClarification: (question: string, action: string, payload?: Record<string, unknown>) => void;
  buildDefaultPolyline: BuildDefaultPolyline;
  clearGeneratedPreview: () => void;
  debugLog: (label: string, payload?: Record<string, unknown>) => void;
  ensureSiteBoundary: (reason: string) => boolean;
  markSystemsStale: (systems: EngineeringSystemKey[]) => void;
  persistDraftRefresh: (reason: string) => void;
  resolveDefaultBuildingDims: () => { w: number; d: number };
  resolveLotBounds: () => LotBounds;
  setActivePlacementId: StateSetter<string | null>;
  setBuildingPlacements: StateSetter<BuildingPlacement[]>;
  setPlacementModeEnabled: StateSetter<boolean>;
  setPreviewInteraction: (value: "static" | "edit") => void;
  setPreviewMode: (value: "2d" | "3d") => void;
  setSelectedObjectIds: StateSetter<string[]>;
  setStatusMessage: (message: string) => void;
  systemsImpactedByPlacement: SystemsImpactedByPlacement;
};

function clampUnit(value: number) {
  return Math.min(Math.max(value, 0), 1);
}

export function runDashboardPlaceBuilding({
  position,
  activePlacementId,
  buildingPlacements,
  siteScaleLocked,
  actions,
}: {
  position: { x: number; y: number };
  activePlacementId: string | null;
  buildingPlacements: BuildingPlacement[];
  siteScaleLocked: boolean;
  actions: DashboardPlacementActions;
}) {
  actions.clearGeneratedPreview();
  if (!siteScaleLocked) {
    actions.setStatusMessage("Lock the site boundary before placing buildings.");
    return;
  }
  const lot = actions.resolveLotBounds();
  if (!lot.w || !lot.h) {
    actions.setStatusMessage("Set the site width and height before placing buildings.");
    return;
  }
  const { w, d } = actions.resolveDefaultBuildingDims();
  const clampedX = clampUnit(position.x);
  const clampedY = clampUnit(position.y);
  const nextX = lot.x + clampedX * lot.w - w / 2;
  const nextY = lot.y + clampedY * lot.h - d / 2;
  if (!Number.isFinite(nextX) || !Number.isFinite(nextY)) {
    actions.setStatusMessage("Placement failed: invalid coordinates.");
    return;
  }
  const boundedX = Math.min(Math.max(nextX, lot.x), lot.x + lot.w - w);
  const boundedY = Math.min(Math.max(nextY, lot.y), lot.y + lot.h - d);
  actions.debugLog("place-building", {
    activePlacementId: activePlacementId ?? null,
    boundedX,
    boundedY,
  });
  if (activePlacementId) {
    const activePlacement = buildingPlacements.find((item) => item.id === activePlacementId);
    actions.setBuildingPlacements((prev) =>
      prev.map((item) =>
        item.id === activePlacementId
          ? {
              ...item,
              x: boundedX,
              y: boundedY,
              placed: true,
              geometry:
                item.geometryType === "polyline"
                  ? actions.buildDefaultPolyline({ x: boundedX, y: boundedY, w: item.w, d: item.d })
                  : item.geometry,
            }
          : item,
      ),
    );
    actions.setActivePlacementId(null);
    actions.markSystemsStale(actions.systemsImpactedByPlacement(activePlacement));
    actions.debugLog("place-building-commit", { id: activePlacementId ?? null });
    actions.setStatusMessage("Object placed. Regenerate systems to reflect the new layout.");
    actions.persistDraftRefresh("Refreshing preview after object placement...");
    return;
  }
  const nextPlacement: BuildingPlacement = {
    id: `building-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    label: `Building ${buildingPlacements.length + 1}`,
    type: "building",
    x: boundedX,
    y: boundedY,
    w,
    d,
    rotation: 0,
    locked: false,
    placed: true,
  };
  actions.setBuildingPlacements((prev) => [...prev, nextPlacement]);
  actions.debugLog("place-building-new", {
    id: nextPlacement.id,
    x: nextPlacement.x,
    y: nextPlacement.y,
  });
  actions.markSystemsStale(actions.systemsImpactedByPlacement(nextPlacement));
  actions.setStatusMessage("Object placed. Regenerate systems to reflect the new layout.");
  actions.persistDraftRefresh("Refreshing preview after object placement...");
}

export function runDashboardPlaceObject({
  id,
  position,
  buildingPlacements,
  siteScaleLocked,
  actions,
}: {
  id: string;
  position: { x: number; y: number };
  buildingPlacements: BuildingPlacement[];
  siteScaleLocked: boolean;
  actions: DashboardPlacementActions;
}) {
  actions.clearGeneratedPreview();
  if (!siteScaleLocked) {
    actions.setStatusMessage("Lock the site boundary before placing objects.");
    return;
  }
  const lot = actions.resolveLotBounds();
  if (!lot.w || !lot.h) {
    const ok = actions.ensureSiteBoundary("Place the object again to drop it on the new site.");
    if (!ok) {
      actions.setStatusMessage("Set the site width and height before placing objects.");
    }
    return;
  }
  const clampedX = clampUnit(position.x);
  const clampedY = clampUnit(position.y);
  actions.debugLog("place-object", { id, clampedX, clampedY });
  const target = buildingPlacements.find((item) => item.id === id);
  actions.setBuildingPlacements((prev) =>
    prev.map((item) => {
      if (item.id !== id) return item;
      const x = lot.x + clampedX * lot.w - item.w / 2;
      const y = lot.y + clampedY * lot.h - item.d / 2;
      if (!Number.isFinite(x) || !Number.isFinite(y)) {
        return { ...item, placed: false };
      }
      const boundedX = Math.min(Math.max(x, lot.x), lot.x + lot.w - item.w);
      const boundedY = Math.min(Math.max(y, lot.y), lot.y + lot.h - item.d);
      actions.debugLog("place-object-commit", { id, x: boundedX, y: boundedY });
      return {
        ...item,
        x: boundedX,
        y: boundedY,
        placed: true,
        geometry:
          item.geometryType === "polyline"
            ? actions.buildDefaultPolyline({ x: boundedX, y: boundedY, w: item.w, d: item.d })
            : item.geometry,
      };
    }),
  );
  actions.setActivePlacementId((prev) => (prev === id ? null : prev));
  actions.setPlacementModeEnabled(false);
  actions.markSystemsStale(actions.systemsImpactedByPlacement(target));
  actions.debugLog("place-object-complete", { id });
  actions.setStatusMessage("Object placed. Regenerate systems to reflect the new layout.");
  actions.persistDraftRefresh("Refreshing preview after object placement...");
}

export function runDashboardSelectPlacementTarget({
  id,
  buildingPlacements,
  actions,
}: {
  id: string;
  buildingPlacements: BuildingPlacement[];
  actions: DashboardPlacementActions;
}) {
  const lot = actions.resolveLotBounds();
  const target = buildingPlacements.find((item) => item.id === id);
  if (!lot.w || !lot.h) {
    const message = `Cannot place ${target?.label || "object"} yet: site width and depth are missing. Set or draw a site boundary first.`;
    actions.askClarification(message, "place_object_missing_site", { id });
    return;
  }
  if (target && target.type === "site") {
    actions.setStatusMessage("Site boundary is already configured and cannot be moved from the object tray.");
    return;
  }
  if (target && !target.placed) {
    const nextX = Math.min(Math.max(16, (lot.w - target.w) / 2), Math.max(0, lot.w - target.w));
    const nextY = Math.min(Math.max(16, (lot.h - target.d) / 2), Math.max(0, lot.h - target.d));
    actions.setBuildingPlacements((prev) =>
      prev.map((item) =>
        item.id === id
          ? {
              ...item,
              x: Number.isFinite(nextX) ? nextX : 0,
              y: Number.isFinite(nextY) ? nextY : 0,
              placed: true,
            }
          : item,
      ),
    );
    actions.markSystemsStale(actions.systemsImpactedByPlacement(target));
    actions.setPreviewMode("2d");
    actions.setPreviewInteraction("edit");
    actions.setActivePlacementId(id);
    actions.setPlacementModeEnabled(false);
    actions.setStatusMessage(`${target.label} placed as a visible draft. Select it to move or edit.`);
    return;
  }
  actions.setPreviewMode("2d");
  actions.setPreviewInteraction("edit");
  actions.setActivePlacementId(id);
  actions.setPlacementModeEnabled(true);
  actions.setStatusMessage(
    target
      ? `Ready to place ${target.label}. Click on the canvas to drop it.`
      : "Placement active. Click on the canvas to drop the object.",
  );
}
