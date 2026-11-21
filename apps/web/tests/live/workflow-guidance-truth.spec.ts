import { expect, test } from "@playwright/test";

import { buildAnalysisTruthCopy } from "../../app/components/AnalysisPanel";
import { buildCalculatedExportReadiness } from "../../app/components/DeliverPanel";
import { buildDashboardNextAction } from "../../app/utils/dashboardWorkflowHints";
import { buildDashboardResultTruth } from "../../app/utils/dashboardResultTruth";
import type { PlanResponse } from "../../app/types";

const currentResult = { success: true, metadata: { calculation_save_v1: { disposition: "active" } } } as unknown as PlanResponse;
const truth = (freshness: "missing" | "stale" | "current") => buildDashboardResultTruth({
  result: freshness === "missing" ? null : currentResult,
  freshness,
  localStale: freshness === "stale",
});

test("next action follows persisted setup and calculation truth", () => {
  const base = { hasLocationEvidence: true, siteSizeSet: true, hasSiteBoundary: true, siteScaleLocked: true, placedObjectCount: 4, firstSystemBlocker: undefined, exportBlockReason: "" };
  expect(buildDashboardNextAction({ ...base, hasLocationEvidence: false, resultTruth: truth("missing") })).toMatchObject({ label: "Set up site", panel: "site_existing" });
  expect(buildDashboardNextAction({ ...base, resultTruth: truth("stale") })).toMatchObject({ label: "Recalculate", panel: "generate" });
  expect(buildDashboardNextAction({ ...base, resultTruth: truth("current"), exportBlockReason: "grading is stale" })).toMatchObject({ label: "Review export blockers", panel: "deliverables", detail: "grading is stale" });
  expect(buildDashboardNextAction({ ...base, resultTruth: truth("current") })).toMatchObject({ label: "Export current review package", panel: "deliverables" });
});

test("Review never presents an unchecked empty list as a clean zero", () => {
  const missing = buildAnalysisTruthCopy(truth("missing"), 0, 0);
  expect(missing.headline).toContain("not been checked");
  expect(missing.emptyIssues).toContain("No current calculation");
  const current = buildAnalysisTruthCopy(truth("current"), 0, 0);
  expect(current.headline).toBe("No active review issues");
});

test("Deliver separates current drawing from revision-bound calculated readiness", () => {
  expect(buildCalculatedExportReadiness("recalculate grading", "calc-12")).toEqual({ state: "Blocked", detail: "recalculate grading", reference: "calc-12" });
  expect(buildCalculatedExportReadiness("", "calc-13")).toEqual({ state: "Current", detail: "Calculated results match the active saved project and may be exported for qualified review.", reference: "calc-13" });
  expect(buildCalculatedExportReadiness("", undefined).reference).toBe("not available");
});
