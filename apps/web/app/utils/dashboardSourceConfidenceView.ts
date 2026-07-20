import type { SiteInputs, SourceConfidenceEntry, SourceConfidenceMap } from "../types";
import { buildDashboardSourceHubMetrics } from "./dashboardEvidenceSummaries";

export type DashboardSourceConfidenceView = {
  entries: SourceConfidenceEntry[];
  summary: NonNullable<SourceConfidenceMap["summary"]>;
  rows: SourceConfidenceEntry[];
  hubMetrics: Array<[string, string | number]>;
  byObjectId: Map<string, SourceConfidenceEntry>;
};

type BuildDashboardSourceConfidenceViewOptions = {
  sourceConfidenceMap: SourceConfidenceMap;
  siteInputs: SiteInputs;
  hasTerrainSource: boolean;
  mapAnalysisSuccess: boolean;
};

export function buildDashboardSourceConfidenceView({
  sourceConfidenceMap,
  siteInputs,
  hasTerrainSource,
  mapAnalysisSuccess,
}: BuildDashboardSourceConfidenceViewOptions): DashboardSourceConfidenceView {
  const entries = sourceConfidenceMap.entries ?? [];
  const summary = sourceConfidenceMap.summary ?? {};
  const byObjectId = new Map<string, SourceConfidenceEntry>();
  entries.forEach((entry) => {
    if (entry.object_id && !byObjectId.has(entry.object_id)) {
      byObjectId.set(entry.object_id, entry);
    }
  });
  return {
    entries,
    summary,
    rows: entries.slice(0, 10),
    hubMetrics: buildDashboardSourceHubMetrics({
      coordinateSystem: (siteInputs as { coordinate_system?: string } | null)?.coordinate_system || "",
      hasTerrainSource,
      mapAnalysisSuccess,
      lowConfidenceCount: Number(summary.low_confidence_count ?? 0),
      needsSurveyControlCount: Number(summary.needs_survey_control_count ?? 0),
      staleOrMissingCount: Number(summary.stale_or_missing_count ?? 0),
    }),
    byObjectId,
  };
}
