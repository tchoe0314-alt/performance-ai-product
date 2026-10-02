import { useCallback, type MutableRefObject } from "react";
import type { BuildingPlacement, ProjectRecord } from "../types";
import type { DraftUndoAction, RecentChange } from "../utils/dashboardTypes";
import type { EngineeringSystemKey } from "../utils/workflowConstants";
import { resolveDependencyProposal, type CanonicalDependencyProposal } from "../utils/canonicalDependencyPolicies";
import { planCanonicalBatchTransaction, type CanonicalBatchEdit } from "../utils/canonicalBatchTransaction";
import { guardedTransactionSave } from "../utils/guardedTransactionSave";

type Input = {
  proposal: CanonicalDependencyProposal | null;
  placementsRef: MutableRefObject<BuildingPlacement[]>;
  projectRef: MutableRefObject<ProjectRecord | null>;
  generationRef: MutableRefObject<number>;
  ensureDraftRef: MutableRefObject<() => Promise<string | null>>;
  saveRef: MutableRefObject<(options?: { silent?: boolean }) => Promise<unknown>>;
  refreshIntentRef: MutableRefObject<{ reason: string; track?: boolean } | null>;
  setPlacements: (placements: BuildingPlacement[]) => void;
  setProposal: (proposal: CanonicalDependencyProposal | null) => void;
  clearPreview: () => void;
  markStale: (systems?: EngineeringSystemKey[]) => void;
  recordUndo: (action: DraftUndoAction) => void;
  recordChange: (change: Omit<RecentChange, "id" | "createdAt">) => void;
  report: (message: string) => void;
  reportObject: (message: string) => void;
  recover: (message: string) => void;
};

/** Transaction orchestration only; pure planners own geometry and dependency policy. */
export function useDashboardPlacementTransactions({
  proposal, placementsRef, projectRef, generationRef, ensureDraftRef, saveRef,
  refreshIntentRef, setPlacements, setProposal, clearPreview, markStale,
  recordUndo, recordChange, report, reportObject, recover,
}: Input) {
  const persist = useCallback((placements: BuildingPlacement[], failure: string, refreshReason?: string) => {
    const snapshot = JSON.stringify(placements);
    const generation = generationRef.current;
    void guardedTransactionSave({
      isCurrent: () => generationRef.current === generation && JSON.stringify(placementsRef.current) === snapshot,
      ensureDraft: () => ensureDraftRef.current(),
      save: () => saveRef.current({ silent: true }),
      refresh: refreshReason ? () => { refreshIntentRef.current = { reason: refreshReason, track: true }; } : undefined,
      onFailure: () => recover(failure),
    });
  }, [generationRef, placementsRef, ensureDraftRef, saveRef, refreshIntentRef, recover]);

  const commit = useCallback((placements: BuildingPlacement[], undo: DraftUndoAction,
    change: Omit<RecentChange, "id" | "createdAt" | "undo">) => {
    placementsRef.current = placements;
    setPlacements(placements);
    clearPreview();
    markStale(["roads", "parking", "grading", "drainage", "utilities"]);
    recordUndo(undo);
    recordChange({ ...change, undo });
  }, [placementsRef, setPlacements, clearPreview, markStale, recordUndo, recordChange]);

  const handleAcceptDependencyProposal = useCallback(() => {
    if (!proposal) return;
    const result = resolveDependencyProposal(proposal, placementsRef.current, projectRef.current?.project_id ?? null);
    if (!result.accepted) {
      setProposal(null);
      report(result.reason);
      reportObject(result.reason);
      recover(result.reason);
      return;
    }
    const undo = { action: "bulk_update" as const, before: proposal.before, after: proposal.after,
      label: `accepted parking proposal for ${proposal.buildingLabel}` };
    setProposal(null);
    commit(result.placements, undo, { type: "object_style_changed", label: "Linked parking proposal accepted",
      detail: `Accepted the complete ${proposal.after.length}-object transaction for ${proposal.buildingLabel}.` });
    const message = "Complete dependency proposal accepted. Undo restores all previous object positions.";
    report(message);
    reportObject(message);
    recover(message);
    persist(result.placements, "The accepted revision remains in the working plan, but saving failed. Retry Save Project.",
      "Refreshing preview after accepting linked parking...");
  }, [proposal, placementsRef, projectRef, setProposal, report, reportObject, recover, commit, persist]);

  const handleRejectDependencyProposal = useCallback(() => {
    if (!proposal) return;
    setProposal(null);
    const message = "Dependency proposal rejected. The entire working plan stayed unchanged.";
    report(message);
    reportObject(message);
  }, [proposal, setProposal, report, reportObject]);

  const handleCanonicalBatchEdit = useCallback((edits: CanonicalBatchEdit[], label: string) => {
    const result = planCanonicalBatchTransaction(placementsRef.current, edits,
      projectRef.current?.project_id ?? null, label, `batch-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`);
    if (result.status === "blocked") {
      report(result.reason);
      recover(result.reason);
      return "blocked" as const;
    }
    if (result.proposal) {
      setProposal(result.proposal);
      report("Review the complete commercial revision before applying. The working plan is unchanged.");
      return "proposed" as const;
    }
    const undo = { action: "bulk_update" as const, before: result.before, after: result.after, label };
    commit(result.placements, undo, { type: "object_type_changed", label,
      detail: `${result.after.length} objects revised in one transaction.` });
    persist(result.placements, "The revision remains in the working plan, but saving needs attention. Retry Save Project.");
    return "applied" as const;
  }, [placementsRef, projectRef, report, recover, setProposal, commit, persist]);

  return { handleAcceptDependencyProposal, handleRejectDependencyProposal, handleCanonicalBatchEdit };
}
