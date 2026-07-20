import type { Dispatch, MutableRefObject, RefObject, SetStateAction } from "react";
import { useCallback } from "react";

import type { ProjectInput, ProjectRecord } from "../types";
import type { AutoExistingConditionsUiStatus } from "../utils/dashboardDataTypes";
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

type SaveSiteAddress = (
  addressOverride?: string,
  options?: { preserveLockedSite?: boolean; siteWidth?: number; siteHeight?: number },
) => Promise<void>;

type UpdateProjectStatus = (updates: Omit<ProjectStatusSummary, "updatedAt">) => void;

type UseDashboardSiteSetupUtilityActionsOptions = {
  autoFitSite: AutoFitSite;
  clearGeneratedPreview: () => void;
  currentProject: ProjectRecord | null;
  lastAppliedSiteRef: MutableRefObject<{ w: number; h: number; lat?: number; lng?: number } | null>;
  lotHeight: string;
  lotWidth: string;
  payloadPreview: ProjectInput;
  saveProject: SaveProject;
  saveSiteAddress: SaveSiteAddress;
  setActiveSidePanel: Dispatch<SetStateAction<SidePanelKey | null>>;
  setActiveWorkspaceMode: Dispatch<SetStateAction<WorkspaceMode>>;
  setAutoExistingConditionsStatus: Dispatch<SetStateAction<AutoExistingConditionsUiStatus>>;
  setFitToSiteRequest: Dispatch<SetStateAction<number>>;
  setLotHeight: Dispatch<SetStateAction<string>>;
  setLotWidth: Dispatch<SetStateAction<string>>;
  setPreviewInteraction: Dispatch<SetStateAction<"static" | "edit">>;
  setPreviewMode: Dispatch<SetStateAction<"2d" | "3d">>;
  setPreviewQuality: Dispatch<SetStateAction<"standard" | "high">>;
  setRenderedSidePanel: Dispatch<SetStateAction<SidePanelKey | null>>;
  setRightRailCollapsed: Dispatch<SetStateAction<boolean>>;
  setShowSiteBounds: Dispatch<SetStateAction<boolean>>;
  setSidePanelVisible: Dispatch<SetStateAction<boolean>>;
  setSiteSelectionMode: Dispatch<SetStateAction<boolean>>;
  setStatusMessage: (message: string) => void;
  siteAddress: string;
  siteAddressInputRef: RefObject<HTMLInputElement | null>;
  updateProjectStatus: UpdateProjectStatus;
  viewportCenter: { lat: number; lng: number } | null;
};

export function useDashboardSiteSetupUtilityActions({
  autoFitSite,
  clearGeneratedPreview,
  currentProject,
  lastAppliedSiteRef,
  lotHeight,
  lotWidth,
  payloadPreview,
  saveProject,
  saveSiteAddress,
  setActiveSidePanel,
  setActiveWorkspaceMode,
  setAutoExistingConditionsStatus,
  setFitToSiteRequest,
  setLotHeight,
  setLotWidth,
  setPreviewInteraction,
  setPreviewMode,
  setPreviewQuality,
  setRenderedSidePanel,
  setRightRailCollapsed,
  setShowSiteBounds,
  setSidePanelVisible,
  setSiteSelectionMode,
  setStatusMessage,
  siteAddress,
  siteAddressInputRef,
  updateProjectStatus,
  viewportCenter,
}: UseDashboardSiteSetupUtilityActionsOptions) {
  const handleCreateCenteredSiteFromSetup = useCallback(async () => {
    const address = siteAddress.trim();
    const width = parsePositiveNumber(lotWidth) ?? 1000;
    const height = parsePositiveNumber(lotHeight) ?? 1000;
    if (!address) {
      updateProjectStatus({
        state: "needs review",
        area: "setup",
        title: "Address needed",
        detail: "Type the site address first.",
        nextAction: "Enter an address, then create the centered site.",
      });
      siteAddressInputRef.current?.focus();
      return;
    }
    setLotWidth(String(Math.round(width)));
    setLotHeight(String(Math.round(height)));
    clearGeneratedPreview();
    autoFitSite(width, height, "Site Boundary", undefined, true, true, true);
    setShowSiteBounds(false);
    setSiteSelectionMode(false);
    setPreviewMode("2d");
    setPreviewQuality("high");
    setPreviewInteraction("static");
    setActiveWorkspaceMode("canvas");
    setActiveSidePanel(null);
    setRenderedSidePanel(null);
    setSidePanelVisible(false);
    setRightRailCollapsed(true);
    setFitToSiteRequest((value) => value + 1);
    updateProjectStatus({
      state: "working",
      area: "setup",
      title: "Creating centered site",
      detail: `${address} is being applied with a ${Math.round(width)} ft by ${Math.round(height)} ft site box centered on the address.`,
      nextAction: "Review the detected source context, then draw or generate inside the locked site.",
    });
    setAutoExistingConditionsStatus({
      status: "running",
      message: `Creating a ${Math.round(width)} ft by ${Math.round(height)} ft site centered on ${address}, then checking available source context.`,
      candidateCount: 0,
      missing: [],
    });
    lastAppliedSiteRef.current = {
      w: width,
      h: height,
      lat: viewportCenter?.lat,
      lng: viewportCenter?.lng,
    };
    await saveSiteAddress(address, {
      preserveLockedSite: true,
      siteWidth: width,
      siteHeight: height,
    });
  }, [
    autoFitSite,
    clearGeneratedPreview,
    lastAppliedSiteRef,
    lotHeight,
    lotWidth,
    saveSiteAddress,
    setActiveSidePanel,
    setActiveWorkspaceMode,
    setAutoExistingConditionsStatus,
    setFitToSiteRequest,
    setLotHeight,
    setLotWidth,
    setPreviewInteraction,
    setPreviewMode,
    setPreviewQuality,
    setRenderedSidePanel,
    setRightRailCollapsed,
    setShowSiteBounds,
    setSidePanelVisible,
    setSiteSelectionMode,
    siteAddress,
    siteAddressInputRef,
    updateProjectStatus,
    viewportCenter?.lat,
    viewportCenter?.lng,
  ]);

  const handleMapCenter = useCallback(
    async (payload: { lat: number; lng: number }) => {
      const currentInput = currentProject?.project_input ?? payloadPreview;
      const nextSiteInputs = {
        ...(currentInput?.meta?.site_inputs ?? {}),
        geocode: {
          ...(currentInput?.meta?.site_inputs?.geocode ?? {}),
          lat: payload.lat,
          lng: payload.lng,
          display_name: currentInput?.meta?.site_inputs?.geocode?.display_name ?? "Map center",
        },
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
        },
      });
      setFitToSiteRequest((value) => value + 1);
      setStatusMessage("Site centered on the map view.");
    },
    [currentProject, payloadPreview, saveProject, setFitToSiteRequest, setStatusMessage],
  );

  return { handleCreateCenteredSiteFromSetup, handleMapCenter };
}
