import type { SidebarStatus } from "./workspaceShell";

export type SidebarReviewItem = { label: string; value: string; status: SidebarStatus };

export function buildSidebarTruthItems({
  hasTruthEvidence,
  releaseStatus,
  trustScore,
  trustScoreLabel,
  assumptionCount,
  hasBackendResult,
  staleSystems,
  hasHardSystemBlock,
  previewBlockedReasonCount,
}: {
  hasTruthEvidence: boolean;
  releaseStatus: string;
  trustScore: number | null;
  trustScoreLabel: string;
  assumptionCount: number;
  hasBackendResult: boolean;
  staleSystems: string[];
  hasHardSystemBlock: boolean;
  previewBlockedReasonCount: number;
}): SidebarReviewItem[] {
  return [
    {
      label: "Engineer review",
      value: !hasTruthEvidence
        ? "not evaluated"
        : releaseStatus === "ready"
          ? "ready_for_engineer_review"
          : releaseStatus === "blocked"
            ? "needs input"
            : "review required",
      status: !hasTruthEvidence ? "idle" : "review",
    },
    {
      label: "Professional review",
      value: hasTruthEvidence ? "independent review required" : "not evaluated",
      status: hasTruthEvidence ? "review" : "idle",
    },
    {
      label: "Low confidence",
      value: !hasTruthEvidence
        ? "not evaluated"
        : typeof trustScore === "number" && trustScore >= 80
          ? "none flagged"
          : trustScoreLabel,
      status: !hasTruthEvidence
        ? "idle"
        : typeof trustScore === "number" && trustScore >= 80
          ? "ok"
          : "review",
    },
    {
      label: "Assumptions",
      value: !hasBackendResult
        ? "not evaluated"
        : assumptionCount
          ? `${assumptionCount} need acceptance`
          : "none reported",
      status: !hasBackendResult ? "idle" : assumptionCount ? "review" : "ok",
    },
    {
      label: "Stale outputs",
      value: !hasBackendResult
        ? "not evaluated"
        : staleSystems.length
          ? staleSystems.slice(0, 2).join(", ")
          : "none",
      status: !hasBackendResult ? "idle" : staleSystems.length ? "review" : "ok",
    },
    {
      label: "Needs input",
      value: !hasTruthEvidence
        ? "not evaluated"
        : hasHardSystemBlock || previewBlockedReasonCount
          ? "review inputs"
          : "none recorded",
      status: !hasTruthEvidence ? "idle" : hasHardSystemBlock || previewBlockedReasonCount ? "block" : "ok",
    },
  ];
}

export function buildReviewGateItems({
  standardsOk,
  hasTerrainSource,
  hasBackendResult,
  releaseStatus,
}: {
  standardsOk: boolean;
  hasTerrainSource: boolean;
  hasBackendResult: boolean;
  releaseStatus: string;
}): SidebarReviewItem[] {
  return [
    {
      label: "Standards",
      value: standardsOk ? "engineer/user acceptance" : "sources or criteria needed",
      status: standardsOk ? "review" : "block",
    },
    {
      label: "Survey / control",
      value: hasTerrainSource ? "verification required" : "missing",
      status: hasTerrainSource ? "review" : "block",
    },
    {
      label: "Calculations",
      value: hasBackendResult ? "engineer review required" : "not generated",
      status: hasBackendResult ? "review" : "block",
    },
    {
      label: "Exports",
      value: releaseStatus === "ready" ? "review package ready" : releaseStatus === "blocked" ? "blocked" : "review package",
      status: releaseStatus === "blocked" ? "block" : "review",
    },
    {
      label: "Independent review",
      value: "required outside Civora",
      status: "review",
    },
  ];
}

export function buildDashboardSidebarReviewState({
  systemStatuses,
  missingSite,
  hasTerrainSource,
  hasBasinPlaced,
  drainageFresh,
  backendResultPresent,
  siteScaleLocked,
  buildingPlacementCount,
  siteAddress,
  siteInputAddress,
  siteInputLat,
  siteInputLng,
  uploadedImagePreviewUrl,
  uploadedImageApiUrl,
  surveyPreviewPointCount,
  mapSnapshotPath,
  releaseStatusRaw,
  trustScoreRaw,
  assumptionCategories,
  hasHardSystemBlock,
  previewBlockedReasonCount,
  standardsOk,
}: {
  systemStatuses: Record<string, string>;
  missingSite: boolean;
  hasTerrainSource: boolean;
  hasBasinPlaced: boolean;
  drainageFresh: boolean;
  backendResultPresent: boolean;
  siteScaleLocked: boolean;
  buildingPlacementCount: number;
  siteAddress: string;
  siteInputAddress?: unknown;
  siteInputLat?: unknown;
  siteInputLng?: unknown;
  uploadedImagePreviewUrl?: string | null;
  uploadedImageApiUrl?: string | null;
  surveyPreviewPointCount: number;
  mapSnapshotPath?: string | null;
  releaseStatusRaw?: unknown;
  trustScoreRaw?: unknown;
  assumptionCategories?: unknown;
  hasHardSystemBlock: boolean;
  previewBlockedReasonCount: number;
  standardsOk: boolean;
}) {
  const sidebarStaleSystems = Object.entries(systemStatuses)
    .filter(([, status]) => status === "stale")
    .map(([system]) => system);
  const sidebarMissingInputs = [
    missingSite ? "site" : null,
    !hasTerrainSource ? "terrain" : null,
    !hasBasinPlaced && !drainageFresh ? "basin" : null,
  ].filter(Boolean) as string[];
  const sidebarHasTruthEvidence = Boolean(
    backendResultPresent ||
      siteScaleLocked ||
      buildingPlacementCount ||
      siteAddress.trim() ||
      siteInputAddress ||
      siteInputLat ||
      siteInputLng ||
      uploadedImagePreviewUrl ||
      uploadedImageApiUrl ||
      surveyPreviewPointCount ||
      mapSnapshotPath,
  );
  const sidebarReleaseStatus = String(releaseStatusRaw || "review").toLowerCase();
  const sidebarTrustScore =
    typeof trustScoreRaw === "number" ? `${Math.round(trustScoreRaw)}%` : "not reported";
  const sidebarAssumptions = Array.isArray(assumptionCategories)
    ? assumptionCategories.filter(Boolean)
    : [];
  const sidebarTruthItems = buildSidebarTruthItems({
    hasTruthEvidence: sidebarHasTruthEvidence,
    releaseStatus: sidebarReleaseStatus,
    trustScore: typeof trustScoreRaw === "number" ? trustScoreRaw : null,
    trustScoreLabel: sidebarTrustScore,
    assumptionCount: sidebarAssumptions.length,
    hasBackendResult: backendResultPresent,
    staleSystems: sidebarStaleSystems,
    hasHardSystemBlock,
    previewBlockedReasonCount,
  });
  const reviewGateItems = buildReviewGateItems({
    standardsOk,
    hasTerrainSource,
    hasBackendResult: backendResultPresent,
    releaseStatus: sidebarReleaseStatus,
  });
  return {
    sidebarStaleSystems,
    sidebarMissingInputs,
    sidebarHasTruthEvidence,
    sidebarReleaseStatus,
    sidebarTrustScore,
    sidebarAssumptions,
    sidebarTruthItems,
    reviewGateItems,
  };
}

export function buildIssueDiagnosticSummary({
  projectId,
  projectName,
  panelTitle,
  visibleStatusSummary,
  siteLocked,
  lotWidth,
  lotHeight,
  systemStatuses,
  issueReportMessage,
}: {
  projectId: string;
  projectName: string;
  panelTitle: string;
  visibleStatusSummary: string;
  siteLocked: boolean;
  lotWidth: number;
  lotHeight: number;
  systemStatuses: Record<string, string>;
  issueReportMessage: string;
}) {
  return [
    "Civora pilot issue report",
    `Project ID: ${projectId}`,
    `Project name: ${projectName}`,
    `Panel / workflow step: ${panelTitle}`,
    `Visible status: ${visibleStatusSummary}`,
    `Site: ${siteLocked ? "locked" : "not locked"}; ${lotWidth && lotHeight ? `${lotWidth.toFixed(0)} ft x ${lotHeight.toFixed(0)} ft` : "size unavailable"}`,
    `Systems: ${Object.entries(systemStatuses).map(([key, value]) => `${key}=${value}`).join(", ")}`,
    `User message: ${issueReportMessage.trim() || "(add details before sending)"}`,
    "",
    "Reminder: outputs are review-required materials only. Field use remains outside Civora.",
  ].join("\n");
}
