import { useCallback, type Dispatch, type SetStateAction } from "react";

import type {
  BuildingPlacement,
  ChatMessage,
  ControlOverrides,
  PlanRequestPayload,
  PlanToolMode,
  SurveySlopeResponse,
} from "../types";
import {
  OVERSIZED_SITE_MESSAGE,
  REACTIVE_EDIT_POLICY_PREFERENCE,
  SITE_GRADING_HARD_BLOCK_ACRES,
  buildAssumedSlopeEstimate,
  isHardGenerateBlocker,
  siteAreaAcresFromSize,
  uniqueStrings,
  type EngineeringSystemKey,
  type ReactiveValidationState,
  type SystemGenerationTarget,
  type SystemStatus,
} from "../utils/workflowConstants";
import type { GenerateLayoutContext } from "../utils/dashboardGenerateLayoutContext";
import type { GenerateFlowSummary, AutoSiteContextFlowSummary } from "../utils/dashboardDataTypes";
import type { RecentChange } from "../utils/dashboardTypes";
import { parsePositiveNumber, toReadableLabel } from "../utils/formatting";
import { markCivoraInteraction, measureCivoraInteractionAfterPaint } from "../utils/performanceProbes";
import type { ProjectStatusSummary, SidePanelKey } from "../utils/workspaceShell";

type AppendChatMessage = (
  role: ChatMessage["role"],
  content: string,
  kind?: ChatMessage["kind"],
  feedback?: ChatMessage["feedback"],
) => void;

type ExecutePlanAction = (input: {
  mode: PlanToolMode;
  requestPayload: PlanRequestPayload;
  assistantPrefix?: string | null;
  timeoutMs?: number;
  allowQueueFallback?: boolean;
  forceQueue?: boolean;
}) => Promise<void>;

type BuildPayloadFromOverrides = (
  overrides?: ControlOverrides,
  promptOverride?: string,
  projectId?: string | null,
  placementsOverride?: BuildingPlacement[],
) => PlanRequestPayload;

type UseDashboardGenerateSystemActionInput = {
  appendChatMessage: AppendChatMessage;
  askClarification: (question: string, reason: string, context?: Record<string, unknown>) => void;
  assumedTerrainSlopePct: string;
  autoSiteContextFlowSummary: AutoSiteContextFlowSummary;
  buildPayloadFromOverrides: BuildPayloadFromOverrides;
  createGenerateConceptObjects: (target: SystemGenerationTarget, reviewNotes: string[]) => number;
  currentGenerateLayoutContext: GenerateLayoutContext | null;
  effectiveDemoWorkspaceEnabled: boolean;
  ensureSiteLocked: (action: string) => boolean;
  executePlanAction: ExecutePlanAction;
  getGeneratePreflightBlockers: (target: SystemGenerationTarget) => Array<{ action: SidePanelKey; label: string }>;
  handleOpenSidePanel: (panel: SidePanelKey) => void;
  hasAssumedTerrainSlope: boolean;
  hasSiteBoundary: () => boolean;
  minSlopePct: string;
  pendingPlacementLabels: string[];
  pendingPlacementObjects: BuildingPlacement[];
  persistFlowMetadata: (updates: Partial<{ generate_flow_summary_v1: GenerateFlowSummary }>) => Promise<void>;
  projectId: string;
  reactiveChangedSystems: EngineeringSystemKey[];
  reactiveValidation: ReactiveValidationState;
  recordRecentChange: (change: Omit<RecentChange, "id" | "createdAt">) => void;
  resolveLotBounds: () => { w?: number | null; h?: number | null };
  setGenerateFlowSummary: (summary: GenerateFlowSummary) => void;
  setSystemStatuses: Dispatch<
    SetStateAction<Record<"roads" | "parking" | "grading" | "drainage" | "utilities", SystemStatus>>
  >;
  siteHasGeocode: boolean;
  surveyFileName: string;
  surveySlopePercent: number | null | undefined;
  token: string | null;
  updateProjectStatus: (summary: Omit<ProjectStatusSummary, "updatedAt">) => void;
  useSurveyForGrading: boolean;
  withReactiveRerunContext: (
    payload: PlanRequestPayload,
    target: SystemGenerationTarget,
  ) => PlanRequestPayload;
};

export function useDashboardGenerateSystemAction({
  appendChatMessage,
  askClarification,
  assumedTerrainSlopePct,
  autoSiteContextFlowSummary,
  buildPayloadFromOverrides,
  createGenerateConceptObjects,
  currentGenerateLayoutContext,
  effectiveDemoWorkspaceEnabled,
  ensureSiteLocked,
  executePlanAction,
  getGeneratePreflightBlockers,
  handleOpenSidePanel,
  hasAssumedTerrainSlope,
  hasSiteBoundary,
  minSlopePct,
  pendingPlacementLabels,
  pendingPlacementObjects,
  persistFlowMetadata,
  projectId,
  reactiveChangedSystems,
  reactiveValidation,
  recordRecentChange,
  resolveLotBounds,
  setGenerateFlowSummary,
  setSystemStatuses,
  siteHasGeocode,
  surveyFileName,
  surveySlopePercent,
  token,
  updateProjectStatus,
  useSurveyForGrading,
  withReactiveRerunContext,
}: UseDashboardGenerateSystemActionInput) {
  return useCallback(
    async (
      target: SystemGenerationTarget,
      options?: { slopeEstimateOverride?: SurveySlopeResponse | null },
    ) => {
      const generateStartedAt = markCivoraInteraction();
      const preflightBlockers = getGeneratePreflightBlockers(target);
      const hardPreflightBlockers = preflightBlockers.filter((item) => isHardGenerateBlocker(item.label));
      const userLayoutContextSummary = currentGenerateLayoutContext;
      const reviewNotes = uniqueStrings([
        ...preflightBlockers.filter((item) => !isHardGenerateBlocker(item.label)).map((item) => item.label),
        userLayoutContextSummary
          ? `User layout context used by Generate: ${userLayoutContextSummary.labels.join(", ")}${userLayoutContextSummary.count > userLayoutContextSummary.labels.length ? `, plus ${userLayoutContextSummary.count - userLayoutContextSummary.labels.length} more` : ""}`
          : "",
        userLayoutContextSummary?.semantic_count ? `${userLayoutContextSummary.semantic_count} semantic drafted object${userLayoutContextSummary.semantic_count === 1 ? "" : "s"} included as review context` : "",
        pendingPlacementObjects.length
          ? `Requested objects still need placement before Generate can use them as layout context: ${pendingPlacementLabels.slice(0, 8).join(", ")}${pendingPlacementObjects.length > 8 ? `, plus ${pendingPlacementObjects.length - 8} more` : ""}`
          : "",
        ...autoSiteContextFlowSummary.missingLabels.map((item) => `Auto Site Context missing source: ${item}`),
        autoSiteContextFlowSummary.candidateCount > 0
          ? `Auto Site Context source candidates available for review: ${autoSiteContextFlowSummary.candidateLabels.join(", ") || `${autoSiteContextFlowSummary.candidateCount} candidate(s)`}`
          : "",
        hasAssumedTerrainSlope ? "review-only assumed terrain slope; survey/control still needed" : "",
      ]);
      const targetSystems =
        target === "full"
          ? (["roads", "parking", "grading", "drainage", "utilities"] as EngineeringSystemKey[])
          : ([target] as EngineeringSystemKey[]);
      const skippedSystems =
        target === "full"
          ? []
          : (["roads", "parking", "grading", "drainage", "utilities"] as EngineeringSystemKey[]).filter((system) => system !== target);
      const blockedSummary = (reason: string, nextAction: string): GenerateFlowSummary => ({
        version: "generate_flow_summary_v1",
        generated_at: new Date().toISOString(),
        target,
        ran: [],
        skipped: targetSystems,
        needs_review: uniqueStrings([reason, ...reviewNotes]),
        notes: reviewNotes,
        blocked: true,
        next_action: nextAction,
        auto_site_context: autoSiteContextFlowSummary,
        user_layout_context: userLayoutContextSummary,
        safety_wording:
          "Generate creates review-required drafts for qualified review.",
      });
      const recordGenerateSummary = (summary: GenerateFlowSummary) => {
        setGenerateFlowSummary(summary);
        recordRecentChange({
          type: "generate_recorded",
          label: summary.blocked ? "Generate needs input" : "Generate recorded",
          detail: summary.blocked
            ? `Generate needs input: ${summary.needs_review[0] || summary.next_action}`
            : `Generate ran ${summary.ran.join(", ") || "none"}; skipped ${summary.skipped.join(", ") || "none"}.`,
          undoBlockedReason: "Generate history is a review record. Undo draft object edits separately, then rerun Generate if needed.",
        });
        measureCivoraInteractionAfterPaint("generate.panel.response.visible", generateStartedAt, {
          target,
          blocked: summary.blocked,
          ran: summary.ran.length,
          skipped: summary.skipped.length,
        });
        void persistFlowMetadata({ generate_flow_summary_v1: summary });
      };
      if (hardPreflightBlockers.length) {
        const firstHardBlocker = hardPreflightBlockers[0];
        const summary = blockedSummary(
          firstHardBlocker.label,
          `Open ${toReadableLabel(firstHardBlocker.action)} and fix: ${firstHardBlocker.label}.`,
        );
        recordGenerateSummary(summary);
        appendChatMessage(
          "assistant",
          `Generate needs input: ${firstHardBlocker.label}. Next action: ${summary.next_action}`,
          "status",
        );
        updateProjectStatus({
          state: "blocked",
          area: "generate",
          title: "Generate needs input",
          detail: firstHardBlocker.label,
          nextAction: summary.next_action,
        });
        handleOpenSidePanel(firstHardBlocker.action);
        return;
      }
      if (!hasSiteBoundary()) {
        const summary = blockedSummary("missing site boundary dimensions", "Set site width/depth or draw a site boundary, then lock the site.");
        recordGenerateSummary(summary);
        updateProjectStatus({
          state: "blocked",
          area: "generate",
          title: "Generate needs site boundary",
          detail: "Set and lock a site boundary first.",
          nextAction: summary.next_action,
        });
        askClarification(
          "I need a site boundary before generating systems. What size should the site be?",
          "set_site_then_generate",
          { target },
        );
        return;
      }
      if (!ensureSiteLocked(target)) {
        const summary = blockedSummary("site boundary exists but is not locked", "Lock the site boundary in Setup before running Generate.");
        recordGenerateSummary(summary);
        updateProjectStatus({
          state: "blocked",
          area: "generate",
          title: "Generate needs locked boundary",
          detail: "Site boundary exists but is not locked.",
          nextAction: summary.next_action,
        });
        return;
      }
      if (target === "grading" || target === "drainage" || target === "full") {
        const lot = resolveLotBounds();
        const siteAreaAcres = siteAreaAcresFromSize(lot.w, lot.h);
        if (target === "grading" && siteAreaAcres > SITE_GRADING_HARD_BLOCK_ACRES) {
          const summary = blockedSummary(OVERSIZED_SITE_MESSAGE, "Reduce the site area or zoom to a smaller grading area.");
          recordGenerateSummary(summary);
          updateProjectStatus({
            state: "blocked",
            area: "generate",
            title: "Generate needs smaller grading area",
            detail: OVERSIZED_SITE_MESSAGE,
            nextAction: summary.next_action,
          });
          return;
        }
      }
      const conceptCount = createGenerateConceptObjects(target, reviewNotes);
      const requestPayload = buildPayloadFromOverrides({}, undefined, projectId || null);
      const omitField = { source: "omit", value: null } as const;
      const nextManualFields = {
        ...(requestPayload.manual_fields ?? {}),
      } as Record<string, unknown>;
      const targetUsesTerrain = target === "grading" || target === "drainage" || target === "full";
      const hasSurvey = Boolean(surveyFileName) && useSurveyForGrading;
      const hasMapTerrain = siteHasGeocode;
      const slopeEstimateOverride =
        options?.slopeEstimateOverride ??
        (targetUsesTerrain && !hasSurvey && !hasMapTerrain && !surveySlopePercent
          ? buildAssumedSlopeEstimate(parsePositiveNumber(assumedTerrainSlopePct) ?? 8)
          : null);
      if (slopeEstimateOverride?.slope_percent) {
        nextManualFields.grading = {
          ...((typeof nextManualFields.grading === "object" && nextManualFields.grading !== null
            ? nextManualFields.grading
            : {}) as Record<string, unknown>),
          min_slope_pct:
            parsePositiveNumber(minSlopePct) ?? slopeEstimateOverride.slope_percent,
          assumed_terrain_source: true,
        };
        nextManualFields.terrain =
          slopeEstimateOverride.direction && slopeEstimateOverride.slope_percent
            ? `First-pass assumed ${slopeEstimateOverride.slope_percent.toFixed(2)}% slope toward ${slopeEstimateOverride.direction}`
            : "First-pass assumed terrain slope";
      }

      if (target === "roads" || target === "parking") {
        nextManualFields.grading = omitField;
        nextManualFields.drainage = omitField;
        nextManualFields.utility_network = omitField;
      } else if (target === "grading") {
        nextManualFields.drainage = omitField;
        nextManualFields.utility_network = omitField;
      } else if (target === "drainage") {
        nextManualFields.utility_network = omitField;
      } else if (target === "utilities") {
        nextManualFields.drainage = omitField;
      }

      const systemLabel = target === "full" ? "full site systems" : target;
      const queueLongRun = target === "full";
      if (
        target !== "full" &&
        reactiveValidation.requiresConfirmation &&
        REACTIVE_EDIT_POLICY_PREFERENCE.require_confirmation_for_heavy_engineering
      ) {
        const confirmed = window.confirm(
          `This rerun will update ${reactiveValidation.changedSystems.join(", ")} from the saved checkpoint and may touch ${reactiveValidation.changedTargets.length} downstream stages. Run it now?`,
        );
        if (!confirmed) {
          updateProjectStatus({
            state: "stale",
            area: "generate",
            title: "Generate stale",
            detail: "Reactive engineering rerun cancelled. Visual edits remain live; engineering outputs are still stale.",
            nextAction: "Review changed objects, then rerun affected systems when ready.",
          });
          return;
        }
      }
      const systemRequestPayload = withReactiveRerunContext(
        {
          ...requestPayload,
          full_design_mode: target === "full",
          manual_fields: nextManualFields,
          meta: {
            ...(requestPayload.meta ?? {}),
            requested_system: target,
            auto_site_context_review_summary: autoSiteContextFlowSummary,
            user_layout_context_summary: userLayoutContextSummary,
            generate_notes: reviewNotes,
          },
          prompt_text: null,
        },
        target,
      );
      if (!token && effectiveDemoWorkspaceEnabled) {
        const runSummary: GenerateFlowSummary = {
          version: "generate_flow_summary_v1",
          generated_at: new Date().toISOString(),
          target,
          ran: targetSystems,
          skipped: skippedSystems,
          needs_review: reviewNotes,
          notes: reviewNotes,
          blocked: false,
          next_action: reviewNotes.length
            ? "Review the local draft notes and provide or accept missing sources before relying on outputs."
            : "Review the local draft package; outputs remain engineer-review-required.",
          auto_site_context: autoSiteContextFlowSummary,
          user_layout_context: userLayoutContextSummary,
          safety_wording:
            "Generate creates review-required drafts for qualified review.",
        };
        recordGenerateSummary(runSummary);
        setSystemStatuses((prev) => {
          const next = { ...prev };
          targetSystems.forEach((system) => {
            next[system] = "fresh";
          });
          return next;
        });
        updateProjectStatus({
          state: "needs review",
          area: "generate",
          title: runSummary.skipped.length ? "Started, with skipped systems" : "Generate draft ready",
          detail: `${systemLabel} ran in local demo mode with review-required outputs.`,
          nextAction: runSummary.next_action,
        });
        appendChatMessage(
          "assistant",
          [
            `${runSummary.skipped.length ? "Started, with skipped systems" : "Generate started"}. Ran: ${runSummary.ran.join(", ")}.`,
            conceptCount ? `Canvas: added ${conceptCount} visible review concept object${conceptCount === 1 ? "" : "s"}.` : "",
            runSummary.skipped.length ? `Skipped: ${runSummary.skipped.join(", ")}.` : "Skipped: none.",
            runSummary.needs_review.length ? `Needs review: ${runSummary.needs_review.slice(0, 5).join("; ")}.` : "Needs review: standard engineer review.",
          ].filter(Boolean).join(" "),
          "status",
        );
        return;
      }
      if (!token) {
        const summary = blockedSummary(
          "backend/auth session is required for hosted engineering generation",
          "Keep editing this local review layout, or sign in before running backend generation.",
        );
        recordGenerateSummary(summary);
        updateProjectStatus({
          state: conceptCount ? "needs review" : "blocked",
          area: "generate",
          title: conceptCount ? "Local draft concepts added" : "Generate needs sign-in",
          detail: conceptCount
            ? "Civora added local review concept geometry. Backend engineering generation needs a signed-in session."
            : "Hosted engineering generation needs a signed-in backend session. No backend request was sent.",
          nextAction: summary.next_action,
        });
        appendChatMessage(
          "assistant",
          conceptCount
            ? `I added ${conceptCount} visible review concept object${conceptCount === 1 ? "" : "s"} to the canvas. Sign in when you want backend engineering generation; this local layout remains review-only.`
            : "Generate needs a signed-in backend session for backend engineering generation. I did not send an engineering request; keep editing locally or sign in to run Generate.",
          "status",
        );
        return;
      }
      const runSummary: GenerateFlowSummary = {
        version: "generate_flow_summary_v1",
        generated_at: new Date().toISOString(),
        target,
        ran: targetSystems,
        skipped: skippedSystems,
        needs_review: reviewNotes,
        notes: reviewNotes,
        blocked: false,
        next_action: reviewNotes.length
          ? "Review the generated draft notes and provide or accept missing sources before relying on outputs."
          : "Review the generated draft package; outputs remain engineer-review-required.",
        auto_site_context: autoSiteContextFlowSummary,
        user_layout_context: userLayoutContextSummary,
        safety_wording:
          "Generate creates review-required drafts for qualified review.",
      };
      recordGenerateSummary(runSummary);
      updateProjectStatus({
        state: "working",
        area: "generate",
        title: "Generate working",
        detail: `Running ${systemLabel} from the locked site.`,
        nextAction: "Wait for the run to finish, queue, or show a blocker.",
      });
      appendChatMessage(
        "assistant",
        [
          `${runSummary.skipped.length ? "Started, with skipped systems" : "Generate started"}. Ran: ${runSummary.ran.join(", ")}.`,
          conceptCount ? `Canvas: added ${conceptCount} visible review concept object${conceptCount === 1 ? "" : "s"}.` : "",
          runSummary.skipped.length ? `Skipped: ${runSummary.skipped.join(", ")}.` : "Skipped: none.",
          runSummary.needs_review.length ? `Needs review: ${runSummary.needs_review.slice(0, 5).join("; ")}.` : "Needs review: standard engineer review.",
        ].filter(Boolean).join(" "),
        "status",
      );
      await executePlanAction({
        mode: "run",
        requestPayload: systemRequestPayload,
        assistantPrefix: `Generating a review draft for ${systemLabel} around the locked site...`,
        timeoutMs: queueLongRun ? undefined : 20_000,
        allowQueueFallback: true,
        forceQueue: queueLongRun,
      });
      if (queueLongRun) {
        return;
      }
      setSystemStatuses((prev) => {
        const next = { ...prev };
        next[target] = "fresh";
        reactiveChangedSystems.forEach((system) => {
          next[system] = "fresh";
        });
        return next;
      });
      updateProjectStatus({
        state: "needs review",
        area: "generate",
        title: "Generate needs review",
        detail: `${systemLabel} draft is current in this workspace.`,
        nextAction: runSummary.next_action,
      });
    },
    [
      appendChatMessage,
      askClarification,
      assumedTerrainSlopePct,
      autoSiteContextFlowSummary,
      buildPayloadFromOverrides,
      createGenerateConceptObjects,
      currentGenerateLayoutContext,
      effectiveDemoWorkspaceEnabled,
      ensureSiteLocked,
      executePlanAction,
      getGeneratePreflightBlockers,
      handleOpenSidePanel,
      hasAssumedTerrainSlope,
      hasSiteBoundary,
      minSlopePct,
      pendingPlacementLabels,
      pendingPlacementObjects,
      persistFlowMetadata,
      projectId,
      reactiveChangedSystems,
      reactiveValidation,
      recordRecentChange,
      resolveLotBounds,
      setGenerateFlowSummary,
      setSystemStatuses,
      siteHasGeocode,
      surveyFileName,
      surveySlopePercent,
      token,
      updateProjectStatus,
      useSurveyForGrading,
      withReactiveRerunContext,
    ],
  );
}
