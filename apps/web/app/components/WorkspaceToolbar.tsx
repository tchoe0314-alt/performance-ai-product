"use client";

import React from "react";
import { ChevronDown } from "lucide-react";

import type { ProjectSummary } from "../types";

type WorkspaceToolbarProps = {
  onRefreshWorkspace: () => void;
  showProjectDropdown: boolean;
  onToggleProjectDropdown: () => void;
  projects: ProjectSummary[];
  projectId: string;
  onSelectProject: (projectId: string) => void;
};

export default function WorkspaceToolbar({
  onRefreshWorkspace,
  showProjectDropdown,
  onToggleProjectDropdown,
  projects,
  projectId,
  onSelectProject,
}: WorkspaceToolbarProps) {
  return (
    <div className="flex items-center justify-between border-b border-slate-200 bg-white/80 px-4 py-3 backdrop-blur md:px-6">
      <div className="flex items-center gap-2">
        <a
          href="/upgrades"
          className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
        >
          Upgrades
        </a>
        <button
          type="button"
          onClick={onRefreshWorkspace}
          className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
        >
          Refresh
        </button>
      </div>
      <div className="relative hidden items-center gap-2 md:flex">
        <button
          type="button"
          onClick={onToggleProjectDropdown}
          className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
        >
          Projects
          <ChevronDown
            className={`h-4 w-4 transition ${showProjectDropdown ? "rotate-180" : ""}`}
          />
        </button>
        {showProjectDropdown ? (
          <div className="absolute right-0 top-full z-30 mt-2 w-[280px] overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-lg">
            <div className="border-b border-slate-200 px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
              Projects
            </div>
            <div className="max-h-[320px] overflow-y-auto p-2">
              {projects.length === 0 ? (
                <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-500">
                  No projects yet.
                </div>
              ) : (
                projects.map((project) => (
                  <button
                    key={project.project_id}
                    type="button"
                    onClick={() => onSelectProject(project.project_id)}
                    className={`flex w-full items-center justify-between rounded-xl px-3 py-2 text-left text-sm transition ${
                      project.project_id === projectId
                        ? "bg-slate-950 text-white"
                        : "text-slate-700 hover:bg-slate-100"
                    }`}
                  >
                    <span className="truncate">{project.name || "Untitled Project"}</span>
                    <span className="text-[11px] uppercase tracking-[0.12em] opacity-70">
                      {project.has_result ? "Saved" : "Draft"}
                    </span>
                  </button>
                ))
              )}
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
