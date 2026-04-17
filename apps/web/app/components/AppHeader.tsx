"use client";

import React, { useMemo, useState } from "react";

import type { ProjectSummary } from "../types";

type AppHeaderProps = {
  userEmail: string;
  projects: ProjectSummary[];
  activeProjectId: string;
  onSelectProject: (projectId: string) => void;
  onViewDocs: (projectId: string) => void;
  onLogout: () => void;
};

export default function AppHeader({
  userEmail,
  projects,
  activeProjectId,
  onSelectProject,
  onViewDocs,
  onLogout,
}: AppHeaderProps) {
  const [openMenu, setOpenMenu] = useState<"projects" | "docs" | null>(null);
  const hasProjects = projects.length > 0;
  const sortedProjects = useMemo(
    () =>
      [...projects].sort((a, b) => (b.updated_at ?? 0) - (a.updated_at ?? 0)),
    [projects],
  );

  return (
    <header className="w-full bg-[radial-gradient(circle_at_top,#1f2937_0%,#0b1120_55%,#0a0f1d_100%)] text-white">
      <div className="mx-auto flex w-full max-w-7xl items-center justify-between px-6 py-4">
        <div className="flex items-center gap-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-full border border-white/20 bg-white/10 text-lg font-semibold">
            C
          </div>
          <div>
            <p className="text-lg font-semibold tracking-tight">Civora AI</p>
            <p className="text-xs uppercase tracking-[0.3em] text-white/60">Autonomous Civil</p>
          </div>
        </div>
        <nav className="relative hidden items-center gap-6 text-sm font-medium text-white/80 md:flex">
          <button
            type="button"
            onClick={() => setOpenMenu((value) => (value === "projects" ? null : "projects"))}
            className={`transition ${openMenu === "projects" ? "text-white" : "text-white/70 hover:text-white"}`}
          >
            Projects
          </button>
          <button type="button" className="border-b-2 border-white pb-1 text-white">Knowledge Base</button>
          <button
            type="button"
            onClick={() => setOpenMenu((value) => (value === "docs" ? null : "docs"))}
            className={`transition ${openMenu === "docs" ? "text-white" : "text-white/70 hover:text-white"}`}
          >
            Docs
          </button>
          {openMenu === "projects" ? (
            <div className="absolute left-0 top-full z-40 mt-4 w-[280px] overflow-hidden rounded-2xl border border-white/10 bg-slate-900/95 shadow-xl">
              <div className="border-b border-white/10 px-4 py-3 text-xs font-semibold uppercase tracking-[0.2em] text-white/60">
                Projects
              </div>
              <div className="max-h-[320px] overflow-y-auto p-2">
                {hasProjects ? (
                  sortedProjects.map((project) => (
                    <button
                      key={project.project_id}
                      type="button"
                      onClick={() => {
                        onSelectProject(project.project_id);
                        setOpenMenu(null);
                      }}
                      className={`flex w-full items-center justify-between rounded-xl px-3 py-2 text-left text-sm transition ${
                        project.project_id === activeProjectId
                          ? "bg-white/10 text-white"
                          : "text-white/70 hover:bg-white/5 hover:text-white"
                      }`}
                    >
                      <span className="truncate">{project.name || "Untitled Project"}</span>
                      <span className="text-[11px] uppercase tracking-[0.2em] text-white/50">
                        {project.has_result ? "Saved" : "Draft"}
                      </span>
                    </button>
                  ))
                ) : (
                  <div className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs text-white/60">
                    No projects yet.
                  </div>
                )}
              </div>
            </div>
          ) : null}
          {openMenu === "docs" ? (
            <div className="absolute left-32 top-full z-40 mt-4 w-[320px] overflow-hidden rounded-2xl border border-white/10 bg-slate-900/95 shadow-xl">
              <div className="border-b border-white/10 px-4 py-3 text-xs font-semibold uppercase tracking-[0.2em] text-white/60">
                Preview Docs
              </div>
              <div className="max-h-[320px] overflow-y-auto p-3">
                {hasProjects ? (
                  <div className="grid gap-2">
                    {sortedProjects.map((project) => (
                      <div
                        key={project.project_id}
                        className="flex items-center justify-between rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm"
                      >
                        <div className="min-w-0">
                          <p className="truncate text-white">{project.name || "Untitled Project"}</p>
                          <p className="text-xs text-white/50">
                            {project.has_result ? "Preview available" : "No preview yet"}
                          </p>
                        </div>
                        <button
                          type="button"
                          onClick={() => {
                            onViewDocs(project.project_id);
                            setOpenMenu(null);
                          }}
                          className="rounded-full border border-white/20 bg-white/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.2em] text-white/80 transition hover:bg-white/20"
                        >
                          View
                        </button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs text-white/60">
                    No previews yet.
                  </div>
                )}
              </div>
            </div>
          ) : null}
        </nav>
        <div className="flex items-center gap-3">
          <span className="hidden rounded-full border border-white/20 bg-white/10 px-3 py-1 text-xs text-white/70 md:inline-flex">
            {userEmail}
          </span>
          <button
            type="button"
            onClick={onLogout}
            className="rounded-full border border-white/20 bg-white/10 px-3 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-white/80 transition hover:bg-white/20"
          >
            Sign Out
          </button>
        </div>
      </div>
    </header>
  );
}
