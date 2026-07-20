import type { BuildingPlacement, MapAnalysis } from "../types";
import type { CapabilityExposure } from "./dashboardTypes";
import type { SidebarStatus } from "./workspaceShell";

type CapabilityAuditRowsContext = {
  currentPlanMeta: Record<string, unknown>;
  manualFields?: Record<string, unknown>;
  buildingPlacements: BuildingPlacement[];
  existingConditionRows: ReadonlyArray<{ status?: string }>;
  backendResultPresent: boolean;
  hasLocationEvidence: boolean;
  hasVerifiedSurveyControl: boolean;
  mapAnalysis: MapAnalysis | null;
  placedObjectCount: number;
  quantityRowCount: number;
  reactiveChangedSystems: string[];
  reactiveRerunSummary: {
    enabled?: boolean;
    rerunStages?: unknown[];
    skippedStages?: unknown[];
  };
  uploadedImageApiUrl: string;
  uploadedImagePreviewUrl: string;
  exportBlockReason: string | null;
};

const readRecordFrom = (source: Record<string, unknown>, key: string): Record<string, unknown> =>
  source[key] && typeof source[key] === "object" ? (source[key] as Record<string, unknown>) : {};

const readArray = (record: Record<string, unknown>, key: string): unknown[] =>
  Array.isArray(record[key]) ? (record[key] as unknown[]) : [];

const blockerCount = (record: Record<string, unknown>) =>
  readArray(record, "blockers").length +
  readArray(record, "warnings").length +
  readArray(record, "missing_inputs").length;

const statusFrom = (present: boolean, blocked: boolean, review = true): SidebarStatus =>
  !present ? "idle" : blocked ? "block" : review ? "review" : "ok";

export function buildDashboardCapabilityAuditRows({
  currentPlanMeta,
  manualFields,
  buildingPlacements,
  existingConditionRows,
  backendResultPresent,
  hasLocationEvidence,
  hasVerifiedSurveyControl,
  mapAnalysis,
  placedObjectCount,
  quantityRowCount,
  reactiveChangedSystems,
  reactiveRerunSummary,
  uploadedImageApiUrl,
  uploadedImagePreviewUrl,
  exportBlockReason,
}: CapabilityAuditRowsContext): CapabilityExposure[] {
  const readRecord = (key: string): Record<string, unknown> => readRecordFrom(currentPlanMeta, key);
  const packageStatus = (...keys: string[]) => {
    for (const key of keys) {
      const rec = readRecord(key);
      const status = String(
        rec.status ||
          rec.review_status ||
          rec.export_status ||
          rec.readiness_status ||
          rec.qa_status ||
          "",
      );
      if (status) return status;
    }
    return "";
  };
  const hasRecord = (...keys: string[]) => keys.some((key) => Object.keys(readRecord(key)).length > 0);
  const row = (
    key: string,
    label: string,
    present: boolean,
    surfaces: string[],
    value: string,
    missingWiring: string,
    exactFix: string,
    blocked = false,
    review = true,
  ): CapabilityExposure => ({
    key,
    label,
    exposed: present ? "yes" : "no",
    surfaces,
    status: statusFrom(present, blocked, review),
    value,
    missingWiring: present ? "None for status visibility" : missingWiring,
    exactFix: present ? "Review the listed blockers or accept/reupload evidence where required." : exactFix,
  });

  const standardsPackage = readRecord("standards_package");
  const standardsRegistry = readRecord("standards_source_registry");
  const standardsCandidateReport = readRecord("candidate_rule_report");
  const standardsAcceptanceReport = readRecord("standards_acceptance_report");
  const existingPackage = readRecord("existing_conditions_package");
  const surveyControl = readRecord("survey_control_package");
  const mapFeatureReport = readRecord("map_feature_detection_report_v1");
  const planPdfReport = readRecord("plan_pdf_analysis_v1");
  const planPdfSheet = readRecord("plan_pdf_editable_sheet_v1");
  const engineDepth = readRecord("engine_depth_audit_report_v1");
  const productionEvidence = readRecord("production_evidence");
  const quantityCost = productionEvidence.quantity_cost && typeof productionEvidence.quantity_cost === "object"
    ? (productionEvidence.quantity_cost as Record<string, unknown>)
    : {};
  const exportPackage = readRecord("export_package_report_v1");
  const reviewSupportPackage = readRecord("construction_document_support_package_v1");
  const reviewSupportManifest = readRecord("construction_package_manifest");
  const engineerReviewPackage = readRecord("engineer_review_package_v1");
  const reactiveReport = readRecord("reactive_update_report");
  const reactivePartial = readRecord("reactive_partial_rerun");
  const handoffs =
    Array.isArray(manualFields?.canonical_geometry_handoff_v1)
      ? (manualFields.canonical_geometry_handoff_v1 as unknown[])
      : buildingPlacements.filter((item) => item.meta && typeof item.meta === "object" && "canonical_geometry_handoff_v1" in item.meta);
  const mapCandidateCount = Number(mapFeatureReport.candidate_count ?? 0);
  const acceptedStandards = Number(
    standardsCandidateReport.accepted_rule_count ??
      (standardsAcceptanceReport.rules && typeof standardsAcceptanceReport.rules === "object"
        ? (standardsAcceptanceReport.rules as Record<string, unknown>).accepted_rule_count
        : 0) ??
      0,
  );
  const standardsCandidateCount = Number(
    standardsCandidateReport.candidate_count ??
      (standardsAcceptanceReport.rules && typeof standardsAcceptanceReport.rules === "object"
        ? ((standardsAcceptanceReport.rules as Record<string, unknown>).candidates as Record<string, unknown> | undefined)?.candidate_count
        : 0) ??
      0,
  );
  const surveyPresent = hasRecord("survey_control_package") || hasVerifiedSurveyControl;
  const existingPresent = hasRecord("existing_conditions_package") || existingConditionRows.some((item) => item.status !== "block");
  const costPresent = hasRecord("production_evidence") || hasRecord("cost_estimate") || quantityRowCount > 0;
  const exportBlocked = Boolean(exportPackage.export_blocked || exportBlockReason);
  const reactivePresent = hasRecord("reactive_update_report") || hasRecord("reactive_partial_rerun") || reactiveChangedSystems.length > 0;

  return [
    row(
      "standards_source_registry",
      "Standards source registry",
      hasRecord("standards_source_registry", "standards_package"),
      ["UI", "chat", "API", "report"],
      standardsRegistry.accepted_source_count !== undefined
        ? `${standardsRegistry.accepted_source_count} accepted source(s)`
        : packageStatus("standards_package") || "Needs accepted official source",
      "Registry is only produced after standards discovery/acceptance evidence exists.",
      "Run standards discovery, review candidate sources, accept official HTTPS sources, then regenerate the standards package.",
      blockerCount(standardsPackage) > 0 || standardsRegistry.accepted_source_count === 0,
    ),
    row(
      "candidate_standards_review",
      "Candidate standards review",
      hasRecord("candidate_rule_report", "standards_acceptance_report", "standards_package"),
      ["UI", "chat", "API", "report"],
      `${standardsCandidateCount || 0} candidate(s), ${acceptedStandards || 0} accepted`,
      "Candidate rules are absent until extraction/review packet evidence is saved.",
      "Extract standards candidates or build a standards review packet, then accept/reject each candidate rule.",
      standardsCandidateCount > 0 && acceptedStandards === 0,
    ),
    row(
      "existing_conditions_package",
      "Existing conditions package",
      existingPresent,
      ["UI", "chat", "API", "report"],
      packageStatus("existing_conditions_package") || (existingPresent ? "Imported / review required" : "Missing imports"),
      "No existing conditions import package is attached.",
      "Upload survey/topo/GIS files or fetch online existing-condition sources, then rerun import validation.",
      blockerCount(existingPackage) > 0 || !hasLocationEvidence,
    ),
    row(
      "survey_control_package",
      "Survey control package",
      surveyPresent,
      ["UI", "chat", "API", "report"],
      packageStatus("survey_control_package") || (hasVerifiedSurveyControl ? "Uploaded / verify control" : "Missing verified control"),
      "Survey/control status is blocked until control evidence exists.",
      "Upload survey/control evidence with datum, benchmark, coordinate system, and verification status.",
      blockerCount(surveyControl) > 0 || !hasVerifiedSurveyControl,
    ),
    row(
      "map_feature_candidates",
      "Map feature candidates",
      hasRecord("map_feature_detection_report_v1") || Boolean(mapAnalysis?.success || uploadedImageApiUrl || uploadedImagePreviewUrl),
      ["UI", "chat", "API", "report"],
      mapCandidateCount ? `${mapCandidateCount} candidate(s) need review` : mapAnalysis?.success ? "Map analyzed; candidates need review" : "No candidates yet",
      "No map feature report is attached.",
      "Upload/analyze a map snapshot or accept GIS feature sources, then review candidates before drafting objects.",
      blockerCount(mapFeatureReport) > 0 || mapCandidateCount === 0,
    ),
    row(
      "plan_pdf_understanding",
      "Plan PDF understanding",
      hasRecord("plan_pdf_analysis_v1", "plan_pdf_editable_sheet_v1"),
      ["UI", "chat", "API", "report"],
      planPdfReport.source_confidence
        ? `${planPdfReport.source_confidence} · ${Number((planPdfSheet.summary as Record<string, unknown> | undefined)?.element_count ?? 0)} object(s)`
        : "No plan PDF imported",
      "No plan PDF analysis is attached.",
      "Upload a plan PDF from the Data panel, then review extracted sheet/object candidates.",
      blockerCount(planPdfReport) > 0 || !hasRecord("plan_pdf_editable_sheet_v1"),
    ),
    row(
      "engine_depth_audit",
      "Engine depth audit",
      hasRecord("engine_depth_dashboard_v1", "engine_depth_audit_report_v1", "engine_depth_audit", "engine_readiness"),
      ["UI", "chat", "API", "report"],
      packageStatus("engine_depth_audit_report_v1", "engine_depth_audit", "engine_readiness") || "Needs generated model evidence",
      "No engine depth audit is present in the current plan meta.",
      "Run the planner or golden depth audit so each discipline records readiness, blockers, and validation depth.",
      blockerCount(engineDepth) > 0,
    ),
    row(
      "production_evidence",
      "Production evidence",
      hasRecord("production_evidence"),
      ["UI", "chat", "API", "report"],
      productionEvidence.production_evidence_ready === true ? "Ready for review handoff" : "Review/blocked evidence only",
      "No canonical production evidence record is present.",
      "Run production evidence assembly after standards, existing conditions, quantities, export audit, and reactive checks exist.",
      productionEvidence.production_evidence_ready !== true,
    ),
    row(
      "cost_book_pricing",
      "Cost book / pricing",
      costPresent,
      ["UI", "chat", "API", "report"],
      quantityCost.ready === true ? "Reviewed pricing source covers quantities" : "Needs reviewed/current unit-price book",
      "Cost pricing validation is absent until quantities and a unit-price book exist.",
      "Normalize and validate a reviewed unit-price book, then rerun quantities/cost evidence.",
      quantityCost.ready !== true,
    ),
    row(
      "export_package_report",
      "Export package report",
      hasRecord("export_package_report_v1") || backendResultPresent,
      ["UI", "chat", "API", "report"],
      packageStatus("export_package_report_v1") || (exportBlocked ? String(exportBlockReason) : "Review export available"),
      "No export package report has been generated yet.",
      "Generate a report/DXF export package so export audit, support matrix, traceability, and blockers are recorded.",
      exportBlocked || blockerCount(exportPackage) > 0,
    ),
    row(
      "review_document_support_package",
      "Review document support package",
      hasRecord("construction_document_support_package_v1", "construction_package_manifest"),
      ["UI", "chat", "API", "report"],
      packageStatus("construction_document_support_package_v1", "construction_package_manifest") || "Review-only support; independent review required",
      "Review document support package is not attached to this plan.",
      "Build the review document support package after deliverable artifacts, standards, survey/control, QA, and pricing evidence exist.",
      blockerCount(reviewSupportPackage) > 0 || blockerCount(reviewSupportManifest) > 0 || true,
    ),
    row(
      "engineer_review_package",
      "Engineer review package",
      hasRecord("engineer_review_package_v1"),
      ["UI", "chat", "API", "report"],
      packageStatus("engineer_review_package_v1") ||
        (blockerCount(engineerReviewPackage)
          ? `${blockerCount(engineerReviewPackage)} review blocker(s)`
          : "External licensed engineer review required"),
      "No engineer review package is attached.",
      "Generate the engineer review package from the current plan and route blockers to a licensed external reviewer.",
      true,
    ),
    row(
      "reactive_rerun_evidence",
      "Reactive rerun evidence",
      reactivePresent,
      ["UI", "chat", "API", "report"],
      reactiveRerunSummary.enabled
        ? `${reactiveRerunSummary.rerunStages?.length ?? 0} rerun stage(s), ${reactiveRerunSummary.skippedStages?.length ?? 0} skipped`
        : reactiveChangedSystems.length
          ? `${reactiveChangedSystems.length} stale system(s) need rerun`
          : "No reactive rerun yet",
      "Reactive evidence appears only after a saved edit or partial rerun.",
      "Make a scoped model edit, confirm the reactive policy if required, and run the dependency-aware partial rerun.",
      readArray(reactiveReport, "stale_outputs").length > 0 || readArray(reactivePartial, "stale_outputs").length > 0 || reactiveChangedSystems.length > 0,
    ),
    row(
      "cad_geometry_handoff",
      "Draft geometry handoff",
      handoffs.length > 0 || placedObjectCount > 0,
      ["UI", "chat", "API", "report"],
      handoffs.length ? `${handoffs.length} canonical handoff(s)` : placedObjectCount ? "Draft objects need canonical handoff review" : "No geometry yet",
      "No canonical geometry handoff exists.",
      "Draw or import geometry, classify it, then preserve the canonical_geometry_handoff_v1 record for review/export.",
      handoffs.length === 0,
    ),
  ];
}
