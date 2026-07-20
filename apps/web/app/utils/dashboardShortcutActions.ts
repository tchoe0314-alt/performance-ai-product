import type { BuildingPlacement, ChatMessage, ProjectRecord } from "../types";
import type { ProjectStatusSummary, SidePanelKey, WorkspaceMode } from "./workspaceShell";

type SaveProjectResult = ProjectRecord | null | undefined;

export function runDashboardShortcutSaveProject({
  effectiveProjectId,
  token,
  demoWorkspaceEnabled,
  isSeededDemoProjectId,
  saveProject,
  appendChatMessage,
  updateProjectStatus,
}: {
  effectiveProjectId: string | null;
  token: string | null;
  demoWorkspaceEnabled: boolean;
  isSeededDemoProjectId: (projectId: string | null) => boolean;
  saveProject: () => Promise<SaveProjectResult>;
  appendChatMessage: (role: ChatMessage["role"], content: string, kind?: ChatMessage["kind"]) => void;
  updateProjectStatus: (updates: Omit<ProjectStatusSummary, "updatedAt">) => void;
}) {
  if (!token) {
    appendChatMessage("assistant", "Sign in/connect backend to save projects.", "status");
    updateProjectStatus({
      state: "blocked",
      area: "projects",
      title: "Save needs sign-in",
      detail: "Sign in/connect backend to save projects.",
      nextAction: "Sign in or reconnect backend, then press Cmd/Ctrl+S again.",
    });
    return;
  }
  if (demoWorkspaceEnabled && isSeededDemoProjectId(effectiveProjectId)) {
    appendChatMessage("assistant", "Demo workspace changes stay local and are not saved to pilot projects.", "status");
    updateProjectStatus({
      state: "blocked",
      area: "projects",
      title: "Save unavailable in demo",
      detail: "Demo workspace changes stay local and are not saved to pilot projects.",
      nextAction: "Start a non-demo project or sign in/connect backend before saving.",
    });
    return;
  }
  void saveProject().then((project) => {
    appendChatMessage(
      "assistant",
      project
        ? `Saved project "${project.name || "Untitled Project"}".`
        : "Sign in/connect backend to save projects.",
      "status",
    );
  });
}

export function runDashboardCancelActiveTool({
  shortcutsOverlayOpen,
  activeSidePanel,
  previewFullscreenOpen,
  closeSidePanel,
  setShortcutsOverlayOpen,
  setPreviewFullscreenOpen,
  setPlacementModeEnabled,
  setActivePlacementId,
  setSelectedObjectIds,
  setPendingClarification,
  setPreviewInteraction,
  setCadToolRequestSelect,
  updateProjectStatus,
}: {
  shortcutsOverlayOpen: boolean;
  activeSidePanel: SidePanelKey | null;
  previewFullscreenOpen: boolean;
  closeSidePanel: () => void;
  setShortcutsOverlayOpen: (value: boolean) => void;
  setPreviewFullscreenOpen: (value: boolean) => void;
  setPlacementModeEnabled: (value: boolean) => void;
  setActivePlacementId: (value: string | null) => void;
  setSelectedObjectIds: (value: string[]) => void;
  setPendingClarification: (value: null) => void;
  setPreviewInteraction: (value: "static" | "edit") => void;
  setCadToolRequestSelect: () => void;
  updateProjectStatus: UpdateProjectStatus;
}) {
  if (shortcutsOverlayOpen) {
    setShortcutsOverlayOpen(false);
    return;
  }
  if (activeSidePanel === "projects" && document.querySelector('[data-testid="projects-drawer"]')) {
    closeSidePanel();
    updateProjectStatus({
      state: "ready",
      area: "projects",
      title: "Projects closed",
      detail: "Projects drawer closed.",
      nextAction: "Continue from the canvas or use / for commands.",
    });
    return;
  }
  if (previewFullscreenOpen) setPreviewFullscreenOpen(false);
  setPlacementModeEnabled(false);
  setActivePlacementId(null);
  setSelectedObjectIds([]);
  setPendingClarification(null);
  setPreviewInteraction("static");
  setCadToolRequestSelect();
  updateProjectStatus({
    state: "ready",
    area: "chat",
    title: "Active tool cancelled",
    detail: "Active drawing/tool state cancelled.",
    nextAction: "Select another tool, continue drawing, or use the command bar.",
  });
}

export function runDashboardShortcutOpenGenerate({
  openSidePanel,
  updateProjectStatus,
}: {
  openSidePanel: (panel: SidePanelKey) => void;
  updateProjectStatus: (updates: Omit<ProjectStatusSummary, "updatedAt">) => void;
}) {
  openSidePanel("generate");
  updateProjectStatus({
    state: "ready",
    area: "generate",
    title: "Generate opened",
    detail: "Generate panel opened.",
    nextAction: "Choose a focused system or run the unambiguous generate control.",
  });
}

export function runDashboardShortcutOpenDrawCanvas({
  openWorkspaceMode,
  openSidePanel,
  updateProjectStatus,
}: {
  openWorkspaceMode: (mode: WorkspaceMode) => void;
  openSidePanel: (panel: SidePanelKey) => void;
  updateProjectStatus: (updates: Omit<ProjectStatusSummary, "updatedAt">) => void;
}) {
  openWorkspaceMode("canvas");
  openSidePanel("objects");
  updateProjectStatus({
    state: "ready",
    area: "setup",
    title: "Draw opened",
    detail: "Draw Canvas mode opened.",
    nextAction: "Select a draw/object tool or use the command bar.",
  });
}

export function runDashboardShortcutOpenProjects({
  openSidePanel,
  updateProjectStatus,
}: {
  openSidePanel: (panel: SidePanelKey) => void;
  updateProjectStatus: (updates: Omit<ProjectStatusSummary, "updatedAt">) => void;
}) {
  openSidePanel("projects");
  updateProjectStatus({
    state: "ready",
    area: "projects",
    title: "Projects opened",
    detail: "Projects drawer opened.",
    nextAction: "Save, open, or delete a project from the drawer.",
  });
}

type UpdateProjectStatus = (updates: Omit<ProjectStatusSummary, "updatedAt">) => void;
type AppendChatMessage = (role: ChatMessage["role"], content: string, kind?: ChatMessage["kind"]) => void;
type ObjectEditAction = "rename" | "style" | "type" | "hide" | "delete" | "copy" | "transform" | "resize";

export function runDashboardShortcutDeleteSelectedObject({
  selectedObjectIds,
  activePlacementId,
  buildingPlacements,
  bulkDelete,
  removeBuilding,
  setObjectManagerStatusMessage,
  appendChatMessage,
  updateProjectStatus,
}: {
  selectedObjectIds: string[];
  activePlacementId: string | null;
  buildingPlacements: BuildingPlacement[];
  bulkDelete: () => void;
  removeBuilding: (id: string) => void;
  setObjectManagerStatusMessage: (message: string) => void;
  appendChatMessage: AppendChatMessage;
  updateProjectStatus: UpdateProjectStatus;
}) {
  if (selectedObjectIds.length > 1) {
    bulkDelete();
    return;
  }
  const target = activePlacementId
    ? buildingPlacements.find((item) => item.id === activePlacementId)
    : selectedObjectIds[0]
      ? buildingPlacements.find((item) => item.id === selectedObjectIds[0])
      : null;
  if (!target) {
    const message = "Select an editable object before deleting.";
    setObjectManagerStatusMessage(message);
    updateProjectStatus({
      state: "blocked",
      area: "chat",
      title: "Delete needs a selection",
      detail: "No object is selected.",
      nextAction: "Select an editable draft object, then press Delete again.",
    });
    appendChatMessage("assistant", message, "status");
    return;
  }
  if (target.type === "site" || target.capabilities?.deletable === false) {
    const message = `${target.label} cannot be deleted from shortcuts.`;
    setObjectManagerStatusMessage(message);
    updateProjectStatus({
      state: "blocked",
      area: "chat",
      title: "Open Object Manager",
      detail: `${target.label} cannot be deleted from shortcuts.`,
      nextAction: "Open Object Manager to review object locks and capabilities.",
    });
    appendChatMessage("assistant", message, "status");
    return;
  }
  if (target.locked) {
    const message = `Unlock ${target.label} before deleting it.`;
    setObjectManagerStatusMessage(message);
    updateProjectStatus({
      state: "blocked",
      area: "chat",
      title: "Delete needs unlock",
      detail: `Unlock ${target.label} before deleting it.`,
      nextAction: "Open Object Manager, unlock the object if appropriate, then delete.",
    });
    appendChatMessage("assistant", message, "status");
    return;
  }
  removeBuilding(target.id);
  appendChatMessage("assistant", `Deleted ${target.label}.`, "status");
  updateProjectStatus({
    state: "stale",
    area: "chat",
    title: "Object deleted",
    detail: `Deleted ${target.label}. Generated systems may be stale.`,
    nextAction: "Undo if needed, or rerun affected generated systems.",
  });
}

export function runDashboardShortcutCopySelectedObject({
  selectedObjectIds,
  activePlacementId,
  buildingPlacements,
  getObjectEditBlocker,
  cloneBuildingPlacementForUndo,
  setObjectClipboard,
  setObjectManagerStatusMessage,
  setStatusMessage,
  reportObjectActionBlocker,
  copyObject,
  updateProjectStatus,
}: {
  selectedObjectIds: string[];
  activePlacementId: string | null;
  buildingPlacements: BuildingPlacement[];
  getObjectEditBlocker: (item: BuildingPlacement, action: ObjectEditAction) => string | null;
  cloneBuildingPlacementForUndo: (item: BuildingPlacement) => BuildingPlacement;
  setObjectClipboard: (items: BuildingPlacement[]) => void;
  setObjectManagerStatusMessage: (message: string) => void;
  setStatusMessage: (message: string) => void;
  reportObjectActionBlocker: (message: string) => void;
  copyObject: (item: BuildingPlacement) => void;
  updateProjectStatus: UpdateProjectStatus;
}) {
  if (selectedObjectIds.length > 1) {
    const targets = buildingPlacements.filter((item) => selectedObjectIds.includes(item.id));
    const editable = targets.filter((item) => !getObjectEditBlocker(item, "copy"));
    const blockedCount = targets.length - editable.length;
    if (!editable.length) {
      reportObjectActionBlocker("Select editable draft objects before copying.");
      updateProjectStatus({
        state: "blocked",
        area: "chat",
        title: "Copy needs editable objects",
        detail: "Selected objects are locked, source-only, or required project evidence.",
        nextAction: "Select editable draft objects, then press Cmd/Ctrl+C again.",
      });
      return;
    }
    setObjectClipboard(editable.map(cloneBuildingPlacementForUndo));
    const message = `Copied ${editable.length} selected draft object${editable.length === 1 ? "" : "s"}${blockedCount ? `; ${blockedCount} blocked.` : "."}`;
    setObjectManagerStatusMessage(message);
    setStatusMessage(message);
    updateProjectStatus({
      state: "ready",
      area: "chat",
      title: "Objects copied",
      detail: message,
      nextAction: "Press Cmd/Ctrl+V or use Paste to place draft duplicates.",
    });
    return;
  }
  const target = activePlacementId
    ? buildingPlacements.find((item) => item.id === activePlacementId)
    : selectedObjectIds[0]
      ? buildingPlacements.find((item) => item.id === selectedObjectIds[0])
      : null;
  if (!target) {
    reportObjectActionBlocker("Select an editable draft object before copying.");
    updateProjectStatus({
      state: "blocked",
      area: "chat",
      title: "Copy needs a selection",
      detail: "No object is selected.",
      nextAction: "Select an editable draft object, then press Cmd/Ctrl+C again.",
    });
    return;
  }
  copyObject(target);
  updateProjectStatus({
    state: "ready",
    area: "chat",
    title: "Object copied",
    detail: `Copied ${target.label}.`,
    nextAction: "Press Cmd/Ctrl+V or use Paste to place a draft duplicate.",
  });
}

export function runDashboardShortcutPasteSelectedObject({
  objectClipboard,
  pasteObject,
  updateProjectStatus,
}: {
  objectClipboard: BuildingPlacement[];
  pasteObject: () => void;
  updateProjectStatus: UpdateProjectStatus;
}) {
  pasteObject();
  const clipboardCount = objectClipboard.length;
  updateProjectStatus({
    state: clipboardCount ? "stale" : "blocked",
    area: "chat",
    title: clipboardCount ? (clipboardCount === 1 ? "Object pasted" : "Objects pasted") : "Paste needs a copied object",
    detail: clipboardCount
      ? clipboardCount === 1
        ? `Pasted ${objectClipboard[0].label} as an editable draft duplicate.`
        : `Pasted ${clipboardCount} copied draft objects as editable draft duplicates.`
      : "Copy an editable object before pasting.",
    nextAction: clipboardCount
      ? "Move, rename, or regenerate affected systems after review."
      : "Select an editable draft object, then press Cmd/Ctrl+C.",
  });
}
