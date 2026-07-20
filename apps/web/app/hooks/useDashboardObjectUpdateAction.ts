import { useCallback } from "react";
import type { MutableRefObject } from "react";

import type { BuildingPlacement, PlanResponse, ProjectInput, ProjectRecord } from "../types";
import { buildDashboardObjectUpdateRecentChange } from "../utils/dashboardObjectChangeMessages";
import { systemsImpactedByPlacement } from "../utils/dashboardGenerateLayoutContext";
import type { DraftUndoAction, RecentChange } from "../utils/dashboardTypes";
import {
  buildCustomGeometryMeta,
  isCustomGeometryMode,
  type CustomGeometryMode,
} from "../utils/objectGeometry";
import type { ParkingParams } from "../utils/previewGeometryTruth";
import type { EngineeringSystemKey } from "../utils/workflowConstants";

type StateSetter<T> = (value: T | ((prev: T) => T)) => void;
type SaveProject = (options?: {
  silent?: boolean;
  projectIdOverride?: string | null;
  nameOverride?: string;
  fileNameOverride?: string;
  projectInputOverride?: ProjectInput;
  latestResultOverride?: PlanResponse;
  autoNamedOverride?: boolean;
  autoFileNamedOverride?: boolean;
}) => Promise<ProjectRecord | null>;
type ParkingFootprint = {
  w: number;
  d: number;
  maxStalls: number;
  moduleCount: number;
  stallsPerRow: number;
  moduleCols: number;
  moduleRows: number;
};
type ResolvedParkingParams = Required<Pick<
  ParkingParams,
  | "stallWidth"
  | "stallDepth"
  | "aisleWidth"
  | "adaAisleWidth"
  | "adaCount"
  | "compactCount"
  | "compactWidth"
  | "angleDeg"
  | "loading"
  | "autoResizeToFitCount"
  | "useMixedAngles"
  | "compactZone"
>>;

type UseDashboardObjectUpdateActionInput = {
  buildingPlacements: BuildingPlacement[];
  buildingPlacementsRef: MutableRefObject<BuildingPlacement[]>;
  clearGeneratedPreview: () => void;
  computeParkingFootprint: (
    target: BuildingPlacement,
    params: Omit<ResolvedParkingParams, "autoResizeToFitCount" | "useMixedAngles" | "compactZone">,
    stallCount: number,
  ) => ParkingFootprint;
  currentProject: ProjectRecord | null;
  ensureProjectDraftRef: MutableRefObject<() => Promise<string | null>>;
  markSystemsStale: (systems?: EngineeringSystemKey[]) => void;
  payloadPreview: ProjectInput;
  previewRefreshIntentRef: MutableRefObject<{ reason: string; track?: boolean } | null>;
  pushRecoveryMessage: (message: string) => void;
  recordDraftUndoAction: (action: DraftUndoAction) => void;
  recordRecentChange: (change: Omit<RecentChange, "id" | "createdAt">) => void;
  resolveParkingParams: (
    target: BuildingPlacement,
    overrides?: Partial<BuildingPlacement>,
  ) => ResolvedParkingParams;
  saveProjectRef: MutableRefObject<SaveProject>;
  setBuildingPlacements: StateSetter<BuildingPlacement[]>;
  setFitToSiteRequest: StateSetter<number>;
  setStatusMessage: (message: string) => void;
  units: string;
};

export function useDashboardObjectUpdateAction({
  buildingPlacements,
  buildingPlacementsRef,
  clearGeneratedPreview,
  computeParkingFootprint,
  currentProject,
  ensureProjectDraftRef,
  markSystemsStale,
  payloadPreview,
  previewRefreshIntentRef,
  pushRecoveryMessage,
  recordDraftUndoAction,
  recordRecentChange,
  resolveParkingParams,
  saveProjectRef,
  setBuildingPlacements,
  setFitToSiteRequest,
  setStatusMessage,
  units,
}: UseDashboardObjectUpdateActionInput) {
  return useCallback((id: string, updates: Partial<BuildingPlacement>) => {
    clearGeneratedPreview();
    const nextUpdates = { ...updates };
    const target = buildingPlacements.find((item) => item.id === id);
    if (target?.type === "site" && (typeof updates.x === "number" || typeof updates.y === "number")) {
      const currentX = target.x ?? 0;
      const currentY = target.y ?? 0;
      const nextX = typeof updates.x === "number" ? updates.x : currentX;
      const nextY = typeof updates.y === "number" ? updates.y : currentY;
      const deltaX = nextX - currentX;
      const deltaY = nextY - currentY;
      const currentInput = currentProject?.project_input ?? payloadPreview;
      const geocode = currentInput?.meta?.site_inputs?.geocode;
      if (geocode?.lat && geocode?.lng) {
        const metersPerDegLat = 111320;
        const metersPerDegLng = 111320 * Math.cos((geocode.lat * Math.PI) / 180);
        const dxM = deltaX * 0.3048;
        const dyM = -deltaY * 0.3048;
        const nextLat = geocode.lat + dyM / metersPerDegLat;
        const nextLng = geocode.lng + dxM / metersPerDegLng;
        const nextSiteInputs = {
          ...(currentInput?.meta?.site_inputs ?? {}),
          geocode: {
            ...(geocode ?? {}),
            lat: nextLat,
            lng: nextLng,
          },
        };
        void saveProjectRef.current?.({
          silent: true,
          projectInputOverride: {
            ...currentInput,
            input_mode: "user",
            strict_mode: false,
            allow_ai_fill_for_blanks: false,
            meta: {
              ...(currentInput?.meta ?? {}),
              site_inputs: nextSiteInputs,
            },
          },
        });
        setFitToSiteRequest((value) => value + 1);
        nextUpdates.x = 0;
        nextUpdates.y = 0;
      }
    }
    if (typeof updates.x === "number" || typeof updates.y === "number") {
      nextUpdates.placed = true;
    }
    if (
      target?.geometryType &&
      Array.isArray(target.geometry) &&
      !Array.isArray(updates.geometry) &&
      (typeof updates.x === "number" || typeof updates.y === "number")
    ) {
      const deltaX = (typeof updates.x === "number" ? updates.x : target.x ?? 0) - (target.x ?? 0);
      const deltaY = (typeof updates.y === "number" ? updates.y : target.y ?? 0) - (target.y ?? 0);
      if (Number.isFinite(deltaX) && Number.isFinite(deltaY)) {
        nextUpdates.geometry = target.geometry.map(([px, py]) => [px + deltaX, py + deltaY]);
      }
    }
    if (
      target?.geometryType &&
      Array.isArray(target.geometry) &&
      (typeof updates.w === "number" || typeof updates.d === "number")
    ) {
      const sourceGeometry = Array.isArray(nextUpdates.geometry) ? nextUpdates.geometry : target.geometry;
      const xs = sourceGeometry.map(([px]) => px);
      const ys = sourceGeometry.map(([, py]) => py);
      const minX = Math.min(...xs);
      const minY = Math.min(...ys);
      const width = Math.max(0.001, Math.max(...xs) - minX);
      const depth = Math.max(0.001, Math.max(...ys) - minY);
      const nextW = typeof updates.w === "number" && updates.w > 0 ? updates.w : target.w;
      const nextD = typeof updates.d === "number" && updates.d > 0 ? updates.d : target.d;
      const scaleX = nextW / width;
      const scaleY = nextD / depth;
      if (Number.isFinite(scaleX) && Number.isFinite(scaleY)) {
        nextUpdates.geometry = sourceGeometry.map(([px, py]) => [
          minX + (px - minX) * scaleX,
          minY + (py - minY) * scaleY,
        ]);
      }
    }
    if (target?.type === "custom") {
      const geometryType = isCustomGeometryMode(updates.geometryType ?? target.geometryType)
        ? (updates.geometryType ?? target.geometryType) as CustomGeometryMode
        : undefined;
      const geometry = Array.isArray(nextUpdates.geometry)
        ? nextUpdates.geometry
        : Array.isArray(target.geometry)
          ? target.geometry
          : undefined;
      if (geometryType && geometry?.length) {
        nextUpdates.source = "manual_drawn";
        nextUpdates.generated = false;
        nextUpdates.meta = {
          ...buildCustomGeometryMeta(
            target.id,
            updates.label ?? target.label,
            geometryType,
            geometry,
            units || "ft",
            target.meta,
          ),
          ...(updates.meta ?? {}),
        };
      }
    }
    if (target?.type === "parking") {
      const params = resolveParkingParams(target, updates);
      const stallCount = typeof updates.stallCount === "number" ? updates.stallCount : target.stallCount ?? 0;
      const totalStalls = Math.max(stallCount, params.adaCount + params.compactCount);
      const footprint = computeParkingFootprint(target, params, totalStalls);
      nextUpdates.meta = {
        ...(target.meta ?? {}),
        ...(updates.meta ?? {}),
        parkingParams: {
          ...(target.meta as { parkingParams?: ParkingParams })?.parkingParams,
          ...(updates.meta as { parkingParams?: ParkingParams })?.parkingParams,
          ...params,
        },
        parkingCapacity: footprint.maxStalls,
        parkingModuleCols: footprint.moduleCols,
        parkingModuleRows: footprint.moduleRows,
      };
      if (params.autoResizeToFitCount && totalStalls > 0) {
        nextUpdates.w = footprint.w;
        nextUpdates.d = footprint.d;
      }
    }
    const nextObject = target ? { ...target, ...nextUpdates } : null;
    let recentChange: Omit<RecentChange, "id" | "createdAt"> | null = null;
    let bulkUpdateUndo: DraftUndoAction | null = null;
    if (target && nextObject) {
      const combinedSourceIds = Array.isArray(target.meta?.combined_from_object_ids)
        ? target.meta.combined_from_object_ids.map((sourceId) => String(sourceId)).filter(Boolean)
        : [];
      const groupGeometryChanged =
        typeof updates.x === "number" ||
        typeof updates.y === "number" ||
        typeof updates.w === "number" ||
        typeof updates.d === "number" ||
        typeof updates.rotation === "number" ||
        Array.isArray(updates.geometry);
      const shouldSyncCombinedSources =
        combinedSourceIds.length > 0 &&
        (
          typeof updates.label === "string" ||
          updates.type !== undefined ||
          typeof updates.locked === "boolean" ||
          groupGeometryChanged ||
          Boolean(updates.meta && ("ui_color" in updates.meta || "color" in updates.meta || "style" in updates.meta))
        );
      if (shouldSyncCombinedSources) {
        const sourceObjects = buildingPlacements.filter((item) => combinedSourceIds.includes(item.id));
        if (sourceObjects.length) {
          const nextGroupLabel = nextObject.label || target.label;
          const nextGroupType = nextObject.type ?? target.type ?? "custom";
          const nextGroupColor = nextObject.meta?.ui_color ?? nextObject.meta?.color ?? target.meta?.ui_color ?? target.meta?.color;
          const groupOriginX = target.x ?? 0;
          const groupOriginY = target.y ?? 0;
          const nextGroupOriginX = nextObject.x ?? groupOriginX;
          const nextGroupOriginY = nextObject.y ?? groupOriginY;
          const groupScaleX = target.w > 0 && nextObject.w > 0 ? nextObject.w / target.w : 1;
          const groupScaleY = target.d > 0 && nextObject.d > 0 ? nextObject.d / target.d : 1;
          const groupCenterX = groupOriginX + target.w / 2;
          const groupCenterY = groupOriginY + target.d / 2;
          const nextGroupCenterX = nextGroupOriginX + nextObject.w / 2;
          const nextGroupCenterY = nextGroupOriginY + nextObject.d / 2;
          const rotationDeltaRadians = ((((nextObject.rotation ?? 0) - (target.rotation ?? 0)) % 360) * Math.PI) / 180;
          const cosDelta = Math.cos(rotationDeltaRadians);
          const sinDelta = Math.sin(rotationDeltaRadians);
          const transformPoint = ([px, py]: [number, number]): [number, number] => [
            nextGroupCenterX + ((px - groupCenterX) * groupScaleX) * cosDelta - ((py - groupCenterY) * groupScaleY) * sinDelta,
            nextGroupCenterY + ((px - groupCenterX) * groupScaleX) * sinDelta + ((py - groupCenterY) * groupScaleY) * cosDelta,
          ];
          const afterSources = sourceObjects.map((source) => {
            const sourceCorners: Array<[number, number]> = [
              [source.x ?? 0, source.y ?? 0],
              [(source.x ?? 0) + source.w, source.y ?? 0],
              [(source.x ?? 0) + source.w, (source.y ?? 0) + source.d],
              [source.x ?? 0, (source.y ?? 0) + source.d],
            ];
            const transformedGeometry = source.geometry?.map((point) => groupGeometryChanged ? transformPoint(point) : ([point[0], point[1]] as [number, number]));
            const boundsPoints = groupGeometryChanged ? (transformedGeometry?.length ? transformedGeometry : sourceCorners.map(transformPoint)) : sourceCorners;
            const boundsXs = boundsPoints.map(([x]) => x);
            const boundsYs = boundsPoints.map(([, y]) => y);
            const minSourceX = Math.min(...boundsXs);
            const maxSourceX = Math.max(...boundsXs);
            const minSourceY = Math.min(...boundsYs);
            const maxSourceY = Math.max(...boundsYs);
            return {
              ...source,
              x: groupGeometryChanged ? minSourceX : source.x,
              y: groupGeometryChanged ? minSourceY : source.y,
              w: groupGeometryChanged ? Math.max(1, maxSourceX - minSourceX) : source.w,
              d: groupGeometryChanged ? Math.max(1, maxSourceY - minSourceY) : source.d,
              rotation: groupGeometryChanged ? ((source.rotation ?? 0) + ((nextObject.rotation ?? 0) - (target.rotation ?? 0))) % 360 : source.rotation,
              geometry: transformedGeometry,
              capabilities: source.capabilities ? { ...source.capabilities } : source.capabilities,
              meta: {
                ...(source.meta ?? {}),
                combined_into_object_id: target.id,
                combined_into_label: nextGroupLabel,
                combined_into_type: nextGroupType,
                combined_trace_synced_at: new Date().toISOString(),
                ...(typeof updates.locked === "boolean" ? { combined_into_locked: updates.locked } : {}),
                ...(groupGeometryChanged ? { combined_transform_synced: true } : {}),
                ...(typeof nextGroupColor === "string" ? { combined_into_color: nextGroupColor } : {}),
              },
              locked: typeof updates.locked === "boolean" ? updates.locked : source.locked,
            };
          });
          bulkUpdateUndo = {
            action: "bulk_update",
            before: [target, ...sourceObjects].map((item) => ({
              ...item,
              geometry: item.geometry?.map(([x, y]) => [x, y] as [number, number]),
              meta: item.meta ? { ...item.meta } : item.meta,
              capabilities: item.capabilities ? { ...item.capabilities } : item.capabilities,
            })),
            after: [nextObject, ...afterSources],
            label: "combined object trace update",
          };
        }
      }
      const undo: DraftUndoAction = {
        action: "update",
        objectId: target.id,
        before: target,
        after: nextObject,
        label: target.label,
      };
      const changeUndo = bulkUpdateUndo ?? undo;
      recentChange = buildDashboardObjectUpdateRecentChange({ target, updates, undo: changeUndo });
    }
    const nextPlacements = bulkUpdateUndo?.after
      ? (() => {
          const afterById = new Map(bulkUpdateUndo.after.map((item) => [item.id, item]));
          return buildingPlacementsRef.current.map((item) =>
            afterById.has(item.id) ? { ...afterById.get(item.id)! } : item,
          );
        })()
      : buildingPlacementsRef.current.map((item) => (item.id === id ? { ...item, ...nextUpdates } : item));
    buildingPlacementsRef.current = nextPlacements;
    setBuildingPlacements(nextPlacements);
    markSystemsStale(systemsImpactedByPlacement(target));
    if (recentChange?.undo) {
      recordDraftUndoAction(recentChange.undo);
      recordRecentChange(recentChange);
      pushRecoveryMessage(`${recentChange.detail} Undo can restore the previous draft object state.`);
    } else {
      setStatusMessage("Object updated. Regenerate systems to reflect the new layout.");
    }
    void ensureProjectDraftRef.current()
      .then(() => saveProjectRef.current({ silent: true }))
      .then(() => previewRefreshIntentRef.current = { reason: "Refreshing preview after object update...", track: true });
  }, [
    buildingPlacements,
    buildingPlacementsRef,
    clearGeneratedPreview,
    computeParkingFootprint,
    currentProject,
    ensureProjectDraftRef,
    markSystemsStale,
    payloadPreview,
    previewRefreshIntentRef,
    pushRecoveryMessage,
    recordDraftUndoAction,
    recordRecentChange,
    resolveParkingParams,
    saveProjectRef,
    setBuildingPlacements,
    setFitToSiteRequest,
    setStatusMessage,
    units,
  ]);
}
