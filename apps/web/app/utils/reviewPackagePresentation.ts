import type { PlanSheetSet } from "../components/PlanSheetEditor";
import type { ReviewPackageFlowSummary } from "./dashboardDataTypes";

const INTERNAL_AUTHORITY_NOTE =
  /construction\s+(?:release|readiness)|not\s+for\s+construction|stamp(?:ed|ing)?|seal(?:ed|ing)?|certif(?:y|ied|ication)|approve(?:d|s|ing)?\s+construction|engineer\s+of\s+record/i;

export function customerFacingReviewNotes(values: Iterable<unknown>): string[] {
  const notes: string[] = [];
  for (const value of values) {
    const note = String(value ?? "").trim();
    if (!note || INTERNAL_AUTHORITY_NOTE.test(note) || notes.includes(note)) continue;
    notes.push(note);
  }
  return notes;
}

export function normalizeReviewSheetSetForProject(
  sheetSet: PlanSheetSet,
  rawProjectName: string,
): PlanSheetSet {
  const projectName = rawProjectName.trim() || "Untitled Project";
  const sheets = sheetSet.sheets.map((sheet) => ({
    ...sheet,
    titleBlock: {
      ...sheet.titleBlock,
      projectName,
    },
  }));
  return {
    ...sheetSet,
    name: `${projectName} Review Package`,
    sheets,
    sheetIndex: sheets.map((sheet) => ({
      sheetNumber: sheet.titleBlock.sheetNumber,
      title: sheet.titleBlock.sheetTitle,
    })),
    plotStyles: {
      ...sheetSet.plotStyles,
      reviewWatermark: "REVIEW ONLY",
    },
    blockers: customerFacingReviewNotes(sheetSet.blockers),
  };
}

export function normalizeReviewPackageSummary(
  summary: ReviewPackageFlowSummary | null,
): ReviewPackageFlowSummary | null {
  if (!summary) return null;
  const missing = customerFacingReviewNotes(summary.missing);
  return {
    ...summary,
    missing,
    next_action: missing.length
      ? `Review missing package inputs: ${missing.slice(0, 3).join("; ")}.`
      : "Send the package for professional review.",
  };
}
