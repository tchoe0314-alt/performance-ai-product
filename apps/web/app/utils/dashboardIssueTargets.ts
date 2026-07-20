import type { Issue } from "../types";

type PreviewIssueLabel = {
  label: string;
};

const ISSUE_TARGET_KEYWORDS = [
  { key: "pipe", token: "PIPE" },
  { key: "drain", token: "DRAIN" },
  { key: "storm", token: "STORM" },
  { key: "basin", token: "BASIN" },
  { key: "parking", token: "PARK" },
  { key: "ada", token: "ADA" },
  { key: "road", token: "ROAD" },
  { key: "utility", token: "UTIL" },
  { key: "water", token: "WATER" },
  { key: "sanitary", token: "SAN" },
];

const numberOrNull = (value: unknown) => {
  const next = typeof value === "number" ? value : Number(value);
  return Number.isFinite(next) ? next : null;
};

export function buildDashboardIssueTargets(issues: Issue[], previewLabels: PreviewIssueLabel[]) {
  if (!issues.length) return [];
  return issues.map((issue, idx) => {
    const lowered = issue.message.toLowerCase();
    const matched = ISSUE_TARGET_KEYWORDS.find((item) => lowered.includes(item.key));
    const labelMatch = matched
      ? previewLabels.find((label) => label.label.toLowerCase().includes(matched.key))
      : null;
    return {
      id: `${issue.message}-${idx}`,
      label: labelMatch?.label ?? "",
    };
  });
}

export function buildDashboardGradingBlocker(issues: Issue[]) {
  const issue = issues.find(
    (item) => (item.code ?? "").toUpperCase() === "DRAINAGE_BLOCKED_BY_GRADING",
  );
  if (!issue?.context || typeof issue.context !== "object") return null;
  const ctx = issue.context as Record<string, unknown>;
  const toPoint = (value: unknown) => {
    if (!value || typeof value !== "object") return null;
    const rec = value as Record<string, unknown>;
    const x = numberOrNull(rec.x);
    const y = numberOrNull(rec.y);
    if (x === null || y === null) return null;
    return { x, y };
  };
  const toZone = (value: unknown) => {
    if (!value || typeof value !== "object") return null;
    const rec = value as Record<string, unknown>;
    const x = numberOrNull(rec.x);
    const y = numberOrNull(rec.y);
    const w = numberOrNull(rec.w);
    const h = numberOrNull(rec.h);
    if (x === null || y === null || w === null || h === null) return null;
    return { x, y, w, h };
  };
  return {
    sourcePoint: toPoint(ctx.source_point),
    blockedTarget: toPoint(ctx.blocked_target),
    blockerLocation: toPoint(ctx.blocker_location),
    suggestedFixZone: toZone(ctx.suggested_fix_zone),
    approximate: Boolean(ctx.approximate),
  };
}
