import type { PlanMeta } from "../types";
import {
  EMPTY_REACTIVE_VALIDATION,
  REACTIVE_EDIT_POLICY_PREFERENCE,
  REACTIVE_SYSTEM_STAGE_MAP,
  type EngineeringSystemKey,
  type ReactiveValidationState,
  type SystemGenerationTarget,
  type SystemStatus,
} from "./workflowConstants";

type StateSetter<T> = (value: T | ((prev: T) => T)) => void;

export function buildDashboardReactiveChangedSystems(
  systemStatuses: Record<string, SystemStatus>,
): EngineeringSystemKey[] {
  return (Object.entries(systemStatuses) as Array<[EngineeringSystemKey, SystemStatus]>)
    .filter(([, status]) => status === "stale")
    .map(([system]) => system);
}

export function buildDashboardReactiveChangedTargets(
  reactiveChangedSystems: EngineeringSystemKey[],
): string[] {
  return Array.from(
    new Set(
      reactiveChangedSystems.flatMap((system) => REACTIVE_SYSTEM_STAGE_MAP[system] ?? []),
    ),
  );
}

export function buildDashboardReactiveRerunSummary(currentPlanMeta: PlanMeta) {
  const partial = currentPlanMeta.reactive_partial_rerun ?? {};
  const report = currentPlanMeta.reactive_update_report ?? {};
  const telemetry = partial.telemetry ?? report.partial_rerun_telemetry ?? {};
  const rerunStages = partial.rerun_stages ?? telemetry.rerun_stages ?? report.impacted_stages ?? [];
  const skippedStages = partial.skipped_stages ?? telemetry.skipped_stages ?? report.skipped_stages ?? [];
  const graphNodes = report.dependency_graph?.nodes ?? [];
  const graphEdges = report.dependency_graph?.edges ?? [];
  const affectedRows =
    report.affected_system_report?.affected_stages ??
    report.impact_matrix?.map((row) => ({
      stage: row.stage,
      why: row.why,
      reason_codes: row.reason_codes,
      rerun_required: true,
    })) ??
    [];
  const skippedRows =
    report.affected_system_report?.skipped_stages ??
    skippedStages.map((stage) => ({
      stage,
      why: "No changed upstream dependency reaches this stage.",
      rerun_required: false,
    }));
  const comparisonRows =
    report.post_rerun_stage_status?.map((row) => ({
      stage: row.stage,
      before: row.before ?? "stale",
      after: row.after ?? (row.completed ? "complete" : "stale"),
      changed: false,
      rerun_required: true,
      skipped: false,
    })) ??
    report.before_after_comparison ??
    [];
  return {
    enabled: Boolean(partial.enabled || report.partial_rerun_executed),
    checkpointRestored: Boolean(partial.checkpoint_restored),
    executionMode: report.execution_mode ?? "",
    rerunStages,
    skippedStages,
    graphNodes,
    graphEdges,
    affectedRows,
    skippedRows,
    comparisonRows,
    postRerunExportBlocked: report.post_rerun_export_blocked,
    elapsedMs: telemetry.elapsed_ms,
    withinQuickThreshold: telemetry.within_quick_threshold,
  };
}

export function resolveDashboardReactiveAffectedRunTarget({
  currentPlanMeta,
  reactiveChangedSystems,
}: {
  currentPlanMeta: PlanMeta;
  reactiveChangedSystems: EngineeringSystemKey[];
}): SystemGenerationTarget | null {
  if (reactiveChangedSystems.length) return reactiveChangedSystems[0];
  const impacted = new Set(currentPlanMeta.reactive_update_report?.impacted_stages ?? []);
  const match = (Object.entries(REACTIVE_SYSTEM_STAGE_MAP) as Array<[EngineeringSystemKey, string[]]>).find(([, stages]) =>
    stages.some((stage) => impacted.has(stage)),
  );
  return match?.[0] ?? null;
}

export function runDashboardReactiveValidation({
  backendFinalPlanPresent,
  reactiveChangedSystems,
  reactiveChangedTargets,
  setReactiveValidation,
}: {
  backendFinalPlanPresent: boolean;
  reactiveChangedSystems: EngineeringSystemKey[];
  reactiveChangedTargets: string[];
  setReactiveValidation: StateSetter<ReactiveValidationState>;
}) {
  if (!reactiveChangedSystems.length || !backendFinalPlanPresent) {
    setReactiveValidation(EMPTY_REACTIVE_VALIDATION);
    return undefined;
  }
  setReactiveValidation((prev) => ({
    ...prev,
    status: "pending",
    changedSystems: reactiveChangedSystems,
    changedTargets: reactiveChangedTargets,
    requiresConfirmation: reactiveChangedTargets.length > 4,
    message: "Checking impacted engineering systems...",
  }));
  const timeout = window.setTimeout(() => {
    const requiresConfirmation = reactiveChangedTargets.length > 4;
    setReactiveValidation({
      status: "ready",
      changedSystems: reactiveChangedSystems,
      changedTargets: reactiveChangedTargets,
      requiresConfirmation,
      message: requiresConfirmation
        ? `This edit affects ${reactiveChangedSystems.join(", ")} and needs confirmation before engineering reruns.`
        : `Ready for quick partial rerun: ${reactiveChangedSystems.join(", ")}.`,
    });
  }, REACTIVE_EDIT_POLICY_PREFERENCE.debounced_validation_ms);
  return () => window.clearTimeout(timeout);
}
