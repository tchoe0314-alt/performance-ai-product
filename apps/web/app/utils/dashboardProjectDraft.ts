import type { ProjectRecord } from "../types";
import type { DashboardSaveProjectOptions } from "../hooks/useDashboardProjectSave";

type DraftOptions = {
  token: string | null;
  demo: boolean;
  resolvedProjectId: string;
  projectId: string;
  currentProjectId?: string;
  pending: { current: Promise<ProjectRecord | null> | null };
  saveProject: (options: DashboardSaveProjectOptions) => Promise<ProjectRecord | null>;
  siteName: string;
  fileName: string;
};

/** Draft creation shares one pending save, without clearing a newer project's save. */
export async function ensureDashboardProjectDraft(options: DraftOptions): Promise<string | null> {
  if (!options.token || options.demo) return null;
  const existing = options.resolvedProjectId || options.projectId || options.currentProjectId;
  if (existing) return existing;
  if (options.pending.current) return (await options.pending.current)?.project_id ?? null;
  const request = options.saveProject({
    silent: true, projectIdOverride: null,
    nameOverride: options.siteName.trim(), fileNameOverride: options.fileName.trim(),
    autoNamedOverride: false, autoFileNamedOverride: false,
  });
  options.pending.current = request;
  try {
    return (await request)?.project_id ?? null;
  } finally {
    if (options.pending.current === request) options.pending.current = null;
  }
}
