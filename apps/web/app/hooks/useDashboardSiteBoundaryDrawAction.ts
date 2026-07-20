import { useCallback } from "react";
import type { MutableRefObject } from "react";

import type { BuildingPlacement, ProjectInput, ProjectRecord, SiteInputs } from "../types";
import { buildDashboardManualFields } from "../utils/dashboardManualFields";
import type { EngineeringSystemKey } from "../utils/workflowConstants";
import { SQFT_PER_ACRE } from "../utils/workflowConstants";

type StateSetter<T> = (value: T | ((prev: T) => T)) => void;
type SaveProject = (options?: {
  silent?: boolean;
  projectInputOverride?: ProjectInput;
}) => Promise<ProjectRecord | null>;
type BuildManualFields = (
  fields: Omit<
    Parameters<typeof buildDashboardManualFields>[0],
    | "buildingPlacements"
    | "surveySlopeEstimate"
    | "drainageForcedInlets"
    | "drainageConnectOrphans"
    | "drainageAllowSlopeAdjust"
    | "drainageMaxSlopeAdjust"
  >,
) => ReturnType<typeof buildDashboardManualFields>;

type UseDashboardSiteBoundaryDrawActionInput = {
  buildManualFields: BuildManualFields;
  buildingCount: string;
  buildingDepth: string;
  buildingPlacements: BuildingPlacement[];
  buildingWidth: string;
  clearGeneratedPreview: () => void;
  currentProject: ProjectRecord | null;
  drainage: boolean;
  ensureProjectDraftRef: MutableRefObject<() => Promise<string | null>>;
  fileName: string;
  grading: boolean;
  markSystemsStale: (systems: EngineeringSystemKey[]) => void;
  maxAdaCrossSlopePct: string;
  maxParkingSlopePct: string;
  maxRoadGradePct: string;
  minSlopePct: string;
  parkingCount: string;
  payloadPreview: ProjectInput;
  pipeMinSlopePct: string;
  previewRefreshIntentRef: MutableRefObject<{ reason: string; track?: boolean } | null>;
  projectType: string;
  roads: boolean;
  saveProjectRef: MutableRefObject<SaveProject>;
  setback: string;
  setBuildingPlacements: StateSetter<BuildingPlacement[]>;
  setCurrentProject: StateSetter<ProjectRecord | null>;
  setFitToSiteRequest: StateSetter<number>;
  setLotHeight: StateSetter<string>;
  setLotWidth: StateSetter<string>;
  setShowSiteBounds: StateSetter<boolean>;
  setSiteScaleLocked: StateSetter<boolean>;
  setSiteSelectionMode: StateSetter<boolean>;
  setStatusMessage: (message: string) => void;
  siteName: string;
  units: string;
  utilities: boolean;
};

export function useDashboardSiteBoundaryDrawAction({
  buildManualFields,
  buildingCount,
  buildingDepth,
  buildingPlacements,
  buildingWidth,
  clearGeneratedPreview,
  currentProject,
  drainage,
  ensureProjectDraftRef,
  fileName,
  grading,
  markSystemsStale,
  maxAdaCrossSlopePct,
  maxParkingSlopePct,
  maxRoadGradePct,
  minSlopePct,
  parkingCount,
  payloadPreview,
  pipeMinSlopePct,
  previewRefreshIntentRef,
  projectType,
  roads,
  saveProjectRef,
  setback,
  setBuildingPlacements,
  setCurrentProject,
  setFitToSiteRequest,
  setLotHeight,
  setLotWidth,
  setShowSiteBounds,
  setSiteScaleLocked,
  setSiteSelectionMode,
  setStatusMessage,
  siteName,
  units,
  utilities,
}: UseDashboardSiteBoundaryDrawActionInput) {
  return useCallback(
    (payload: { points: Array<[number, number]> }) => {
      clearGeneratedPreview();
      const validPoints = payload.points.filter(([x, y]) => Number.isFinite(x) && Number.isFinite(y));
      if (validPoints.length < 3) {
        setStatusMessage("Draw at least three points before locking a site boundary.");
        return;
      }
      const xs = validPoints.map((pt) => pt[0]);
      const ys = validPoints.map((pt) => pt[1]);
      const minX = Math.min(...xs);
      const maxX = Math.max(...xs);
      const minY = Math.min(...ys);
      const maxY = Math.max(...ys);
      const width = Math.max(1, maxX - minX);
      const height = Math.max(1, maxY - minY);
      if (width < 10 || height < 10) {
        setStatusMessage("Drawn site boundary is too small. Add a wider boundary or set dimensions manually.");
        return;
      }
      const normalizedGeometry = validPoints.map(([x, y]) => [x - minX, y - minY] as [number, number]);
      const acres = (width * height) / SQFT_PER_ACRE;
      const siteId = `site-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
      const nextSite: BuildingPlacement = {
        id: siteId,
        label: "Site Boundary",
        type: "site",
        x: 0,
        y: 0,
        w: Number(width.toFixed(0)),
        d: Number(height.toFixed(0)),
        rotation: 0,
        locked: true,
        placed: true,
        source: "manual_drawn",
        generated: false,
        geometryType: "polygon",
        geometry: normalizedGeometry,
        capabilities: {
          movable: false,
          resizable: false,
          rotatable: false,
          deletable: false,
        },
        systemDependencies: ["roads", "parking", "grading", "drainage", "utilities"],
        meta: {
          category: "site",
          site_boundary_state: "locked_canonical",
          source: "manual_drawn",
          source_ui_mode: "canvas_draw",
          confidence: "user_drawn_review_required",
          engineering_status: "review_required",
          construction_release_allowed: false,
          units: units || "ft",
          acres: Number(acres.toFixed(3)),
          boundary_vertices: normalizedGeometry.map(([x, y], idx) => ({
            id: `${siteId}-v-${idx + 1}`,
            x,
            y,
            units: units || "ft",
          })),
        },
      };
      const nextPlacements = [
        nextSite,
        ...buildingPlacements.filter((item) => item.type !== "site"),
      ];
      const nextLotWidth = String(nextSite.w);
      const nextLotHeight = String(nextSite.d);
      const siteBoundaryGeometry: NonNullable<SiteInputs["site_boundary_geometry"]> = {
        type: "polygon",
        source: "manual_drawn",
        units: units || "ft",
        engineering_status: "review_required",
        construction_release_allowed: false,
        vertices: normalizedGeometry.map(([x, y]) => ({ x, y, units: units || "ft" })),
        bounds: {
          x: 0,
          y: 0,
          w: nextSite.w,
          h: nextSite.d,
        },
      };
      setLotWidth(nextLotWidth);
      setLotHeight(nextLotHeight);
      setSiteScaleLocked(true);
      setShowSiteBounds(false);
      setSiteSelectionMode(false);
      setFitToSiteRequest((value) => value + 1);
      setBuildingPlacements(nextPlacements);
      markSystemsStale(["roads", "parking", "grading", "drainage", "utilities"]);
      setStatusMessage(`Site boundary locked at ${nextSite.w.toFixed(0)} ft x ${nextSite.d.toFixed(0)} ft (${acres.toFixed(2)} acres).`);

      const currentInput = currentProject?.project_input ?? payloadPreview;
      const nextManualFields = buildManualFields({
        nextSiteName: siteName,
        nextFileName: fileName,
        nextUnits: units,
        nextProjectType: projectType,
        nextLotWidth,
        nextLotHeight,
        nextSetback: setback,
        nextBuildingWidth: buildingWidth,
        nextBuildingDepth: buildingDepth,
        nextBuildingCount: buildingCount,
        nextParkingCount: parkingCount,
        nextMinSlopePct: minSlopePct,
        nextPipeMinSlopePct: pipeMinSlopePct,
        nextMaxParkingSlopePct: maxParkingSlopePct,
        nextMaxRoadGradePct: maxRoadGradePct,
        nextMaxAdaCrossSlopePct: maxAdaCrossSlopePct,
        nextRoads: roads,
        nextGrading: grading,
        nextDrainage: drainage,
        nextUtilities: utilities,
        placementsOverride: nextPlacements,
      });
      const nextProjectInput: ProjectInput = {
        ...currentInput,
        input_mode: "user",
        strict_mode: false,
        allow_ai_fill_for_blanks: false,
        manual_fields: nextManualFields,
        meta: {
          ...(currentInput?.meta ?? {}),
          site_inputs: {
            ...(currentInput?.meta?.site_inputs ?? {}),
            site_alignment_locked: true,
            site_boundary_source: "manual_drawn",
            site_boundary_state: "locked_canonical",
            site_boundary_acres: Number(acres.toFixed(3)),
            site_boundary_geometry: siteBoundaryGeometry,
          },
        },
      };
      setCurrentProject((project) =>
        project
          ? {
              ...project,
              project_input: nextProjectInput,
              has_result: false,
              latest_result: undefined,
            }
          : project,
      );
      void ensureProjectDraftRef.current()
        .then(() =>
          saveProjectRef.current({
            silent: true,
            projectInputOverride: nextProjectInput,
          }),
        )
        .then(() => {
          previewRefreshIntentRef.current = {
            reason: "Refreshing preview after site boundary draw...",
            track: true,
          };
        });
    },
    [
      buildManualFields,
      buildingCount,
      buildingDepth,
      buildingPlacements,
      buildingWidth,
      clearGeneratedPreview,
      currentProject,
      drainage,
      ensureProjectDraftRef,
      fileName,
      grading,
      markSystemsStale,
      maxAdaCrossSlopePct,
      maxParkingSlopePct,
      maxRoadGradePct,
      minSlopePct,
      parkingCount,
      payloadPreview,
      pipeMinSlopePct,
      previewRefreshIntentRef,
      projectType,
      roads,
      saveProjectRef,
      setback,
      setBuildingPlacements,
      setCurrentProject,
      setFitToSiteRequest,
      setLotHeight,
      setLotWidth,
      setShowSiteBounds,
      setSiteScaleLocked,
      setSiteSelectionMode,
      setStatusMessage,
      siteName,
      units,
      utilities,
    ],
  );
}
