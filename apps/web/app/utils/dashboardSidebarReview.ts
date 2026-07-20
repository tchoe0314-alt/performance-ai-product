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
