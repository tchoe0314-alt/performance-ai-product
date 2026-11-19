import { expect, test } from "@playwright/test";
import { buildDashboardResultTruth } from "../../app/utils/dashboardResultTruth";
import type { PlanResponse } from "../../app/types";

const result = (disposition?: "active" | "archived", success: boolean = true) => ({
  success,
  metadata: { calculation_save_v1: { disposition } },
  final_plan: { actions: [] },
}) as unknown as PlanResponse;

test("Review result truth has conservative precedence for every saved-calculation state", () => {
  expect(buildDashboardResultTruth({ result: null, freshness: "missing", localStale: false }).state).toBe("missing");
  expect(buildDashboardResultTruth({ result: result("active", false), freshness: "current", localStale: false }).state).toBe("failed");
  expect(buildDashboardResultTruth({ result: result("archived"), freshness: "current", localStale: false }).state).toBe("historical");
  expect(buildDashboardResultTruth({ result: result("active"), freshness: "stale", localStale: false }).state).toBe("stale");
  expect(buildDashboardResultTruth({ result: result("active"), freshness: "current", localStale: true }).state).toBe("stale");
  expect(buildDashboardResultTruth({ result: result(), freshness: "unverified", localStale: false }).state).toBe("unverified");
  const current = buildDashboardResultTruth({ result: result("active"), freshness: "current", localStale: false });
  expect(current.state).toBe("current");
  expect(current.canClaimSystemsCurrent).toBe(true);
  expect(current.canUseCalculatedExports).toBe(true);
  for (const state of ["missing", "failed", "historical", "unverified", "stale"] as const) {
    const truth = buildDashboardResultTruth({ result: state === "missing" ? null : result(state === "historical" ? "archived" : "active", state !== "failed"), freshness: state, localStale: state === "stale" });
    expect(truth.canClaimSystemsCurrent).toBe(false);
    expect(truth.canUseCalculatedExports).toBe(false);
  }
});
