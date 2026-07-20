import type { SidePanelKey } from "./workspaceShell";
import {
  OVERSIZED_SITE_MESSAGE,
  SITE_GRADING_HARD_BLOCK_ACRES,
  siteAreaAcresFromSize,
  uniqueStrings,
  type SystemGenerationTarget,
} from "./workflowConstants";

export type GeneratePreflightBlocker = {
  label: string;
  action: SidePanelKey;
};

type IssueLike = {
  message: string;
};

export const buildGeneratePreflightBlockers = ({
  target,
  lot,
  siteScaleLocked,
  hasTerrainSource,
  hasStandardsEvidence,
  hasAppliedAddress,
  onlineSourceLookupUnavailable,
  hasVerifiedSurveyControl,
  hasAssumedTerrainSlope,
}: {
  target: SystemGenerationTarget;
  lot: { w: number; h: number };
  siteScaleLocked: boolean;
  hasTerrainSource: boolean;
  hasStandardsEvidence: boolean;
  hasAppliedAddress: boolean;
  onlineSourceLookupUnavailable: boolean;
  hasVerifiedSurveyControl: boolean;
  hasAssumedTerrainSlope: boolean;
}): GeneratePreflightBlocker[] => {
  const missingBoundary = !(lot.w && lot.h);
  const areaAcres = siteAreaAcresFromSize(lot.w, lot.h);
  const needsAll = target === "full";
  const needsGrading = needsAll || target === "grading" || target === "drainage";
  const blockers: GeneratePreflightBlocker[] = [];

  if (missingBoundary) blockers.push({ label: "missing site boundary dimensions", action: "site_existing" });
  if (!siteScaleLocked) blockers.push({ label: "site boundary exists but is not locked", action: "site_existing" });
  if (needsGrading && !hasTerrainSource) blockers.push({ label: "missing terrain/source", action: "import_survey" });
  if (!hasStandardsEvidence) blockers.push({ label: "missing standards", action: "standards" });
  if (needsAll && hasAppliedAddress && onlineSourceLookupUnavailable) {
    blockers.push({ label: "Address applied; online source lookup not configured/available.", action: "data" });
  }
  if (needsAll && !hasVerifiedSurveyControl && hasAssumedTerrainSlope) {
    blockers.push({ label: "assumed terrain slope / survey-control still needed", action: "import_survey" });
  }
  if (areaAcres > SITE_GRADING_HARD_BLOCK_ACRES && needsGrading) {
    blockers.push({ label: OVERSIZED_SITE_MESSAGE, action: "site_existing" });
  }
  return Array.from(new Map(blockers.map((item) => [item.label, item])).values());
};

export const buildCanonicalWorkspaceBlockers = ({
  fullGeneratePreflightBlockers,
  issues,
  analysisIssues,
  siteBoundaryState,
  siteScaleLocked,
}: {
  fullGeneratePreflightBlockers: GeneratePreflightBlocker[];
  issues: IssueLike[];
  analysisIssues: IssueLike[];
  siteBoundaryState?: string | null;
  siteScaleLocked: boolean;
}) =>
  uniqueStrings([
    ...fullGeneratePreflightBlockers.map((item) => item.label),
    ...issues.map((issue) => issue.message),
    ...analysisIssues.map((issue) => issue.message),
    siteScaleLocked && siteBoundaryState === "draft_editable"
      ? "site locked state contradicts draft boundary source"
      : "",
    !siteScaleLocked && siteBoundaryState === "locked_canonical"
      ? "site unlocked state contradicts locked boundary source"
      : "",
  ]).filter(Boolean);
