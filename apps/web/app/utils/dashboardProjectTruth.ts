type ProjectTruthRecord = {
  project_id?: string | null;
  updated_at?: number | null;
};

type BuildProjectTruthLabelsOptions = {
  effectiveDemoWorkspaceEnabled: boolean;
  workspaceRestoreState: "idle" | "restoring" | "restored" | "failed";
  currentProject?: ProjectTruthRecord | null;
  token?: string | null;
  projectDrawerNotice?: string;
};

export type ProjectTruthLabels = {
  restoreTruthLabel: string;
  projectDrawerStateLabel: string;
  projectDrawerStateDetail: string;
};

export function buildProjectTruthLabels({
  effectiveDemoWorkspaceEnabled,
  workspaceRestoreState,
  currentProject,
  token,
  projectDrawerNotice = "",
}: BuildProjectTruthLabelsOptions): ProjectTruthLabels {
  const restoreTruthLabel =
    workspaceRestoreState === "failed"
      ? "Could not restore saved workspace"
      : effectiveDemoWorkspaceEnabled
        ? "Local demo only"
        : workspaceRestoreState === "restored" && currentProject?.project_id
          ? "Restored saved workspace"
          : currentProject?.project_id && currentProject?.updated_at
            ? "Project saved; restore available after reload"
            : currentProject?.project_id
              ? "Project saved; restore status pending"
              : "Restore unavailable";

  const projectDrawerStateLabel =
    effectiveDemoWorkspaceEnabled
      ? "Local demo"
      : workspaceRestoreState === "failed"
        ? "Could not restore"
        : currentProject?.project_id
          ? "Saved"
          : token
            ? "Unsaved draft"
            : "Restore unavailable";

  const projectDrawerStateDetail =
    effectiveDemoWorkspaceEnabled
      ? "Demo changes stay local and are not saved to project storage."
      : workspaceRestoreState === "failed"
        ? projectDrawerNotice || "The saved project could not be restored from the backend."
        : currentProject?.project_id
          ? "This browser can restore the active saved project after reload."
          : token
            ? "This clean workspace has not been saved yet."
            : "Sign in and connect to the backend to list, save, open, or delete projects.";

  return {
    restoreTruthLabel,
    projectDrawerStateLabel,
    projectDrawerStateDetail,
  };
}
