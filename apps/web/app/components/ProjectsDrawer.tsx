"use client";

import { useMemo, useState } from "react";
import { Archive, ArchiveRestore, Copy, RotateCcw, Trash2 } from "lucide-react";
import type { ProjectSummary } from "../types";
import { ProjectTeamMemoryPanel } from "./ProjectTeamMemoryPanel";

type ProjectsDrawerProps = {
  stateLabel: string;
  stateDetail: string;
  notice: string;
  projectTitle: string;
  activeProjectId?: string | null;
  projects: ProjectSummary[];
  deletedProjects: ProjectSummary[];
  token?: string | null;
  onNewProject: () => Promise<void> | void;
  onSaveProject: () => void;
  onOpenProject: (projectId: string) => void;
  onDeleteProject: (projectId: string) => Promise<void> | void;
  onDuplicateProject: (projectId: string) => Promise<void> | void;
  onArchiveProject: (projectId: string, archived: boolean) => Promise<void> | void;
  onRestoreProject: (projectId: string) => Promise<void> | void;
};

export function ProjectsDrawer({
  stateLabel,
  stateDetail,
  notice,
  projectTitle,
  activeProjectId,
  projects,
  deletedProjects,
  token,
  onNewProject,
  onSaveProject,
  onOpenProject,
  onDeleteProject,
  onDuplicateProject,
  onArchiveProject,
  onRestoreProject,
}: ProjectsDrawerProps) {
  const [query, setQuery] = useState("");
  const [showAll, setShowAll] = useState(false);
  const [view, setView] = useState<"active" | "archived" | "deleted">("active");
  const filteredProjects = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    const source = view === "deleted" ? deletedProjects : projects;
    return source
      .filter((project) => {
        const archived = Boolean(project.archived_at);
        if (view === "active" && archived) return false;
        if (view === "archived" && !archived) return false;
        if (!normalizedQuery) return true;
        return `${project.name || "Untitled Project"} ${project.description || ""}`.toLowerCase().includes(normalizedQuery);
      })
      .sort((a, b) => {
        if (a.project_id === activeProjectId) return -1;
        if (b.project_id === activeProjectId) return 1;
        return Number(b.updated_at || 0) - Number(a.updated_at || 0);
      });
  }, [activeProjectId, deletedProjects, projects, query, view]);
  const visibleProjects = showAll ? filteredProjects : filteredProjects.slice(0, 12);

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
      </div>
      <div className="grid grid-cols-3 gap-1 rounded-xl bg-slate-100 p-1" aria-label="Project list view">
        {(["active", "archived", "deleted"] as const).map((item) => (
          <button
            key={item}
            type="button"
            onClick={() => {
              setView(item);
              setShowAll(false);
            }}
            className={`rounded-lg px-2 py-2 text-xs font-semibold capitalize transition ${
              view === item ? "bg-white text-slate-950 shadow-sm" : "text-slate-500 hover:text-slate-800"
            }`}
          >
            {item === "deleted" ? "Recently deleted" : item === "active" ? "Active" : "Archived"}
          </button>
        ))}
      </div>
      {(view === "deleted" ? deletedProjects.length : projects.length) ? (
        <div className="space-y-2">
          <label className="block">
            <span className="sr-only">Search projects</span>
            <input
              type="search"
              value={query}
              onChange={(event) => {
                setQuery(event.target.value);
                setShowAll(false);
              }}
              placeholder="Search projects"
              className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-slate-400"
            />
          </label>
          {visibleProjects.map((projectSummary) => (
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
                  disabled={view === "deleted"}
                  className="min-w-0 flex-1 text-left disabled:cursor-default"
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
                <div className="flex shrink-0 items-center gap-1">
                  {view === "deleted" ? (
                    <button
                      type="button"
                      title="Restore project"
                      aria-label={`Restore project ${projectSummary.name || "Untitled Project"}`}
                      onClick={() => void onRestoreProject(projectSummary.project_id)}
                      className="rounded-lg border border-slate-200 p-1.5 text-slate-500 hover:bg-slate-50"
                    >
                      <RotateCcw size={14} />
                    </button>
                  ) : (
                    <>
                      <button
                        type="button"
                        title="Duplicate project"
                        aria-label={`Duplicate project ${projectSummary.name || "Untitled Project"}`}
                        onClick={() => void onDuplicateProject(projectSummary.project_id)}
                        className={projectSummary.project_id === activeProjectId ? "rounded-lg p-1.5 text-white/80 hover:bg-white/10" : "rounded-lg p-1.5 text-slate-500 hover:bg-slate-50"}
                      >
                        <Copy size={14} />
                      </button>
                      <button
                        type="button"
                        title={view === "archived" ? "Return to Active" : "Archive project"}
                        aria-label={`${view === "archived" ? "Unarchive" : "Archive"} project ${projectSummary.name || "Untitled Project"}`}
                        onClick={() => void onArchiveProject(projectSummary.project_id, view !== "archived")}
                        className={projectSummary.project_id === activeProjectId ? "rounded-lg p-1.5 text-white/80 hover:bg-white/10" : "rounded-lg p-1.5 text-slate-500 hover:bg-slate-50"}
                      >
                        {view === "archived" ? <ArchiveRestore size={14} /> : <Archive size={14} />}
                      </button>
                      <button
                        type="button"
                        title="Move to Recently Deleted"
                        aria-label={`Delete project ${projectSummary.name || "Untitled Project"}`}
                        onClick={(event) => {
                          event.stopPropagation();
                          void onDeleteProject(projectSummary.project_id);
                        }}
                        className={projectSummary.project_id === activeProjectId ? "rounded-lg p-1.5 text-white/80 hover:bg-white/10" : "rounded-lg p-1.5 text-slate-500 hover:bg-slate-50 hover:text-red-600"}
                      >
                        <Trash2 size={14} />
                      </button>
                    </>
                  )}
                </div>
              </div>
            </div>
          ))}
          {!visibleProjects.length ? (
            <div className="rounded-xl border border-dashed border-slate-300 bg-white px-4 py-5 text-center">
              <p className="text-sm font-semibold text-slate-900">No projects match that search.</p>
              <button
                type="button"
                onClick={() => setQuery("")}
                className="mt-2 text-xs font-semibold text-blue-700"
              >
                Clear search
              </button>
            </div>
          ) : null}
          {filteredProjects.length > 12 ? (
            <button
              type="button"
              onClick={() => setShowAll((value) => !value)}
              className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-50"
            >
              {showAll ? "Show recent projects" : `Show ${filteredProjects.length - 12} more`}
            </button>
          ) : null}
        </div>
      ) : (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white px-4 py-5 text-center">
          <p className="text-sm font-semibold text-slate-900">
            {view === "active" ? "No active projects yet." : view === "archived" ? "No archived projects." : "Recently Deleted is empty."}
          </p>
          <p className="mt-1 text-xs text-slate-500">
            {view === "active"
              ? "Use New Project above to start clean, then Save Project when this draft should be restored later."
              : view === "archived"
                ? "Archived projects stay saved and can return to Active at any time."
                : "Deleted projects stay recoverable here until a future retention policy purges them."}
          </p>
        </div>
      )}
      <ProjectTeamMemoryPanel projectId={activeProjectId} projectName={projectTitle} token={token} />
    </div>
  );
}
