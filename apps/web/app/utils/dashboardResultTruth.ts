import type { PlanResponse } from "../types";

export type DashboardResultTruthState = "missing" | "failed" | "historical" | "unverified" | "stale" | "current";
export type DashboardResultTruth = {
  state: DashboardResultTruthState;
  label: string;
  reason: string;
  canClaimSystemsCurrent: boolean;
  canUseCalculatedExports: boolean;
};

export function buildDashboardResultTruth({ result, freshness, localStale }: { result: PlanResponse | null; freshness?: DashboardResultTruthState | null; localStale: boolean }): DashboardResultTruth {
  const disposition = String(result?.metadata?.calculation_save_v1?.disposition ?? "").toLowerCase();
  let state: DashboardResultTruthState = !result || !Object.keys(result).length ? freshness === "stale" ? "stale" : freshness === "failed" ? "failed" : "missing"
    : result.success === false ? "failed"
      : disposition === "archived" ? "historical"
        : freshness === "stale" || localStale ? "stale"
          : freshness === "current" ? "current"
            : "unverified";
  const copy: Record<DashboardResultTruthState, [string, string]> = {
    current: ["Current calculation", "The saved calculation matches the active canonical project input."],
    stale: ["Recalculation required", "The layout changed after the saved calculation. Prior output is retained as history and is not current."],
    historical: ["Historical calculation", "This calculation is retained in history and is not the active project result."],
    failed: ["Calculation failed", "The latest calculation did not produce a usable current result. Review missing inputs or failure details."],
    missing: ["No current calculation", "Run Generate after completing required inputs. Drawing review remains available, but calculated results are absent."],
    unverified: ["Calculation not verified", "Civora cannot verify this result against the active saved input. Recalculate before relying on it."],
  };
  return { state, label: copy[state][0], reason: copy[state][1], canClaimSystemsCurrent: state === "current", canUseCalculatedExports: state === "current" };
}
