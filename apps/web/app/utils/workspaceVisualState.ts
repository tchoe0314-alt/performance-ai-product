import type { SourceConfidenceEntry } from "../types";
import type { WorkspaceVisualState } from "../components/WorkspaceStateBadge";

export function sourceVisualState(entry: SourceConfidenceEntry): WorkspaceVisualState {
  if (entry.stale || entry.dirty) return "stale";
  if (entry.missing) return "blocked";
  if (entry.verified === true && !entry.needs_verification && !entry.needs_survey_control) return "verified";
  if (entry.source_type === "inferred") return "assumed";
  return "unverified";
}
