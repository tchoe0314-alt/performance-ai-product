import { useCallback, type Dispatch, type MutableRefObject, type SetStateAction } from "react";
import type { BuildingPlacement, ProjectRecord } from "../types";
import {
  parseLayoutGoals, rerankLayoutSearch, searchLayoutAlternatives,
  type LayoutAlternativeSearch, type LayoutGoal,
} from "../utils/layoutAlternatives";

type Input = {
  placementsRef: MutableRefObject<BuildingPlacement[]>;
  projectRef: MutableRefObject<ProjectRecord | null>;
  sourceRef: MutableRefObject<{ projectId: string | null; placements: string } | null>;
  setSearch: Dispatch<SetStateAction<LayoutAlternativeSearch | null>>;
  setGoals: Dispatch<SetStateAction<LayoutGoal[]>>;
  setSelectedId: Dispatch<SetStateAction<string>>;
  showComparison: () => void;
  report: (message: string) => void;
};

/** Preview-only orchestration. Applying a candidate remains an explicit transaction. */
export function useDashboardLayoutComparison({
  placementsRef, projectRef, sourceRef, setSearch, setGoals, setSelectedId, showComparison, report,
}: Input) {
  const handleGenerateLayoutAlternatives = useCallback((count: number, goalPrompt = "") => {
    const request = parseLayoutGoals(goalPrompt);
    const search = searchLayoutAlternatives(placementsRef.current, count, request);
    sourceRef.current = {
      projectId: projectRef.current?.project_id ?? null,
      placements: JSON.stringify(placementsRef.current),
    };
    setGoals(request.goals ?? []);
    setSearch(search);
    setSelectedId(search.alternatives[0]?.id ?? "");
    showComparison();
    const goalSummary = request.goals?.map(goal => goal.label).join(" and ") ?? "balanced feasibility";
    report(search.alternatives.length
      ? `${search.alternatives.length} alternatives are ranked to ${goalSummary}. The working plan is unchanged. No modeled hard conflicts were found; unverified requirements still need review.`
      : `No valid alternative was found in ${search.searchReport.explored} candidates. ${search.searchReport.rejectionReasons.join("; ")}. Review the conflicting requirements or explicitly relax them before trying again. This bounded search does not prove that a feasible design is impossible. The working plan is unchanged.`);
  }, [placementsRef, projectRef, sourceRef, setGoals, setSearch, setSelectedId, showComparison, report]);

  const handleCancelLayoutAlternatives = useCallback(() => {
    setSearch(null);
    setSelectedId("");
    setGoals([]);
    report("Layout comparison closed. The working plan was not changed.");
  }, [setSearch, setSelectedId, setGoals, report]);

  const handleLayoutAlternativeGoalsChange = useCallback((goals: LayoutGoal[]) => {
    const effectiveGoals = goals.length ? goals : parseLayoutGoals("").goals ?? [];
    setGoals(effectiveGoals);
    setSearch(current => current ? rerankLayoutSearch(current, effectiveGoals) : null);
    report(`Layout options reranked to ${effectiveGoals.map(goal => goal.label).join(" and ")}. The working plan is unchanged.`);
  }, [setGoals, setSearch, report]);

  return { handleGenerateLayoutAlternatives, handleCancelLayoutAlternatives, handleLayoutAlternativeGoalsChange };
}
