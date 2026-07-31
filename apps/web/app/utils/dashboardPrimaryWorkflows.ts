import type { PrimaryWorkflowKey } from "./dashboardTypes";
import type { SidePanelKey, WorkspaceMode } from "./workspaceShell";

export const PRIMARY_WORKFLOW_GROUPS: Record<PrimaryWorkflowKey, SidePanelKey[]> = {
  setup: ["site_existing", "import_survey", "data", "standards"],
  draw: ["model", "layers", "files"],
  objects: ["objects", "model", "details"],
  design: [
    "generate",
    "grading",
    "drainage",
    "sanitary",
    "water",
    "utilities",
    "roadway",
    "landscape",
    "system_grading",
    "system_storm",
    "system_sanitary",
    "system_water",
    "system_roadway",
    "system_utilities",
    "system_landscape",
  ],
  analyze: ["analysis", "quantities", "jobs", "catalogs", "chat"],
  deliver: ["deliverables", "reports", "settings"],
};

export function resolveActivePrimaryWorkflowKey({
  sidePanelForRender,
  activeWorkspaceMode,
}: {
  sidePanelForRender: SidePanelKey | null;
  activeWorkspaceMode: WorkspaceMode;
}): PrimaryWorkflowKey {
  const panelMatch = Object.entries(PRIMARY_WORKFLOW_GROUPS).find(([, panels]) =>
    sidePanelForRender ? panels.includes(sidePanelForRender) : false,
  )?.[0] as PrimaryWorkflowKey | undefined;
  if (panelMatch) return panelMatch;
  if (activeWorkspaceMode === "setup") return "setup";
  if (activeWorkspaceMode === "canvas" || activeWorkspaceMode === "layers") return "draw";
  if (activeWorkspaceMode === "deliver") return "deliver";
  if (activeWorkspaceMode === "data") return "setup";
  return "analyze";
}
