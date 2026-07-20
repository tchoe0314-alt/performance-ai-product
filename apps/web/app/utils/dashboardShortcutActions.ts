import type { ChatMessage, ProjectRecord } from "../types";
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
