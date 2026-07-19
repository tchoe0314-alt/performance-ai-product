import type { ProjectSummary } from "../types";

type ProjectsDrawerProps = {
  stateLabel: string;
  stateDetail: string;
  notice: string;
  projectTitle: string;
  activeProjectId?: string | null;
  projects: ProjectSummary[];
  onNewProject: () => Promise<void> | void;
  onSaveProject: () => void;
  onOpenJobs: () => void;
  onOpenProject: (projectId: string) => void;
  onDeleteProject: (projectId: string) => Promise<void> | void;
};

export function ProjectsDrawer({
  stateLabel,
  stateDetail,
  notice,
  projectTitle,
  activeProjectId,
  projects,
  onNewProject,
  onSaveProject,
  onOpenJobs,
  onOpenProject,
  onDeleteProject,
}: ProjectsDrawerProps) {
  return (
    <div className="space-y-4" data-testid="projects-drawer">
      <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
        <div className="flex items-center justify-between gap-3">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
            Project state
          </p>
          <span
            data-testid="project-drawer-state"
            className={`rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${
              stateLabel === "Saved"
                ? "bg-emerald-50 text-emerald-700"
                : stateLabel === "Could not restore"
                  ? "bg-red-50 text-red-700"
                  : "bg-amber-50 text-amber-700"
            }`}
          >
            {stateLabel}
          </span>
        </div>
        <p className="mt-2 text-sm font-semibold text-slate-900">
          {projectTitle || "Untitled Project"}
        </p>
        <p data-testid="project-drawer-detail" className="mt-1 text-xs leading-5 text-slate-600">
          {notice || stateDetail}
        </p>
        <p className="mt-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">
          Review-only workspace. Civora does not stamp, seal, sign, certify, approve construction, submit construction documents, or act as engineer of record.
        </p>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <button
          type="button"
          onClick={() => {
            void onNewProject();
          }}
          className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50"
        >
          New Project
        </button>
        <button
          type="button"
          onClick={onSaveProject}
          className="rounded-xl border border-slate-950 bg-slate-950 px-3 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-slate-800"
        >
          Save Project
        </button>
        <button
          type="button"
          onClick={onOpenJobs}
          className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50"
        >
          Open Jobs
        </button>
      </div>
      {projects.length ? (
        <div className="space-y-2">
          {projects.map((projectSummary) => (
            <div
              key={projectSummary.project_id}
              className={`w-full rounded-xl border px-3 py-3 text-left transition ${
                projectSummary.project_id === activeProjectId
                  ? "border-slate-900 bg-slate-950 text-white"
                  : "border-slate-200 bg-white text-slate-700"
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <button
                  type="button"
                  aria-label={`Open project ${projectSummary.name || "Untitled Project"}`}
                  onClick={() => {
                    onOpenProject(projectSummary.project_id);
                  }}
                  className="min-w-0 flex-1 text-left"
                >
                  <p className="truncate text-sm font-semibold">
                    {projectSummary.name || "Untitled Project"}
                  </p>
                  <p className="mt-1 text-xs uppercase tracking-[0.12em] opacity-70">
                    {projectSummary.description ||
                      (projectSummary.updated_at
                        ? `Updated ${new Date(projectSummary.updated_at * 1000).toLocaleDateString()}`
                        : "No description")}
                  </p>
                </button>
                <button
                  type="button"
                  aria-label={`Delete project ${projectSummary.name || "Untitled Project"}`}
                  onClick={(event) => {
                    event.stopPropagation();
                    void onDeleteProject(projectSummary.project_id);
                  }}
                  className={`shrink-0 rounded-lg border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${
                    projectSummary.project_id === activeProjectId
                      ? "border-white/40 text-white/80 hover:bg-white/10"
                      : "border-slate-200 text-slate-500 hover:bg-slate-50"
                  }`}
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white px-4 py-5 text-center">
          <p className="text-sm font-semibold text-slate-900">No saved projects yet.</p>
          <p className="mt-1 text-xs text-slate-500">
            Start clean, then Save Project when this draft should be restored later.
          </p>
          <button
            type="button"
            onClick={() => {
              void onNewProject();
            }}
            className="mt-3 rounded-xl border border-slate-950 bg-slate-950 px-3 py-2 text-sm font-semibold text-white"
          >
            New Project
          </button>
        </div>
      )}
    </div>
  );
}
