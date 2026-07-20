import type { OnlineExistingConditionsDiscovery } from "../types";
import type {
  AutoExistingConditionsUiStatus,
  AutoSiteContextFlowSummary,
} from "./dashboardDataTypes";
import { toReadableLabel } from "./formatting";
import { uniqueStrings } from "./workflowConstants";

export type AutoSiteContextRow = {
  key: string;
  title: string;
  status: string;
  count: number;
  provider: string;
  detail: string;
};

export type PreviewSourceContextBadge = {
  label: string;
  tone: "found" | "missing" | "review";
};

const readable = (value: unknown) => toReadableLabel(String(value ?? "")).trim();
const textFor = (value: unknown) => readable(value).toLowerCase();

const matchesSourceTerms = (record: Record<string, unknown>, terms: string[]) => {
  const blob = [
    record.key,
    record.label,
    record.source_type,
    record.feature_type,
    record.provider,
    record.agency,
    record.status,
    record.message,
  ].map(textFor).join(" ");
  return terms.some((term) => blob.includes(term));
};

const missingMatches = (value: unknown, terms: string[]) => {
  const record = value && typeof value === "object" ? (value as Record<string, unknown>) : { label: value };
  return matchesSourceTerms(record, terms);
};

export const buildAutoSiteContextFlowSummary = ({
  autoContext,
  onlineDiscovery,
  autoExistingConditionsStatus,
}: {
  autoContext: Record<string, unknown>;
  onlineDiscovery: OnlineExistingConditionsDiscovery;
  autoExistingConditionsStatus: AutoExistingConditionsUiStatus;
}): AutoSiteContextFlowSummary => {
  const discoverySources = Array.isArray(onlineDiscovery.sources) ? onlineDiscovery.sources : [];
  const candidateLabels = uniqueStrings([
    ...discoverySources
      .filter((source) => Number(source.candidate_count ?? 0) > 0)
      .map((source) => source.label || source.key || source.source_type),
    Number(autoContext.candidate_count ?? 0) > 0 ? "Auto Site Context source candidates" : "",
  ]).slice(0, 8);
  const discoveryMissing = Array.isArray((onlineDiscovery as Record<string, unknown>).missing_sources)
    ? ((onlineDiscovery as Record<string, unknown>).missing_sources as unknown[])
    : [];
  const missingLabels = uniqueStrings([
    ...discoverySources
      .filter((source) => Number(source.candidate_count ?? 0) <= 0)
      .map((source) => source.label || source.key || source.source_type),
    ...discoveryMissing.map((source) => {
      if (source && typeof source === "object") {
        const record = source as Record<string, unknown>;
        return record.label || record.key || record.source_type;
      }
      return source;
    }),
    ...(Array.isArray(autoContext.missing_sources) ? autoContext.missing_sources : []),
  ]).slice(0, 8);
  const candidateCount = Math.max(
    Number(autoContext.candidate_count ?? 0),
    Number(onlineDiscovery.candidate_count ?? 0),
    autoExistingConditionsStatus.candidateCount,
    candidateLabels.length,
  );
  const status = String(autoContext.status || onlineDiscovery.status || autoExistingConditionsStatus.status || "waiting");
  const message =
    candidateCount > 0
      ? `Apply Address found ${candidateCount} review-required source candidate${candidateCount === 1 ? "" : "s"} that Generate can use as context.`
      : missingLabels.length
        ? `Apply Address found no usable source candidates yet. Sources still needed: ${missingLabels.slice(0, 3).join(", ")}.`
        : autoExistingConditionsStatus.message || "Auto Site Context has not produced review candidates yet.";
  return {
    candidateCount,
    candidateLabels,
    missingLabels,
    status,
    message,
    reviewRequired: true,
  };
};

export const buildAutoSiteContextRows = ({
  onlineDiscovery,
  onlineDiscoverySources,
  siteIntelligenceFound,
  siteIntelligenceMissing,
  siteIntelligenceAssumed,
  siteIntelligenceOutside,
  hasAssumedTerrainSlope,
  assumedTerrainSlopePct,
}: {
  onlineDiscovery: OnlineExistingConditionsDiscovery;
  onlineDiscoverySources: NonNullable<OnlineExistingConditionsDiscovery["sources"]>;
  siteIntelligenceFound: Array<Record<string, unknown>>;
  siteIntelligenceMissing: Array<Record<string, unknown>>;
  siteIntelligenceAssumed: Array<Record<string, unknown>>;
  siteIntelligenceOutside: Array<Record<string, unknown>>;
  hasAssumedTerrainSlope: boolean;
  assumedTerrainSlopePct: string;
}): AutoSiteContextRow[] => {
  const missingRecords = Array.isArray((onlineDiscovery as Record<string, unknown>).missing_sources)
    ? ((onlineDiscovery as Record<string, unknown>).missing_sources as unknown[])
    : [];
  const categories = [
    { key: "parcel", title: "Parcel / site boundary", terms: ["parcel", "boundary", "site"] },
    { key: "roads", title: "Roads / ROW", terms: ["road", "row", "right of way", "frontage", "drive"] },
    { key: "buildings", title: "Buildings", terms: ["building", "footprint", "structure"] },
    { key: "terrain", title: "Terrain / elevation", terms: ["terrain", "elevation", "dem", "lidar", "contour", "grading"] },
    { key: "flood_wetlands", title: "Flood / wetlands", terms: ["flood", "wetland", "constraint"] },
    { key: "utilities", title: "Utilities", terms: ["utility", "utilities", "water", "sanitary", "storm", "sewer"] },
  ];
  return categories.map((category) => {
    const source = onlineDiscoverySources.find((item) => matchesSourceTerms(item as Record<string, unknown>, category.terms));
    const intelligenceFound = siteIntelligenceFound.filter((item) => matchesSourceTerms(item, category.terms));
    const intelligenceMissing = siteIntelligenceMissing.filter((item) => matchesSourceTerms(item, category.terms));
    const intelligenceAssumed = siteIntelligenceAssumed.filter((item) => matchesSourceTerms(item, category.terms));
    const intelligenceOutside = siteIntelligenceOutside.filter((item) => matchesSourceTerms(item, category.terms));
    const explicitMissing = missingRecords.filter((item) => missingMatches(item, category.terms));
    const count = Math.max(
      Number(source?.candidate_count ?? 0),
      ...intelligenceFound.map((item) => Number(item.count ?? 1)).filter(Number.isFinite),
      0,
    );
    const status =
      count > 0
        ? "found"
        : intelligenceOutside.length
          ? "outside"
          : intelligenceAssumed.length || (category.key === "terrain" && hasAssumedTerrainSlope)
            ? "assumed"
            : source || explicitMissing.length || intelligenceMissing.length
              ? "missing"
              : "not_checked";
    const blocker =
      Array.isArray(source?.blockers) && source.blockers.length
        ? source.blockers.map(String).join("; ")
        : explicitMissing.length
          ? explicitMissing
              .map((item) => {
                const record = item && typeof item === "object" ? (item as Record<string, unknown>) : { label: item };
                const missing = Array.isArray(record.missing) ? record.missing.map(String).join("; ") : "";
                return missing || readable(record.label || record.key || record.source_type);
              })
              .filter(Boolean)
              .join("; ")
          : intelligenceMissing.length
            ? intelligenceMissing.map((item) => readable(item.label || item.source_type || item.status)).join("; ")
            : "";
    const provider = readable(source?.provider || source?.agency || source?.source_type || "");
    const detail =
      status === "found"
        ? `${count} review candidate${count === 1 ? "" : "s"}${provider ? ` from ${provider}` : ""}.`
        : status === "outside"
          ? `${intelligenceOutside.length} candidate${intelligenceOutside.length === 1 ? "" : "s"} found outside the active site.`
          : status === "assumed"
            ? category.key === "terrain" && hasAssumedTerrainSlope
              ? `Using explicit ${assumedTerrainSlopePct || "8"}% assumed slope until survey/terrain is added.`
              : "Context is inferred/assumed and needs review."
            : status === "missing"
              ? blocker || `${category.title} source returned no usable features or is not configured.`
              : "Not checked yet. Apply an address and create/lock a site.";
    return {
      key: category.key,
      title: category.title,
      status,
      count,
      provider,
      detail,
    };
  });
};

export const buildPreviewSourceContextBadges = ({
  autoSiteContextFlowSummary,
  hasAssumedTerrainSlope,
  assumedTerrainSlopePct,
}: {
  autoSiteContextFlowSummary: AutoSiteContextFlowSummary;
  hasAssumedTerrainSlope: boolean;
  assumedTerrainSlopePct: string;
}): PreviewSourceContextBadge[] =>
  [
    ...autoSiteContextFlowSummary.candidateLabels.slice(0, 3).map((label) => ({
      label: toReadableLabel(String(label)).slice(0, 26),
      tone: "found" as const,
    })),
    ...autoSiteContextFlowSummary.missingLabels.slice(0, 3).map((label) => ({
      label: toReadableLabel(String(label)).slice(0, 26),
      tone: "missing" as const,
    })),
    ...(hasAssumedTerrainSlope
      ? [{ label: `${assumedTerrainSlopePct || "8"}% slope`, tone: "review" as const }]
      : []),
  ].slice(0, 5);
