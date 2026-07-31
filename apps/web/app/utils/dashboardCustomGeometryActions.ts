import type { MutableRefObject } from "react";

import type { BuildingPlacement, SiteObjectType } from "../types";
import {
  buildCustomGeometryMeta,
} from "./objectGeometry";
import type { EngineeringSystemKey } from "./workflowConstants";

type StateSetter<T> = (value: T | ((prev: T) => T)) => void;
type LotBounds = { x: number; y: number; w: number; h: number };

export type DashboardCustomGeometryActions = {
  clearGeneratedPreview: () => void;
  ensureSiteBoundary: (reason: string) => boolean;
  markSystemsStale: (systems: EngineeringSystemKey[]) => void;
  persistDraftRefresh: (reason: string) => void;
  resolveLotBounds: () => LotBounds;
  setActivePlacementId: StateSetter<string | null>;
  setBuildingPlacements: StateSetter<BuildingPlacement[]>;
  setPlacementModeEnabled: StateSetter<boolean>;
  setPreviewInteraction: (value: "static" | "edit") => void;
  setPreviewMode: (value: "2d" | "3d") => void;
  setSelectedObjectIds: StateSetter<string[]>;
  setStatusMessage: (message: string) => void;
};

export type DashboardCustomGeometryPayload = {
  mode: "polyline" | "polygon" | "rect" | "point";
  points: Array<[number, number]>;
  label?: string;
  meta?: Record<string, unknown>;
};

export function runDashboardCreateCustomGeometry({
  payload,
  buildingPlacementsRef,
  siteScaleLocked,
  units,
  actions,
}: {
  payload: DashboardCustomGeometryPayload;
  buildingPlacementsRef: MutableRefObject<BuildingPlacement[]>;
  siteScaleLocked: boolean;
  units: string;
  actions: DashboardCustomGeometryActions;
}) {
  actions.clearGeneratedPreview();
  const isDraftCopyCommand =
    String(payload.meta?.cad_command || "").toUpperCase() === "COPY" &&
    typeof payload.meta?.copied_from_object_id === "string";
  if (!siteScaleLocked && !isDraftCopyCommand) {
    actions.setStatusMessage("Lock the site boundary before drawing objects.");
    return;
  }
  const lot = actions.resolveLotBounds();
  if (!lot.w || !lot.h) {
    const ok = actions.ensureSiteBoundary("Draw the geometry again after confirming the site boundary.");
    if (!ok) {
      actions.setStatusMessage("Set the site width and height before drawing geometry.");
    }
    return;
  }
  const validPoints = payload.points
    .map(([x, y]) => [
      Math.min(Math.max(x, 0), lot.w),
      Math.min(Math.max(y, 0), lot.h),
    ] as [number, number])
    .filter(([x, y]) => Number.isFinite(x) && Number.isFinite(y));
  const minRequired = payload.mode === "point" ? 1 : payload.mode === "rect" ? 2 : payload.mode === "polygon" ? 3 : 2;
  if (validPoints.length < minRequired) {
    actions.setStatusMessage("Drawn geometry needs more points before it can be added.");
    return;
  }
  const geometry =
    payload.mode === "rect"
      ? (() => {
          const [a, b] = validPoints;
          const minX = Math.min(a[0], b[0]);
          const maxX = Math.max(a[0], b[0]);
          const minY = Math.min(a[1], b[1]);
          const maxY = Math.max(a[1], b[1]);
          return [
            [minX, minY],
            [maxX, minY],
            [maxX, maxY],
            [minX, maxY],
          ] as Array<[number, number]>;
        })()
      : validPoints;
  const xs = geometry.map((pt) => pt[0]);
  const ys = geometry.map((pt) => pt[1]);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const isLine = payload.mode === "polyline";
  const isPoint = payload.mode === "point";
  const currentPlacements = buildingPlacementsRef.current;
  const existingCustomCount =
    currentPlacements.filter((item) => item.type === "custom").length + 1;
  const nextId = `custom-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  const nextLabel =
    payload.label ??
    `Custom ${payload.mode === "polyline" ? "Line" : payload.mode === "polygon" ? "Area" : payload.mode === "rect" ? "Rectangle" : "Point"} ${existingCustomCount}`;
  const nextPlacement: BuildingPlacement = {
    id: nextId,
    label: nextLabel,
    type:
      typeof payload.meta?.copied_object_type === "string" && payload.meta.copied_object_type !== "site"
        ? (payload.meta.copied_object_type as SiteObjectType)
        : ("custom" as SiteObjectType),
    x: isPoint ? geometry[0][0] - 5 : minX,
    y: isPoint ? geometry[0][1] - 5 : minY,
    w: isPoint ? 10 : Math.max(5, maxX - minX),
    d: isPoint ? 10 : Math.max(5, maxY - minY),
    rotation: 0,
    locked: false,
    placed: true,
    source: "manual_drawn",
    generated: false,
    geometryType: payload.mode,
    geometry,
    capabilities: {
      movable: true,
      resizable: payload.mode === "rect" || payload.mode === "polygon" || payload.mode === "point",
      rotatable: payload.mode === "rect",
      deletable: true,
    },
    systemDependencies: ["roads", "parking", "grading", "drainage", "utilities"],
    meta: {
      ...buildCustomGeometryMeta(nextId, nextLabel, payload.mode, geometry, units || "ft"),
      ...(payload.meta ?? {}),
      source: "manual_drawn",
      engineering_status: "draft_review_required",
      review_status: "engineer_review_required",
      handoff_status: "draft_review_required",
      construction_release_allowed: false,
    },
  };
  if (isLine) {
    nextPlacement.capabilities = {
      movable: true,
      resizable: false,
      rotatable: false,
      deletable: true,
    };
  }
  const nextPlacements = [...currentPlacements, nextPlacement];
  buildingPlacementsRef.current = nextPlacements;
  actions.setBuildingPlacements(nextPlacements);
  actions.setActivePlacementId(nextPlacement.id);
  actions.setSelectedObjectIds([nextPlacement.id]);
  actions.setPlacementModeEnabled(false);
  actions.setPreviewMode("2d");
  actions.setPreviewInteraction("edit");
  actions.markSystemsStale(["roads", "parking", "grading", "drainage", "utilities"]);
  actions.setStatusMessage("Custom geometry added as user-authored project geometry. Regenerate systems only after reviewing impacts.");
  actions.persistDraftRefresh("Refreshing preview after custom geometry draw...");
}
