import type { MutableRefObject } from "react";

import type { Assumption, BuildingPlacement, Issue, MapAnalysis, ProjectInput, ProjectRecord } from "../types";
import type { AddressSuggestion, AutoExistingConditionsUiStatus } from "./dashboardDataTypes";
import type { RecentChange } from "./dashboardTypes";
import {
  DEFAULT_BLANK_SITE_DEPTH_FT,
  DEFAULT_BLANK_SITE_WIDTH_FT,
  type EngineeringSystemKey,
  type SystemStatus,
} from "./workflowConstants";

type StateSetter<T> = (value: T | ((prev: T) => T)) => void;
type SaveProject = (options?: {
  silent?: boolean;
  projectIdOverride?: string | null;
  nameOverride?: string;
  fileNameOverride?: string;
  projectInputOverride?: ProjectInput;
  autoNamedOverride?: boolean;
  autoFileNamedOverride?: boolean;
}) => Promise<ProjectRecord | null>;
type AutoFitSite = (
  width: number,
  height: number,
  label?: string,
  siteIdOverride?: string | null,
  unlockSite?: boolean,
  fitMap?: boolean,
  lockSite?: boolean,
) => void;
type AnalysisPath = {
  id: string;
  buildingId: string;
  accessId: string;
  from: { x: number; y: number };
  to: { x: number; y: number };
  label: string;
  points?: Array<{ x: number; y: number }>;
};
type AnalysisIssue = {
  id: string;
  buildingId: string;
  accessId: string;
  distanceFt: number;
  thresholdFt: number;
  message: string;
  pathId: string;
  issueType: "distance" | "no_access" | "no_buildings" | "no_access_objects";
};

export type DashboardSiteSetupActions = {
  autoExistingRunKeyRef: MutableRefObject<string>;
  autoFitSite: AutoFitSite;
  clearGeneratedPreview: () => void;
  currentProject: ProjectRecord | null;
  defaultAssumptions: Assumption[];
  lastAppliedSiteRef: MutableRefObject<{ w: number; h: number; lat?: number; lng?: number } | null>;
  lastViewportSyncRef: MutableRefObject<{ w: number; h: number } | null>;
  payloadPreview: ProjectInput;
  pushRecoveryMessage: (message: string) => void;
  recordRecentChange: (change: Omit<RecentChange, "id" | "createdAt">) => void;
  saveProject: SaveProject;
  scrollToDrawingSurface: () => void;
  setActiveSidePanel: (value: null) => void;
  setActiveWorkspaceMode: (value: "canvas") => void;
  setAddressSuggestions: StateSetter<AddressSuggestion[]>;
  setAnalysisIssues: StateSetter<AnalysisIssue[]>;
  setAnalysisPaths: StateSetter<AnalysisPath[]>;
  setAnalysisSelectedIssueId: StateSetter<string | null>;
  setAssumptions: StateSetter<Assumption[]>;
  setAutoExistingConditionsStatus: StateSetter<AutoExistingConditionsUiStatus>;
  setBuildingPlacements: StateSetter<BuildingPlacement[]>;
  setCurrentProject: StateSetter<ProjectRecord | null>;
  setDetectedPlacements: StateSetter<BuildingPlacement[]>;
  setFileName: StateSetter<string>;
  setFileNameAuto: StateSetter<boolean>;
  setFitToSiteRequest: StateSetter<number>;
  setFocusDetectedId: StateSetter<string | null>;
  setFocusObjectId: StateSetter<string | null>;
  setIssues: StateSetter<Issue[]>;
  setLeftSidebarOpen: StateSetter<boolean>;
  setMapAnalysis: StateSetter<MapAnalysis | null>;
  setMapSnapshotPath: StateSetter<string>;
  setPreviewInteraction: (value: "static" | "edit") => void;
  setRenderedSidePanel: (value: null) => void;
  setRightRailCollapsed: StateSetter<boolean>;
  setSelectedAddressSuggestion: StateSetter<AddressSuggestion | null>;
  setSelectedIssueId: StateSetter<string | null>;
  setShowSiteBounds: StateSetter<boolean>;
  setSidePanelVisible: StateSetter<boolean>;
  setSiteAddress: StateSetter<string>;
  setSiteDrawRequest: StateSetter<number>;
  setSiteName: StateSetter<string>;
  setSiteNameAuto: StateSetter<boolean>;
  setSiteScaleLocked: StateSetter<boolean>;
  setSiteSelectionMode: StateSetter<boolean>;
  setStatusMessage: (message: string) => void;
  setSystemStatuses: StateSetter<Record<EngineeringSystemKey, SystemStatus>>;
  setUploadedImageApiUrl: StateSetter<string>;
  setUploadedImagePreviewUrl: StateSetter<string>;
  systemStatusesDefault: Record<EngineeringSystemKey, SystemStatus>;
};

export function runDashboardToggleSiteLock({
  actions,
  siteScaleLocked,
}: {
  actions: DashboardSiteSetupActions;
  siteScaleLocked: boolean;
}) {
  if (siteScaleLocked) return;
  const lastApplied = actions.lastAppliedSiteRef.current;
  if (lastApplied?.w && lastApplied?.h) {
    actions.autoFitSite(lastApplied.w, lastApplied.h, "Site Boundary", undefined, false, true);
  }
  actions.setSiteScaleLocked(true);
  actions.setShowSiteBounds(false);
  actions.setFitToSiteRequest((value) => value + 1);
  const currentInput = actions.currentProject?.project_input ?? actions.payloadPreview;
  void actions.saveProject({
    silent: true,
    projectInputOverride: {
      ...currentInput,
      input_mode: "user",
      strict_mode: false,
      allow_ai_fill_for_blanks: false,
      meta: {
        ...(currentInput?.meta ?? {}),
        site_inputs: {
          ...(currentInput?.meta?.site_inputs ?? {}),
          site_alignment_locked: true,
        },
      },
    },
  });
  actions.setBuildingPlacements((prevPlacements) =>
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
  actions.recordRecentChange({
    type: "site_boundary_relocked",
    label: "Site boundary relocked",
    detail: "Site boundary was locked for review drafting.",
    undoBlockedReason: "Use Change Site / Unlock to edit the boundary again.",
  });
  actions.pushRecoveryMessage("Site alignment locked. Unlock is available from Setup if you need to revise the draft boundary.");
}

export function runDashboardUnlockSite({
  actions,
  siteScaleLocked,
}: {
  actions: DashboardSiteSetupActions;
  siteScaleLocked: boolean;
}) {
  if (!siteScaleLocked) return;
  actions.setSiteScaleLocked(false);
  actions.setShowSiteBounds(true);
  actions.setSiteSelectionMode(true);
  actions.lastViewportSyncRef.current = null;
  const currentInput = actions.currentProject?.project_input ?? actions.payloadPreview;
  void actions.saveProject({
    silent: true,
    projectInputOverride: {
      ...currentInput,
      input_mode: "user",
      strict_mode: false,
      allow_ai_fill_for_blanks: false,
      meta: {
        ...(currentInput?.meta ?? {}),
        site_inputs: {
          ...(currentInput?.meta?.site_inputs ?? {}),
          site_alignment_locked: false,
        },
      },
    },
  });
  actions.setBuildingPlacements((prevPlacements) =>
    prevPlacements.map((item) =>
      item.type === "site"
        ? {
            ...item,
            locked: false,
            meta: {
              ...(item.meta ?? {}),
              site_boundary_state: "draft_editable",
              engineering_status: "review_required",
              construction_release_allowed: false,
            },
            capabilities: {
              ...item.capabilities,
              movable: true,
              resizable: true,
              rotatable: true,
            },
          }
        : item,
    ),
  );
  actions.recordRecentChange({
    type: "site_boundary_unlocked",
    label: "Site boundary unlocked",
    detail: "Site boundary is editable again; generated systems may be stale.",
    undoBlockedReason: "Relock the site boundary from Setup after review.",
  });
  actions.pushRecoveryMessage("Site unlocked for editing. Relock the boundary before running Generate.");
}

export function runDashboardStartBlankSite({ actions }: { actions: DashboardSiteSetupActions }) {
  const width = DEFAULT_BLANK_SITE_WIDTH_FT;
  const height = DEFAULT_BLANK_SITE_DEPTH_FT;
  const blankSiteName = "Blank Site";
  const blankFileName = "blank-site";
  actions.clearGeneratedPreview();
  actions.setSiteName(blankSiteName);
  actions.setFileName(blankFileName);
  actions.setSiteNameAuto(false);
  actions.setFileNameAuto(false);
  actions.setSiteAddress("");
  actions.setSelectedAddressSuggestion(null);
  actions.setAddressSuggestions([]);
  actions.setUploadedImagePreviewUrl("");
  actions.setUploadedImageApiUrl("");
  actions.setMapSnapshotPath("");
  actions.setMapAnalysis(null);
  actions.setDetectedPlacements([]);
  actions.setAnalysisIssues([]);
  actions.setAnalysisPaths([]);
  actions.setAnalysisSelectedIssueId(null);
  actions.setIssues([]);
  actions.setSelectedIssueId(null);
  actions.autoExistingRunKeyRef.current = "";
  actions.setAutoExistingConditionsStatus({
    status: "waiting",
    message: "Blank site started. Add an address later if you want Civora to auto-check public source context.",
    candidateCount: 0,
    missing: [],
  });
  actions.setAssumptions(actions.defaultAssumptions);
  actions.setFocusDetectedId(null);
  actions.setFocusObjectId(null);
  actions.setSystemStatuses(actions.systemStatusesDefault);
  actions.setSiteSelectionMode(true);
  actions.setShowSiteBounds(true);
  actions.setPreviewInteraction("edit");
  actions.autoFitSite(width, height, "Blank Site Boundary", undefined, true, false, false);
  actions.lastAppliedSiteRef.current = null;
  const currentInput = actions.currentProject?.project_input ?? actions.payloadPreview;
  const nextSiteInputs: Record<string, unknown> = {
    ...(currentInput?.meta?.site_inputs ?? {}),
    site_alignment_locked: false,
    site_boundary_source: "blank_user_defined",
    site_boundary_state: "draft_editable",
  };
  delete nextSiteInputs.address;
  delete nextSiteInputs.geocode;
  delete nextSiteInputs.map_analysis;
  delete nextSiteInputs.viewport_bounds;
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
      project_name: blankSiteName,
      lot: {
        x: 0,
        y: 0,
        w: width,
        h: height,
      },
    },
  };
  actions.setCurrentProject((project) =>
    project
      ? {
          ...project,
          name: blankSiteName,
          description: "Blank user-defined site.",
          project_input: nextProjectInput,
          latest_result: undefined,
          has_result: false,
        }
      : project,
  );
  void actions.saveProject({
    silent: true,
    nameOverride: blankSiteName,
    fileNameOverride: blankFileName,
    autoNamedOverride: false,
    autoFileNamedOverride: false,
    projectInputOverride: {
      ...nextProjectInput,
    },
  });
  actions.setActiveWorkspaceMode("canvas");
  actions.setActiveSidePanel(null);
  actions.setRenderedSidePanel(null);
  actions.setSidePanelVisible(false);
  actions.setRightRailCollapsed(true);
  actions.setSiteDrawRequest((value) => Math.max(value + 1, Date.now()));
  if (typeof window !== "undefined") {
    actions.setLeftSidebarOpen(false);
  }
  actions.scrollToDrawingSurface();
  actions.setStatusMessage("Blank site started. Set dimensions, draw the boundary, then lock it for review.");
}

export function runDashboardStartSiteBoundaryDraw({
  actions,
  height,
  unlockSite,
  width,
  siteScaleLocked,
}: {
  actions: DashboardSiteSetupActions;
  height: number | null | undefined;
  unlockSite: () => void;
  width: number | null | undefined;
  siteScaleLocked: boolean;
}) {
  if (!width || !height) {
    actions.setStatusMessage("Set site width and depth before drawing the boundary.");
    return;
  }
  if (siteScaleLocked) {
    unlockSite();
  }
  actions.setActiveWorkspaceMode("canvas");
  actions.setActiveSidePanel(null);
  actions.setRenderedSidePanel(null);
  actions.setSidePanelVisible(false);
  actions.setRightRailCollapsed(true);
  if (typeof window !== "undefined") {
    actions.setLeftSidebarOpen(false);
  }
  actions.setShowSiteBounds(true);
  actions.setSiteSelectionMode(true);
  actions.setPreviewInteraction("edit");
  actions.setSiteDrawRequest((value) => Math.max(value + 1, Date.now()));
  actions.scrollToDrawingSurface();
  actions.setStatusMessage("Draw the site boundary on the canvas. Double-click or use Finish to lock it.");
}
