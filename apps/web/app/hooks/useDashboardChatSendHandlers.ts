import type { KeyboardEvent } from "react";
import { useCallback } from "react";

import type {
  BuildingPlacement,
  ChatMessage,
  PlanToolMode,
  SiteObjectType,
  SurveySlopeResponse,
} from "../types";
import { buildAssumedSlopeEstimate } from "../utils/workflowConstants";
import { parsePositiveNumber } from "../utils/formatting";
import type { SystemGenerationTarget } from "../utils/workflowConstants";

type PendingClarification = {
  question: string;
  action: string;
  payload?: Record<string, unknown>;
} | null;

type StateSetter<T> = (value: T | ((prev: T) => T)) => void;

type AppendChatMessage = (
  role: ChatMessage["role"],
  content: string,
  kind?: ChatMessage["kind"],
  feedback?: ChatMessage["feedback"],
) => void;

type UseDashboardChatSendHandlersInput = {
  activeJob: { status?: string | null } | null | undefined;
  appendChatMessage: AppendChatMessage;
  assumedTerrainSlopePct: string;
  buildingPlacements: BuildingPlacement[];
  busy: boolean;
  cancelActiveCommandState: () => void;
  handleAddObject: (type: SiteObjectType) => void;
  handleAnalyzeImageFeatures: () => void | Promise<void>;
  handleAnalyzeSiteAccess: () => void;
  handleContinueActiveJob: () => void;
  handleGenerateSystem: (
    target: SystemGenerationTarget,
    options?: { slopeEstimateOverride?: SurveySlopeResponse | null },
  ) => void | Promise<void>;
  handleSelectPlacementTarget: (id: string) => void;
  handleToggleSiteLock: () => void;
  imageName: string | null;
  mapSnapshotPath: string | null;
  pendingClarification: PendingClarification;
  prompt: string;
  refuseUnsafeConstructionCommand: (message: string) => boolean;
  resolveLotBounds: () => { w: number; h: number };
  runOrchestrator: (mode?: PlanToolMode) => void | Promise<void>;
  setPendingClarification: StateSetter<PendingClarification>;
  setPrompt: StateSetter<string>;
  setStatusMessage: StateSetter<string>;
  setSurveySlopeEstimate: StateSetter<SurveySlopeResponse | null>;
  setUseSurveyForGrading: StateSetter<boolean>;
  shouldRouteToOrchestrator: (message: string) => boolean;
  surveyFileName: string | null;
  tryHandleActionIntent: (message: string) => boolean;
  tryHandleInfoIntent: (message: string) => boolean;
  tryHandleObjectIntent: (message: string) => boolean;
  tryHandlePowerCommand: (message: string) => boolean;
  tryHandleSheetIntent: (message: string) => boolean;
};

export function useDashboardChatSendHandlers({
  activeJob,
  appendChatMessage,
  assumedTerrainSlopePct,
  buildingPlacements,
  busy,
  cancelActiveCommandState,
  handleAddObject,
  handleAnalyzeImageFeatures,
  handleAnalyzeSiteAccess,
  handleContinueActiveJob,
  handleGenerateSystem,
  handleSelectPlacementTarget,
  handleToggleSiteLock,
  imageName,
  mapSnapshotPath,
  pendingClarification,
  prompt,
  refuseUnsafeConstructionCommand,
  resolveLotBounds,
  runOrchestrator,
  setPendingClarification,
  setPrompt,
  setStatusMessage,
  setSurveySlopeEstimate,
  setUseSurveyForGrading,
  shouldRouteToOrchestrator,
  surveyFileName,
  tryHandleActionIntent,
  tryHandleInfoIntent,
  tryHandleObjectIntent,
  tryHandlePowerCommand,
  tryHandleSheetIntent,
}: UseDashboardChatSendHandlersInput) {
  const handleSendMessage = useCallback(() => {
    const trimmed = prompt.trim();
    if (!trimmed && !imageName) return;
    if (trimmed && /\b(stamp|seal|sign|certify|approve construction|submit construction documents|engineer of record|eor)\b/i.test(trimmed)) {
      refuseUnsafeConstructionCommand(trimmed);
      setPrompt("");
      return;
    }
    const normalizedStatus = String(activeJob?.status || "").toLowerCase();
    const approvalCommand = Boolean(
      trimmed &&
        /^(ok(ay)?|approve|continue|yes|y|go ahead|start next|proceed)$/i.test(trimmed.trim()),
    );
    if (normalizedStatus === "awaiting_approval" && approvalCommand) {
      appendChatMessage("user", trimmed);
      setPrompt("");
      handleContinueActiveJob();
      return;
    }
    if (pendingClarification && trimmed) {
      appendChatMessage("user", trimmed);
      setPrompt("");
      const lot = resolveLotBounds();
      const hasSite = Boolean(lot.w && lot.h);
      if (pendingClarification.action === "set_site_then_add") {
        const handled = tryHandleObjectIntent(trimmed);
        if (handled && hasSite) {
          const type = pendingClarification.payload?.type as SiteObjectType | undefined;
          if (type) {
            setPendingClarification(null);
            handleAddObject(type);
            return;
          }
        }
        appendChatMessage("assistant", pendingClarification.question, "status");
        return;
      }
      if (pendingClarification.action === "set_site_then_detect") {
        const handled = tryHandleObjectIntent(trimmed);
        if (handled && hasSite) {
          setPendingClarification(null);
          void handleAnalyzeImageFeatures();
          return;
        }
        appendChatMessage("assistant", pendingClarification.question, "status");
        return;
      }
      if (pendingClarification.action === "set_site_then_generate") {
        const handled = tryHandleObjectIntent(trimmed);
        if (handled && hasSite) {
          const target = pendingClarification.payload?.target as SystemGenerationTarget | undefined;
          if (target) {
            setPendingClarification(null);
            void handleGenerateSystem(target);
            return;
          }
        }
        appendChatMessage("assistant", pendingClarification.question, "status");
        return;
      }
      if (pendingClarification.action === "place_object_missing_site") {
        const handled = tryHandleObjectIntent(trimmed);
        if (handled && hasSite) {
          const id = pendingClarification.payload?.id as string | undefined;
          if (id) {
            setPendingClarification(null);
            handleSelectPlacementTarget(id);
            return;
          }
        }
        appendChatMessage("assistant", pendingClarification.question, "status");
        return;
      }
      if (pendingClarification.action === "upload_image_then_detect") {
        if (mapSnapshotPath) {
          setPendingClarification(null);
          void handleAnalyzeImageFeatures();
          return;
        }
        appendChatMessage(
          "assistant",
          "Please upload a site image/map snapshot first, then say “done.”",
          "status",
        );
        return;
      }
      if (pendingClarification.action === "access_analysis_missing") {
        const confirmed = buildingPlacements.filter(
          (item) => item.placed && (item.source === "user" || item.source === "user_confirmed"),
        );
        const accessTypes = new Set<SiteObjectType>(["road", "entrance", "parking", "sidewalk", "driveway"]);
        const buildingTypes = new Set<SiteObjectType>([
          "building",
          "retail_building",
          "multifamily_building",
          "industrial_building",
          "office_building",
          "pad",
        ]);
        const buildings = confirmed.filter((item) => buildingTypes.has(item.type as SiteObjectType));
        const access = confirmed.filter((item) => accessTypes.has(item.type as SiteObjectType));
        if (buildings.length && access.length) {
          setPendingClarification(null);
          handleAnalyzeSiteAccess();
          return;
        }
        appendChatMessage(
          "assistant",
          "Once you add or confirm buildings and access objects, I can run access analysis.",
          "status",
        );
        return;
      }
      if (pendingClarification.action === "grading_source") {
        const lower = trimmed.toLowerCase();
        let slopeEstimateOverride: SurveySlopeResponse | null = null;
        if (/(survey)/.test(lower)) {
          if (!surveyFileName) {
            appendChatMessage("assistant", "Please upload a survey/topo file first.", "status");
            return;
          }
          setUseSurveyForGrading(true);
        } else if (/(map|terrain)/.test(lower)) {
          setUseSurveyForGrading(false);
        } else if (/(assume|assumed|fallback)/.test(lower)) {
          slopeEstimateOverride = buildAssumedSlopeEstimate(parsePositiveNumber(assumedTerrainSlopePct) ?? 8);
          setUseSurveyForGrading(false);
          setSurveySlopeEstimate(slopeEstimateOverride);
        } else {
          appendChatMessage(
            "assistant",
            "Should I use survey, map terrain, or an assumed slope?",
            "status",
          );
          return;
        }
        const target = pendingClarification.payload?.target as SystemGenerationTarget | undefined;
        if (target) {
          setPendingClarification(null);
          void handleGenerateSystem(target, { slopeEstimateOverride });
          return;
        }
      }
      if (pendingClarification.action === "drainage_missing_basin") {
        const hasBasin = buildingPlacements.some((item) => item.type === "basin" && item.placed);
        if (hasBasin) {
          const target = pendingClarification.payload?.target as "drainage" | "full" | undefined;
          if (target) {
            setPendingClarification(null);
            void handleGenerateSystem(target);
            return;
          }
        }
        appendChatMessage(
          "assistant",
          "Add a basin object first, then I can run drainage.",
          "status",
        );
        return;
      }
      if (pendingClarification.action === "lock_site_required") {
        const lower = trimmed.toLowerCase();
        if (/(yes|ok|lock|confirm)/.test(lower)) {
          setPendingClarification(null);
          handleToggleSiteLock();
          const target = pendingClarification.payload?.action as SystemGenerationTarget | undefined;
          if (target) {
            void handleGenerateSystem(target);
          }
          return;
        }
        appendChatMessage(
          "assistant",
          "Lock the site when you're ready, then I can continue.",
          "status",
        );
        return;
      }
    }
    if (busy || activeJob) {
      if (trimmed || imageName) {
        appendChatMessage("user", trimmed || "Uploaded an image.");
        appendChatMessage(
          "assistant",
          "A run is already in progress. Please wait for it to finish before sending a new request.",
          "status",
        );
      }
      setStatusMessage("A run is already in progress. Please wait for it to finish.");
      setPrompt("");
      return;
    }
    if (trimmed) {
      const handledPowerCommand = tryHandlePowerCommand(trimmed);
      if (handledPowerCommand) {
        setPrompt("");
        return;
      }
      const routeToOrchestrator = shouldRouteToOrchestrator(trimmed);
      if (!routeToOrchestrator) {
        const handled = tryHandleObjectIntent(trimmed);
        if (handled) {
          setPrompt("");
          return;
        }
        const handledSheet = tryHandleSheetIntent(trimmed);
        if (handledSheet) {
          setPrompt("");
          return;
        }
        const handledInfo = tryHandleInfoIntent(trimmed);
        if (handledInfo) {
          setPrompt("");
          return;
        }
        const handledAction = tryHandleActionIntent(trimmed);
        if (handledAction) {
          setPrompt("");
          return;
        }
      }
    }
    void runOrchestrator("run");
  }, [
    activeJob,
    appendChatMessage,
    assumedTerrainSlopePct,
    buildingPlacements,
    busy,
    handleAddObject,
    handleAnalyzeImageFeatures,
    handleAnalyzeSiteAccess,
    handleContinueActiveJob,
    handleGenerateSystem,
    handleSelectPlacementTarget,
    handleToggleSiteLock,
    imageName,
    mapSnapshotPath,
    pendingClarification,
    prompt,
    refuseUnsafeConstructionCommand,
    resolveLotBounds,
    runOrchestrator,
    setPendingClarification,
    setPrompt,
    setStatusMessage,
    setSurveySlopeEstimate,
    setUseSurveyForGrading,
    shouldRouteToOrchestrator,
    surveyFileName,
    tryHandleActionIntent,
    tryHandleInfoIntent,
    tryHandleObjectIntent,
    tryHandlePowerCommand,
    tryHandleSheetIntent,
  ]);

  const handlePromptKeyDown = useCallback((event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Escape") {
      event.preventDefault();
      cancelActiveCommandState();
      return;
    }
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSendMessage();
    }
  }, [cancelActiveCommandState, handleSendMessage]);

  const handleContinuePendingClarification = useCallback(() => {
    if (!pendingClarification) return;
    const lot = resolveLotBounds();
    const hasSite = Boolean(lot.w && lot.h);
    if (pendingClarification.action === "set_site_then_add") {
      if (!hasSite) {
        appendChatMessage("assistant", pendingClarification.question, "status");
        return;
      }
      const type = pendingClarification.payload?.type as SiteObjectType | undefined;
      if (type) {
        setPendingClarification(null);
        handleAddObject(type);
      }
      return;
    }
    if (pendingClarification.action === "set_site_then_detect") {
      if (!hasSite) {
        appendChatMessage("assistant", pendingClarification.question, "status");
        return;
      }
      setPendingClarification(null);
      void handleAnalyzeImageFeatures();
      return;
    }
    if (pendingClarification.action === "set_site_then_generate") {
      if (!hasSite) {
        appendChatMessage("assistant", pendingClarification.question, "status");
        return;
      }
      const target = pendingClarification.payload?.target as SystemGenerationTarget | undefined;
      if (target) {
        setPendingClarification(null);
        void handleGenerateSystem(target);
      }
      return;
    }
    if (pendingClarification.action === "upload_image_then_detect") {
      if (!mapSnapshotPath) {
        appendChatMessage("assistant", "Please upload a site image/map snapshot first.", "status");
        return;
      }
      setPendingClarification(null);
      void handleAnalyzeImageFeatures();
      return;
    }
    if (pendingClarification.action === "access_analysis_missing") {
      setPendingClarification(null);
      handleAnalyzeSiteAccess();
      return;
    }
    if (pendingClarification.action === "grading_source") {
      const target = pendingClarification.payload?.target as SystemGenerationTarget | undefined;
      if (target) {
        const slopeEstimateOverride = buildAssumedSlopeEstimate(parsePositiveNumber(assumedTerrainSlopePct) ?? 8);
        setUseSurveyForGrading(false);
        setSurveySlopeEstimate(slopeEstimateOverride);
        setPendingClarification(null);
        void handleGenerateSystem(target, { slopeEstimateOverride });
      }
    }
  }, [
    appendChatMessage,
    assumedTerrainSlopePct,
    handleAddObject,
    handleAnalyzeImageFeatures,
    handleAnalyzeSiteAccess,
    handleGenerateSystem,
    mapSnapshotPath,
    pendingClarification,
    resolveLotBounds,
    setPendingClarification,
    setSurveySlopeEstimate,
    setUseSurveyForGrading,
  ]);

  return { handleContinuePendingClarification, handlePromptKeyDown, handleSendMessage };
}
