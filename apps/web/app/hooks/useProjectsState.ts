import { useCallback, useState } from "react";

import { getJson } from "../../lib/api";

import type { ProjectRecord, ProjectSummary } from "../types";

function sortProjects(items: ProjectSummary[]) {
  return [...items].sort((a, b) => {
    const aSaved = a.has_result ? 1 : 0;
    const bSaved = b.has_result ? 1 : 0;
    if (aSaved !== bSaved) return bSaved - aSaved;
    return (b.updated_at ?? 0) - (a.updated_at ?? 0);
  });
}

export default function useProjectsState() {
  const [projects, setProjects] = useState<ProjectSummary[]>([]);

  const refreshProjects = useCallback(async (authToken: string) => {
    if (!authToken) return;
    const data = await getJson<{ projects: ProjectSummary[] }>("/api/projects", {
      token: authToken,
    });
    const nextProjects = Array.isArray(data.projects) ? data.projects : [];
    setProjects(sortProjects(nextProjects));
  }, []);

  const upsertProjectSummary = useCallback(
    (project: ProjectRecord | ProjectSummary) => {
      const summary: ProjectSummary = {
        project_id: project.project_id,
        name: project.name || "Untitled Project",
        description: project.description ?? "",
        has_result:
          typeof project.has_result === "boolean"
            ? project.has_result
            : Boolean((project as ProjectRecord).latest_result),
        updated_at: project.updated_at,
      };
      setProjects((current) => {
        const existingIndex = current.findIndex(
          (item) => item.project_id === summary.project_id,
        );
        if (existingIndex < 0) {
          return sortProjects([summary, ...current]);
        }
        const next = [...current];
        next[existingIndex] = { ...next[existingIndex], ...summary };
        return sortProjects(next);
      });
    },
    [],
  );

  const removeProjectSummary = useCallback((projectIdToRemove: string) => {
    setProjects((current) =>
      current.filter((item) => item.project_id !== projectIdToRemove),
    );
  }, []);

  return {
    projects,
    setProjects,
    refreshProjects,
    upsertProjectSummary,
    removeProjectSummary,
  };
}
