import type { PlanMeta, SmartFixRecommendation, SmartFixRecommendationsV1 } from "../types";

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : {};
}

export function buildSmartFixBlockedReasons(currentPlanMeta: PlanMeta): string[] {
  const releaseReview = asRecord(currentPlanMeta.release_review);
  const exportAudit = asRecord(currentPlanMeta.export_audit);
  const manualFailures = Array.isArray(currentPlanMeta.manual_validation?.failures)
    ? currentPlanMeta.manual_validation.failures
    : [];
  const values = [
    ...(Array.isArray(releaseReview.blocked_reasons) ? releaseReview.blocked_reasons : []),
    ...(Array.isArray(releaseReview.blocked_exports) ? releaseReview.blocked_exports : []),
    ...(currentPlanMeta.convergence_summary?.blocked_reasons ?? []),
    ...(currentPlanMeta.convergence_summary?.blocked_exports ?? []),
    ...(Array.isArray(exportAudit.blocked_reasons) ? exportAudit.blocked_reasons : []),
    ...manualFailures.map((failure) => {
      const record = asRecord(failure);
      return record.message || record.reason || record.code || "manual validation failure";
    }),
  ];
  return Array.from(new Set(values.map((item) => String(item || "").trim()).filter(Boolean)));
}

export function buildSmartFixRecommendations(
  currentPlanMeta: PlanMeta,
  smartFixBlockedReasons: string[],
): SmartFixRecommendationsV1 {
  const stored = currentPlanMeta.smart_fix_recommendations_v1;
  if (stored?.recommendations?.length) return stored;
  const recommendations: SmartFixRecommendation[] = smartFixBlockedReasons.slice(0, 6).map((reason, index) => ({
    id: `ui_smart_fix_${index + 1}`,
    blocker_code: reason.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "") || "ui_blocker",
    category: reason.toLowerCase().includes("export")
      ? "exports"
      : reason.toLowerCase().includes("boundary") || reason.toLowerCase().includes("setup")
        ? "setup_site_boundary"
        : "general",
    what_is_wrong: reason,
    why_it_matters: "Civora keeps unresolved needs visible so review outputs do not overstate the current state.",
    can_civora_fix: !reason.toLowerCase().includes("survey") && !reason.toLowerCase().includes("standards"),
    fix_mode: !reason.toLowerCase().includes("survey") && !reason.toLowerCase().includes("standards") ? "auto_supported" : "manual_input_required",
    one_action_needed_next: reason.toLowerCase().includes("export")
      ? "Open Deliver and rebuild the review report after needs are resolved."
      : reason.toLowerCase().includes("boundary")
        ? "Open Setup and lock the site boundary."
        : "Run a fix pass.",
    missing_user_input_or_source: reason.toLowerCase().includes("survey")
      ? "survey/control source"
      : reason.toLowerCase().includes("standards")
        ? "accepted standards source"
        : "",
    what_happens_after_fix: "Civora will refresh needs and keep remaining review gates visible.",
    ui_action: reason.toLowerCase().includes("export")
      ? { type: "open_panel", panel: "deliverables" }
      : reason.toLowerCase().includes("boundary") || reason.toLowerCase().includes("setup")
        ? { type: "open_panel", panel: "site_existing" }
        : { type: "run_fix" },
    engineer_review_required: true,
  }));
  return {
    version: "smart_fix_recommendations_v1",
    recommendation_count: recommendations.length,
    auto_fix_action_count: recommendations.filter((item) => item.can_civora_fix).length,
    manual_action_count: recommendations.filter((item) => !item.can_civora_fix).length,
    recommendations,
    next_best_recommendation: recommendations[0],
    truth_label: "Smart Fix explains needs and only runs supported actions.",
  };
}
