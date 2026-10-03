import { useEffect, useRef } from "react";
import type { ProjectRecord } from "../types";
import { buildDashboardSiteRestore, type DashboardSiteRestoreState } from "../utils/dashboardSiteRestore";

type RestoreSetters = {
  [K in keyof DashboardSiteRestoreState as `set${Capitalize<K>}`]: (value: DashboardSiteRestoreState[K]) => void;
};

/** Restores loaded context once per project; save acknowledgements must not replace live edits. */
export function useDashboardSiteRestore(project: ProjectRecord | null, token: string | null, setters: RestoreSetters, generation: number, loading: boolean) {
  const restoredProject = useRef("");
  useEffect(() => {
    if (!project) { restoredProject.current = ""; return; }
    if (loading) return;
    const restoreKey = `${generation}:${project.project_id}`;
    if (restoredProject.current === restoreKey) return;
    restoredProject.current = restoreKey;
    const state = buildDashboardSiteRestore(project.project_input ?? {}, token);
    for (const key of Object.keys(state) as Array<keyof DashboardSiteRestoreState>) {
      // Each mapped setter receives exactly its corresponding restoration field.
      const setter = setters[`set${key[0].toUpperCase()}${key.slice(1)}` as keyof RestoreSetters] as (value: DashboardSiteRestoreState[typeof key]) => void;
      setter(state[key]);
    }
  }, [project, token, setters, generation, loading]);
}
