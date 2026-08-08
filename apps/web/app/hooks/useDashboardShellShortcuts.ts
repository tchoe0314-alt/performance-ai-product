import { useCallback, useMemo } from "react";
import type { MutableRefObject } from "react";

import type { BuildingPlacement, ChatMessage, ProjectRecord } from "../types";
import {
  runDashboardCancelActiveTool,
  runDashboardShortcutCopySelectedObject,
  runDashboardShortcutDeleteSelectedObject,
  runDashboardShortcutOpenDrawCanvas,
  runDashboardShortcutOpenGenerate,
  runDashboardShortcutOpenProjects,
  runDashboardShortcutPasteSelectedObject,
  runDashboardShortcutSaveProject,
} from "../utils/dashboardShortcutActions";
import {
  runDashboardRedoDraftAction,
  runDashboardUndoDraftAction,
  runDashboardUndoRecentChange,
} from "../utils/dashboardRecoveryActions";
import {
  runDashboardCloseSidePanel,
  runDashboardOpenPanelFromDrawer,
  runDashboardOpenSidePanel,
  runDashboardOpenWorkspaceMode,
  runDashboardTriggerCadTool,
} from "../utils/dashboardShellActions";
import { cloneBuildingPlacementForUndo } from "../utils/dashboardObjectManagerTrace";
import { getObjectEditBlocker } from "../utils/objectGeometry";
import type {
  CadToolRequestForPreview,
  DraftUndoAction,
  RecentChange,
} from "../utils/dashboardTypes";
import type { EngineeringSystemKey } from "../utils/workflowConstants";
import type {
  ProjectStatusSummary,
  SidePanelKey,
  WorkspaceMode,
} from "../utils/workspaceShell";

type StateSetter<T> = (value: T | ((prev: T) => T)) => void;
type AppendChatMessage = (role: ChatMessage["role"], content: string, kind?: ChatMessage["kind"]) => void;
type UpdateProjectStatus = (updates: Omit<ProjectStatusSummary, "updatedAt">) => void;
type RecordRecentChange = (change: Omit<RecentChange, "id" | "createdAt">) => void;
type SystemsImpactedByPlacement = (target?: Partial<BuildingPlacement> | null) => EngineeringSystemKey[];
type SaveProjectResult = ProjectRecord | null | undefined;

type PanelProbeRef = MutableRefObject<{
  label: string;
  panel: SidePanelKey | null;
  startedAt: number;
} | null>;

type UseDashboardShellShortcutsOptions = {
  activePlacementId: string | null;
  activeSidePanel: SidePanelKey | null;
  appendChatMessage: AppendChatMessage;
  buildingPlacements: BuildingPlacement[];
  clearDraftUndoAction: () => void;
  currentProjectId: string | undefined;
  effectiveDemoWorkspaceEnabled: boolean;
  handleObjectManagerBulkDelete: () => void;
  handleObjectManagerCopy: (item: BuildingPlacement) => void;
  handleObjectManagerPaste: () => void;
  handleRemoveBuilding: (id: string) => void;
  handleRestoreBuilding: (object: BuildingPlacement) => void;
  isSeededDemoProjectId: (projectId: string | null) => boolean;
  lastDraftAction: DraftUndoAction | null;
  lastDraftActionRef: MutableRefObject<DraftUndoAction | null>;
  markSystemsStale: (systems: EngineeringSystemKey[]) => void;
  objectClipboard: BuildingPlacement[];
  panelCloseProbeRef: PanelProbeRef;
  panelOpenProbeRef: PanelProbeRef;
  previewFullscreenOpen: boolean;
  projectId: string | null;
  pushRecoveryMessage: (message: string) => void;
  recordDraftRedoAction: (action: DraftUndoAction) => void;
  recordDraftUndoAction: (action: DraftUndoAction) => void;
  recordRecentChange: RecordRecentChange;
  redoDraftAction: DraftUndoAction | null;
  redoDraftActionRef: MutableRefObject<DraftUndoAction | null>;
  reportObjectActionBlocker: (message: string) => void;
  resolvedProjectIdRef: MutableRefObject<string>;
  saveProject: () => Promise<SaveProjectResult>;
  selectedObjectIds: string[];
  setActivePlacementId: StateSetter<string | null>;
  setActiveSidePanel: StateSetter<SidePanelKey | null>;
  setActiveWorkspaceMode: StateSetter<WorkspaceMode>;
  setBuildingPlacements: StateSetter<BuildingPlacement[]>;
  setCadToolRequest: StateSetter<CadToolRequestForPreview | null>;
  setLayerManagerOpen: StateSetter<boolean>;
  setLeftSidebarOpen: StateSetter<boolean>;
  setObjectClipboard: StateSetter<BuildingPlacement[]>;
  setObjectManagerStatusMessage: (message: string) => void;
  setPendingClarification: (value: null) => void;
  setPlacementModeEnabled: StateSetter<boolean>;
  setPreviewFullscreenOpen: (value: boolean) => void;
  setPreviewInteraction: StateSetter<"static" | "edit">;
  setRenderedSidePanel: StateSetter<SidePanelKey | null>;
  setRightRailCollapsed: StateSetter<boolean>;
  setSelectedObjectIds: StateSetter<string[]>;
  setShortcutsOverlayOpen: (value: boolean) => void;
  setSidePanelVisible: StateSetter<boolean>;
  setStatusMessage: (message: string) => void;
  setWorkspaceChromeMinimized: StateSetter<boolean>;
  sidePanelCloseTimeoutRef: MutableRefObject<number | null>;
  shortcutsOverlayOpen: boolean;
  systemsImpactedByPlacement: SystemsImpactedByPlacement;
  token: string | null;
  updateProjectStatus: UpdateProjectStatus;
};

export function useDashboardShellShortcuts({
  activePlacementId,
  activeSidePanel,
  appendChatMessage,
  buildingPlacements,
  clearDraftUndoAction,
  currentProjectId,
  effectiveDemoWorkspaceEnabled,
  handleObjectManagerBulkDelete,
  handleObjectManagerCopy,
  handleObjectManagerPaste,
  handleRemoveBuilding,
  handleRestoreBuilding,
  isSeededDemoProjectId,
  lastDraftAction,
  lastDraftActionRef,
  markSystemsStale,
  objectClipboard,
  panelCloseProbeRef,
  panelOpenProbeRef,
  previewFullscreenOpen,
  projectId,
  pushRecoveryMessage,
  recordDraftRedoAction,
  recordDraftUndoAction,
  recordRecentChange,
  redoDraftAction,
  redoDraftActionRef,
  reportObjectActionBlocker,
  resolvedProjectIdRef,
  saveProject,
  selectedObjectIds,
  setActivePlacementId,
  setActiveSidePanel,
  setActiveWorkspaceMode,
  setBuildingPlacements,
  setCadToolRequest,
  setLayerManagerOpen,
  setLeftSidebarOpen,
  setObjectClipboard,
  setObjectManagerStatusMessage,
  setPendingClarification,
  setPlacementModeEnabled,
  setPreviewFullscreenOpen,
  setPreviewInteraction,
  setRenderedSidePanel,
  setRightRailCollapsed,
  setSelectedObjectIds,
  setShortcutsOverlayOpen,
  setSidePanelVisible,
  setStatusMessage,
  setWorkspaceChromeMinimized,
  sidePanelCloseTimeoutRef,
  shortcutsOverlayOpen,
  systemsImpactedByPlacement,
  token,
  updateProjectStatus,
}: UseDashboardShellShortcutsOptions) {
  const handleOpenSidePanel = useCallback((panel: SidePanelKey | null) => {
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
    if (panel) {
      setRenderedSidePanel(panel);
      setSidePanelVisible(true);
    }
  }, [
    panelOpenProbeRef,
    setActiveSidePanel,
    setActiveWorkspaceMode,
    setCadToolRequest,
    setLayerManagerOpen,
    setPlacementModeEnabled,
    setPreviewInteraction,
    setRenderedSidePanel,
    setRightRailCollapsed,
    setSidePanelVisible,
    sidePanelCloseTimeoutRef,
  ]);

  const handleCloseSidePanel = useCallback(() => {
    runDashboardCloseSidePanel({
      activeSidePanel,
      panelCloseProbeRef,
      sidePanelCloseTimeoutRef,
      setActiveSidePanel,
      setRenderedSidePanel,
      setRightRailCollapsed,
      setSidePanelVisible,
    });
  }, [
    activeSidePanel,
    panelCloseProbeRef,
    setActiveSidePanel,
    setRenderedSidePanel,
    setRightRailCollapsed,
    setSidePanelVisible,
    sidePanelCloseTimeoutRef,
  ]);

  const handleOpenPanelFromDrawer = useCallback((panel: SidePanelKey) => {
    runDashboardOpenPanelFromDrawer({
      panel,
      openSidePanel: handleOpenSidePanel,
    });
  }, [handleOpenSidePanel]);

  const handleOpenWorkspaceMode = useCallback((mode: WorkspaceMode) => {
    runDashboardOpenWorkspaceMode({
      mode,
      openSidePanel: handleOpenSidePanel,
      setActiveWorkspaceMode,
      setLeftSidebarOpen,
    });
  }, [handleOpenSidePanel, setActiveWorkspaceMode, setLeftSidebarOpen]);

  const triggerCadTool = useCallback((tool: CadToolRequestForPreview["tool"], label: string) => {
    runDashboardTriggerCadTool({
      label,
      setActiveSidePanel,
      setActiveWorkspaceMode,
      setCadToolRequest,
      setPreviewInteraction,
      setRightRailCollapsed,
      setStatusMessage,
      setWorkspaceChromeMinimized,
      tool,
    });
  }, [
    setActiveSidePanel,
    setActiveWorkspaceMode,
    setCadToolRequest,
    setPreviewInteraction,
    setRightRailCollapsed,
    setStatusMessage,
    setWorkspaceChromeMinimized,
  ]);

  const handleCancelActiveTool = useCallback(() => {
    runDashboardCancelActiveTool({
      shortcutsOverlayOpen,
      activeSidePanel,
      previewFullscreenOpen,
      closeSidePanel: handleCloseSidePanel,
      setShortcutsOverlayOpen,
      setPreviewFullscreenOpen,
      setPlacementModeEnabled,
      setActivePlacementId,
      setSelectedObjectIds,
      setPendingClarification,
      setPreviewInteraction,
      setCadToolRequestSelect: () => setCadToolRequest({ id: Date.now() + Math.random(), tool: "select" }),
      updateProjectStatus,
    });
  }, [
    activeSidePanel,
    handleCloseSidePanel,
    previewFullscreenOpen,
    setActivePlacementId,
    setCadToolRequest,
    setPendingClarification,
    setPlacementModeEnabled,
    setPreviewFullscreenOpen,
    setPreviewInteraction,
    setSelectedObjectIds,
    setShortcutsOverlayOpen,
    shortcutsOverlayOpen,
    updateProjectStatus,
  ]);

  const handleDeleteSelectedObject = useCallback(() => {
    runDashboardShortcutDeleteSelectedObject({
      selectedObjectIds,
      activePlacementId,
      buildingPlacements,
      bulkDelete: handleObjectManagerBulkDelete,
      removeBuilding: handleRemoveBuilding,
      setObjectManagerStatusMessage,
      appendChatMessage,
      updateProjectStatus,
    });
  }, [
    activePlacementId,
    appendChatMessage,
    buildingPlacements,
    handleObjectManagerBulkDelete,
    handleRemoveBuilding,
    selectedObjectIds,
    setObjectManagerStatusMessage,
    updateProjectStatus,
  ]);

  const handleCopySelectedObject = useCallback(() => {
    runDashboardShortcutCopySelectedObject({
      selectedObjectIds,
      activePlacementId,
      buildingPlacements,
      getObjectEditBlocker,
      cloneBuildingPlacementForUndo,
      setObjectClipboard,
      setObjectManagerStatusMessage,
      setStatusMessage,
      reportObjectActionBlocker,
      copyObject: handleObjectManagerCopy,
      updateProjectStatus,
    });
  }, [
    activePlacementId,
    buildingPlacements,
    handleObjectManagerCopy,
    reportObjectActionBlocker,
    selectedObjectIds,
    setObjectClipboard,
    setObjectManagerStatusMessage,
    setStatusMessage,
    updateProjectStatus,
  ]);

  const handlePasteSelectedObject = useCallback(() => {
    runDashboardShortcutPasteSelectedObject({
      objectClipboard,
      pasteObject: handleObjectManagerPaste,
      updateProjectStatus,
    });
  }, [handleObjectManagerPaste, objectClipboard, updateProjectStatus]);

  const recoveryActions = useMemo(() => ({
    setBuildingPlacements,
    setSelectedObjectIds,
    setActivePlacementId,
    setPlacementModeEnabled,
    setObjectManagerStatusMessage,
    setStatusMessage,
    pushRecoveryMessage,
    appendChatMessage,
    updateProjectStatus,
    recordRecentChange,
    markSystemsStale,
    systemsImpactedByPlacement,
    handleRestoreBuilding,
  }), [
    appendChatMessage,
    handleRestoreBuilding,
    markSystemsStale,
    pushRecoveryMessage,
    recordRecentChange,
    setActivePlacementId,
    setBuildingPlacements,
    setObjectManagerStatusMessage,
    setPlacementModeEnabled,
    setSelectedObjectIds,
    setStatusMessage,
    systemsImpactedByPlacement,
    updateProjectStatus,
  ]);

  const handleUndoDraftAction = useCallback(() => {
    runDashboardUndoDraftAction({
      draftAction: lastDraftActionRef.current ?? lastDraftAction,
      clearDraftAction: () => {
        lastDraftActionRef.current = null;
        clearDraftUndoAction();
      },
      recordDraftRedoAction,
      actions: recoveryActions,
    });
  }, [clearDraftUndoAction, lastDraftAction, lastDraftActionRef, recordDraftRedoAction, recoveryActions]);

  const handleRedoDraftAction = useCallback(() => {
    runDashboardRedoDraftAction({
      redoAction: redoDraftActionRef.current ?? redoDraftAction,
      recordDraftUndoAction,
      actions: recoveryActions,
    });
  }, [recordDraftUndoAction, recoveryActions, redoDraftAction, redoDraftActionRef]);

  const handleUndoRecentChange = useCallback((change: RecentChange) => {
    runDashboardUndoRecentChange({
      change,
      recordDraftRedoAction,
      actions: recoveryActions,
    });
  }, [recordDraftRedoAction, recoveryActions]);

  const handleShortcutSaveProject = useCallback(() => {
    const effectiveProjectId = resolvedProjectIdRef.current || projectId || currentProjectId || null;
    runDashboardShortcutSaveProject({
      effectiveProjectId,
      token,
      demoWorkspaceEnabled: effectiveDemoWorkspaceEnabled,
      isSeededDemoProjectId,
      saveProject,
      appendChatMessage,
      updateProjectStatus,
    });
  }, [
    appendChatMessage,
    currentProjectId,
    effectiveDemoWorkspaceEnabled,
    isSeededDemoProjectId,
    projectId,
    resolvedProjectIdRef,
    saveProject,
    token,
    updateProjectStatus,
  ]);

  const handleShortcutOpenGenerate = useCallback(() => {
    runDashboardShortcutOpenGenerate({
      openSidePanel: handleOpenSidePanel,
      updateProjectStatus,
    });
  }, [handleOpenSidePanel, updateProjectStatus]);

  const handleShortcutOpenDrawCanvas = useCallback(() => {
    runDashboardShortcutOpenDrawCanvas({
      openWorkspaceMode: handleOpenWorkspaceMode,
      openSidePanel: handleOpenSidePanel,
      updateProjectStatus,
    });
  }, [handleOpenSidePanel, handleOpenWorkspaceMode, updateProjectStatus]);

  const handleShortcutOpenProjects = useCallback(() => {
    runDashboardShortcutOpenProjects({
      openSidePanel: handleOpenSidePanel,
      updateProjectStatus,
    });
  }, [handleOpenSidePanel, updateProjectStatus]);

  return {
    handleCancelActiveTool,
    handleCloseSidePanel,
    handleCopySelectedObject,
    handleDeleteSelectedObject,
    handleOpenPanelFromDrawer,
    handleOpenSidePanel,
    handleOpenWorkspaceMode,
    handlePasteSelectedObject,
    handleRedoDraftAction,
    handleShortcutOpenDrawCanvas,
    handleShortcutOpenGenerate,
    handleShortcutOpenProjects,
    handleShortcutSaveProject,
    handleUndoDraftAction,
    handleUndoRecentChange,
    triggerCadTool,
  };
}
