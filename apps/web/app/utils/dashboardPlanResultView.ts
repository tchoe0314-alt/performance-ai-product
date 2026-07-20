import type {
  Assumption,
  BackendAssumption,
  BackendIssue,
  Issue,
  ManualFailure,
  PlanResponse,
} from "../types";
import { defaultAssumptions } from "./formatting";
import {
  REACTIVE_SYSTEM_STAGE_MAP,
  type EngineeringSystemKey,
  type SystemStatus,
} from "./workflowConstants";

export function buildDashboardAssumptionsFromPlanResult(data: PlanResponse): Assumption[] {
  if (!Array.isArray(data?.assumptions)) return defaultAssumptions;
  return data.assumptions.map((item: BackendAssumption) => ({
    field: item.field_name ?? "unknown",
    value:
      typeof item.assumed_value === "string"
        ? item.assumed_value
        : JSON.stringify(item.assumed_value),
    reason: item.reason ?? "",
  }));
}

export function buildDashboardIssuesFromPlanResult(data: PlanResponse): Issue[] {
  if (!Array.isArray(data?.issues)) return [];
  return data.issues.map((item: BackendIssue) => ({
    severity: item.severity === "error" ? "error" : "warning",
    message: item.message ?? "Unknown issue",
    code: typeof item.code === "string" ? item.code : undefined,
    context: item.context && typeof item.context === "object" ? item.context : undefined,
  }));
}

export function applyDashboardReactiveSystemStatusFromPlanResult(
  data: PlanResponse,
  previous: Record<EngineeringSystemKey, SystemStatus>,
): Record<EngineeringSystemKey, SystemStatus> {
  const report = data?.final_plan?.meta?.reactive_update_report;
  if (!report?.partial_rerun_executed) return previous;
  const completedStages = new Set(
    [
      ...(report.post_rerun_completed_stages ?? []),
      ...(report.post_rerun_stage_status ?? [])
        .filter((row) => row.completed)
        .map((row) => row.stage ?? ""),
    ].filter(Boolean),
  );
  const staleAfter = new Set(report.post_rerun_stale_outputs ?? []);
  const impacted = new Set(report.impacted_stages ?? []);
  const next = { ...previous };
  (Object.entries(REACTIVE_SYSTEM_STAGE_MAP) as Array<[EngineeringSystemKey, string[]]>).forEach(
    ([system, stages]) => {
      const touchedStages = stages.filter((stage) => impacted.has(stage));
      if (!touchedStages.length) return;
      const cleared = touchedStages.every(
        (stage) => completedStages.has(stage) && !staleAfter.has(stage),
      );
      if (cleared) {
        next[system] = "fresh";
      }
    },
  );
  return next;
}

export function buildDashboardSuggestedImproveGoal({
  currentManualFailures,
  issues,
}: {
  currentManualFailures: ManualFailure[];
  issues: Issue[];
}) {
  const failureBlob = [
    ...currentManualFailures.map((failure) =>
      [failure.code, failure.message, failure.system, failure.rule]
        .filter(Boolean)
        .join(" "),
    ),
    ...issues.map((issue) => issue.message),
  ]
    .join(" ")
    .toLowerCase();

  if (failureBlob.includes("drain") || failureBlob.includes("inlet")) {
    return "improve_drainage";
  }
  if (failureBlob.includes("pipe")) {
    return "reduce_pipe_length";
  }
  if (
    failureBlob.includes("grade") ||
    failureBlob.includes("earthwork") ||
    failureBlob.includes("slope")
  ) {
    return "reduce_grading";
  }
  if (failureBlob.includes("parking")) {
    return "maximize_parking";
  }
  return undefined;
}
