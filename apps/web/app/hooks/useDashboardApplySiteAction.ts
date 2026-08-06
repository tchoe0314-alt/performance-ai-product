import type { Dispatch, MutableRefObject, SetStateAction } from "react";
import { useCallback } from "react";

import type { BuildingPlacement, ProjectInput, ProjectRecord, SiteInputs } from "../types";
import { OVERSIZED_SITE_MESSAGE, SITE_WARNING_ACRES, siteAreaAcresFromSize } from "../utils/workflowConstants";
import { parsePositiveNumber } from "../utils/formatting";
import type { ProjectStatusSummary, SidePanelKey, WorkspaceMode } from "../utils/workspaceShell";

type SaveProject = (options?: {
  silent?: boolean;
  projectInputOverride?: ProjectInput;
}) => Promise<ProjectRecord | null>;

type AutoFitSite = (
  width: number,
  height: number,
  label?: string,
  siteIdOverride?: string | null,
  fitMap?: boolean,
  lockSite?: boolean,
  preserveExistingObjects?: boolean,
) => void;

type UpdateProjectStatus = (updates: Omit<ProjectStatusSummary, "updatedAt">) => void;

type ViewportFootprint = {
  widthFt: number;
  heightFt: number;
  bounds?: {
    north: number;
    south: number;
    east: number;
    west: number;
    centerLat: number;
    centerLng: number;
  };
};

type UseDashboardApplySiteActionOptions = {
  applyingSiteRef: MutableRefObject<boolean>;
  autoFitSite: AutoFitSite;
  buildingPlacements: BuildingPlacement[];
  currentProject: ProjectRecord | null;
  hasSiteBoundary: () => boolean;
  lastAppliedSiteRef: MutableRefObject<{ w: number; h: number; lat?: number; lng?: number } | null>;
  lotHeight: string;
  lotWidth: string;
  payloadPreview: ProjectInput;
  runAutoExistingConditionsAfterSiteLock: (projectInputOverride?: ProjectInput) => Promise<void>;
  saveProject: SaveProject;
  setActiveSidePanel: Dispatch<SetStateAction<SidePanelKey | null>>;
  setActiveWorkspaceMode: Dispatch<SetStateAction<WorkspaceMode>>;
  setBuildingPlacements: Dispatch<SetStateAction<BuildingPlacement[]>>;
  setCurrentProject: Dispatch<SetStateAction<ProjectRecord | null>>;
  setFitToSiteRequest: Dispatch<SetStateAction<number>>;
  setLeftSidebarOpen: Dispatch<SetStateAction<boolean>>;
  setRenderedSidePanel: Dispatch<SetStateAction<SidePanelKey | null>>;
  setRightRailCollapsed: Dispatch<SetStateAction<boolean>>;
  setShowSiteBounds: Dispatch<SetStateAction<boolean>>;
  setSidePanelVisible: Dispatch<SetStateAction<boolean>>;
  setSiteScaleLocked: Dispatch<SetStateAction<boolean>>;
  setSiteSelectionMode: Dispatch<SetStateAction<boolean>>;
  siteScaleLocked: boolean;
  updateProjectStatus: UpdateProjectStatus;
  viewportCenter: { lat: number; lng: number } | null;
  viewportFootprint: ViewportFootprint | null;
};

export function useDashboardApplySiteAction({
  applyingSiteRef,
  autoFitSite,
  buildingPlacements,
  currentProject,
  hasSiteBoundary,
  lastAppliedSiteRef,
  lotHeight,
  lotWidth,
  payloadPreview,
  runAutoExistingConditionsAfterSiteLock,
  saveProject,
  setActiveSidePanel,
  setActiveWorkspaceMode,
  setBuildingPlacements,
  setCurrentProject,
  setFitToSiteRequest,
  setLeftSidebarOpen,
  setRenderedSidePanel,
  setRightRailCollapsed,
  setShowSiteBounds,
  setSidePanelVisible,
  setSiteScaleLocked,
  setSiteSelectionMode,
  siteScaleLocked,
  updateProjectStatus,
  viewportCenter,
  viewportFootprint,
}: UseDashboardApplySiteActionOptions) {
  return useCallback(async () => {
    if (applyingSiteRef.current) return;
    if (siteScaleLocked) {
      if (hasSiteBoundary()) {
        updateProjectStatus({
          state: "ready",
          area: "setup",
          title: "Site already locked",
          detail: "Site boundary is already locked.",
          nextAction: "Open Generate when you are ready to create review drafts.",
        });
        return;
      }
      setSiteScaleLocked(false);
    }
    applyingSiteRef.current = true;
    const currentInput = currentProject?.project_input ?? payloadPreview;
    const visibleWidth = parsePositiveNumber(lotWidth);
    const visibleHeight = parsePositiveNumber(lotHeight);
    const invalidVisibleWidth = Boolean(lotWidth.trim()) && !visibleWidth;
    const invalidVisibleHeight = Boolean(lotHeight.trim()) && !visibleHeight;
    if (invalidVisibleWidth || invalidVisibleHeight) {
      updateProjectStatus({
        state: "blocked",
        area: "setup",
        title: "Apply site needs size",
        detail: "Enter a positive width and height in feet before locking the site.",
        nextAction: "Correct the width/depth, or clear both fields to use the drawn boundary dimensions.",
      });
      applyingSiteRef.current = false;
      return;
    }
    const width = visibleWidth ?? viewportFootprint?.widthFt;
    const height = visibleHeight ?? viewportFootprint?.heightFt;
    if (!width || !height) {
      updateProjectStatus({
        state: "blocked",
        area: "setup",
        title: "Apply site needs size",
        detail: "Set the site width and height before applying the site.",
        nextAction: "Type width/depth or draw a site boundary, then lock the site.",
      });
      applyingSiteRef.current = false;
      return;
    }
    const selectedAreaAcres = siteAreaAcresFromSize(width, height);
    if (selectedAreaAcres > SITE_WARNING_ACRES) {
      updateProjectStatus({
        state: "blocked",
        area: "setup",
        title: "Apply site needs smaller area",
        detail: OVERSIZED_SITE_MESSAGE,
        nextAction: "Reduce the site area or zoom to a smaller review boundary.",
      });
      applyingSiteRef.current = false;
      return;
    }
    updateProjectStatus({
      state: "working",
      area: "setup",
      title: "Applying site",
      detail: "Civora is locking the site boundary and preparing site context checks.",
      nextAction: "Wait for the boundary to lock, then review source context results.",
    });
    const existingSite = buildingPlacements.find((item) => item.type === "site");
    if (existingSite && !existingSite.locked) {
      const existingBoundarySource = currentInput?.meta?.site_inputs?.site_boundary_source ?? existingSite.source;
      const normalizedBoundarySource: SiteInputs["site_boundary_source"] =
        existingBoundarySource === "manual_drawn" ||
        existingBoundarySource === "map_viewport" ||
        existingBoundarySource === "imported"
          ? existingBoundarySource
          : "dimensions";
      const nextSiteInputs: SiteInputs = {
        ...(currentInput?.meta?.site_inputs ?? {}),
        site_alignment_locked: true,
        site_boundary_state: "locked_canonical",
        site_boundary_source: normalizedBoundarySource,
      };
      const nextProjectInput: ProjectInput = {
        ...currentInput,
        input_mode: "user",
        strict_mode: false,
        allow_ai_fill_for_blanks: false,
        meta: {
          ...(currentInput?.meta ?? {}),
          site_inputs: nextSiteInputs,
        },
        manual_fields: {
          ...(currentInput?.manual_fields ?? {}),
          lot: {
            x: existingSite.x ?? 0,
            y: existingSite.y ?? 0,
            w: width,
            h: height,
          },
        },
      };
      setSiteScaleLocked(true);
      setShowSiteBounds(false);
      setSiteSelectionMode(false);
      setActiveWorkspaceMode("canvas");
      setActiveSidePanel(null);
      setRenderedSidePanel(null);
      setRightRailCollapsed(true);
      setSidePanelVisible(false);
      setFitToSiteRequest((value) => value + 1);
      setBuildingPlacements((prevPlacements) =>
        prevPlacements.map((item) =>
          item.type === "site"
            ? {
                ...item,
                locked: true,
                meta: {
                  ...(item.meta ?? {}),
                  site_boundary_state: "locked_canonical",
                  engineering_status: "review_required",
                  construction_release_allowed: false,
                },
                capabilities: {
                  ...item.capabilities,
                  movable: false,
                  resizable: false,
                  rotatable: false,
                },
              }
            : item,
        ),
      );
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
      await saveProject({
        silent: true,
        projectInputOverride: nextProjectInput,
      });
      lastAppliedSiteRef.current = {
        w: width,
        h: height,
        lat: viewportCenter?.lat,
        lng: viewportCenter?.lng,
      };
      applyingSiteRef.current = false;
      updateProjectStatus({
        state: "working",
        area: "setup",
        title: "Detecting site context",
        detail: "Site boundary locked. Checking available existing-condition sources inside the site.",
        nextAction: "Review found candidates or needs before generating.",
      });
      void runAutoExistingConditionsAfterSiteLock(nextProjectInput);
      return;
    }
    const lastApplied = lastAppliedSiteRef.current;
    if (
      lastApplied &&
      Math.abs(lastApplied.w - width) < 1 &&
      Math.abs(lastApplied.h - height) < 1 &&
      (!viewportCenter ||
        (Math.abs((lastApplied.lat ?? 0) - viewportCenter.lat) < 1e-6 &&
          Math.abs((lastApplied.lng ?? 0) - viewportCenter.lng) < 1e-6))
    ) {
      updateProjectStatus({
        state: "ready",
        area: "setup",
        title: "Site already applied",
        detail: "Site already matches the current viewport.",
        nextAction: "Open Generate when you are ready to create review drafts.",
      });
      applyingSiteRef.current = false;
      return;
    }
    autoFitSite(width, height, "Site Boundary", undefined, false, true);
    setShowSiteBounds(false);
    setSiteScaleLocked(true);
    const nextSiteInputs = {
      ...(currentInput?.meta?.site_inputs ?? {}),
      site_alignment_locked: true,
      ...(viewportFootprint?.bounds
        ? {
            viewport_bounds: {
              north: viewportFootprint.bounds.north,
              south: viewportFootprint.bounds.south,
              east: viewportFootprint.bounds.east,
              west: viewportFootprint.bounds.west,
              center_lat: viewportFootprint.bounds.centerLat,
              center_lng: viewportFootprint.bounds.centerLng,
              width_ft: width,
              height_ft: height,
            },
          }
        : {}),
      ...(viewportCenter
        ? {
            geocode: {
              ...(currentInput?.meta?.site_inputs?.geocode ?? {}),
              lat: viewportCenter.lat,
              lng: viewportCenter.lng,
              display_name: currentInput?.meta?.site_inputs?.geocode?.display_name ?? "Map center",
            },
          }
        : {}),
    };
    await saveProject({
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
        manual_fields: {
          ...(currentInput?.manual_fields ?? {}),
          lot: {
            x: 0,
            y: 0,
            w: width,
            h: height,
          },
        },
      },
    });
    setSiteSelectionMode(false);
    setActiveWorkspaceMode("canvas");
    setActiveSidePanel(null);
    setRenderedSidePanel(null);
    setRightRailCollapsed(true);
    setSidePanelVisible(false);
    if (typeof window !== "undefined" && window.innerWidth < 1024) {
      setLeftSidebarOpen(false);
    }
    updateProjectStatus({
      state: "working",
      area: "setup",
      title: "Detecting site context",
      detail: "Site applied and locked. Civora is checking source context inside the site.",
      nextAction: "Review found candidates or needs before generating.",
    });
    lastAppliedSiteRef.current = {
      w: width,
      h: height,
      lat: viewportCenter?.lat,
      lng: viewportCenter?.lng,
    };
    applyingSiteRef.current = false;
    void runAutoExistingConditionsAfterSiteLock({
      ...currentInput,
      input_mode: "user",
      strict_mode: false,
      allow_ai_fill_for_blanks: false,
      meta: {
        ...(currentInput?.meta ?? {}),
        site_inputs: nextSiteInputs,
      },
      manual_fields: {
        ...(currentInput?.manual_fields ?? {}),
        lot: {
          x: 0,
          y: 0,
          w: width,
          h: height,
        },
      },
    });
  }, [
    applyingSiteRef,
    autoFitSite,
    buildingPlacements,
    currentProject,
    hasSiteBoundary,
    lastAppliedSiteRef,
    lotHeight,
    lotWidth,
    payloadPreview,
    runAutoExistingConditionsAfterSiteLock,
    saveProject,
    setActiveSidePanel,
    setActiveWorkspaceMode,
    setBuildingPlacements,
    setCurrentProject,
    setFitToSiteRequest,
    setLeftSidebarOpen,
    setRenderedSidePanel,
    setRightRailCollapsed,
    setShowSiteBounds,
    setSidePanelVisible,
    setSiteScaleLocked,
    setSiteSelectionMode,
    siteScaleLocked,
    updateProjectStatus,
    viewportCenter,
    viewportFootprint,
  ]);
}
