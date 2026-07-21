import { useCallback, useMemo, type Dispatch, type MutableRefObject, type SetStateAction } from "react";

import type { BuildingPlacement, PlanRequestPayload, ProjectInput, ProjectRecord, SiteInputs } from "../types";
import type { GenerateFlowSummary, ReviewPackageFlowSummary } from "../utils/dashboardDataTypes";
import type { CadToolRequestForPreview } from "../utils/dashboardTypes";
import { runDashboardOpenSidePanel } from "../utils/dashboardShellActions";
import type { SidePanelKey, WorkspaceMode } from "../utils/workspaceShell";

type StateSetter<T> = (value: T | ((prev: T) => T)) => void;
type PanelProbeRef = MutableRefObject<{
  label: string;
  panel: SidePanelKey | null;
  startedAt: number;
} | null>;

type UseDashboardGenerateFlowCoordinatorInput = {
  buildingPlacements: BuildingPlacement[];
  currentProject: ProjectRecord | null;
  panelOpenProbeRef: PanelProbeRef;
  payloadPreview: PlanRequestPayload;
  saveProject: (options: { silent?: boolean; projectInputOverride?: ProjectInput }) => Promise<unknown>;
  setActiveSidePanel: StateSetter<SidePanelKey | null>;
  setActiveWorkspaceMode: StateSetter<WorkspaceMode>;
  setCadToolRequest: StateSetter<CadToolRequestForPreview | null>;
  setCurrentProject: Dispatch<SetStateAction<ProjectRecord | null>>;
  setLayerManagerOpen: StateSetter<boolean>;
  setPlacementModeEnabled: StateSetter<boolean>;
  setPreviewInteraction: StateSetter<"static" | "edit">;
  setRightRailCollapsed: StateSetter<boolean>;
  sidePanelCloseTimeoutRef: MutableRefObject<number | null>;
};

export function useDashboardGenerateFlowCoordinator({
  buildingPlacements,
  currentProject,
  panelOpenProbeRef,
  payloadPreview,
  saveProject,
  setActiveSidePanel,
  setActiveWorkspaceMode,
  setCadToolRequest,
  setCurrentProject,
  setLayerManagerOpen,
  setPlacementModeEnabled,
  setPreviewInteraction,
  setRightRailCollapsed,
  sidePanelCloseTimeoutRef,
}: UseDashboardGenerateFlowCoordinatorInput) {
  const persistFlowMetadata = useCallback(
    async (
      updates: Partial<{
        generate_flow_summary_v1: GenerateFlowSummary;
        review_package_flow_summary_v1: ReviewPackageFlowSummary;
      }>,
    ) => {
      const currentInput = currentProject?.project_input ?? payloadPreview;
      const currentInputMode = currentInput?.input_mode === "assisted" ? "assisted" : "user";
      const nextProjectInput: ProjectInput = {
        ...currentInput,
        input_mode: currentInputMode,
        strict_mode: currentInput?.strict_mode ?? false,
        allow_ai_fill_for_blanks: currentInput?.allow_ai_fill_for_blanks ?? false,
        meta: {
          ...(currentInput?.meta ?? {}),
          site_inputs: {
            ...((currentInput?.meta?.site_inputs ?? {}) as SiteInputs),
            ...updates,
          },
        },
      };
      setCurrentProject((project) =>
        project
          ? {
              ...project,
              project_input: nextProjectInput,
              updated_at: Date.now() / 1000,
            }
          : project,
      );
      await saveProject({ silent: true, projectInputOverride: nextProjectInput });
    },
    [currentProject, payloadPreview, saveProject, setCurrentProject],
  );

  const generatePendingPlacementObjects = useMemo(
    () => buildingPlacements.filter((item) => !item.placed && item.type !== "site"),
    [buildingPlacements],
  );
  const generatePendingPlacementLabels = useMemo(
    () => generatePendingPlacementObjects.map((item) => item.label),
    [generatePendingPlacementObjects],
  );

  const openGenerateBlockerPanel = useCallback(
    (panel: SidePanelKey) => {
      runDashboardOpenSidePanel({
        panel,
        panelOpenProbeRef,
        sidePanelCloseTimeoutRef,
        setActiveSidePanel,
        setActiveWorkspaceMode,
        setCadToolRequest,
        setLayerManagerOpen,
        setPlacementModeEnabled,
        setPreviewInteraction,
        setRightRailCollapsed,
      });
    },
    [
      panelOpenProbeRef,
      setActiveSidePanel,
      setActiveWorkspaceMode,
      setCadToolRequest,
      setLayerManagerOpen,
      setPlacementModeEnabled,
      setPreviewInteraction,
      setRightRailCollapsed,
      sidePanelCloseTimeoutRef,
    ],
  );

  return {
    generatePendingPlacementLabels,
    generatePendingPlacementObjects,
    openGenerateBlockerPanel,
    persistFlowMetadata,
  };
}
