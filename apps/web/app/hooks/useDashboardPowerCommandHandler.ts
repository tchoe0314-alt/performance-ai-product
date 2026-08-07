import { useCallback } from "react";

import type {
  BuildingPlacement,
  ChatMessage,
  Issue,
  ProgressTimelineV1,
  SiteObjectType,
} from "../types";
import type {
  AutoExistingConditionsUiStatus,
  GenerateFlowSummary,
} from "../utils/dashboardDataTypes";
import { parseDashboardDirectSiteSetupCommand } from "../utils/dashboardChatCommandParsing";
import {
  normalizeDashboardChatIntent,
  userFacingWorkflowNeeds,
} from "../utils/dashboardChatIntent";
import {
  createDenseCommercialConceptPlacements,
  createDenseSubdivisionCadPlanPlacements,
  createUrbanizationCampusPlanPlacements,
} from "../utils/demoWorkspaceData";
import { parsePositiveNumber } from "../utils/formatting";
import type {
  CadToolRequestForPreview,
  RecentChange,
} from "../utils/dashboardTypes";
import type { PreviewLayerVisibility } from "../components/FloatingLayerManager";
import {
  projectStatusDisplayLabel,
  type ProjectStatusSummary,
  type SidePanelKey,
  type WorkspaceMode,
} from "../utils/workspaceShell";
import type {
  EngineeringSystemKey,
  SystemGenerationTarget,
} from "../utils/workflowConstants";
import { uniqueStrings } from "../utils/workflowConstants";
import type { DashboardAccessAnalysisIssue } from "./useDashboardSiteAccessAnalysis";

type StateSetter<T> = (value: T | ((prev: T) => T)) => void;

type AppendChatMessage = (
  role: ChatMessage["role"],
  content: string,
  kind?: ChatMessage["kind"],
  feedback?: ChatMessage["feedback"],
) => void;

type HandleAddObject = (
  type: SiteObjectType,
  options?: {
    label?: string;
    style?: Record<string, string>;
    geometryType?: "polygon" | "polyline" | "rect";
    placed?: boolean;
    width?: number;
    depth?: number;
    meta?: Record<string, unknown>;
  },
) => void;

type AutoFitSite = (
  width: number,
  height: number,
  label?: string,
  siteIdOverride?: string | null,
  fitMap?: boolean,
  lockSite?: boolean,
  preserveExistingObjects?: boolean,
) => void;

type SaveSiteAddress = (
  addressOverride?: string,
  options?: {
    preserveLockedSite?: boolean;
    siteWidth?: number;
    siteHeight?: number;
  },
) => Promise<unknown>;

type WorkflowReviewDashboard = {
  release_blockers?: string[];
} | null;

type RecordRecentChange = (change: Omit<RecentChange, "id" | "createdAt">) => void;

type UseDashboardPowerCommandHandlerInput = {
  activePlacementId: string | null;
  appendChatMessage: AppendChatMessage;
  analysisIssues: DashboardAccessAnalysisIssue[];
  autoFitSite: AutoFitSite;
  buildingPlacements: BuildingPlacement[];
  canonicalWorkspaceBlockers: string[];
  clearGeneratedPreview: () => void;
  generateFlowSummary: GenerateFlowSummary | null;
  handleAddObject: HandleAddObject;
  handleCreateDenseCommercialConcept: (message: string) => boolean;
  handleGenerateSystem: (target: SystemGenerationTarget) => void | Promise<void>;
  handleMakeReviewPackage: () => void | Promise<void>;
  handleOpenSidePanel: (panel: SidePanelKey) => void;
  handleSetPreviewMode: (mode: "2d" | "3d") => void;
  handleSetPreviewQuality: (quality: "standard" | "high") => void;
  handleStartBlankSite: () => void;
  handleStartSiteBoundaryDraw: () => void;
  hasSiteBoundary: () => boolean;
  issues: Issue[];
  markSystemsStale: (systems: EngineeringSystemKey[]) => void;
  parkingCount: string;
  pendingPlacementObjects: BuildingPlacement[];
  placementModeEnabled: boolean;
  progressTimelineState: ProgressTimelineV1;
  projectStatusSummary: ProjectStatusSummary;
  recordRecentChange: RecordRecentChange;
  refuseUnsafeConstructionCommand: (message: string) => boolean;
  resolveLotBounds: () => { w: number; h: number };
  saveSiteAddress: SaveSiteAddress;
  setActivePlacementId: StateSetter<string | null>;
  setActiveSidePanel: StateSetter<SidePanelKey | null>;
  setActiveWorkspaceMode: StateSetter<WorkspaceMode>;
  setAutoExistingConditionsStatus: StateSetter<AutoExistingConditionsUiStatus>;
  setBuildingPlacements: StateSetter<BuildingPlacement[]>;
  setCadToolRequest: StateSetter<CadToolRequestForPreview | null>;
  setCommandBarExpanded: StateSetter<boolean>;
  setFitToSiteRequest: StateSetter<number>;
  setLotHeight: StateSetter<string>;
  setLotWidth: StateSetter<string>;
  setParkingCount: StateSetter<string>;
  setPreviewInteraction: StateSetter<"static" | "edit">;
  setPreviewLayers: StateSetter<PreviewLayerVisibility>;
  setPreviewMode: StateSetter<"2d" | "3d">;
  setRenderedSidePanel: StateSetter<SidePanelKey | null>;
  setRightRailCollapsed: StateSetter<boolean>;
  setShowSiteBounds: StateSetter<boolean>;
  setSidePanelVisible: StateSetter<boolean>;
  setSiteAddress: StateSetter<string>;
  setSiteSelectionMode: StateSetter<boolean>;
  setStatusMessage: StateSetter<string>;
  siteAddress: string;
  siteScaleLocked: boolean;
  systemStatuses: Record<string, string>;
  updateProjectStatus: (summary: Omit<ProjectStatusSummary, "updatedAt">) => void;
  workflowActionHints: string[];
  workflowReviewDashboard: WorkflowReviewDashboard;
};

export function useDashboardPowerCommandHandler({
  activePlacementId,
  appendChatMessage,
  analysisIssues,
  autoFitSite,
  buildingPlacements,
  canonicalWorkspaceBlockers,
  clearGeneratedPreview,
  generateFlowSummary,
  handleAddObject,
  handleCreateDenseCommercialConcept,
  handleGenerateSystem,
  handleMakeReviewPackage,
  handleOpenSidePanel,
  handleSetPreviewMode,
  handleSetPreviewQuality,
  handleStartBlankSite,
  handleStartSiteBoundaryDraw,
  hasSiteBoundary,
  issues,
  markSystemsStale,
  parkingCount,
  pendingPlacementObjects,
  placementModeEnabled,
  progressTimelineState,
  projectStatusSummary,
  recordRecentChange,
  refuseUnsafeConstructionCommand,
  resolveLotBounds,
  saveSiteAddress,
  setActivePlacementId,
  setActiveSidePanel,
  setActiveWorkspaceMode,
  setAutoExistingConditionsStatus,
  setBuildingPlacements,
  setCadToolRequest,
  setCommandBarExpanded,
  setFitToSiteRequest,
  setLotHeight,
  setLotWidth,
  setParkingCount,
  setPreviewInteraction,
  setPreviewLayers,
  setPreviewMode,
  setRenderedSidePanel,
  setRightRailCollapsed,
  setShowSiteBounds,
  setSidePanelVisible,
  setSiteAddress,
  setSiteSelectionMode,
  setStatusMessage,
  siteAddress,
  siteScaleLocked,
  systemStatuses,
  updateProjectStatus,
  workflowActionHints,
  workflowReviewDashboard,
}: UseDashboardPowerCommandHandlerInput) {
  const tryHandleSiteProgramCommand = useCallback((message: string): boolean => {
    const lower = normalizeDashboardChatIntent(message)
      .replace(/\bada\s+walks?\b/g, "ada route");
    if (!/\b(add|create|place|make|include|put|recreate|copy|draft|draw|layout|produce)\b/.test(lower)) return false;
    const wantsDensePlan =
      /\b(dense|full|complete|professional|civil|utility design|site plan|plan sheet|like the image|like this image|recreate|copy this|as many|detailed|realistic)\b/.test(
        lower,
      ) &&
      (/\b(office|building|parking|basin|detention|drainage|storm|water|sanitary|sidewalk|driveway|utilities|roads?|site|plan|image|sheet|stuff|layout)\b/.test(
        lower,
      ) ||
        /\b(recreate|copy|like the image|like this image)\b/.test(lower));
    const wantsCampusPlan =
      /\b(urbanization|campus|boulevard|plaza|municipal|park|parks|master plan|site model|3d massing|massing|community|civic|trees?)\b/.test(
        lower,
      ) &&
      /\b(plan|site|layout|model|3d|buildings?|roads?|paths?|parking|trees?|plaza|like this|image)\b/.test(lower);
    if (wantsDensePlan || wantsCampusPlan) {
      return handleCreateDenseCommercialConcept(message);
    }
    const lot = resolveLotBounds();
    const allowAdditionalObjects = /\b(another|additional|second|extra|one more)\b/.test(lower);
    const hasPlacedObject = (predicate: (item: BuildingPlacement) => boolean) =>
      buildingPlacements.some((item) => item.placed !== false && predicate(item));
    const requested: Array<() => void> = [];
    const labels: string[] = [];
    const addedLabels: string[] = [];
    const keptLabels: string[] = [];
    const queueUniqueObject = (alreadyExists: boolean, label: string, action: () => void) => {
      labels.push(label);
      if (alreadyExists && !allowAdditionalObjects) {
        keptLabels.push(label);
        return;
      }
      addedLabels.push(label);
      requested.push(action);
    };
    const officeArea = lower.match(
      /(\d{1,3}(?:,\d{3})+|\d{3,8})\s*(?:sf|sq\s*ft|sqft|square\s*feet)\s+(?:(?:office\s+)?building|office(?:\s+project)?)\b/,
    );
    if (officeArea || /\boffice\s+(?:building|project)\b/.test(lower)) {
      const area = officeArea ? Number(officeArea[1].replace(/,/g, "")) : null;
      const depth = area ? Math.round(Math.sqrt(area / 1.8)) : undefined;
      const width = area && depth ? Math.round(area / Math.max(depth, 1)) : undefined;
      const label = area ? `${Math.round(area).toLocaleString()} sf office building` : "office building";
      queueUniqueObject(
        hasPlacedObject((item) => item.type === "office_building"),
        label,
        () => handleAddObject("office_building", {
          label: area ? `Office Building - ${Math.round(area).toLocaleString()} sf` : undefined,
          placed: true,
          width,
          depth,
          meta: area ? { requested_area_sf: Math.round(area), command_created: true } : { command_created: true },
        }),
      );
    }
    const parking = lower.match(/(\d{1,5})\s+(?:parking\s+)?(?:spaces|stalls|spots?)/);
    if (parking || /\bparking\b/.test(lower)) {
      const stalls = parking ? Number(parking[1]) : parsePositiveNumber(parkingCount) ?? 140;
      const fieldWidth = Math.max(260, Math.min((lot.w || 1000) * 0.48, Math.ceil(stalls / 2) * 9 + 36));
      const fieldDepth = Math.max(120, Math.min((lot.h || 1000) * 0.20, 18 * 2 + 24 + Math.ceil(stalls / 70) * 42));
      queueUniqueObject(
        hasPlacedObject((item) => item.type === "parking"),
        `${Math.round(stalls)} parking stalls`,
        () => {
          setParkingCount(String(Math.round(stalls)));
          handleAddObject("parking", {
            label: `Parking Field - ${Math.round(stalls)} stalls`,
            placed: true,
            width: fieldWidth,
            depth: fieldDepth,
            meta: { command_created: true, requested_stalls: Math.round(stalls) },
          });
        },
      );
    }
    if (/\b(basin|detention|pond)\b/.test(lower)) {
      queueUniqueObject(
        hasPlacedObject((item) => item.type === "basin"),
        "detention basin",
        () => handleAddObject("basin", { placed: true, meta: { command_created: true } }),
      );
    }
    if (/\b(driveway|drive aisle|access)\b/.test(lower)) {
      queueUniqueObject(
        hasPlacedObject((item) => item.type === "driveway"),
        "driveway/access",
        () => handleAddObject("driveway", { placed: true, meta: { command_created: true } }),
      );
    }
    if (/\b(sidewalk|sidewalks|ada route|ada routes|path|paths)\b/.test(lower)) {
      queueUniqueObject(
        hasPlacedObject((item) => item.type === "sidewalk"),
        "sidewalk / ADA route",
        () => handleAddObject("sidewalk", { label: "Sidewalk / ADA Route", placed: true, meta: { command_created: true, routeKind: "ada_review_route" } }),
      );
    }
    if (/\b(public water|water line|water)\b/.test(lower)) {
      queueUniqueObject(
        hasPlacedObject((item) => item.type === "utility_corridor" && String(item.meta?.network || "") === "water"),
        "public water line",
        () => handleAddObject("utility_corridor", { label: "Public Water Line", geometryType: "polyline", placed: true, meta: { network: "water", command_created: true } }),
      );
    }
    const requestsSanitary = /\b(public sanitary|sanitary(?: sewer)?|wastewater)\b/.test(lower) ||
      (/\bsewer\b/.test(lower) && !/\bstorm\s+sewer\b/.test(lower));
    if (requestsSanitary) {
      queueUniqueObject(
        hasPlacedObject((item) => item.type === "utility_corridor" && String(item.meta?.network || "") === "sanitary"),
        "public sanitary line",
        () => handleAddObject("utility_corridor", { label: "Public Sanitary Line", geometryType: "polyline", placed: true, meta: { network: "sanitary", command_created: true } }),
      );
    }
    if (/\bstorm\b/.test(lower)) {
      queueUniqueObject(
        hasPlacedObject((item) => item.type === "utility_corridor" && String(item.meta?.network || "") === "storm"),
        "storm sewer",
        () => handleAddObject("utility_corridor", { label: "Storm Sewer", geometryType: "polyline", placed: true, meta: { network: "storm", command_created: true } }),
      );
    }
    if (/\boutfall\b/.test(lower)) {
      queueUniqueObject(
        hasPlacedObject((item) => item.type === "outfall"),
        "outfall",
        () => handleAddObject("outfall", { placed: true, meta: { command_created: true, role: "storm_outfall_review_point" } }),
      );
    }
    if (/\binlet\b/.test(lower)) {
      queueUniqueObject(
        hasPlacedObject((item) => item.type === "inlet"),
        "inlet",
        () => handleAddObject("inlet", { placed: true, meta: { command_created: true, role: "storm_inlet_review_point" } }),
      );
    }
    if (labels.length < 2) return false;
    appendChatMessage("user", message);
    if (!hasSiteBoundary()) {
      appendChatMessage(
        "assistant",
        "I understood the site program, but I need a site boundary before I can place those objects at project scale. Tell me the address and site size, or draw/lock the site first.",
        "status",
      );
      handleOpenSidePanel("site_existing");
      return true;
    }
    if (requested.length) {
      requested.forEach((action) => action());
      setActivePlacementId(null);
      setCommandBarExpanded(false);
      setPreviewInteraction("static");
      setActiveWorkspaceMode("canvas");
      setActiveSidePanel(null);
      setRenderedSidePanel(null);
      setSidePanelVisible(false);
      setRightRailCollapsed(true);
    }
    const additionSummary = addedLabels.length
      ? `Added and placed ${addedLabels.join(", ")} as draft review objects.`
      : "No duplicate objects were added.";
    const existingSummary = keptLabels.length
      ? ` Existing ${keptLabels.join(", ")} already satisfy this request.`
      : "";
    appendChatMessage(
      "assistant",
      `${additionSummary}${existingSummary} The project objects are editable on the canvas and still require review before Generate/Deliver.`,
      "status",
    );
    return true;
  }, [
    appendChatMessage,
    buildingPlacements,
    handleAddObject,
    handleCreateDenseCommercialConcept,
    handleOpenSidePanel,
    hasSiteBoundary,
    parkingCount,
    resolveLotBounds,
    setActivePlacementId,
    setActiveSidePanel,
    setActiveWorkspaceMode,
    setCommandBarExpanded,
    setParkingCount,
    setPreviewInteraction,
    setRenderedSidePanel,
    setRightRailCollapsed,
    setSidePanelVisible,
  ]);

  return useCallback((message: string): boolean | "panel" => {
    const normalized = message.trim().toLowerCase().replace(/\s+/g, " ");
    const intentText = normalizeDashboardChatIntent(message);
    if (!normalized) return false;
    if (/\b(stamp|seal|sign|certify|approve construction|submit construction documents|engineer of record|eor)\b/.test(normalized)) {
      return refuseUnsafeConstructionCommand(message);
    }
    const heightCommand = normalized.match(
      /^(?:set|make|change|update)\s+(?:the\s+)?(.+?)\s+(?:(?:height\s+)?to\s+)?(\d+(?:\.\d+)?)\s*(?:ft|feet|foot)\s*(?:tall|high)?$/,
    );
    if (heightCommand) {
      const targetPhrase = heightCommand[1]
        .replace(/\b(?:selected|object|the)\b/g, " ")
        .replace(/\s+/g, " ")
        .trim();
      const requestedHeight = Number(heightCommand[2]);
      const isHeightCapable = (item: BuildingPlacement) =>
        /building|office|structure/.test(`${item.type || ""} ${item.label || ""}`.toLowerCase());
      const selectedTarget = activePlacementId
        ? buildingPlacements.find((item) => item.id === activePlacementId && isHeightCapable(item))
        : null;
      const namedTarget = buildingPlacements.find((item) => {
        if (!isHeightCapable(item)) return false;
        const searchable = `${item.label || ""} ${item.type || ""}`.toLowerCase().replaceAll("_", " ");
        return targetPhrase === "building" || targetPhrase === "" || searchable.includes(targetPhrase);
      });
      const target = selectedTarget ?? namedTarget;
      appendChatMessage("user", message);
      if (!target) {
        appendChatMessage(
          "assistant",
          "Select a building first, or include its name, then give me the height in feet.",
          "status",
        );
        return true;
      }
      if (!Number.isFinite(requestedHeight) || requestedHeight < 1 || requestedHeight > 500) {
        appendChatMessage("assistant", "Building height must be between 1 ft and 500 ft.", "status");
        return true;
      }
      setBuildingPlacements((previous) =>
        previous.map((item) =>
          item.id === target.id
            ? {
                ...item,
                h: requestedHeight,
                meta: {
                  ...(item.meta ?? {}),
                  height_ft: requestedHeight,
                  height_source: "user_command",
                },
              }
            : item,
        ),
      );
      setActivePlacementId(target.id);
      markSystemsStale(["grading", "drainage", "utilities"]);
      recordRecentChange({
        type: "object_style_changed",
        label: `${target.label} height changed`,
        detail: `Height set to ${requestedHeight} ft. Grading, drainage, and utilities need review for possible impacts.`,
      });
      setPreviewInteraction("static");
      setPreviewMode("3d");
      setActiveWorkspaceMode("canvas");
      setActiveSidePanel(null);
      setRenderedSidePanel(null);
      setSidePanelVisible(false);
      setRightRailCollapsed(true);
      window.requestAnimationFrame(() => setPreviewMode("3d"));
      appendChatMessage(
        "assistant",
        `${target.label} is now ${requestedHeight} ft tall. The canonical object and 3D preview use the same height; affected systems are marked for review.`,
        "status",
      );
      return "panel";
    }
    const directSiteSetup = parseDashboardDirectSiteSetupCommand(message, siteAddress.trim());
    if (directSiteSetup) {
      appendChatMessage("user", message);
      clearGeneratedPreview();
      const wantsProgramAfterSiteSetup =
        /\b(office|building|parking|spaces|stalls|basin|detention|pond|storm|water|sanitary|sewer|sidewalk|ada|driveway|road|grading|drainage|utilities|utility)\b/i.test(message) &&
        /\b(add|include|create|make|generate|design|layout|put|place|with)\b/i.test(message);
      const explicitlyPreserveExistingProgram =
        /\b(?:keep|reuse|preserve|use)\b[^.]{0,100}\b(?:existing|drawn|current|already)\b/i.test(message) ||
        /\b(?:do not|don't|dont|without|no)\s+(?:create\s+)?duplicates?\b/i.test(message);
      const existingProgramObjectCount = buildingPlacements.filter(
        (item) => item.type !== "site" && !item.meta?.source_candidate && !item.meta?.candidate,
      ).length;
      const reuseExistingProgram =
        wantsProgramAfterSiteSetup && explicitlyPreserveExistingProgram && existingProgramObjectCount > 0;
      const requestedParkingCount = message.match(
        /\b(\d{1,4})\s*(?:parking\s+)?(?:spaces?|stalls?)\b/i,
      )?.[1];
      const wantsSubdivisionCadPlan =
        /\b(recreate|copy|like the image|like this image|subdivision|master plan|lots?|parcels?|contours?|cad screenshot|as many)\b/i.test(message) &&
        /\b(image|plan|site|cad|subdivision|lots?|parcels?|contours?|dense|stuff)\b/i.test(message);
      const wantsUrbanizationCampusPlan =
        /\b(urbanization|campus|boulevard|plaza|municipal|park|parks|master plan|site model|3d massing|massing|community|civic)\b/i.test(message) &&
        /\b(plan|site|layout|model|3d|buildings?|roads?|paths?|parking|trees?|plaza|like this|image)\b/i.test(message);
      setSiteAddress(directSiteSetup.address);
      setLotWidth(String(Math.round(directSiteSetup.width)));
      setLotHeight(String(Math.round(directSiteSetup.height)));
      autoFitSite(
        directSiteSetup.width,
        directSiteSetup.height,
        "Site Boundary",
        undefined,
        true,
        true,
      );
      if (wantsProgramAfterSiteSetup && !reuseExistingProgram) {
        const conceptObjects = (wantsUrbanizationCampusPlan
          ? createUrbanizationCampusPlanPlacements({
              w: directSiteSetup.width,
              h: directSiteSetup.height,
            })
          : wantsSubdivisionCadPlan
            ? createDenseSubdivisionCadPlanPlacements({
                w: directSiteSetup.width,
                h: directSiteSetup.height,
              })
            : createDenseCommercialConceptPlacements({
                w: directSiteSetup.width,
                h: directSiteSetup.height,
              })
        ).map((item) => ({
          ...item,
          meta: {
            ...(item.meta ?? {}),
            command_created: true,
            command_source: wantsUrbanizationCampusPlan
              ? "site_setup_urbanization_campus_command"
              : wantsSubdivisionCadPlan
                ? "site_setup_subdivision_cad_command"
                : "site_setup_program_command",
          },
        }));
        setParkingCount(requestedParkingCount ?? "140");
        setBuildingPlacements((prev) => [
          ...prev.filter((item) => item.type === "site" || !item.meta?.dense_concept_generated),
          ...conceptObjects,
        ]);
        markSystemsStale(["roads", "parking", "grading", "drainage", "utilities"]);
        recordRecentChange({
          type: "object_added",
          label: wantsUrbanizationCampusPlan ? "Urbanization campus plan placed from chat" : wantsSubdivisionCadPlan ? "Subdivision CAD plan placed from chat" : "Site program placed from chat",
          detail: wantsUrbanizationCampusPlan
            ? "Parcels, boulevard roads, civic buildings, plaza, park, trees, parking, and service networks were placed from one natural-language command."
            : wantsSubdivisionCadPlan
            ? "Lots, roads, contours, amenity/drainage core, hatches, utility spines, ponds, and plan symbols were placed from one natural-language command."
            : "Office, parking, basin, driveway, sidewalks, water, sanitary, storm, inlet, outfall, hydrant, and manhole draft objects were placed from one natural-language command.",
        });
      } else if (reuseExistingProgram) {
        if (requestedParkingCount) setParkingCount(requestedParkingCount);
        markSystemsStale(["roads", "parking", "grading", "drainage", "utilities"]);
        recordRecentChange({
          type: "object_style_changed",
          label: "Existing site program reused from chat",
          detail: `${existingProgramObjectCount} existing non-site objects were preserved; no replacement concept geometry was created.`,
        });
      }
      setShowSiteBounds(false);
      setSiteSelectionMode(false);
      setCommandBarExpanded(false);
      setPreviewMode("2d");
      setPreviewInteraction("static");
      setActiveWorkspaceMode("canvas");
      setActiveSidePanel(null);
      setRenderedSidePanel(null);
      setSidePanelVisible(false);
      setRightRailCollapsed(true);
      setFitToSiteRequest((value) => value + 1);
      updateProjectStatus({
        state: "working",
        area: "setup",
        title: "Site setup started",
        detail: `${directSiteSetup.address} is being applied with a ${Math.round(directSiteSetup.width)} ft by ${Math.round(directSiteSetup.height)} ft locked review site.`,
        nextAction: "Civora is checking available roads, buildings, terrain, utilities, and source context. Draw or Generate after the context check finishes.",
      });
      setAutoExistingConditionsStatus({
        status: "running",
        message: reuseExistingProgram
          ? `Applying ${directSiteSetup.address}, preserving ${existingProgramObjectCount} existing project objects without duplicates, and checking available source context inside a ${Math.round(directSiteSetup.width)} ft by ${Math.round(directSiteSetup.height)} ft locked site.`
          : wantsProgramAfterSiteSetup
          ? `Applying ${directSiteSetup.address}, placing the requested draft site program, and checking available source context inside a ${Math.round(directSiteSetup.width)} ft by ${Math.round(directSiteSetup.height)} ft locked site.`
          : `Applying ${directSiteSetup.address} and checking available source context inside a ${Math.round(directSiteSetup.width)} ft by ${Math.round(directSiteSetup.height)} ft locked site.`,
        candidateCount: 0,
        missing: [],
      });
      appendChatMessage(
        "assistant",
        reuseExistingProgram
          ? `Got it. I kept ${existingProgramObjectCount} existing drawn objects for the ${Math.round(directSiteSetup.width)} ft by ${Math.round(directSiteSetup.height)} ft site at ${directSiteSetup.address} and did not create duplicate concept geometry. I am refreshing source context; Generate will use the existing canonical objects${requestedParkingCount ? ` with a ${requestedParkingCount}-space parking target` : ""}.`
          : wantsProgramAfterSiteSetup
          ? `Got it. I set up a ${Math.round(directSiteSetup.width)} ft by ${Math.round(directSiteSetup.height)} ft review site centered on ${directSiteSetup.address}, placed an editable office/parking/drainage/utility/sidewalk draft concept, and started source context detection. You can move, rename, delete, or redraw the objects before Generate.`
          : `Got it. I set up a ${Math.round(directSiteSetup.width)} ft by ${Math.round(directSiteSetup.height)} ft review site centered on ${directSiteSetup.address}, locked the site frame, and started source context detection. Any roads, buildings, terrain, utilities, or constraints found from configured sources stay review-required.`,
        "status",
      );
      void saveSiteAddress(directSiteSetup.address, {
        preserveLockedSite: true,
        siteWidth: directSiteSetup.width,
        siteHeight: directSiteSetup.height,
      });
      return true;
    }
    if (/^(?:add|create|place|put|make)\s+(?:a\s+)?(?:(?:detention|stormwater|drainage)\s+)?(?:basin|pond)$/.test(normalized)) {
      appendChatMessage("user", message);
      handleAddObject("basin", {
        label: "Detention Basin",
        placed: true,
        meta: { command_created: true, command_source: "direct_object_command" },
      });
      setActivePlacementId(null);
      setCommandBarExpanded(false);
      setPreviewInteraction("static");
      setActiveWorkspaceMode("canvas");
      setActiveSidePanel(null);
      setRenderedSidePanel(null);
      setSidePanelVisible(false);
      setRightRailCollapsed(true);
      appendChatMessage(
        "assistant",
        "Added and placed a detention basin as draft review geometry. It will be passed into Generate as review context.",
        "status",
      );
      return true;
    }
    if (tryHandleSiteProgramCommand(message)) {
      return true;
    }
    if (
      /^(select\s+(?:all|none|clear|layer\b.*)|align\b.*|distribute\b.*|move\b.*|copy\b.*|rotate\b.*|scale\b.*|mirror\b.*|flip\b.*|array\b.*|layer\b.*|delete\b.*|erase\b.*|offset\b.*|trim\b.*|extend\b.*|fillet\b.*|join\b.*|split\b.*|break\b.*|close\b.*|open\b.*|reverse\b.*|dist\b.*|measure\b.*)$/i.test(
        message.trim(),
      )
    ) {
      appendChatMessage("user", message);
      setPreviewMode("2d");
      setPreviewInteraction("edit");
      setActiveWorkspaceMode("canvas");
      setActiveSidePanel("objects");
      setRenderedSidePanel("objects");
      setSidePanelVisible(true);
      setRightRailCollapsed(false);
      setCadToolRequest({ id: Date.now() + Math.random(), tool: "command", commandText: message.trim() });
      setCommandBarExpanded(false);
      appendChatMessage(
        "assistant",
        `Running draft command: ${message.trim()}. Results are shown in Draw / Object Manager command feedback. Draft objects remain review-required.`,
        "status",
      );
      return "panel";
    }
    if (/^(start site|start a site|new site)$/.test(normalized)) {
      appendChatMessage("user", message);
      handleStartBlankSite();
      setCommandBarExpanded(false);
      appendChatMessage("assistant", "Started a blank review site. Draw the boundary on the clear canvas; it remains review-required until locked.", "status");
      return true;
    }
    if (/^apply address$/.test(normalized)) {
      appendChatMessage("user", message);
      if (!siteAddress.trim()) {
        handleOpenSidePanel("site_existing");
        appendChatMessage("assistant", "Apply Address needs a project address in Setup first.", "status");
        updateProjectStatus({
          state: "blocked",
          area: "setup",
          title: "Apply address needs input",
          detail: "No address is typed.",
          nextAction: "Type a project address in Setup, then run apply address again.",
        });
        return true;
      }
      void saveSiteAddress();
      appendChatMessage("assistant", "Applying the typed address as source context. Exact provider/auth needs will stay visible in Setup if the backend cannot apply it.", "status");
      return true;
    }
    if (/^draw site boundary$/.test(normalized)) {
      appendChatMessage("user", message);
      handleStartSiteBoundaryDraw();
      setCommandBarExpanded(false);
      appendChatMessage("assistant", "Site boundary drawing is active. Draw the boundary on the canvas; it remains review-required until locked.", "status");
      return "panel";
    }
    if (/^add water line$/.test(normalized)) {
      appendChatMessage("user", message);
      handleAddObject("utility_corridor", { label: "Water Line", geometryType: "polyline", placed: true, meta: { network: "water", command_created: true } });
      appendChatMessage("assistant", "Added and placed a water-line utility corridor as draft review geometry.", "status");
      return true;
    }
    if (/^add sanitary line$/.test(normalized)) {
      appendChatMessage("user", message);
      handleAddObject("utility_corridor", { label: "Sanitary Line", geometryType: "polyline", placed: true, meta: { network: "sanitary", command_created: true } });
      appendChatMessage("assistant", "Added and placed a sanitary-line utility corridor as draft review geometry.", "status");
      return true;
    }
    if (/^add storm sewer$/.test(normalized)) {
      appendChatMessage("user", message);
      handleAddObject("utility_corridor", { label: "Storm Sewer", geometryType: "polyline", placed: true, meta: { network: "storm", command_created: true } });
      appendChatMessage("assistant", "Added and placed a storm-sewer utility corridor as draft review geometry.", "status");
      return true;
    }
    if (/^add (?:detention )?basin$/.test(normalized)) {
      appendChatMessage("user", message);
      handleAddObject("basin", { label: "Detention Basin", placed: true, meta: { command_created: true } });
      appendChatMessage("assistant", "Added and placed a detention basin as draft review geometry.", "status");
      return true;
    }
    if (/^add outfall$/.test(normalized)) {
      appendChatMessage("user", message);
      handleAddObject("outfall", { label: "Outfall", placed: true, meta: { command_created: true, role: "storm_outfall_review_point" } });
      appendChatMessage("assistant", "Added and placed an outfall point as draft review geometry.", "status");
      return true;
    }
    if (/^hide utilities$/.test(normalized)) {
      appendChatMessage("user", message);
      setPreviewLayers((prev) => ({ ...prev, utilities: false, drainage: false, structures: false }));
      const hiddenTypes: SiteObjectType[] = ["utility_corridor", "manhole", "hydrant", "inlet", "outfall", "basin"];
      const hiddenCount = buildingPlacements.filter((item) => item.type && hiddenTypes.includes(item.type)).length;
      setBuildingPlacements((prev) =>
        prev.map((item) => {
          if (!item.type || !hiddenTypes.includes(item.type)) return item;
          return {
            ...item,
            meta: {
              ...(item.meta ?? {}),
              ui_hidden: true,
            },
          };
        }),
      );
      appendChatMessage(
        "assistant",
        hiddenCount
          ? `Utility and drainage layers are hidden in the preview. ${hiddenCount} utility/drainage object${hiddenCount === 1 ? "" : "s"} are marked hidden in Object Manager.`
          : "Utility and drainage layers are hidden in the preview. No utility/drainage objects are in Object Manager yet.",
        "status",
      );
      recordRecentChange({
        type: "object_visibility_changed",
        label: "Utilities hidden",
        detail: hiddenCount
          ? `${hiddenCount} utility/drainage object${hiddenCount === 1 ? "" : "s"} marked hidden.`
          : "Utility and drainage layers hidden; no matching objects were present.",
        undoBlockedReason: "Use Object Manager Show all to make hidden utility/drainage objects visible again.",
      });
      setStatusMessage(
        hiddenCount
          ? `Utility and drainage layers are hidden in the preview. ${hiddenCount} utility/drainage object${hiddenCount === 1 ? "" : "s"} are marked hidden in Object Manager.`
          : "Utility and drainage layers are hidden in the preview. No utility/drainage objects are in Object Manager yet.",
      );
      updateProjectStatus({
        state: "ready",
        area: "chat",
        title: "Utilities hidden",
        detail: hiddenCount ? `${hiddenCount} utility/drainage object${hiddenCount === 1 ? "" : "s"} marked hidden.` : "Utility and drainage layers are hidden.",
        nextAction: "Open Layers or Object Manager to review visibility.",
      });
      return true;
    }
    if (/^show only blockers$/.test(normalized)) {
      appendChatMessage("user", message);
      handleOpenSidePanel("analysis");
      appendChatMessage("assistant", "Opened the needs/review view. If no needs are recorded, the panel will show the exact empty state.", "status");
      updateProjectStatus({
        state: canonicalWorkspaceBlockers.length ? "blocked" : "ready",
        area: "chat",
        title: "Blocker view opened",
        detail: canonicalWorkspaceBlockers.length ? canonicalWorkspaceBlockers[0] : "No current needs-input items are recorded in the active workspace.",
        nextAction: canonicalWorkspaceBlockers.length ? "Review the needs-input panel and fix the first item." : "Continue setup, generate, or deliver from the current workspace.",
      });
      return "panel";
    }
    if (/^generate$/.test(normalized)) {
      appendChatMessage("user", message);
      handleOpenSidePanel("generate");
      appendChatMessage("assistant", "Running Generate from the locked site. I will show visible review concepts on the canvas and exact needs if a system cannot run.", "status");
      void handleGenerateSystem("full");
      return "panel";
    }
    if (/^(make review package|create review package)$/.test(normalized)) {
      appendChatMessage("user", message);
      handleOpenSidePanel("deliverables");
      void handleMakeReviewPackage();
      appendChatMessage("assistant", "Opened Deliver and created/updated the review package summary. It remains review-only.", "status");
      return "panel";
    }
    if (/^what changed\b/.test(intentText)) {
      appendChatMessage("user", message);
      const changed = Object.entries(systemStatuses)
        .filter(([, status]) => status === "stale")
        .map(([system]) => system);
      appendChatMessage(
        "assistant",
        changed.length
          ? `Changed/stale systems: ${changed.join(", ")}. Regenerate only the affected systems after reviewing draft objects.`
          : `No stale generated systems are currently marked. Project status: ${projectStatusSummary.state}. ${projectStatusSummary.detail}`,
        "status",
      );
      return true;
    }
    if (/^(what is blocked|what blocked|what needs input|what needs attention)(?: right now)?$/.test(intentText)) {
      appendChatMessage("user", message);
      const blockers = userFacingWorkflowNeeds(uniqueStrings([
        projectStatusSummary.state === "blocked" ? `${projectStatusSummary.title}: ${projectStatusSummary.detail}` : "",
        ...issues.map((issue) => issue.message),
        ...analysisIssues.map((issue) => issue.message),
        ...(workflowReviewDashboard?.release_blockers ?? []),
        ...(generateFlowSummary?.needs_review ?? []),
      ]));
      appendChatMessage(
        "assistant",
        blockers.length
          ? `Needs input:\n${blockers.map((item) => `- ${item}`).join("\n")}`
          : "Nothing is stopping the current review workflow. Review outputs are available; final professional use remains outside Civora.",
        "status",
      );
      return true;
    }
    if (/^what should i do next\b/.test(intentText)) {
      appendChatMessage("user", message);
      const activePlacementObject =
        activePlacementId && placementModeEnabled
          ? buildingPlacements.find((item) => item.id === activePlacementId)
          : null;
      const next = activePlacementObject
        ? `Click the canvas to place ${activePlacementObject.label}.`
        : pendingPlacementObjects.length
          ? `Open Objects and place ${pendingPlacementObjects[0].label}.`
          : projectStatusSummary.nextAction || workflowActionHints[0] || progressTimelineState.next_action || (siteScaleLocked ? "Open Generate and run a review draft." : "Open Setup and lock a site boundary.");
      appendChatMessage("assistant", `Next action: ${next} Current status: ${projectStatusDisplayLabel[projectStatusSummary.state]}.`, "status");
      return true;
    }
    if (/^create ai (?:realism|visualization)$/.test(normalized)) {
      appendChatMessage("user", message);
      handleSetPreviewQuality("high");
      handleSetPreviewMode("2d");
      handleOpenSidePanel("model");
      appendChatMessage("assistant", "Opened high-quality preview mode. Use the AI Visualization toggle there; provider/layout needs will be shown exactly in the preview panel.", "status");
      return true;
    }
    if (/^turn ai (?:realism|visualization) off$/.test(normalized)) {
      appendChatMessage("user", message);
      handleSetPreviewQuality("standard");
      appendChatMessage("assistant", "Turned AI Visualization off by returning to Standard preview quality.", "status");
      return true;
    }
    return false;
  }, [
    activePlacementId,
    analysisIssues,
    appendChatMessage,
    autoFitSite,
    buildingPlacements,
    canonicalWorkspaceBlockers,
    clearGeneratedPreview,
    generateFlowSummary,
    handleAddObject,
    handleGenerateSystem,
    handleMakeReviewPackage,
    handleOpenSidePanel,
    handleSetPreviewMode,
    handleSetPreviewQuality,
    handleStartBlankSite,
    handleStartSiteBoundaryDraw,
    issues,
    markSystemsStale,
    pendingPlacementObjects,
    placementModeEnabled,
    progressTimelineState.next_action,
    projectStatusSummary,
    recordRecentChange,
    refuseUnsafeConstructionCommand,
    saveSiteAddress,
    setActivePlacementId,
    setActiveSidePanel,
    setActiveWorkspaceMode,
    setAutoExistingConditionsStatus,
    setBuildingPlacements,
    setCadToolRequest,
    setCommandBarExpanded,
    setFitToSiteRequest,
    setLotHeight,
    setLotWidth,
    setParkingCount,
    setPreviewInteraction,
    setPreviewLayers,
    setPreviewMode,
    setRenderedSidePanel,
    setRightRailCollapsed,
    setShowSiteBounds,
    setSidePanelVisible,
    setSiteAddress,
    setSiteSelectionMode,
    setStatusMessage,
    siteAddress,
    siteScaleLocked,
    systemStatuses,
    tryHandleSiteProgramCommand,
    updateProjectStatus,
    workflowActionHints,
    workflowReviewDashboard,
  ]);
}
