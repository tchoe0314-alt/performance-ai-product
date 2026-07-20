import type {
  BuildingPlacement,
  CandidateReviewInbox,
  CandidateReviewItem,
  CanonicalGeometryHandoffV1,
  DesignAlternativesV1,
  Issue,
  PlanMeta,
  ReviewIssue,
  ReviewIssueTrackerV1,
  SiteInputs,
  SourceConfidenceEntry,
  SourceConfidenceMap,
} from "../types";

export function buildCandidateReviewInbox(
  siteInputs: SiteInputs | null | undefined,
  currentPlanMeta: PlanMeta,
): CandidateReviewInbox {
  const stored = siteInputs?.candidate_review_inbox_v1 ?? currentPlanMeta.candidate_review_inbox_v1;
  if (stored?.candidates?.length) return stored;
  const mapFeatureReport = siteInputs?.map_feature_detection_report_v1 ?? currentPlanMeta.map_feature_detection_report_v1;
  const mapCandidates = ((mapFeatureReport?.feature_candidates ?? []) as unknown[]).map((item, index) => {
    const rec = item as Record<string, unknown>;
    const featureType = String(rec.feature_type ?? "map_feature_candidate");
    return {
      candidate_id: String(rec.candidate_id ?? `map-candidate-${index + 1}`),
      candidate_type:
        featureType === "parcel_or_site_boundary"
          ? "parcel_site_boundary"
          : featureType === "building_footprint"
            ? "building_footprint"
            : featureType === "road_or_drive"
              ? "road_row"
              : featureType === "utility"
                ? "utility"
                : "floodplain_wetland_constraint",
      label: featureType.replaceAll("_", " "),
      source: String(rec.evidence_source ?? rec.source_name ?? rec.source_type ?? "map/GIS source"),
      provider: String(rec.source_name ?? rec.source_type ?? "map/GIS"),
      source_url: String(rec.source_url ?? ""),
      confidence: typeof rec.confidence === "number" || typeof rec.confidence === "string" ? rec.confidence : "unknown",
      status: String(rec.acceptance_status ?? "pending"),
      object_count: typeof rec.object_count === "number" ? rec.object_count : 1,
      blocker_review_reason: Array.isArray(rec.blockers) && rec.blockers.length
        ? rec.blockers.map(String).join("; ")
        : "Map/GIS candidate needs project review before use.",
    } satisfies CandidateReviewItem;
  });
  const standardsCandidates = (
    currentPlanMeta.candidate_rule_report?.candidate_rules ??
    currentPlanMeta.standards_candidate_rule_report?.candidate_rules ??
    []
  ).map((item, index) => {
    const rec = item as Record<string, unknown>;
    return {
      candidate_id: `std_${String(rec.rule_id ?? index + 1)}`,
      candidate_type: "standards",
      label: String(rec.topic ?? rec.discipline ?? "Standards candidate"),
      source: String(rec.source_id ?? rec.source_type ?? "standards source"),
      provider: String(rec.source_id ?? rec.source_type ?? "standards"),
      source_url: String(rec.source_url ?? ""),
      source_date: String(rec.retrieved_date ?? rec.retrieved_at ?? ""),
      confidence: typeof rec.confidence === "number" || typeof rec.confidence === "string" ? rec.confidence : "unknown",
      status: String(rec.acceptance_status ?? rec.status ?? "pending"),
      object_count: 1,
      blocker_review_reason: "Candidate standards need explicit review before QA can rely on them.",
    } satisfies CandidateReviewItem;
  });
  const candidates = [...mapCandidates, ...standardsCandidates];
  const counts = candidates.reduce(
    (acc, item) => {
      const status = item.status === "accepted" || item.status === "rejected" ? item.status : "pending";
      acc[status] += 1;
      return acc;
    },
    { accepted: 0, rejected: 0, pending: 0 },
  );
  return {
    version: "candidate_review_inbox_v1",
    candidate_count: candidates.length,
    counts,
    candidates,
    construction_release_allowed: false,
    construction_release_blocked: true,
    truth_label: "Accepted candidates are project draft/review-required evidence only.",
  };
}

export function buildDesignAlternatives(currentPlanMeta: PlanMeta): DesignAlternativesV1 {
  const stored = currentPlanMeta.design_alternatives_v1;
  if (stored?.alternatives?.length) return stored;
  return {
    version: "design_alternatives_v1",
    alternative_count: 0,
    alternatives: [],
    review_required: true,
    construction_release_allowed: false,
    construction_readiness_implied: false,
    truth_label: "Design alternatives are review-required concepts until generated from project context.",
  };
}

export function buildReviewIssueTracker(
  currentPlanMeta: PlanMeta,
  issues: Issue[],
  analysisIssues: unknown[],
): ReviewIssueTrackerV1 {
  const stored = currentPlanMeta.review_issue_tracker_v1;
  if (stored?.issues?.length || stored?.open_issues?.length) return stored;
  const fallbackIssues: ReviewIssue[] = [
    ...issues.map((issue, index): ReviewIssue => {
      const message = typeof issue.message === "string" ? issue.message : JSON.stringify(issue.message ?? "Review issue");
      return {
        issue_id: `ui_issue_${index + 1}`,
        title: message,
        description: message,
        status: "open",
        severity: issue.severity || "warning",
        discipline: String(issue.context?.system ?? issue.context?.discipline ?? "qa"),
        assigned_role: "qa_reviewer",
        next_action: "Review and resolve the recorded QA item.",
        links: { system_ids: issue.context?.system ? [String(issue.context.system)] : [], source_keys: ["ui_issues"] },
      };
    }),
    ...analysisIssues.map((issue, index): ReviewIssue => {
      const message = typeof issue === "string" ? issue : JSON.stringify(issue ?? "Analysis issue");
      return {
        issue_id: `analysis_issue_${index + 1}`,
        title: message,
        description: message,
        status: "open",
        severity: "review",
        discipline: "qa",
        assigned_role: "qa_reviewer",
        next_action: "Review the analysis item and rerun affected checks.",
        links: { system_ids: ["analysis"], source_keys: ["analysis_issues"] },
      };
    }),
  ];
  const openIssues = fallbackIssues.filter((item) => ["open", "in_review", "reopened"].includes(String(item.status ?? "open")));
  return {
    version: "review_issue_tracker_v1",
    issue_count: fallbackIssues.length,
    open_count: openIssues.length,
    needs_review_count: openIssues.length,
    by_status: { open: openIssues.length },
    by_severity: {},
    by_discipline: {},
    issues: fallbackIssues,
    open_issues: openIssues,
    engineer_review_queue: openIssues,
    field_use_allowed: false,
    truth_label: "Review issues are workflow records. Closing an item does not change field-use boundaries.",
  };
}

export function buildSourceConfidenceMap({
  currentPlanMeta,
  candidateReviewItems,
  buildingPlacements,
  hasVerifiedSurveyControl,
}: {
  currentPlanMeta: PlanMeta;
  candidateReviewItems: CandidateReviewItem[];
  buildingPlacements: BuildingPlacement[];
  hasVerifiedSurveyControl: boolean;
}): SourceConfidenceMap {
  const stored = currentPlanMeta.source_confidence_map_v1;
  if (stored?.entries?.length) return stored;
  const entries: SourceConfidenceEntry[] = [];
  const addEntry = (entry: SourceConfidenceEntry) => {
    entries.push({
      construction_release_allowed: false,
      construction_readiness_implied: false,
      ...entry,
    });
  };
  candidateReviewItems.forEach((item) => {
    const isAccepted = item.status === "accepted";
    const sourceType = item.candidate_type === "standards"
      ? isAccepted
        ? "official GIS source"
        : "inferred"
      : isAccepted
        ? "official GIS source"
        : "GIS candidate";
    addEntry({
      entry_id: item.candidate_id,
      label: item.label || item.candidate_type || "Candidate source",
      category: item.candidate_type === "standards" ? "standards" : "candidate",
      object_id: item.accepted_as || item.candidate_id,
      source_type: sourceType,
      source_name: item.source || item.provider || "candidate source",
      confidence_score: typeof item.confidence === "number" ? item.confidence : isAccepted ? 0.56 : 0.38,
      confidence_band: isAccepted ? "review" : "low",
      visible_badge: `${sourceType} · ${isAccepted ? "review" : "low"}`,
      status: item.status || "pending",
      accepted: isAccepted,
      needs_verification: true,
      needs_survey_control: item.candidate_type !== "standards",
      low_confidence_reasons: [item.blocker_review_reason || "Candidate source needs review and verification."],
      why_low_confidence: item.blocker_review_reason || "Candidate source needs review and verification.",
      next_action: "Review candidate evidence and verify against survey/control before relying on it.",
    });
  });
  buildingPlacements.forEach((item) => {
    const handoff = item.meta && typeof item.meta === "object"
      ? (item.meta as { canonical_geometry_handoff_v1?: CanonicalGeometryHandoffV1 }).canonical_geometry_handoff_v1
      : undefined;
    const sourceType = item.source === "manual_drawn" || item.source === "user" || handoff?.source === "manual_drawn" ? "user-drawn" : "inferred";
    addEntry({
      entry_id: `ui-object-${item.id}`,
      label: item.label || item.type || "Draft object",
      category: "object",
      object_id: item.id,
      layer: item.type,
      source_type: sourceType,
      source_name: handoff?.source_ui_mode || item.source || "ui",
      confidence_score: sourceType === "user-drawn" ? 0.48 : 0.28,
      confidence_band: sourceType === "user-drawn" ? "review" : "low",
      visible_badge: `${sourceType} · ${sourceType === "user-drawn" ? "review" : "low"}`,
      status: handoff?.engineering_status || "draft_review_required",
      needs_verification: true,
      needs_survey_control: true,
      low_confidence_reasons: [
        sourceType === "user-drawn"
          ? "User-drawn geometry is draft review evidence, not survey/control truth."
          : "Object source is inferred from UI state.",
      ],
      why_low_confidence:
        sourceType === "user-drawn"
          ? "User-drawn geometry is draft review evidence, not survey/control truth."
          : "Object source is inferred from UI state.",
      next_action: "Verify object geometry against survey/control or keep it review-only.",
    });
  });
  if (!entries.some((item) => item.source_type === "survey-backed")) {
    addEntry({
      entry_id: "ui-missing-survey-control",
      label: "Verified survey/control",
      category: "source",
      source_type: hasVerifiedSurveyControl ? "survey-backed" : "missing",
      source_name: hasVerifiedSurveyControl ? "survey/control" : "missing",
      confidence_score: hasVerifiedSurveyControl ? 0.9 : 0,
      confidence_band: hasVerifiedSurveyControl ? "higher" : "missing",
      visible_badge: hasVerifiedSurveyControl ? "survey-backed · higher" : "missing · missing",
      status: hasVerifiedSurveyControl ? "verified" : "missing",
      verified: hasVerifiedSurveyControl,
      missing: !hasVerifiedSurveyControl,
      needs_verification: !hasVerifiedSurveyControl,
      needs_survey_control: !hasVerifiedSurveyControl,
      low_confidence_reasons: hasVerifiedSurveyControl ? [] : ["Verified survey/control is not attached."],
      why_low_confidence: hasVerifiedSurveyControl ? "" : "Verified survey/control is not attached.",
      next_action: "Attach verified survey/control with datum, benchmark, CRS, and verification status.",
    });
  }
  const low = entries.filter((item) => item.confidence_band === "low" || item.confidence_band === "missing" || item.stale || item.dirty);
  const userDrawn = entries.filter((item) => item.source_type === "user-drawn");
  const needsControl = entries.filter((item) => item.needs_survey_control);
  const staleMissing = entries.filter((item) => item.stale || item.dirty || item.missing);
  return {
    version: "source_confidence_map_v1",
    entries,
    summary: {
      entry_count: entries.length,
      trusted_count: entries.filter((item) => item.confidence_band === "higher").length,
      low_confidence_count: low.length,
      user_drawn_count: userDrawn.length,
      needs_survey_control_count: needsControl.length,
      stale_or_missing_count: staleMissing.length,
      low_confidence_labels: low.map((item) => item.label || "").filter(Boolean),
      user_drawn_labels: userDrawn.map((item) => item.label || "").filter(Boolean),
      needs_survey_control_labels: needsControl.map((item) => item.label || "").filter(Boolean),
      stale_or_missing_labels: staleMissing.map((item) => item.label || "").filter(Boolean),
    },
    construction_release_allowed: false,
    construction_readiness_implied: false,
    truth_label: "UI fallback confidence map keeps low-confidence sources visible; it does not imply field-use readiness.",
  };
}
