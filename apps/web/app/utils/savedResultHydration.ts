export function shouldRetrySavedResultHydration(input: {
  token: string | null;
  workspaceRestoreState: string;
  projectId?: string | null;
  hasBackendResult: boolean;
}): boolean {
  return Boolean(
    input.token &&
    input.workspaceRestoreState === "restored" &&
    input.projectId &&
    !input.hasBackendResult,
  );
}

export function shouldDiscardSavedResultResponse(input: {
  requestId: number;
  latestRequestId: number;
  workspaceGeneration: number;
  latestWorkspaceGeneration: number;
  requestedProjectId: string;
  activeProjectId: string;
}): boolean {
  if (input.requestId !== input.latestRequestId) return true;
  if (input.workspaceGeneration === input.latestWorkspaceGeneration) return false;
  // Restoring the same project can legitimately advance the workspace
  // generation while a large saved result is in flight. Only discard the
  // response when that generation change also points at a different project.
  return input.activeProjectId !== input.requestedProjectId;
}
