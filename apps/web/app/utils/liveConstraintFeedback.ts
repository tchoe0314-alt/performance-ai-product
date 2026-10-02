import type { BuildingPlacement } from "../types";
import { assessSiteInterference, type InterferenceResult } from "./siteInterference";

export type LiveConstraintFeedback = {
  issues: InterferenceResult[];
  objectIds: string[];
  conflictCount: number;
  reviewCount: number;
};

const LIVE_CONSTRAINT_CODES = new Set([
  "outside_site_boundary",
  "setback_rule_violation",
  "surface_footprint_contact",
  "physical_volume_contact",
  "access_crosses_island",
  "coordination_envelope_contact",
]);

export function buildLiveConstraintFeedback(
  objects: BuildingPlacement[],
  selectedObjectId: string | null,
): LiveConstraintFeedback {
  if (!selectedObjectId) return { issues: [], objectIds: [], conflictCount: 0, reviewCount: 0 };
  const issues = assessSiteInterference(objects).filter((issue) =>
    issue.objectIds.includes(selectedObjectId) && LIVE_CONSTRAINT_CODES.has(issue.code),
  );
  return {
    issues,
    objectIds: [...new Set(issues.flatMap((issue) => issue.objectIds).filter((id) => objects.some((item) => item.id === id && item.type !== "site")))],
    conflictCount: issues.filter((issue) => issue.severity === "conflict").length,
    reviewCount: issues.filter((issue) => issue.severity === "review").length,
  };
}
