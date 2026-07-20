import type {
  ProgressTimelineStep,
  ProgressTimelineV1,
  SetupWizardStateV1,
  SetupWizardStep,
} from "../types";
import type { SidePanelKey } from "./workspaceShell";

type SystemStatuses = Record<string, string>;

export function buildDashboardSetupWizardState({
  persistedSetupWizardState,
  hasAppliedAddress,
  siteAddress,
  appliedAddressLabel,
  siteScaleLocked,
  siteSizeSet,
  hasSiteObject,
  hasSourceContext,
  onlineSourceLookupLabel,
  hasVerifiedSurveyControl,
  hasTerrainSource,
  surveyPreviewPointCount,
  hasAssumedTerrainSlope,
  standardsOk,
  placedObjectCount,
  parkingCount,
  systemStatuses,
  hasBackendResult,
  exportBlockText,
}: {
  persistedSetupWizardState?: SetupWizardStateV1;
  hasAppliedAddress: boolean;
  siteAddress: string;
  appliedAddressLabel: string;
  siteScaleLocked: boolean;
  siteSizeSet: boolean;
  hasSiteObject: boolean;
  hasSourceContext: boolean;
  onlineSourceLookupLabel: string;
  hasVerifiedSurveyControl: boolean;
  hasTerrainSource: boolean;
  surveyPreviewPointCount: number;
  hasAssumedTerrainSlope: boolean;
  standardsOk: boolean;
  placedObjectCount: number;
  parkingCount: number | string;
  systemStatuses: SystemStatuses;
  hasBackendResult: boolean;
  exportBlockText: string;
}): { setupWizardState: SetupWizardStateV1; setupWizardSteps: SetupWizardStep[]; nextSetupAction: string } {
  const anyFreshSystem = Object.values(systemStatuses).some((status) => status === "fresh");
  const derivedSetupWizardSteps: SetupWizardStep[] = [
    {
      id: "address_location",
      label: "Address / Location",
      status: hasAppliedAddress ? "needs_review" : siteAddress.trim() ? "pending" : "not_started",
      panel: "site_existing",
      next_action: hasAppliedAddress
        ? `Address applied: ${appliedAddressLabel || "location context available"}. Continue to site boundary.`
        : siteAddress.trim()
          ? "Apply the entered address or choose a geocode suggestion."
          : "Enter an address, provide coordinates, or choose a blank site.",
      review_required: Boolean(hasAppliedAddress || siteAddress.trim()),
    },
    {
      id: "site_boundary",
      label: "Site Boundary",
      status: siteScaleLocked ? "complete" : siteSizeSet || hasSiteObject ? "pending" : "blocked",
      panel: "site_existing",
      next_action: siteScaleLocked
        ? "Review source candidates and survey/control evidence next."
        : siteSizeSet || hasSiteObject
          ? "Review and lock the site boundary before using it for systems."
          : "Set dimensions or draw/import the boundary.",
      why_blocked: siteScaleLocked || siteSizeSet || hasSiteObject ? "" : "A trusted boundary has not been defined.",
    },
    {
      id: "online_sources_candidates",
      label: "Online Sources / Candidates",
      status: hasSourceContext || hasAppliedAddress ? "needs_review" : "blocked",
      panel: "data",
      next_action: hasSourceContext
        ? "Review the source result; no online/GIS candidate is auto-accepted."
        : hasAppliedAddress
          ? onlineSourceLookupLabel
          : "Add address/location evidence before source discovery.",
      why_blocked: hasAppliedAddress ? "" : "Online/source discovery needs a location or uploaded source.",
      review_required: Boolean(hasSourceContext || hasAppliedAddress),
    },
    {
      id: "survey_terrain_control",
      label: "Survey / Terrain / Control",
      status: hasVerifiedSurveyControl ? "complete" : hasTerrainSource || surveyPreviewPointCount ? "needs_review" : "blocked",
      panel: "import_survey",
      next_action: hasVerifiedSurveyControl
        ? "Continue to standards acceptance."
        : hasAssumedTerrainSlope
          ? "Terrain slope is assumed; survey/control still needed."
          : hasTerrainSource || surveyPreviewPointCount
            ? "Review survey/control, datum, benchmark, coordinate system, and terrain source."
            : "Upload survey/topo/control evidence or explicitly choose an assumed terrain path.",
      why_blocked: hasVerifiedSurveyControl || hasTerrainSource || surveyPreviewPointCount ? "" : "Survey/control remains an explicit gate.",
      review_required: Boolean(!hasVerifiedSurveyControl && (hasTerrainSource || surveyPreviewPointCount)),
    },
    {
      id: "standards",
      label: "Standards",
      status: standardsOk ? "needs_review" : "blocked",
      panel: "standards",
      next_action: "Review standards sources and accept/reject applicable candidate rules.",
      why_blocked: standardsOk ? "" : "Standards acceptance remains an explicit gate.",
      review_required: true,
    },
    {
      id: "objects_program",
      label: "Objects / Program",
      status: placedObjectCount > 1 && Boolean(parkingCount) ? "complete" : siteScaleLocked ? "pending" : "blocked",
      panel: "objects",
      next_action: placedObjectCount > 1 && Boolean(parkingCount)
        ? "Run systems when survey/control and standards gates are ready."
        : siteScaleLocked
          ? "Add buildings, parking/program, roads/access, basin/outfall, and utility points as needed."
          : "Lock the site boundary before placing relied-on objects.",
      why_blocked: siteScaleLocked ? "" : "Objects/program depends on a locked boundary.",
    },
    {
      id: "run_systems",
      label: "Run Systems",
      status: anyFreshSystem ? "complete" : siteScaleLocked && placedObjectCount > 1 && hasTerrainSource && standardsOk ? "pending" : "blocked",
      panel: "generate",
      next_action: anyFreshSystem
        ? "Review blockers and prepare the review/export package."
        : "Clear setup gates before running systems.",
      why_blocked: anyFreshSystem || (siteScaleLocked && placedObjectCount > 1 && hasTerrainSource && standardsOk)
        ? ""
        : "Needs boundary, survey/control, standards, or objects/program.",
    },
    {
      id: "review_export_package",
      label: "Review / Export Package",
      status: hasBackendResult && !exportBlockText ? "needs_review" : "blocked",
      panel: "deliverables",
      next_action: hasBackendResult
        ? "Review the package contents and unresolved notes."
        : "Run systems before preparing the review/export package.",
      why_blocked: hasBackendResult ? exportBlockText || "" : "No system run evidence is available yet.",
      review_required: Boolean(hasBackendResult && !exportBlockText),
    },
  ];
  const persistedSetupWizardSteps =
    persistedSetupWizardState?.schema_version === "setup_wizard_state_v1" &&
    Array.isArray(persistedSetupWizardState.steps)
      ? persistedSetupWizardState.steps
      : [];
  const setupWizardSteps = persistedSetupWizardSteps.length
    ? persistedSetupWizardSteps
    : derivedSetupWizardSteps;
  const setupWizardCurrentStep =
    setupWizardSteps.find((item) => item.id === persistedSetupWizardState?.current_step_id) ??
    setupWizardSteps.find((item) => ["blocked", "needs_review", "pending", "not_started"].includes(item.status)) ??
    setupWizardSteps[setupWizardSteps.length - 1];
  const setupWizardState: SetupWizardStateV1 = {
    schema_version: "setup_wizard_state_v1",
    steps: setupWizardSteps,
    current_step_id: setupWizardCurrentStep?.id,
    current_step_label: setupWizardCurrentStep?.label,
    current_status: setupWizardCurrentStep?.status,
    next_action: persistedSetupWizardState?.next_action || setupWizardCurrentStep?.next_action || "",
    why_blocked: persistedSetupWizardState?.why_blocked || setupWizardCurrentStep?.why_blocked || "",
    blocked_step_ids: setupWizardSteps.filter((item) => item.status === "blocked").map((item) => item.id),
    needs_review_step_ids: setupWizardSteps.filter((item) => item.status === "needs_review").map((item) => item.id),
    exact_blockers:
      persistedSetupWizardState?.exact_blockers ??
      setupWizardSteps.flatMap((item) => item.status === "blocked" ? (item.blockers ?? [item.why_blocked].filter(Boolean) as string[]) : []),
    missing_inputs:
      persistedSetupWizardState?.missing_inputs ??
      setupWizardSteps.flatMap((item) => item.status !== "complete" ? (item.missing_inputs ?? []) : []),
    primary_action_label: persistedSetupWizardState?.primary_action_label || setupWizardCurrentStep?.primary_action_label,
    safe_actions: persistedSetupWizardState?.safe_actions || setupWizardCurrentStep?.safe_actions || [],
    completed_count: setupWizardSteps.filter((item) => item.status === "complete").length,
    total_count: setupWizardSteps.length,
    truth_rules: persistedSetupWizardState?.truth_rules,
  };
  return {
    setupWizardState,
    setupWizardSteps,
    nextSetupAction: setupWizardState.next_action || "Start setup.",
  };
}

export function statusFromSetup(status?: SetupWizardStep["status"]): ProgressTimelineStep["status"] {
  return status === "complete"
    ? "completed"
    : status === "blocked"
      ? "blocked"
      : status === "needs_review"
        ? "needs_review"
        : status === "not_started"
          ? "not_started"
          : "pending";
}

export function progressTimelineStatusClass(status?: ProgressTimelineStep["status"]): string {
  return status === "completed"
    ? "text-emerald-700"
    : status === "blocked"
      ? "text-red-600"
      : status === "needs_review" || status === "current"
        ? "text-amber-600"
        : status === "pending"
          ? "text-slate-600"
          : "text-slate-400";
}

export function progressTimelineDotClass(status?: ProgressTimelineStep["status"]): string {
  return status === "completed"
    ? "border-emerald-600 bg-emerald-600"
    : status === "blocked"
      ? "border-red-500 bg-red-500"
      : status === "needs_review" || status === "current"
        ? "border-amber-500 bg-amber-500"
        : "border-slate-300 bg-white";
}

export function buildDashboardProgressTimelineState({
  persistedProgressTimeline,
  setupWizardSteps,
  candidatePendingCount,
  candidateAcceptedCount,
  candidateItemCount,
  candidateTotalCount,
  placedObjectCount,
  systemStatuses,
  bottomBlockerItems,
  hasHardSystemBlock,
  hasBackendResult,
  exportBlockText,
}: {
  persistedProgressTimeline?: ProgressTimelineV1;
  setupWizardSteps: SetupWizardStep[];
  candidatePendingCount: number;
  candidateAcceptedCount: number;
  candidateItemCount: number;
  candidateTotalCount: number;
  placedObjectCount: number;
  systemStatuses: SystemStatuses;
  bottomBlockerItems: string[];
  hasHardSystemBlock: boolean;
  hasBackendResult: boolean;
  exportBlockText: string;
}): { progressTimelineState: ProgressTimelineV1; progressTimelineSteps: ProgressTimelineStep[]; progressPercent: number } {
  const setupBlockedText = setupWizardSteps
    .filter((item) => item.status === "blocked")
    .map((item) => item.why_blocked || item.next_action)
    .filter(Boolean);
  const derivedProgressTimelineSteps: ProgressTimelineStep[] = [
    {
      id: "setup",
      label: "Setup",
      status: setupWizardSteps.slice(0, 2).some((item) => item.status === "blocked" || item.status === "not_started")
        ? "blocked"
        : setupWizardSteps.slice(0, 2).some((item) => item.status !== "complete")
          ? "needs_review"
          : "completed",
      summary: "Address, location, and boundary establish the project frame.",
      blockers: setupBlockedText.slice(0, 2),
      action_label: "Open setup",
      action_panel: "site_existing",
    },
    {
      id: "sources",
      label: "Sources",
      status: setupWizardSteps.slice(2, 5).some((item) => item.status === "blocked")
        ? "blocked"
        : setupWizardSteps.slice(2, 5).some((item) => item.status !== "complete")
          ? "needs_review"
          : "completed",
      summary: "Survey, terrain, standards, online, and imported evidence.",
      blockers: setupWizardSteps.slice(2, 5).filter((item) => item.status === "blocked").map((item) => item.why_blocked || item.next_action).filter(Boolean),
      action_label: "Review sources",
      action_panel: "data",
    },
    {
      id: "candidates",
      label: "Candidates",
      status: candidatePendingCount > 0
        ? "needs_review"
        : candidateItemCount
          ? "completed"
          : candidateTotalCount > 0
            ? "needs_review"
            : "pending",
      summary: `${candidatePendingCount} pending, ${candidateAcceptedCount} accepted candidate(s).`,
      blockers: candidatePendingCount > 0 ? ["Review pending candidates before relying on them."] : [],
      action_label: "Review candidates",
      action_panel: "data",
    },
    {
      id: "design_objects",
      label: "Design Objects",
      status: statusFromSetup(setupWizardSteps.find((item) => item.id === "objects_program")?.status),
      summary: `${Math.max(0, placedObjectCount)} object(s) in the project model.`,
      blockers: setupWizardSteps.find((item) => item.id === "objects_program")?.why_blocked
        ? [String(setupWizardSteps.find((item) => item.id === "objects_program")?.why_blocked)]
        : [],
      action_label: "Open objects",
      action_panel: "objects",
    },
    {
      id: "systems",
      label: "Systems",
      status: statusFromSetup(setupWizardSteps.find((item) => item.id === "run_systems")?.status),
      summary: Object.entries(systemStatuses).map(([key, value]) => `${key}: ${value}`).join(", "),
      blockers: setupWizardSteps.find((item) => item.id === "run_systems")?.why_blocked
        ? [String(setupWizardSteps.find((item) => item.id === "run_systems")?.why_blocked)]
        : [],
      action_label: "Run systems",
      action_panel: "generate",
    },
    {
      id: "qa",
      label: "QA",
      status: bottomBlockerItems.length || hasHardSystemBlock ? "blocked" : hasBackendResult ? "needs_review" : "pending",
      summary: bottomBlockerItems.length ? `${bottomBlockerItems.length} blocker/review item(s).` : "QA waits for model output.",
      blockers: bottomBlockerItems.slice(0, 4),
      action_label: "Open QA",
      action_panel: "analysis",
    },
    {
      id: "review_package",
      label: "Review Package",
      status: exportBlockText ? "blocked" : hasBackendResult ? "needs_review" : "pending",
      summary: hasBackendResult ? "Review package evidence is available for review." : "Run systems before package review.",
      blockers: exportBlockText ? [exportBlockText] : [],
      action_label: "Open review",
      action_panel: "reports",
    },
    {
      id: "deliverables",
      label: "Deliverables",
      status: exportBlockText ? "blocked" : hasBackendResult ? "needs_review" : "pending",
      summary: hasBackendResult ? "Sheets, reports, exports, and package gates." : "Deliverables need a generated result.",
      blockers: exportBlockText ? [exportBlockText] : [],
      action_label: "Open deliverables",
      action_panel: "deliverables",
    },
  ];
  const progressTimelineSteps =
    persistedProgressTimeline?.schema_version === "progress_timeline_v1" && persistedProgressTimeline.steps?.length
      ? persistedProgressTimeline.steps
      : derivedProgressTimelineSteps;
  const progressTimelineCurrentStep =
    progressTimelineSteps.find((item) => item.id === persistedProgressTimeline?.current_step_id) ??
    progressTimelineSteps.find((item) => ["blocked", "needs_review", "current", "pending", "not_started"].includes(item.status)) ??
    progressTimelineSteps[progressTimelineSteps.length - 1];
  const progressTimelineState: ProgressTimelineV1 = {
    schema_version: "progress_timeline_v1",
    steps: progressTimelineSteps,
    current_step_id: progressTimelineCurrentStep?.id,
    current_step_label: progressTimelineCurrentStep?.label,
    current_status: progressTimelineCurrentStep?.status,
    current_panel: persistedProgressTimeline?.current_panel || progressTimelineCurrentStep?.action_panel as SidePanelKey | undefined,
    next_action: persistedProgressTimeline?.next_action || progressTimelineCurrentStep?.action_label || "",
    exact_blockers:
      persistedProgressTimeline?.exact_blockers ??
      progressTimelineSteps.flatMap((item) => item.status === "blocked" ? (item.blockers ?? []) : []).filter(Boolean),
    blocked_step_ids: progressTimelineSteps.filter((item) => item.status === "blocked").map((item) => item.id),
    needs_review_step_ids: progressTimelineSteps.filter((item) => item.status === "needs_review").map((item) => item.id),
    completed_count: progressTimelineSteps.filter((item) => item.status === "completed").length,
    total_count: progressTimelineSteps.length,
    can_export: persistedProgressTimeline?.can_export ?? !exportBlockText,
    export_blockers: persistedProgressTimeline?.export_blockers ?? (exportBlockText ? [exportBlockText] : []),
    chat_summary: persistedProgressTimeline?.chat_summary,
  };
  const progressPercent =
    progressTimelineState.total_count
      ? Math.round(((progressTimelineState.completed_count ?? 0) / progressTimelineState.total_count) * 100)
      : 0;
  return { progressTimelineState, progressTimelineSteps, progressPercent };
}
