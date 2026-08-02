import type { Dispatch, MutableRefObject, SetStateAction } from "react";
import { useCallback } from "react";

import type { BuildingPlacement, ProjectInput, ProjectRecord, SiteInputs, SurveySlopeResponse } from "../types";
import type { AutoExistingConditionsUiStatus, OnlineExistingConditionsFetchResponse } from "../utils/dashboardDataTypes";
import { buildAssumedSlopeEstimate, type SystemGenerationTarget } from "../utils/workflowConstants";
import { parsePositiveNumber } from "../utils/formatting";
import { runQueuedSourceContextLookup } from "../utils/sourceContextJobs";
import type { ProjectStatusSummary } from "../utils/workspaceShell";

type SaveProject = (options?: {
  silent?: boolean;
  projectInputOverride?: ProjectInput;
  latestResultOverride?: ProjectRecord["latest_result"];
}) => Promise<ProjectRecord | null>;

type UpdateProjectStatus = (updates: Omit<ProjectStatusSummary, "updatedAt">) => void;

type ViewportFootprint = {
  widthFt: number;
  heightFt: number;
  bounds?: {
    north: number;
    south: number;
    east: number;
    west: number;
    centerLat: number;
    centerLng: number;
  };
};

type UseDashboardAutoExistingConditionsOptions = {
  assumedTerrainSlopePct: string;
  autoExistingRunKeyRef: MutableRefObject<string>;
  buildingPlacements: BuildingPlacement[];
  configuredLocalGisProviderCount: number;
  currentProject: ProjectRecord | null;
  handleGenerateSystemRef: MutableRefObject<
    | ((target: SystemGenerationTarget, options?: { slopeEstimateOverride?: SurveySlopeResponse | null }) => Promise<void>)
    | null
  >;
  hasTerrainSource: boolean;
  hasVerifiedSurveyControl: boolean;
  lotHeight: string;
  lotWidth: string;
  payloadPreview: ProjectInput;
  projectId: string | null;
  saveProject: SaveProject;
  setAssumedTerrainSlopePct: Dispatch<SetStateAction<string>>;
  setAutoExistingConditionsStatus: Dispatch<SetStateAction<AutoExistingConditionsUiStatus>>;
  setCurrentProject: Dispatch<SetStateAction<ProjectRecord | null>>;
  setOnlineDiscoveryBusy: Dispatch<SetStateAction<boolean>>;
  setSurveySlopeEstimate: Dispatch<SetStateAction<SurveySlopeResponse | null>>;
  setUseSurveyForGrading: Dispatch<SetStateAction<boolean>>;
  siteAddress: string;
  siteInputs: SiteInputs;
  surveySlopeEstimate: SurveySlopeResponse | null;
  token: string | null;
  updateProjectStatus: UpdateProjectStatus;
  viewportCenter: { lat: number; lng: number } | null;
  viewportFootprint: ViewportFootprint | null;
};

export function useDashboardAutoExistingConditions({
  assumedTerrainSlopePct,
  autoExistingRunKeyRef,
  buildingPlacements,
  configuredLocalGisProviderCount,
  currentProject,
  handleGenerateSystemRef,
  hasTerrainSource,
  hasVerifiedSurveyControl,
  lotHeight,
  lotWidth,
  payloadPreview,
  projectId,
  saveProject,
  setAssumedTerrainSlopePct,
  setAutoExistingConditionsStatus,
  setCurrentProject,
  setOnlineDiscoveryBusy,
  setSurveySlopeEstimate,
  setUseSurveyForGrading,
  siteAddress,
  siteInputs,
  surveySlopeEstimate,
  token,
  updateProjectStatus,
  viewportCenter,
  viewportFootprint,
}: UseDashboardAutoExistingConditionsOptions) {
  return useCallback(
    async (projectInputOverride?: ProjectInput) => {
      const currentInput = projectInputOverride ?? currentProject?.project_input ?? payloadPreview;
      const currentSiteInputs = (currentInput?.meta?.site_inputs ?? {}) as SiteInputs;
      const geocode = currentSiteInputs.geocode;
      const address = String(currentSiteInputs.address || geocode?.display_name || siteAddress || "").trim();
      const site = buildingPlacements.find((item) => item.type === "site");
      const width = parsePositiveNumber(lotWidth) ?? site?.w ?? viewportFootprint?.widthFt ?? 0;
      const height = parsePositiveNumber(lotHeight) ?? site?.d ?? viewportFootprint?.heightFt ?? 0;
      const runKey = [
        projectId || currentProject?.project_id || "local",
        address,
        geocode?.lat ?? viewportCenter?.lat ?? "",
        geocode?.lng ?? viewportCenter?.lng ?? "",
        Math.round(width),
        Math.round(height),
        site?.id ?? "",
      ].join("|");

      if (!address && !(geocode?.lat && geocode?.lng)) {
        setAutoExistingConditionsStatus({
          status: "blocked",
          message: "Site is locked. Add an address to automatically check roads, buildings, terrain, constraints, and utilities.",
          candidateCount: 0,
          missing: ["address/geocode"],
        });
        updateProjectStatus({
          state: "blocked",
          area: "setup",
          title: "Site context needs address",
          detail: "Site is locked, but address/geocode context is missing.",
          nextAction: "Add an address or map center context, then recheck sources inside the site.",
        });
        return;
      }
      if (!token) {
        setAutoExistingConditionsStatus({
          status: "blocked",
          message: "Site is locked. Sign in or connect the backend to run automatic source discovery.",
          candidateCount: 0,
          missing: ["backend session"],
        });
        updateProjectStatus({
          state: "blocked",
          area: "setup",
          title: "Site context needs connection",
          detail: "Automatic source discovery needs a backend session.",
          nextAction: "Sign in or reconnect backend, then recheck sources inside the site.",
        });
        return;
      }
      if (autoExistingRunKeyRef.current === runKey) {
        return;
      }
      autoExistingRunKeyRef.current = runKey;
      setOnlineDiscoveryBusy(true);
      setAutoExistingConditionsStatus({
        status: "running",
        message: "Checking parcels, roads, buildings, constraints, utilities, elevation, and grading context inside the locked site...",
        candidateCount: 0,
        missing: [],
      });
      updateProjectStatus({
        state: "working",
        area: "setup",
        title: "Detecting site context",
        detail: "Checking parcels, roads, buildings, constraints, utilities, elevation, and grading context inside the locked site.",
        nextAction: "Wait for source candidates or an exact provider/backend blocker.",
      });

      try {
        let onlineFetch: OnlineExistingConditionsFetchResponse | null = null;
        try {
          onlineFetch = await runQueuedSourceContextLookup({
            projectId,
            token,
            request: {
              address: address || geocode?.display_name || "Locked site",
              bbox: viewportFootprint?.bounds
                ? {
                    north: viewportFootprint.bounds.north,
                    south: viewportFootprint.bounds.south,
                    east: viewportFootprint.bounds.east,
                    west: viewportFootprint.bounds.west,
                    center_lat: viewportFootprint.bounds.centerLat,
                    center_lng: viewportFootprint.bounds.centerLng,
                    width_ft: width || viewportFootprint.widthFt,
                    height_ft: height || viewportFootprint.heightFt,
                  }
                : undefined,
              include_floodplain: true,
              include_wetlands: true,
              include_parcels: true,
              include_building_footprints: true,
              include_roads: true,
              include_utilities: true,
              include_contours: true,
              include_elevation: true,
              include_imagery_detection: true,
              provider_registry: currentSiteInputs.local_gis_provider_registry_v1 ?? siteInputs?.local_gis_provider_registry_v1 ?? {},
            },
            onProgress: (job) => {
              setAutoExistingConditionsStatus({
                status: "running",
                message: job.stage_detail || "Checking site sources in the background...",
                candidateCount: 0,
                missing: [],
              });
            },
          });
        } catch (error) {
          onlineFetch = {
            success: false,
            status: "fetch_failed",
            online_existing_conditions_discovery_v1: {
              version: "online_existing_conditions_discovery_v1",
              status: "fetch_failed",
              candidate_count: 0,
              sources: [],
              blockers: [error instanceof Error ? error.message : "Automatic existing-condition discovery failed."],
              review_required: true,
              acceptance_status: "missing",
              truth_label:
                "Automatic existing-condition discovery failed; no source candidate is treated as accepted project evidence.",
            },
          };
        }

        const discovery = onlineFetch?.online_existing_conditions_discovery_v1;
        const sources = Array.isArray(discovery?.sources) ? discovery.sources : [];
        const candidateCount = Number(discovery?.candidate_count ?? 0);
        const discoveryStatus = String(discovery?.status || onlineFetch?.status || "");
        const providerFailed = discoveryStatus.includes("failed") || Boolean(discovery?.blockers?.length && candidateCount === 0);
        const providersAbsent = candidateCount === 0 && sources.length === 0 && !configuredLocalGisProviderCount;
        const missing = sources
          .filter((source) => Number(source.candidate_count ?? 0) <= 0)
          .map((source) => String(source.label || source.key || source.source_type || "source unavailable"))
          .slice(0, 6);
        const slopePct = parsePositiveNumber(assumedTerrainSlopePct) ?? 8;
        const needsAssumedSlope = !hasTerrainSource && !surveySlopeEstimate?.slope_percent;
        const slopeEstimateOverride = needsAssumedSlope ? buildAssumedSlopeEstimate(slopePct) : null;
        if (needsAssumedSlope && slopeEstimateOverride) {
          setAssumedTerrainSlopePct(String(slopePct));
          setUseSurveyForGrading(false);
          setSurveySlopeEstimate(slopeEstimateOverride);
        }

        const autoExistingConditions = {
          version: "auto_existing_conditions_v1",
          status: candidateCount > 0 || slopeEstimateOverride || hasTerrainSource ? "ready_for_review" : "blocked_or_missing_sources",
          triggered_by: "site_lock",
          clipped_to_locked_site: true,
          candidate_count: candidateCount,
          sources_requested: [
            "parcels",
            "buildings",
            "roads",
            "floodplain",
            "wetlands",
            "utilities",
            "contours",
            "elevation",
            "grading_context",
          ],
          missing_sources: missing,
          grading_context: slopeEstimateOverride
            ? {
                source: "explicit_assumed_slope",
                slope_percent: slopePct,
                review_required: true,
                survey_backed: false,
              }
            : {
                source: hasTerrainSource ? "survey_or_terrain_source" : "missing",
                review_required: true,
                survey_backed: hasVerifiedSurveyControl,
              },
          review_required: true,
          construction_release_allowed: false,
          truth_label:
            "Automatic existing-condition detection creates review-required candidates only; it is not survey/control or final professional evidence.",
        };
        const nextSiteInputs: SiteInputs = {
          ...currentSiteInputs,
          site_alignment_locked: true,
          site_boundary_state: "locked_canonical",
          online_existing_conditions_discovery_v1: discovery ?? currentSiteInputs.online_existing_conditions_discovery_v1,
          map_feature_detection_report_v1:
            onlineFetch?.map_feature_detection_report_v1 ?? currentSiteInputs.map_feature_detection_report_v1,
          existing_conditions_package:
            onlineFetch?.existing_conditions_package ?? currentSiteInputs.existing_conditions_package,
          candidate_review_inbox_v1:
            onlineFetch?.candidate_review_inbox_v1 ?? currentSiteInputs.candidate_review_inbox_v1,
          civora_vision_review_workspace_v1:
            onlineFetch?.civora_vision_review_workspace_v1 ?? currentSiteInputs.civora_vision_review_workspace_v1,
          source_context_detection_coverage_v1:
            onlineFetch?.source_context_detection_coverage_v1 ?? currentSiteInputs.source_context_detection_coverage_v1,
          auto_existing_conditions_v1: autoExistingConditions,
          ...(slopeEstimateOverride
            ? {
                assumed_terrain_slope_pct: slopePct,
                slope_estimate: slopeEstimateOverride,
                use_survey_for_grading: false,
              }
            : {}),
        };
        if (discovery?.local_gis_provider_registry_v1) {
          nextSiteInputs.local_gis_provider_registry_v1 = discovery.local_gis_provider_registry_v1;
        }
        const nextProjectInput: ProjectInput = {
          ...currentInput,
          input_mode: "user",
          strict_mode: false,
          allow_ai_fill_for_blanks: false,
          meta: {
            ...(currentInput?.meta ?? {}),
            site_inputs: nextSiteInputs,
          },
        };
        const latestResultOverride =
          currentProject?.latest_result?.final_plan
            ? {
                ...currentProject.latest_result,
                final_plan: {
                  ...currentProject.latest_result.final_plan,
                  meta: {
                    ...(currentProject.latest_result.final_plan.meta ?? {}),
                    online_existing_conditions_discovery_v1: discovery,
                    map_feature_detection_report_v1: onlineFetch?.map_feature_detection_report_v1,
                    existing_conditions_package: onlineFetch?.existing_conditions_package,
                    existing_conditions_summary: onlineFetch?.existing_conditions_summary,
                    candidate_review_inbox_v1: onlineFetch?.candidate_review_inbox_v1,
                    civora_vision_review_workspace_v1: onlineFetch?.civora_vision_review_workspace_v1,
                    source_context_detection_coverage_v1: onlineFetch?.source_context_detection_coverage_v1,
                    auto_existing_conditions_v1: autoExistingConditions,
                  },
                },
              }
            : undefined;

        setCurrentProject((project) =>
          project
            ? {
                ...project,
                project_input: nextProjectInput,
                latest_result: latestResultOverride ?? project.latest_result,
                has_result: latestResultOverride ? true : project.has_result,
                updated_at: Date.now() / 1000,
              }
            : project,
        );
        await saveProject({
          silent: true,
          projectInputOverride: nextProjectInput,
          latestResultOverride,
        });
        setAutoExistingConditionsStatus({
          status: providerFailed || providersAbsent ? "blocked" : candidateCount > 0 || slopeEstimateOverride || hasTerrainSource ? "ready" : "blocked",
          message:
            providerFailed
              ? `Source provider lookup failed: ${(discovery?.blockers ?? [])[0] || "the backend/provider did not return source candidates"}. Retry source discovery after the provider responds.`
              : providersAbsent
                ? "No source providers are configured. Add GIS providers or upload survey/topo evidence before relying on source context."
                : candidateCount > 0
                  ? `Found ${candidateCount} source candidate${candidateCount === 1 ? "" : "s"} inside/near the locked site for review.`
                  : slopeEstimateOverride
                    ? `No source candidates were found yet. Grading has an explicit ${slopePct}% assumed slope for review only.`
                    : "Configured providers returned no usable features inside/near the locked site.",
          candidateCount,
          missing: providersAbsent ? ["source providers"] : providerFailed ? ["provider lookup"] : missing,
        });
        updateProjectStatus({
          state: providerFailed || providersAbsent ? "blocked" : "needs review",
          area: "setup",
          title: providerFailed
            ? "Site context needs provider"
            : providersAbsent
              ? "Site context needs sources"
              : "Site context needs review",
          detail:
            providerFailed
              ? "Existing-condition source lookup failed; retry after providers/backend respond."
              : providersAbsent
                ? "No source providers are configured yet."
                : candidateCount > 0
                  ? `Found ${candidateCount} existing-condition candidate${candidateCount === 1 ? "" : "s"} for review inside the site.`
                  : slopeEstimateOverride
                    ? `No source candidates found yet; grading is using an explicit ${slopePct}% assumed slope for review only.`
                    : "Existing-condition providers returned no usable features inside the site.",
          nextAction:
            providerFailed
              ? "Retry source discovery after providers/backend respond."
              : providersAbsent
                ? "Add GIS providers or upload survey/topo evidence before relying on source context."
                : "Review source candidates and assumptions before generating.",
        });
        if (slopeEstimateOverride || hasTerrainSource) {
          void handleGenerateSystemRef.current?.("grading", { slopeEstimateOverride });
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : "Automatic existing-condition discovery could not finish.";
        setAutoExistingConditionsStatus({
          status: "blocked",
          message,
          candidateCount: 0,
          missing: ["automatic source discovery"],
        });
        updateProjectStatus({
          state: "blocked",
          area: "setup",
          title: "Site context needs attention",
          detail: message,
          nextAction: "Check backend/provider connectivity, then recheck sources inside the site.",
        });
      } finally {
        setOnlineDiscoveryBusy(false);
      }
    },
    [
      assumedTerrainSlopePct,
      autoExistingRunKeyRef,
      buildingPlacements,
      configuredLocalGisProviderCount,
      currentProject,
      handleGenerateSystemRef,
      hasTerrainSource,
      hasVerifiedSurveyControl,
      lotHeight,
      lotWidth,
      payloadPreview,
      projectId,
      saveProject,
      setAssumedTerrainSlopePct,
      setAutoExistingConditionsStatus,
      setCurrentProject,
      setOnlineDiscoveryBusy,
      setSurveySlopeEstimate,
      setUseSurveyForGrading,
      siteAddress,
      siteInputs,
      surveySlopeEstimate?.slope_percent,
      token,
      updateProjectStatus,
      viewportCenter,
      viewportFootprint,
    ],
  );
}
