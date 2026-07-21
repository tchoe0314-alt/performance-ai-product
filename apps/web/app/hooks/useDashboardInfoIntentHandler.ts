import { useCallback } from "react";

import type { BuildingPlacement, ChatMessage, Issue } from "../types";
import {
  buildDashboardAutoSiteContextMessage,
  buildDashboardPreviewExplanationMessage,
  buildDashboardUsedLayoutMessage,
  buildDashboardWhatChangedMessage,
  formatDashboardChatPlacement,
} from "../utils/dashboardChatResponseView";
import { systemsImpactedByPlacement } from "../utils/dashboardGenerateLayoutContext";
import { formatMetric } from "../utils/formatting";
import { uniqueStrings } from "../utils/workflowConstants";
import {
  projectStatusDisplayLabel,
  sidePanelCopy,
  type ProjectStatusSummary,
  type SidePanelKey,
  type WorkspaceMode,
} from "../utils/workspaceShell";
import type {
  AutoSiteContextFlowSummary,
  GenerateFlowSummary,
  ReviewPackageFlowSummary,
} from "../utils/dashboardDataTypes";
import type { PreviewLayerVisibility } from "../components/FloatingLayerManager";
import type { Civil3DWorkflowTab, RoadwayWorkbenchTab } from "../components/CivilRoadwayWorkbench";
import type { AutoSiteContextRow } from "../utils/dashboardAutoSiteContext";
import type { SystemStatus } from "../utils/workflowConstants";


type AppendChatMessage = (
  role: ChatMessage["role"],
  content: string,
  kind?: ChatMessage["kind"],
  feedback?: ChatMessage["feedback"],
) => void;

type ProgressTimelineState = {
  next_action?: string;
  exact_blockers?: string[];
  current_step_label?: string;
  export_blockers?: string[];
};

type RoadwayWorkbenchData = {
  profilePoints: unknown[];
  sectionPoints: unknown[];
};

type SourceConfidenceRow = {
  label?: string;
  source_name?: string;
  visible_badge?: string;
  confidence_band?: string;
  source_type?: string;
};

type SmartFixSummary = {
  can_civora_fix?: boolean;
  one_action_needed_next?: string;
  missing_user_input_or_source?: string;
  what_happens_after_fix?: string;
} | null;

type UseDashboardInfoIntentHandlerInput = {
  activePlacementId: string | null;
  appendChatMessage: AppendChatMessage;
  appliedAddressLabel: string;
  autoSiteContextFlowSummary: AutoSiteContextFlowSummary;
  autoSiteContextRows: AutoSiteContextRow[];
  basinSize: number | null | undefined;
  buildingPlacements: BuildingPlacement[];
  canonicalWorkspaceBlockerText: string;
  canonicalWorkspaceBlockers: string[];
  civil3DWorkflowBlockers: string[];
  currentProject: { updated_at?: number | null } | null;
  cutFillNet: number | null | undefined;
  flowCfs: number | null | undefined;
  fullGeneratePreflightBlockers: Array<{ action: SidePanelKey; label: string }>;
  generateFlowSummary: GenerateFlowSummary | null;
  getExportBlockReason: () => string | null;
  gradingEarthworkUx: { heatmapCells: Array<{ deltaFt: number; mode: string }> };
  handleOpenSidePanel: (panel: SidePanelKey) => void;
  hasAppliedAddress: boolean;
  hasAssumedTerrainSlope: boolean;
  hasGradingSurface: boolean;
  hasTerrainSource: boolean;
  hasVerifiedSurveyControl: boolean;
  issues: Issue[];
  maxSlope: number | null | undefined;
  minSlope: number | null | undefined;
  nextSetupAction: string;
  onlineSourceLookupLabel: string;
  onlineSourceLookupUnavailable: boolean;
  pendingPlacementObjects: BuildingPlacement[];
  placedObjects: BuildingPlacement[];
  placementModeEnabled: boolean;
  planSheetSet: { revisions: unknown[] };
  previewBlockedReasons: string[];
  previewLayers: PreviewLayerVisibility;
  progressTimelineState: ProgressTimelineState;
  projectStatusSummary: ProjectStatusSummary;
  restoreTruthLabel: string;
  reviewPackageFlowSummary: ReviewPackageFlowSummary | null;
  roadwayWorkbenchData: RoadwayWorkbenchData;
  setActiveCivil3DWorkflowTab: (tab: Civil3DWorkflowTab) => void;
  setActiveRoadwayWorkbenchTab: (tab: RoadwayWorkbenchTab) => void;
  setActiveWorkspaceMode: (mode: WorkspaceMode) => void;
  setPreviewLabelDensity: (density: "low" | "standard" | "high") => void;
  setPreviewLayers: (value: PreviewLayerVisibility | ((prev: PreviewLayerVisibility) => PreviewLayerVisibility)) => void;
  setPreviewMode: (mode: "2d" | "3d") => void;
  siteAddress: string;
  sourceConfidenceRows: SourceConfidenceRow[];
  systemStatuses: Record<string, SystemStatus>;
  topSmartFix: SmartFixSummary;
  totalPipeLength: number | null | undefined;
  workflowActionHints: string[];
};

export function useDashboardInfoIntentHandler({
  activePlacementId,
  appendChatMessage,
  appliedAddressLabel,
  autoSiteContextFlowSummary,
  autoSiteContextRows,
  basinSize,
  buildingPlacements,
  canonicalWorkspaceBlockerText,
  canonicalWorkspaceBlockers,
  civil3DWorkflowBlockers,
  currentProject,
  cutFillNet,
  flowCfs,
  fullGeneratePreflightBlockers,
  generateFlowSummary,
  getExportBlockReason,
  gradingEarthworkUx,
  handleOpenSidePanel,
  hasAppliedAddress,
  hasAssumedTerrainSlope,
  hasGradingSurface,
  hasTerrainSource,
  hasVerifiedSurveyControl,
  issues,
  maxSlope,
  minSlope,
  nextSetupAction,
  onlineSourceLookupLabel,
  onlineSourceLookupUnavailable,
  pendingPlacementObjects,
  placedObjects,
  placementModeEnabled,
  planSheetSet,
  previewBlockedReasons,
  previewLayers,
  progressTimelineState,
  projectStatusSummary,
  restoreTruthLabel,
  reviewPackageFlowSummary,
  roadwayWorkbenchData,
  setActiveCivil3DWorkflowTab,
  setActiveRoadwayWorkbenchTab,
  setActiveWorkspaceMode,
  setPreviewLabelDensity,
  setPreviewLayers,
  setPreviewMode,
  siteAddress,
  sourceConfidenceRows,
  systemStatuses,
  topSmartFix,
  totalPipeLength,
  workflowActionHints,
}: UseDashboardInfoIntentHandlerInput) {
  return useCallback((message: string): boolean => {
    const normalized = message.toLowerCase();
    const placed = buildingPlacements.filter((item) => item.placed);
    const unplaced = buildingPlacements.filter((item) => !item.placed);
    const selected = activePlacementId
      ? buildingPlacements.find((item) => item.id === activePlacementId)
      : null;

    if (/^(hi|hello|hey|yo|good\s+(morning|afternoon|evening))[\s.!?]*$/i.test(normalized)) {
      appendChatMessage(
        "assistant",
        `Hi. I can help with casual project questions, setup commands, draw/edit commands, needs-input review, review/export questions, and focused fixes. ${progressTimelineState.next_action ? `Best next action: ${progressTimelineState.next_action}.` : nextSetupAction} Outputs stay review-required.`,
        "status",
      );
      return true;
    }

    if (/(what(’|')?s on the site|what is on the site|placed objects|site objects)/i.test(normalized)) {
      if (!placed.length) {
        appendChatMessage("assistant", "No objects are placed on the site yet.", "status");
        return true;
      }
      appendChatMessage(
        "assistant",
        `Placed objects:\n${placed.map(formatDashboardChatPlacement).join("\n")}`,
        "status",
      );
      return true;
    }

    if (/(unplaced|in the tray|not placed)/i.test(normalized)) {
      if (!unplaced.length) {
        appendChatMessage("assistant", "All current objects are placed on the site.", "status");
        return true;
      }
      appendChatMessage(
        "assistant",
        `Unplaced objects:\n${unplaced.map(formatDashboardChatPlacement).join("\n")}`,
        "status",
      );
      return true;
    }

    if (/(selected|current selection|what is selected)/i.test(normalized)) {
      if (!selected) {
        appendChatMessage("assistant", "Nothing is selected right now.", "status");
        return true;
      }
      appendChatMessage(
        "assistant",
        `Selected object: ${formatDashboardChatPlacement(selected)}`,
        "status",
      );
      return true;
    }

    if (/(how.*(draw|draft|canvas)|what.*(can|should).*draw|what.*draw.*tools|finish.*(drawing|boundary|line|area|box)|stop.*(drawing|drafting)|cancel.*(drawing|drafting)|submit.*(boundary|drawing)|end.*(drawing|boundary)|where.*finish|how.*use.*(draw|cad))/i.test(normalized)) {
      appendChatMessage(
        "assistant",
        [
          "Draw Canvas works like this:",
          "- Open Draw, then pick Draw Site Boundary, Add Line, Add Area, Add Box, or Add Point.",
          "- Click the preview to place points. The crosshair/readout shows point count and coordinates.",
          "- Press Finish to commit the boundary/object. Finish needs 3 points for a site/area, 2 points for a line/box, and 1 point for a point.",
          "- Press Cancel or Escape to stop the active draw tool without saving it.",
          "- After an object exists, use Object Manager to select, rename, recolor, change type/layer, copy, rotate, mirror, array, combine, hide, or delete it.",
          "Everything drawn this way stays editable draft/review context. Generate can use it as layout intent, but it is not survey/control or final professional evidence.",
        ].join("\n"),
        "status",
      );
      return true;
    }

    if (/(why.*(slow|lag|laggy|stuck|glitch|glitchy)|what.*(slow|lag|laggy|stuck|glitch|glitchy)|is.*(slow|laggy|stuck|glitchy)|performance|taking.*long|debug.*(speed|performance|lag))/i.test(normalized)) {
      type ChatPerfEntry = { label: string; durationMs: number };
      const perfStore =
        typeof window !== "undefined"
          ? (window as typeof window & {
              __civoraPerf?: {
                entries?: ChatPerfEntry[];
                last?: Record<string, ChatPerfEntry>;
              };
            }).__civoraPerf
          : null;
      const entries = [
        ...Object.values(perfStore?.last ?? {}),
        ...(perfStore?.entries ?? []).slice(-8),
      ].filter((entry, index, list) =>
        entry && list.findIndex((other) => other.label === entry.label) === index,
      );
      const priorityLabels = [
        "preview.mode.3d",
        "preview.mode.2d",
        "preview.quality.high",
        "preview.quality.standard",
        "preview.ai_visualization.on",
        "preview.ai_visualization.off",
        "projects.new_project",
        "projects.open_saved_project",
        "generate.panel.response.visible",
        "panel.open.generate",
        "panel.open.deliver",
        "draw.tool.add_line",
        "draw.tool.add_area",
        "preview.pan.drag",
      ];
      const sortedEntries = entries
        .sort((a, b) => {
          const aPriority = priorityLabels.indexOf(a.label);
          const bPriority = priorityLabels.indexOf(b.label);
          const normalizedA = aPriority === -1 ? 999 : aPriority;
          const normalizedB = bPriority === -1 ? 999 : bPriority;
          if (normalizedA !== normalizedB) return normalizedA - normalizedB;
          return b.durationMs - a.durationMs;
        })
        .slice(0, 8);
      const humanLabel = (label: string) =>
        label
          .replace(/^preview\./, "Preview ")
          .replace(/^projects\./, "Projects ")
          .replace(/^generate\./, "Generate ")
          .replace(/^panel\./, "Panel ")
          .replace(/^draw\./, "Draw ")
          .replace(/\./g, " ")
          .replace(/_/g, " ");
      const statusFor = (durationMs: number) => {
        if (durationMs <= 250) return "instant";
        if (durationMs <= 1000) return "normal";
        return "slow, worth checking";
      };

      appendChatMessage(
        "assistant",
        sortedEntries.length
          ? [
              "Recent UI timings from this browser:",
              ...sortedEntries.map(
                (entry) =>
                  `- ${humanLabel(entry.label)}: ${Math.round(entry.durationMs)} ms (${statusFor(entry.durationMs)})`,
              ),
              "If something feels laggy, try that action again and ask me this question again. I will compare the newest timings instead of guessing.",
            ].join("\n")
          : [
              "I do not have recent UI timing samples yet in this browser.",
              "Try opening a panel, switching 2D/3D, toggling Standard/High, drawing, or running Generate, then ask me again. I will summarize the measured timings instead of giving a generic answer.",
            ].join("\n"),
        "status",
      );
      return true;
    }

    if (/(what.*(random|weird|messy).*(circle|line|shape|stuff)|what.*(circle|line|shape).*mean|why.*(circle|line|shape|preview).*look|explain.*(preview|drawing|canvas|map)|what\s+am\s+i\s+looking\s+at|what.*on.*(canvas|preview|map|plan))/i.test(normalized)) {
      appendChatMessage(
        "assistant",
        buildDashboardPreviewExplanationMessage({
          placed,
          buildingPlacements,
          selected: selected ?? null,
        }),
        "status",
      );
      return true;
    }

    if (/(what did.*use|what.*used.*draw|use.*my (drawing|objects|layout)|what.*from.*(drawing|objects|layout)|did.*use.*(drawing|objects|layout))/i.test(normalized)) {
      const userLayoutObjects = placed.filter((item) => {
        if (item.type === "site" || item.meta?.generated_review_concept) return false;
        const source = String(item.source || item.meta?.source || "").toLowerCase();
        return Boolean(
          item.meta?.semantic_object_model ||
          item.meta?.semantic_geometry_state ||
          item.meta?.command_created ||
          ["user", "user_confirmed", "manual_drawn", "generated"].includes(source),
        );
      });
      appendChatMessage(
        "assistant",
        buildDashboardUsedLayoutMessage({
          userLayoutObjects,
          generateFlowSummary,
          systemsImpactedByPlacement,
        }),
        "status",
      );
      return true;
    }

    if (/(what did you find here|what did.*find|what.*detected|what sources.*available|what.*site context|auto site context|found context|roads.*buildings.*terrain|why.*(didn.t|did not|didn't).*(detect|find)|why.*(roads|buildings|grading|terrain|utilities).*(missing|not found|not detected|unavailable))/i.test(normalized)) {
      appendChatMessage("assistant", buildDashboardAutoSiteContextMessage(autoSiteContextRows), "status");
      return true;
    }

    if (/(what changed|what has changed|changes|revision state|revision status)/i.test(normalized)) {
      appendChatMessage(
        "assistant",
        buildDashboardWhatChangedMessage({
          systemStatuses,
          projectStatusSummary,
          restoreTruthLabel,
          currentProjectUpdatedAt: currentProject?.updated_at,
          hasAppliedAddress,
          appliedAddressLabel,
          onlineSourceLookupUnavailable,
          onlineSourceLookupLabel,
          siteAddress,
          placedCount: placedObjects.length,
          pendingPlacementCount: pendingPlacementObjects.length,
          hasAssumedTerrainSlope,
          hasVerifiedSurveyControl,
          generateFlowSummary,
          reviewPackageFlowSummary,
          autoSiteContextFlowSummary,
          planSheetRevisionCount: planSheetSet.revisions.length,
        }),
        "status",
      );
      return true;
    }

    if (/(what ran|what did.*run|which systems ran|what systems ran)/i.test(normalized)) {
      const freshSystems = Object.entries(systemStatuses)
        .filter(([, status]) => status === "fresh")
        .map(([system]) => system);
      appendChatMessage(
        "assistant",
        generateFlowSummary
          ? `Last Generate ran: ${generateFlowSummary.ran.join(", ") || "none"}. Current fresh systems: ${freshSystems.join(", ") || "none"}. Review-only output; engineer review is required.`
          : `No Generate run summary is recorded yet. Current fresh systems: ${freshSystems.join(", ") || "none"}.`,
        "status",
      );
      return true;
    }

    if (/(what did you skip|what.*skipped|what was skipped|skipped systems)/i.test(normalized)) {
      appendChatMessage(
        "assistant",
        generateFlowSummary
          ? `Skipped: ${generateFlowSummary.skipped.join(", ") || "none"}. Needs review: ${generateFlowSummary.needs_review.slice(0, 5).join("; ") || "standard engineer review"}.`
          : "No skipped-system summary is recorded yet because Generate has not run in this workspace state.",
        "status",
      );
      return true;
    }

    if (/(what is blocked|what's blocked|what.*blocked|blocked right now|what needs input|needs input|what needs attention)/i.test(normalized)) {
      const flowBlockers = uniqueStrings([
        projectStatusSummary.state === "blocked" ? `${projectStatusSummary.title}: ${projectStatusSummary.detail}` : "",
        ...(generateFlowSummary?.blocked ? generateFlowSummary.needs_review : []),
        ...(reviewPackageFlowSummary?.missing ?? []),
        getExportBlockReason(),
      ]);
      appendChatMessage(
        "assistant",
        canonicalWorkspaceBlockers.length || flowBlockers.length
          ? `Needs input:\n${uniqueStrings([...canonicalWorkspaceBlockers, ...flowBlockers]).map((reason) => `- ${reason}`).join("\n")}`
          : "No current needs-input items are recorded. Outputs remain review-required.",
        "status",
      );
      return true;
    }

    if (/(what do i need next|what should i do next|what next|next step|where should i start|what do i do next)/i.test(normalized)) {
      const firstBlocker = fullGeneratePreflightBlockers[0];
      const activePlacementObject =
        activePlacementId && placementModeEnabled
          ? buildingPlacements.find((item) => item.id === activePlacementId)
          : null;
      const visibleAction = activePlacementObject
        ? `Click the canvas to place ${activePlacementObject.label}.`
        : firstBlocker
        ? `Open ${sidePanelCopy[firstBlocker.action].title} and fix: ${firstBlocker.label}.`
        : reviewPackageFlowSummary?.missing.length
          ? reviewPackageFlowSummary.next_action
          : generateFlowSummary?.needs_review.length
            ? generateFlowSummary.next_action
            : pendingPlacementObjects.length
              ? `Open Objects and place ${pendingPlacementObjects[0].label}.`
              : projectStatusSummary.nextAction || progressTimelineState.next_action || nextSetupAction;
	      appendChatMessage(
	        "assistant",
	        `${visibleAction} Current status: ${projectStatusDisplayLabel[projectStatusSummary.state]}. Current needs-input source: ${canonicalWorkspaceBlockerText} This is the next visible UI action; all outputs remain review-required.`,
        "status",
      );
      return true;
    }

    if (/(why is this review[- ]only|why.*review[- ]only|why.*engineer review|required review)/i.test(normalized)) {
      const lines = [
        "Civora is review-only because it is showing draft layouts, source evidence, assumptions, needs-input items, and generated artifacts for qualified review.",
        hasAppliedAddress
          ? `Address context is applied (${appliedAddressLabel || "coordinate context"}), but address/GIS context is not survey/control.`
          : "Address/location evidence is not fully applied yet.",
        hasAssumedTerrainSlope
          ? "Terrain slope is assumed; survey/control still needed."
          : hasVerifiedSurveyControl
            ? "Survey/control is uploaded for review but still requires professional verification."
            : "Survey/control is still missing.",
        `${placedObjects.length} design object${placedObjects.length === 1 ? "" : "s"} placed; ${pendingPlacementObjects.length} still need placement.`,
        "Civora does not stamp, seal, sign, certify, approve construction, submit construction documents, or act as engineer of record.",
      ];
      appendChatMessage("assistant", lines.join("\n"), "status");
      return true;
    }

    if (/\bshow\s+profile\b|\bprofile\s+view\b/i.test(normalized)) {
      setActiveWorkspaceMode("canvas");
      handleOpenSidePanel("roadway");
      setActiveCivil3DWorkflowTab("profile");
      setActiveRoadwayWorkbenchTab("profile");
      appendChatMessage(
        "assistant",
        roadwayWorkbenchData.profilePoints.length
          ? `Opened the linked profile view with ${roadwayWorkbenchData.profilePoints.length} profile samples. This remains review-required evidence.`
          : "Opened the profile view. No profile samples are recorded yet, so the corridor still needs review.",
        "status",
      );
      return true;
    }

    if (/\bshow\s+(cross[-\s]?)?sections\b|\bsection\s+view\b/i.test(normalized)) {
      setActiveWorkspaceMode("canvas");
      handleOpenSidePanel("roadway");
      setActiveCivil3DWorkflowTab("sections");
      setActiveRoadwayWorkbenchTab("section");
      appendChatMessage(
        "assistant",
        roadwayWorkbenchData.sectionPoints.length
          ? `Opened the cross-section viewer with ${roadwayWorkbenchData.sectionPoints.length} section samples. These are review-required only.`
          : "Opened the cross-section viewer. Corridor section samples are missing, so review needs remain visible.",
        "status",
      );
      return true;
    }

    if (/why\s+is\s+(the\s+)?corridor\s+blocked|corridor.*blocked/i.test(normalized)) {
      setActiveWorkspaceMode("canvas");
      handleOpenSidePanel("roadway");
      setActiveCivil3DWorkflowTab("blockers");
      const blockers = civil3DWorkflowBlockers.length
        ? civil3DWorkflowBlockers
        : ["No corridor-specific needs-input note is recorded, but profile, section, surface, and source confidence still require review."];
      appendChatMessage(
        "assistant",
        `Corridor review needs:\n${blockers.map((item) => `- ${item}`).join("\n")}`,
        "status",
      );
      return true;
    }

    if (/where\s+is\s+cut\/?fill\s+high|cut\/?fill\s+high|high\s+cut|high\s+fill/i.test(normalized)) {
      setActiveWorkspaceMode("canvas");
      handleOpenSidePanel("roadway");
      setActiveCivil3DWorkflowTab("cutfill");
      const highCells = [...gradingEarthworkUx.heatmapCells]
        .sort((a, b) => Math.abs(b.deltaFt) - Math.abs(a.deltaFt))
        .slice(0, 4);
      appendChatMessage(
        "assistant",
        highCells.length
          ? `Opened cut/fill visualization. Highest review deltas: ${highCells.map((cell) => `${cell.mode} ${cell.deltaFt > 0 ? "+" : ""}${cell.deltaFt.toFixed(1)} ft`).join("; ")}.`
          : "Opened cut/fill visualization. No cut/fill cells are available yet.",
        "status",
      );
      return true;
    }

    if (/show\s+surface\s+confidence|surface\s+confidence/i.test(normalized)) {
      setActiveWorkspaceMode("canvas");
      handleOpenSidePanel("roadway");
      setActiveCivil3DWorkflowTab("confidence");
      const sourceLines = sourceConfidenceRows.slice(0, 4).map((entry) =>
        `- ${entry.label || "Source entry"}: ${entry.visible_badge || entry.confidence_band || entry.source_type || "review"}`,
      );
      appendChatMessage(
        "assistant",
        sourceLines.length
          ? `Opened surface confidence. Source/control note: ${hasVerifiedSurveyControl ? "survey/control uploaded for review" : "no verified survey/control attached"}.\n${sourceLines.join("\n")}`
          : `Opened surface confidence. ${hasVerifiedSurveyControl ? "Survey/control is uploaded for review." : "No verified survey/control is attached."}`,
        "status",
      );
      return true;
    }

    if (/(what should i do next|what next|next step|where should i start|what do i do next)/i.test(normalized)) {
      const blockers = progressTimelineState.exact_blockers?.length
        ? ` Needs input: ${progressTimelineState.exact_blockers.slice(0, 3).join("; ")}.`
        : "";
      const current = progressTimelineState.current_step_label
        ? `Current step: ${progressTimelineState.current_step_label}. `
        : "";
      appendChatMessage(
        "assistant",
        `${current}${progressTimelineState.next_action || nextSetupAction}.${blockers} Everything remains review-required and limited to review evidence.`,
        "status",
      );
      return true;
    }

    if (/(show.*in\s+3d|open\s+3d|3d\s+view|show\s+this\s+3d)/i.test(normalized)) {
      setActiveWorkspaceMode("canvas");
      setPreviewMode("3d");
      handleOpenSidePanel("details");
      appendChatMessage(
        "assistant",
        `Opened the 3D civil model workspace. You are looking at placed site objects, roads/paving, drainage, utilities when evidence exists, confidence badges, and terrain status. ${
          hasTerrainSource && hasGradingSurface
            ? "Terrain is shown only from available preview elevations."
            : "The site is flat because no terrain mesh source is attached to this preview."
        } Visual review does not change canonical geometry.`,
        "status",
      );
      return true;
    }

    if (/why\s+is\s+(this|it|the\s+site|terrain)\s+flat|why.*flat/i.test(normalized)) {
      setActiveWorkspaceMode("canvas");
      setPreviewMode("3d");
      appendChatMessage(
        "assistant",
        hasTerrainSource && hasGradingSurface
          ? "The 3D view is using the available preview elevation samples. If it still appears flat, the preview did not include enough vertical variation or sampled terrain vertices."
          : "It is flat because no terrain mesh source is attached. The fallback plane is labeled in the 3D view, and Civora is not inventing terrain.",
        "status",
      );
      return true;
    }

    if (/show\s+low\s+confidence|low\s+confidence\s+objects|show\s+blockers|show\s+fix\s+badges/i.test(normalized)) {
      setActiveWorkspaceMode("canvas");
      setPreviewMode("3d");
      handleOpenSidePanel("data");
      setPreviewLabelDensity("high");
      appendChatMessage(
        "assistant",
        sourceConfidenceRows.length
          ? `Showing source confidence and review-need badges in 3D. Low-confidence entries: ${sourceConfidenceRows
              .filter((entry) => entry.confidence_band !== "higher")
              .slice(0, 4)
              .map((entry) => entry.label || entry.source_name || "source entry")
              .join("; ") || "none in the visible source map"}.`
          : "Showing 3D confidence badges. No source confidence entries are available yet.",
        "status",
      );
      return true;
    }

    if (/show\s+utilities\s+(in\s+)?3d|utilities\s+in\s+3d|show\s+utility\s+network/i.test(normalized)) {
      setActiveWorkspaceMode("canvas");
      setPreviewMode("3d");
      handleOpenSidePanel("utilities");
      setPreviewLayers((prev) => ({ ...prev, utilities: true, drainage: true }));
      appendChatMessage(
        "assistant",
        "Utilities are enabled in the 3D workspace where utility evidence exists. Depth, pressure, and elevation are not inferred when missing.",
        "status",
      );
      return true;
    }

    if (/(can i export|can we export|export now|why.*export|can(?:not|'t) export|export.*blocked|why.*download)/i.test(normalized)) {
      const reason = getExportBlockReason();
      const exportBlockers = [
        ...(progressTimelineState.export_blockers ?? []),
        ...previewBlockedReasons,
        ...(reviewPackageFlowSummary?.missing ?? []),
      ].filter(Boolean);
	      const blockerText = exportBlockers.length
	        ? ` Current export/review needs: ${Array.from(new Set(exportBlockers)).slice(0, 4).join("; ")}.`
	        : "";
      appendChatMessage(
        "assistant",
        reason
	          ? `Export needs input: ${reason}.${blockerText}`
          : `Exports are available only as engineer-review packages. Field use is outside Civora and requires independent licensed-professional review.${blockerText}`,
        "status",
      );
      return true;
    }

    if (/(stamp|seal|sign|submit|construction[- ]ready|approve.*construction|engineer of record)/i.test(normalized)) {
      appendChatMessage(
        "assistant",
        "No. Civora cannot stamp, seal, sign, certify, submit, approve construction, or act as engineer of record. Civora can prepare review evidence packages, calculations, reports, exports, assumptions, needs, and traceability for qualified review. Field use and professional responsibility remain outside Civora.",
        "status",
      );
      return true;
    }

    if (/(issues|conflicts|problems)/i.test(normalized)) {
      if (!issues.length) {
        appendChatMessage("assistant", "No issues are reported on the latest run.", "status");
        return true;
      }
      appendChatMessage(
        "assistant",
        `Issues:\n${issues.slice(0, 6).map((item) => `- ${item.message}`).join("\n")}`,
        "status",
      );
      return true;
    }

    if (/(blocked|needs input|needs attention|why.*(drainage|utilities|grading))/i.test(normalized)) {
      const blockers = [
        ...(progressTimelineState.exact_blockers ?? []),
        ...previewBlockedReasons,
      ].filter(Boolean);
      if (!blockers.length) {
        appendChatMessage(
          "assistant",
          topSmartFix?.one_action_needed_next
            ? `No needs-input text is currently recorded, but the smart-fix panel recommends: ${topSmartFix.one_action_needed_next}`
            : "No needs-input items are currently recorded in the active project metadata.",
          "status",
        );
        return true;
      }
      appendChatMessage(
        "assistant",
        `Needs input:\n${Array.from(new Set(blockers)).map((reason) => `- ${reason}`).join("\n")}`,
        "status",
      );
      return true;
    }

    if (/(smart\s*fix|best fix|what.*fix|fix request|can civora fix)/i.test(normalized)) {
      if (!topSmartFix) {
        appendChatMessage(
          "assistant",
          workflowActionHints[0]
            ? `Best available fix path: ${workflowActionHints[0]} Review responsibility remains outside Civora.`
            : "No smart-fix recommendation is recorded yet. Run or load a project so Civora can tie fixes to needs and evidence.",
          "status",
        );
        return true;
      }
      appendChatMessage(
        "assistant",
        [
          topSmartFix.can_civora_fix ? "Civora has a focused fix available." : "This needs user/source input before Civora can fix it.",
          topSmartFix.one_action_needed_next ? `Exact fix: ${topSmartFix.one_action_needed_next}` : null,
          topSmartFix.missing_user_input_or_source ? `Missing input/source: ${topSmartFix.missing_user_input_or_source}` : null,
          topSmartFix.what_happens_after_fix ? `After fix: ${topSmartFix.what_happens_after_fix}` : null,
          "Any output remains review-required.",
        ].filter(Boolean).join(" "),
        "status",
      );
      return true;
    }

    if (/(drainage stats|storm stats|pipe length|metrics|quantities)/i.test(normalized)) {
      if (!totalPipeLength && !maxSlope && !minSlope && !flowCfs && !cutFillNet && !basinSize) {
        appendChatMessage("assistant", "Drainage stats are not available yet.", "status");
        return true;
      }
      const metricLines = [
        totalPipeLength ? `Total pipe length: ${formatMetric(totalPipeLength, "ft")}` : null,
        maxSlope ? `Max slope: ${formatMetric(maxSlope, "%")}` : null,
        minSlope ? `Min slope: ${formatMetric(minSlope, "%")}` : null,
        flowCfs ? `Flow: ${formatMetric(flowCfs, "cfs")}` : null,
        cutFillNet ? `Cut/Fill net: ${formatMetric(cutFillNet, "cf")}` : null,
        basinSize ? `Pond size: ${formatMetric(basinSize, "sf")}` : null,
      ].filter(Boolean);
      appendChatMessage("assistant", metricLines.join("\n"), "status");
      return true;
    }

    if (/(systems|generated systems|what systems)/i.test(normalized)) {
      const enabled = [
        previewLayers.buildings ? "buildings" : null,
        previewLayers.roads ? "roads/parking" : null,
        previewLayers.grading ? "grading" : null,
        previewLayers.drainage ? "drainage/storm" : null,
        previewLayers.utilities ? "utilities" : null,
        previewLayers.structures ? "structures" : null,
      ].filter(Boolean);
      appendChatMessage(
        "assistant",
        `Preview layers enabled: ${enabled.length ? enabled.join(", ") : "none"}.`,
        "status",
      );
      return true;
    }

    return false;
  }, [
    activePlacementId,
    appendChatMessage,
    appliedAddressLabel,
    autoSiteContextFlowSummary,
    autoSiteContextRows,
    basinSize,
    buildingPlacements,
    canonicalWorkspaceBlockerText,
    canonicalWorkspaceBlockers,
    civil3DWorkflowBlockers,
    currentProject?.updated_at,
    cutFillNet,
    flowCfs,
    fullGeneratePreflightBlockers,
    generateFlowSummary,
    getExportBlockReason,
    gradingEarthworkUx.heatmapCells,
    handleOpenSidePanel,
    hasAppliedAddress,
    hasAssumedTerrainSlope,
    hasGradingSurface,
    hasTerrainSource,
    hasVerifiedSurveyControl,
    issues,
    maxSlope,
    minSlope,
    nextSetupAction,
    onlineSourceLookupLabel,
    onlineSourceLookupUnavailable,
    pendingPlacementObjects,
    placedObjects.length,
    placementModeEnabled,
    planSheetSet.revisions.length,
    previewBlockedReasons,
    previewLayers,
    progressTimelineState,
    projectStatusSummary,
    restoreTruthLabel,
    reviewPackageFlowSummary,
    roadwayWorkbenchData.profilePoints.length,
    roadwayWorkbenchData.sectionPoints.length,
    setActiveCivil3DWorkflowTab,
    setActiveRoadwayWorkbenchTab,
    setActiveWorkspaceMode,
    setPreviewLabelDensity,
    setPreviewLayers,
    setPreviewMode,
    siteAddress,
    sourceConfidenceRows,
    systemStatuses,
    topSmartFix,
    totalPipeLength,
    workflowActionHints,
  ]);
}
