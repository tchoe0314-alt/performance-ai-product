import type { Dispatch, MutableRefObject, SetStateAction } from "react";
import { useCallback } from "react";

import { postJson, postJsonWithTimeout } from "../../lib/api";
import type { BuildingPlacement, LocalGisProviderRegistry, ProjectInput, ProjectRecord, SiteInputs } from "../types";
import {
  hasAddressCoordinates,
  type AddressSuggestion,
  type AutoExistingConditionsUiStatus,
  type OnlineExistingConditionsFetchResponse,
} from "../utils/dashboardDataTypes";
import { panelErrorMessage } from "../utils/dashboardStatus";
import type { ProjectStatusSummary, SidePanelKey, WorkspaceMode } from "../utils/workspaceShell";

type SaveProject = (options?: {
  silent?: boolean;
  projectInputOverride?: ProjectInput;
  latestResultOverride?: ProjectRecord["latest_result"];
}) => Promise<ProjectRecord | null>;

type UpdateProjectStatus = (updates: Omit<ProjectStatusSummary, "updatedAt">) => void;

type SaveSiteAddressOptions = {
  preserveLockedSite?: boolean;
  siteWidth?: number;
  siteHeight?: number;
};

type UseDashboardSiteAddressActionOptions = {
  autoExistingRunKeyRef: MutableRefObject<string>;
  clearGeneratedPreview: () => void;
  configuredLocalGisProviderCount: number;
  currentProject: ProjectRecord | null;
  localGisProviderRegistry: LocalGisProviderRegistry;
  payloadPreview: ProjectInput;
  runAutoExistingConditionsAfterSiteLock: (projectInputOverride?: ProjectInput) => Promise<void>;
  saveProject: SaveProject;
  selectedAddressSuggestion: AddressSuggestion | null;
  setActiveSidePanel: Dispatch<SetStateAction<SidePanelKey | null>>;
  setActiveWorkspaceMode: Dispatch<SetStateAction<WorkspaceMode>>;
  setAddressSuggestions: Dispatch<SetStateAction<AddressSuggestion[]>>;
  setAutoExistingConditionsStatus: Dispatch<SetStateAction<AutoExistingConditionsUiStatus>>;
  setBuildingPlacements: Dispatch<SetStateAction<BuildingPlacement[]>>;
  setCurrentProject: Dispatch<SetStateAction<ProjectRecord | null>>;
  setOnlineDiscoveryBusy: Dispatch<SetStateAction<boolean>>;
  setPreviewQuality: Dispatch<SetStateAction<"standard" | "high">>;
  setSelectedAddressSuggestion: Dispatch<SetStateAction<AddressSuggestion | null>>;
  setShowSiteBounds: Dispatch<SetStateAction<boolean>>;
  setSiteAddress: Dispatch<SetStateAction<string>>;
  setSiteScaleLocked: Dispatch<SetStateAction<boolean>>;
  setSiteSelectionMode: Dispatch<SetStateAction<boolean>>;
  setViewportCenter: Dispatch<SetStateAction<{ lat: number; lng: number } | null>>;
  siteAddress: string;
  siteScaleLocked: boolean;
  token: string | null;
  updateProjectStatus: UpdateProjectStatus;
};

function clearAddressSourceContext(siteInputs: SiteInputs): SiteInputs {
  const next = { ...(siteInputs ?? {}) };
  delete next.geocode;
  delete next.location_context;
  delete next.online_existing_conditions_discovery_v1;
  delete next.map_feature_detection_report_v1;
  delete next.existing_conditions_package;
  delete next.auto_existing_conditions_v1;
  delete next.slope_estimate;
  return next;
}

function clearLatestResultSourceContext(latestResult: ProjectRecord["latest_result"] | undefined) {
  if (!latestResult?.final_plan) return latestResult;
  const meta: Record<string, unknown> = { ...(latestResult.final_plan.meta ?? {}) };
  delete meta.location_context;
  delete meta.online_existing_conditions_discovery_v1;
  delete meta.map_feature_detection_report_v1;
  delete meta.existing_conditions_package;
  delete meta.existing_conditions_summary;
  delete meta.auto_existing_conditions_v1;
  return {
    ...latestResult,
    final_plan: {
      ...latestResult.final_plan,
      meta,
    },
  };
}

export function useDashboardSiteAddressAction({
  autoExistingRunKeyRef,
  clearGeneratedPreview,
  configuredLocalGisProviderCount,
  currentProject,
  localGisProviderRegistry,
  payloadPreview,
  runAutoExistingConditionsAfterSiteLock,
  saveProject,
  selectedAddressSuggestion,
  setActiveSidePanel,
  setActiveWorkspaceMode,
  setAddressSuggestions,
  setAutoExistingConditionsStatus,
  setBuildingPlacements,
  setCurrentProject,
  setOnlineDiscoveryBusy,
  setPreviewQuality,
  setSelectedAddressSuggestion,
  setShowSiteBounds,
  setSiteAddress,
  setSiteScaleLocked,
  setSiteSelectionMode,
  setViewportCenter,
  siteAddress,
  siteScaleLocked,
  token,
  updateProjectStatus,
}: UseDashboardSiteAddressActionOptions) {
  return useCallback(
    async (addressOverride?: string, options?: SaveSiteAddressOptions) => {
      const trimmed = (addressOverride ?? siteAddress).trim();
      const preserveLockedSite = Boolean(options?.preserveLockedSite);
      const overrideSiteWidth = options?.siteWidth;
      const overrideSiteHeight = options?.siteHeight;
      if (!token) {
        if (!trimmed) {
          const message = "Type a project address before applying.";
          setAutoExistingConditionsStatus({
            status: "waiting",
            message,
            candidateCount: 0,
            missing: ["address"],
          });
          updateProjectStatus({
            state: "needs review",
            area: "setup",
            title: "Address needed",
            detail: message,
            nextAction: "Type an address in Setup, or lock a manually drawn site boundary.",
          });
          return;
        }
        const currentInput = currentProject?.project_input ?? payloadPreview;
        const nextSiteInputs = {
          ...(currentInput?.meta?.site_inputs ?? {}),
          address: trimmed,
        };
        const nextProjectInput: ProjectInput = {
          ...currentInput,
          input_mode: "user",
          strict_mode: false,
          allow_ai_fill_for_blanks: false,
          manual_fields:
            preserveLockedSite && overrideSiteWidth && overrideSiteHeight
              ? {
                  ...(currentInput?.manual_fields ?? {}),
                  lot: { x: 0, y: 0, w: overrideSiteWidth, h: overrideSiteHeight },
                }
              : currentInput?.manual_fields,
          meta: {
            ...(currentInput?.meta ?? {}),
            site_inputs: nextSiteInputs,
          },
        };
        setCurrentProject((project) =>
          project
            ? {
                ...project,
                project_input: nextProjectInput,
                updated_at: Date.now() / 1000,
              }
            : project,
        );
        setSelectedAddressSuggestion(null);
        setAddressSuggestions([]);
        autoExistingRunKeyRef.current = "";
        setActiveWorkspaceMode("setup");
        setActiveSidePanel("site_existing");
        const message = "Address saved locally. Live geocode and source lookup need sign-in/backend access; you can still create a site, draw, and review this local layout.";
        setAutoExistingConditionsStatus({
          status: "blocked",
          message,
          candidateCount: 0,
          missing: ["backend session", "geocode", "source providers"],
        });
        updateProjectStatus({
          state: "needs review",
          area: "setup",
          title: "Address applied locally",
          detail: message,
          nextAction: "Create or lock the site boundary, then draw or generate from the local layout.",
        });
        return;
      }
      const currentInput = currentProject?.project_input ?? payloadPreview;
      const nextSiteInputs = {
        ...(currentInput?.meta?.site_inputs ?? {}),
        address: trimmed || undefined,
      };
      if (!trimmed) {
        const clearedSiteInputs = clearAddressSourceContext(nextSiteInputs);
        delete clearedSiteInputs.address;
        const clearedLatestResult = clearLatestResultSourceContext(currentProject?.latest_result);
        const clearedProjectInput: ProjectInput = {
          ...currentInput,
          input_mode: "user",
          strict_mode: false,
          allow_ai_fill_for_blanks: false,
          meta: {
            ...(currentInput?.meta ?? {}),
            site_inputs: clearedSiteInputs,
          },
        };
        setSelectedAddressSuggestion(null);
        setAddressSuggestions([]);
        setSiteAddress("");
        autoExistingRunKeyRef.current = "";
        setAutoExistingConditionsStatus({
          status: "waiting",
          message: "Apply an address and lock the site. Civora will then check available source context inside the boundary.",
          candidateCount: 0,
          missing: [],
        });
        setCurrentProject((project) =>
          project
            ? {
                ...project,
                project_input: clearedProjectInput,
                latest_result: clearedLatestResult,
                updated_at: Date.now() / 1000,
              }
            : project,
        );
        await saveProject({
          silent: true,
          projectInputOverride: clearedProjectInput,
          latestResultOverride: clearedLatestResult,
        });
        updateProjectStatus({
          state: "needs review",
          area: "setup",
          title: "Address cleared",
          detail: "Site address cleared.",
          nextAction: "Apply a new address or lock a manually drawn site boundary.",
        });
        return;
      }
      try {
        setOnlineDiscoveryBusy(true);
        updateProjectStatus({
          state: "working",
          area: "setup",
          title: "Applying address",
          detail: "Civora is geocoding the address and checking available source context.",
          nextAction: "Wait for source candidates or an exact provider/auth blocker.",
        });
        const runningSiteInputs = clearAddressSourceContext(nextSiteInputs);
        runningSiteInputs.address = trimmed;
        const runningProjectInput: ProjectInput = {
          ...currentInput,
          input_mode: "user",
          strict_mode: false,
          allow_ai_fill_for_blanks: false,
          meta: {
            ...(currentInput?.meta ?? {}),
            site_inputs: runningSiteInputs,
          },
        };
        setCurrentProject((project) =>
          project
            ? {
                ...project,
                project_input: runningProjectInput,
                latest_result: clearLatestResultSourceContext(project.latest_result),
                updated_at: Date.now() / 1000,
              }
            : project,
        );
        let geocode = selectedAddressSuggestion;
        if (!hasAddressCoordinates(geocode)) {
          geocode = await postJson<AddressSuggestion>("/api/geocode", { address: trimmed }, { token });
        }
        if (!hasAddressCoordinates(geocode)) {
          const geocodeMessage =
            geocode?.message ||
            geocode?.blockers?.find((item) => item?.message)?.message ||
            "Address lookup did not return usable map coordinates.";
          setAutoExistingConditionsStatus({
            status: "blocked",
            message: `Geocode failed: ${geocodeMessage} Check the address or place the site manually.`,
            candidateCount: 0,
            missing: ["geocode"],
          });
          updateProjectStatus({
            state: "blocked",
            area: "setup",
            title: "Apply address needs correction",
            detail: `${geocodeMessage} The map was not moved.`,
            nextAction: "Check the address, or set site size/draw the boundary manually.",
          });
          return;
        }
        clearGeneratedPreview();
        nextSiteInputs.address = trimmed;
        nextSiteInputs.geocode = {
          lat: geocode.lat,
          lng: geocode.lng,
          display_name: geocode.display_name,
          provider: geocode.provider ?? "nominatim",
          confidence: geocode.confidence ?? null,
          crs: geocode.crs ?? { epsg: "EPSG:4326", units: "degrees" },
          location_context: geocode.location_context ?? undefined,
        };
        nextSiteInputs.location_context =
          geocode.location_context ?? {
            address: geocode.display_name,
            normalized_address: geocode.display_name,
            coordinates: { lat: geocode.lat, lng: geocode.lng },
            crs: geocode.crs ?? { epsg: "EPSG:4326", units: "degrees" },
            evidence_source: geocode.provider ?? "geocoder",
            truth_label:
              "Address/geocode is location context only; it is not a site boundary, survey, control, or final reliance source.",
          };
        const activeViewportBounds = (nextSiteInputs.viewport_bounds ?? {}) as {
          west?: number;
          south?: number;
          east?: number;
          north?: number;
        };
        const activeSiteBoundary =
          Number.isFinite(Number(activeViewportBounds.west)) &&
          Number.isFinite(Number(activeViewportBounds.south)) &&
          Number.isFinite(Number(activeViewportBounds.east)) &&
          Number.isFinite(Number(activeViewportBounds.north))
            ? {
                west: Number(activeViewportBounds.west),
                south: Number(activeViewportBounds.south),
                east: Number(activeViewportBounds.east),
                north: Number(activeViewportBounds.north),
              }
            : undefined;
        let onlineFetch: OnlineExistingConditionsFetchResponse | null = null;
        try {
          onlineFetch = await postJsonWithTimeout<OnlineExistingConditionsFetchResponse>(
            "/api/existing-conditions/fetch-online",
            {
              address: geocode.display_name,
              bbox: activeSiteBoundary,
              active_site_boundary: activeSiteBoundary ?? {},
              include_floodplain: true,
              include_wetlands: true,
              include_parcels: true,
              include_building_footprints: true,
              include_roads: true,
              include_utilities: true,
              include_contours: true,
              include_elevation: true,
              include_imagery_detection: true,
              provider_registry: localGisProviderRegistry,
            },
            { token },
            90000,
          );
        } catch (error) {
          onlineFetch = {
            success: false,
            status: "fetch_failed",
            online_existing_conditions_discovery_v1: {
              version: "online_existing_conditions_discovery_v1",
              status: "fetch_failed",
              candidate_count: 0,
              sources: [],
              blockers: [error instanceof Error ? error.message : "Online existing-condition discovery failed."],
              review_required: true,
              acceptance_status: "missing",
              truth_label:
                "Online existing-condition discovery failed; no online source candidate is treated as accepted project evidence.",
            },
          };
        }
        if (onlineFetch?.online_existing_conditions_discovery_v1) {
          nextSiteInputs.online_existing_conditions_discovery_v1 = onlineFetch.online_existing_conditions_discovery_v1;
          if (onlineFetch.online_existing_conditions_discovery_v1.local_gis_provider_registry_v1) {
            nextSiteInputs.local_gis_provider_registry_v1 = onlineFetch.online_existing_conditions_discovery_v1.local_gis_provider_registry_v1;
          }
        }
        if (onlineFetch?.map_feature_detection_report_v1) {
          nextSiteInputs.map_feature_detection_report_v1 = onlineFetch.map_feature_detection_report_v1;
        }
        if (onlineFetch?.existing_conditions_package) {
          nextSiteInputs.existing_conditions_package = onlineFetch.existing_conditions_package;
        }
        nextSiteInputs.site_alignment_locked = preserveLockedSite ? true : false;
        if (preserveLockedSite) {
          nextSiteInputs.site_boundary_state = "locked_canonical";
          nextSiteInputs.site_boundary_source = "dimensions";
        }
        setAddressSuggestions([]);
        setActiveWorkspaceMode("setup");
        setActiveSidePanel("site_existing");
        const latestResultOverride =
          currentProject?.latest_result?.final_plan
            ? {
                ...currentProject.latest_result,
                final_plan: {
                  ...currentProject.latest_result.final_plan,
                  meta: {
                    ...(currentProject.latest_result.final_plan.meta ?? {}),
                    location_context: nextSiteInputs.location_context,
                    online_existing_conditions_discovery_v1: onlineFetch?.online_existing_conditions_discovery_v1,
                    map_feature_detection_report_v1: onlineFetch?.map_feature_detection_report_v1,
                    existing_conditions_package: onlineFetch?.existing_conditions_package,
                    existing_conditions_summary: onlineFetch?.existing_conditions_summary,
                  },
                },
              }
            : undefined;
        const nextProjectInput: ProjectInput = {
          ...currentInput,
          input_mode: "user",
          strict_mode: false,
          allow_ai_fill_for_blanks: false,
          meta: {
            ...(currentInput?.meta ?? {}),
            site_inputs: nextSiteInputs,
          },
          manual_fields:
            preserveLockedSite && overrideSiteWidth && overrideSiteHeight
              ? {
                  ...(currentInput?.manual_fields ?? {}),
                  lot: { x: 0, y: 0, w: overrideSiteWidth, h: overrideSiteHeight },
                }
              : currentInput?.manual_fields,
        };
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
        if (preserveLockedSite) {
          setSiteScaleLocked(true);
          setShowSiteBounds(false);
          setSiteSelectionMode(false);
          setBuildingPlacements((prevPlacements) =>
            prevPlacements.map((item) =>
              item.type === "site"
                ? {
                    ...item,
                    locked: true,
                    capabilities: {
                      ...(item.capabilities ?? {}),
                      movable: false,
                      resizable: false,
                      rotatable: false,
                      deletable: false,
                    },
                    meta: {
                      ...(item.meta ?? {}),
                      site_boundary_state: "locked_canonical",
                      source_ui_mode: item.meta?.source_ui_mode ?? "site_setup",
                    },
                  }
                : item,
            ),
          );
        } else {
          setSiteScaleLocked(false);
        }
        setSiteAddress(trimmed);
        setShowSiteBounds(preserveLockedSite ? false : true);
        setPreviewQuality("standard");
        setSiteSelectionMode(preserveLockedSite ? false : true);
        setViewportCenter({ lat: geocode.lat, lng: geocode.lng });
        autoExistingRunKeyRef.current = "";
        const candidateCount = Number(onlineFetch?.online_existing_conditions_discovery_v1?.candidate_count ?? 0);
        const discoveryStatus = String(onlineFetch?.online_existing_conditions_discovery_v1?.status || onlineFetch?.status || "");
        const providerSources = onlineFetch?.online_existing_conditions_discovery_v1?.sources ?? [];
        const lookupUnavailable =
          candidateCount === 0 &&
          (discoveryStatus.includes("failed") ||
            (!configuredLocalGisProviderCount && !providerSources.length));
        const providerAbsent =
          candidateCount === 0 &&
          !discoveryStatus.includes("failed") &&
          !configuredLocalGisProviderCount &&
          !providerSources.length;
        updateProjectStatus({
          state: lookupUnavailable ? "blocked" : candidateCount > 0 ? "needs review" : "ready",
          area: "setup",
          title: lookupUnavailable
            ? "Address applied, source lookup needs attention"
            : candidateCount > 0
              ? "Address applied, sources need review"
              : "Address applied",
          detail:
            candidateCount > 0
              ? `Found ${candidateCount} online source candidate${candidateCount === 1 ? "" : "s"} for review.`
              : lookupUnavailable
                ? providerAbsent
                  ? "Address applied; no online/local source providers are configured yet."
                  : "Address applied; online source lookup failed or providers were unavailable."
                : "Online source discovery found no usable candidates yet; missing providers are listed in setup.",
          nextAction: lookupUnavailable
            ? "Add GIS providers or upload survey/topo evidence before relying on source context."
            : preserveLockedSite || siteScaleLocked
              ? "Review source candidates, then generate review drafts when ready."
              : "Lock the site boundary to check sources inside the site.",
        });
        setAutoExistingConditionsStatus({
          status: lookupUnavailable ? "blocked" : preserveLockedSite || siteScaleLocked ? "running" : "waiting",
          message: lookupUnavailable
            ? providerAbsent
              ? "Address applied, but no source providers are configured. Add GIS providers or upload survey/topo evidence before relying on source context."
              : "Address applied, but provider lookup failed or was unavailable. Retry after the backend/providers respond."
            : preserveLockedSite || siteScaleLocked
              ? "Address changed. Civora will recheck sources inside the locked site."
              : "Address applied. Lock the site boundary to auto-check roads, buildings, terrain, constraints, and utilities inside it.",
          candidateCount,
          missing: lookupUnavailable ? (providerAbsent ? ["source providers"] : ["provider lookup"]) : [],
        });
        setSelectedAddressSuggestion(geocode);
        if (preserveLockedSite || siteScaleLocked) {
          void runAutoExistingConditionsAfterSiteLock(nextProjectInput);
        }
      } catch (error) {
        const message = `Geocode failed: ${panelErrorMessage(error, "Check the address or retry after the backend responds.")}`;
        setAutoExistingConditionsStatus({
          status: "blocked",
          message,
          candidateCount: 0,
          missing: ["geocode"],
        });
        updateProjectStatus({
          state: "blocked",
          area: "setup",
          title: "Apply address needs attention",
          detail: message,
          nextAction: "Check the address or retry after the backend responds.",
        });
      } finally {
        setOnlineDiscoveryBusy(false);
      }
    },
    [
      autoExistingRunKeyRef,
      clearGeneratedPreview,
      configuredLocalGisProviderCount,
      currentProject,
      localGisProviderRegistry,
      payloadPreview,
      runAutoExistingConditionsAfterSiteLock,
      saveProject,
      selectedAddressSuggestion,
      setActiveSidePanel,
      setActiveWorkspaceMode,
      setAddressSuggestions,
      setAutoExistingConditionsStatus,
      setBuildingPlacements,
      setCurrentProject,
      setOnlineDiscoveryBusy,
      setPreviewQuality,
      setSelectedAddressSuggestion,
      setShowSiteBounds,
      setSiteAddress,
      setSiteScaleLocked,
      setSiteSelectionMode,
      setViewportCenter,
      siteAddress,
      siteScaleLocked,
      token,
      updateProjectStatus,
    ],
  );
}
