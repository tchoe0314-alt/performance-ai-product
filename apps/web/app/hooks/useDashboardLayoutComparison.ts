import { useCallback, type Dispatch, type MutableRefObject, type SetStateAction } from "react";
import type { BuildingPlacement, ProjectRecord, ProjectInput } from "../types";
import { liveInputFingerprint } from "../utils/liveCalculationFreshness";
import { layoutRequirementContext, type LayoutPreviewSource } from "../utils/layoutPreviewSource";
import {
  parseLayoutGoals, rerankLayoutSearch, searchLayoutAlternatives,
  type LayoutAlternativeSearch, type LayoutGoal,
} from "../utils/layoutAlternatives";

type Input = {
  placementsRef: MutableRefObject<BuildingPlacement[]>;
  projectRef: MutableRefObject<ProjectRecord | null>;
  sourceRef: MutableRefObject<LayoutPreviewSource | null>;
  inputRef?: MutableRefObject<ProjectInput>;
  setSearch: Dispatch<SetStateAction<LayoutAlternativeSearch | null>>;
  setGoals: Dispatch<SetStateAction<LayoutGoal[]>>;
  setSelectedId: Dispatch<SetStateAction<string>>;
  showComparison: () => void;
  report: (message: string) => void;
};

/** Preview-only orchestration. Applying a candidate remains an explicit transaction. */
export function useDashboardLayoutComparison({
  placementsRef, projectRef, sourceRef, inputRef, setSearch, setGoals, setSelectedId, showComparison, report,
}: Input) {
  const handleGenerateLayoutAlternatives = useCallback((count: number, goalPrompt = "") => {
    const request = parseLayoutGoals(goalPrompt);
    let inputKey: string | undefined;
    try { if (inputRef) inputKey = liveInputFingerprint(inputRef.current); }
    catch { const message = "Fix invalid project inputs before comparing layouts. The working plan is unchanged."; report(message); return message; }
    const search = searchLayoutAlternatives(placementsRef.current, count, { ...request, ...(inputRef ? layoutRequirementContext(inputRef.current) : {}) });
    sourceRef.current = {
      projectId: projectRef.current?.project_id ?? null,
      placements: JSON.stringify(placementsRef.current),
      inputKey,
    };
    setGoals(request.goals ?? []);
    setSearch(search);
    setSelectedId(search.alternatives[0]?.id ?? "");
    showComparison();
    const goalSummary = request.goals?.map(goal => goal.label).join(" and ") ?? "balanced feasibility";
    const message = search.alternatives.length
      ? `${search.alternatives.length} alternatives are ranked to ${goalSummary}. The working plan is unchanged. No modeled hard conflicts were found; unverified requirements still need review.`
      : `No valid alternative was found in ${search.searchReport.explored} candidates. ${search.searchReport.rejectionReasons.join("; ")}. Review the conflicting requirements or explicitly relax them before trying again. This bounded search does not prove that a feasible design is impossible. The working plan is unchanged.`;
    report(message);
    return message;
  }, [placementsRef, projectRef, sourceRef, inputRef, setGoals, setSearch, setSelectedId, showComparison, report]);

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
