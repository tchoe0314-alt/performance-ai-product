import { useMemo } from "react";

import type {
  LocalGisProviderRegistry,
  OnlineExistingConditionsDiscovery,
  PlanMeta,
  SiteInputs,
} from "../types";
import type {
  AutoExistingConditionsUiStatus,
  AutoSiteContextFlowSummary,
} from "../utils/dashboardDataTypes";
import {
  buildAutoSiteContextFlowSummary,
  buildAutoSiteContextRows,
  buildPreviewSourceContextBadges,
} from "../utils/dashboardAutoSiteContext";

type DashboardAutoSiteContextStateOptions = {
  assumedTerrainSlopePct: string;
  autoExistingConditionsStatus: AutoExistingConditionsUiStatus;
  currentPlanMeta: PlanMeta;
  hasAppliedAddress: boolean;
  hasAssumedTerrainSlope: boolean;
  siteInputs: SiteInputs;
};

export function useDashboardAutoSiteContextState({
  assumedTerrainSlopePct,
  autoExistingConditionsStatus,
  currentPlanMeta,
  hasAppliedAddress,
  hasAssumedTerrainSlope,
  siteInputs,
}: DashboardAutoSiteContextStateOptions) {
  const onlineDiscovery = useMemo(
    () =>
      (siteInputs?.online_existing_conditions_discovery_v1 ??
        (currentPlanMeta.online_existing_conditions_discovery_v1 as OnlineExistingConditionsDiscovery | undefined) ??
        {}) as OnlineExistingConditionsDiscovery,
    [currentPlanMeta, siteInputs?.online_existing_conditions_discovery_v1],
  );
  const mapFeatureDetectionReport = useMemo(
    () =>
      ((siteInputs?.map_feature_detection_report_v1 ??
        (currentPlanMeta.map_feature_detection_report_v1 as Record<string, unknown> | undefined) ??
        {}) as Record<string, unknown>),
    [currentPlanMeta, siteInputs?.map_feature_detection_report_v1],
  );
  const siteIntelligenceSummary = useMemo(
    () =>
      ((onlineDiscovery.site_intelligence_summary_v1 ??
        mapFeatureDetectionReport.site_intelligence_summary_v1 ??
        {}) as Record<string, unknown>),
    [mapFeatureDetectionReport, onlineDiscovery],
  );
  const siteIntelligenceFound = useMemo(
    () => Array.isArray(siteIntelligenceSummary.found)
      ? (siteIntelligenceSummary.found as Array<Record<string, unknown>>)
      : [],
    [siteIntelligenceSummary],
  );
  const siteIntelligenceMissing = useMemo(
    () => Array.isArray(siteIntelligenceSummary.missing)
      ? (siteIntelligenceSummary.missing as Array<Record<string, unknown>>)
      : [],
    [siteIntelligenceSummary],
  );
  const siteIntelligenceAssumed = useMemo(
    () => Array.isArray(siteIntelligenceSummary.assumed)
      ? (siteIntelligenceSummary.assumed as Array<Record<string, unknown>>)
      : [],
    [siteIntelligenceSummary],
  );
  const siteIntelligenceOutside = useMemo(
    () => Array.isArray(siteIntelligenceSummary.outside_site)
      ? (siteIntelligenceSummary.outside_site as Array<Record<string, unknown>>)
      : [],
    [siteIntelligenceSummary],
  );
  const roadFrontageHint = (siteIntelligenceSummary.road_frontage ?? {}) as Record<string, unknown>;
  const drivewaySuggestion = Array.isArray(siteIntelligenceSummary.driveway_suggestions)
    ? ((siteIntelligenceSummary.driveway_suggestions as Array<Record<string, unknown>>)[0] ?? {})
    : {};
  const gradingContextHint = (siteIntelligenceSummary.grading_context ?? {}) as Record<string, unknown>;
  const onlineDiscoverySources = useMemo(
    () => Array.isArray(onlineDiscovery.sources) ? onlineDiscovery.sources : [],
    [onlineDiscovery.sources],
  );
  const onlineFoundSources = onlineDiscoverySources.filter((source) => Number(source.candidate_count ?? 0) > 0);
  const onlineDiscoveryCandidateCount = Number(onlineDiscovery.candidate_count ?? 0);
  const localGisProviderRegistry =
    (siteInputs?.local_gis_provider_registry_v1 ??
      onlineDiscovery.local_gis_provider_registry_v1 ??
      (currentPlanMeta.local_gis_provider_registry_v1 as LocalGisProviderRegistry | undefined) ??
      {}) as LocalGisProviderRegistry;
  const localGisProviders = Array.isArray(localGisProviderRegistry.providers) ? localGisProviderRegistry.providers : [];
  const configuredLocalGisProviders = localGisProviders.filter((provider) => Boolean(provider.service_url || provider.arcgis?.service_url));
  const onlineSourceLookupUnavailable =
    hasAppliedAddress &&
    onlineDiscoveryCandidateCount === 0 &&
    String(onlineDiscovery.status || "").includes("failed");
  const onlineSourceProvidersAbsent =
    hasAppliedAddress &&
    onlineDiscoveryCandidateCount === 0 &&
    onlineDiscoverySources.length === 0 &&
    configuredLocalGisProviders.length === 0 &&
    !onlineSourceLookupUnavailable;
  const onlineSourceLookupLabel = !hasAppliedAddress
    ? "Needs address/location first"
    : onlineDiscoveryCandidateCount > 0
      ? `${onlineDiscoveryCandidateCount} candidate${onlineDiscoveryCandidateCount === 1 ? "" : "s"} for review`
      : onlineSourceLookupUnavailable
        ? "Provider lookup failed; retry source discovery."
        : onlineSourceProvidersAbsent
          ? "No source providers configured."
          : "Providers returned no usable features.";
  const autoSiteContextData = useMemo(
    () =>
      ((siteInputs?.auto_existing_conditions_v1 ??
        (currentPlanMeta as Record<string, unknown>).auto_existing_conditions_v1 ??
        {}) as Record<string, unknown>),
    [currentPlanMeta, siteInputs?.auto_existing_conditions_v1],
  );
  const autoSiteContextFlowSummary = useMemo<AutoSiteContextFlowSummary>(
    () =>
      buildAutoSiteContextFlowSummary({
        autoContext: autoSiteContextData,
        onlineDiscovery,
        autoExistingConditionsStatus,
      }),
    [autoExistingConditionsStatus, autoSiteContextData, onlineDiscovery],
  );
  const autoSiteContextRows = useMemo(
    () =>
      buildAutoSiteContextRows({
        onlineDiscovery,
        onlineDiscoverySources,
        siteIntelligenceFound,
        siteIntelligenceMissing,
        siteIntelligenceAssumed,
        siteIntelligenceOutside,
        hasAssumedTerrainSlope,
        assumedTerrainSlopePct,
      }),
    [
      assumedTerrainSlopePct,
      hasAssumedTerrainSlope,
      onlineDiscovery,
      onlineDiscoverySources,
      siteIntelligenceAssumed,
      siteIntelligenceFound,
      siteIntelligenceMissing,
      siteIntelligenceOutside,
    ],
  );
  const previewSourceContextBadges = useMemo(
    () =>
      buildPreviewSourceContextBadges({
        autoSiteContextFlowSummary,
        hasAssumedTerrainSlope,
        assumedTerrainSlopePct,
      }),
    [assumedTerrainSlopePct, autoSiteContextFlowSummary, hasAssumedTerrainSlope],
  );

  return {
    autoSiteContextData,
    autoSiteContextFlowSummary,
    autoSiteContextRows,
    configuredLocalGisProviders,
    drivewaySuggestion,
    gradingContextHint,
    localGisProviderRegistry,
    localGisProviders,
    onlineDiscovery,
    onlineDiscoveryCandidateCount,
    onlineDiscoverySources,
    onlineFoundSources,
    onlineSourceLookupLabel,
    onlineSourceLookupUnavailable,
    onlineSourceProvidersAbsent,
    previewSourceContextBadges,
    roadFrontageHint,
    siteIntelligenceAssumed,
    siteIntelligenceFound,
    siteIntelligenceMissing,
    siteIntelligenceOutside,
    siteIntelligenceSummary,
  };
}
