import { useCallback, type Dispatch, type SetStateAction } from "react";

import { postJson } from "../../lib/api";
import type {
  BuildingPlacement,
  ChatMessage,
  ControlOverrides,
  JobSummary,
  PlanRequestPayload,
  PlanToolMode,
} from "../types";
import type { SystemStatus } from "../utils/workflowConstants";

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
}) => Promise<void>;

type BuildPayloadFromOverrides = (
  overrides?: ControlOverrides,
  promptOverride?: string,
  projectId?: string | null,
  placementsOverride?: BuildingPlacement[],
) => PlanRequestPayload;

type UseDashboardDrainageAutofixInput = {
  appendChatMessage: AppendChatMessage;
  buildPayloadFromOverrides: BuildPayloadFromOverrides;
  currentProjectId: string | null | undefined;
  drainageMaxSlopeAdjust: number;
  ensureSiteLocked: (action: string) => boolean;
  executePlanAction: ExecutePlanAction;
  projectId: string;
  setActiveJobId: (jobId: string) => void;
  setStatusMessage: (message: string) => void;
  setSystemStatuses: Dispatch<
    SetStateAction<Record<"roads" | "parking" | "grading" | "drainage" | "utilities", SystemStatus>>
  >;
  token: string | null;
  withReactiveRerunContext: (payload: PlanRequestPayload, target: "drainage") => PlanRequestPayload;
};

type DrainageAutofixInput = {
  placementsOverride?: BuildingPlacement[];
  forcedInlets?: Array<Record<string, unknown>>;
  forcedBasins?: Array<Record<string, unknown>>;
  connectOrphans?: boolean;
  allowSlopeAdjust?: boolean;
};

export function useDashboardDrainageAutofix({
  appendChatMessage,
  buildPayloadFromOverrides,
  currentProjectId,
  drainageMaxSlopeAdjust,
  ensureSiteLocked,
  executePlanAction,
  projectId,
  setActiveJobId,
  setStatusMessage,
  setSystemStatuses,
  token,
  withReactiveRerunContext,
}: UseDashboardDrainageAutofixInput) {
  return useCallback(
    async ({
      placementsOverride,
      forcedInlets,
      forcedBasins,
      connectOrphans,
      allowSlopeAdjust,
    }: DrainageAutofixInput): Promise<boolean> => {
      if (!ensureSiteLocked("drainage")) return false;
      const requestPayload = buildPayloadFromOverrides({}, undefined, projectId || null, placementsOverride);
      const omitField = { source: "omit", value: null } as const;
      const nextManualFields = {
        ...(requestPayload.manual_fields ?? {}),
      } as Record<string, unknown>;
      const rawDrainage = nextManualFields.drainage;
      const unwrappedDrainage =
        rawDrainage &&
        typeof rawDrainage === "object" &&
        "value" in (rawDrainage as Record<string, unknown>)
          ? ((rawDrainage as Record<string, unknown>).value ?? {})
          : rawDrainage ?? {};
      const nextDrainage = {
        ...(typeof unwrappedDrainage === "object" && unwrappedDrainage !== null ? unwrappedDrainage : {}),
      } as Record<string, unknown>;
      if (forcedInlets && forcedInlets.length) {
        nextDrainage.forced_inlets = forcedInlets;
      }
      if (forcedBasins) {
        if (forcedBasins.length) {
          nextManualFields.ponds = forcedBasins;
        }
        nextDrainage.autofix_action = "add_basin";
      }
      if (connectOrphans) {
        nextDrainage.connect_orphans = true;
      }
      if (allowSlopeAdjust) {
        nextDrainage.allow_slope_adjustment = true;
        nextDrainage.max_slope_adjust = drainageMaxSlopeAdjust;
        nextDrainage.autofix_action = "adjust_slope";
      }
      nextManualFields.drainage = nextDrainage;
      nextManualFields.utility_network = omitField;

      const drainagePayload: PlanRequestPayload = withReactiveRerunContext(
        {
          ...requestPayload,
          manual_fields: nextManualFields,
          meta: {
            ...(requestPayload.meta ?? {}),
            requested_system: "drainage",
          },
          prompt_text: null,
        },
        "drainage",
      );
      if (allowSlopeAdjust) {
        const existingDrainage = (requestPayload.drainage ?? {}) as Record<string, unknown>;
        (drainagePayload as Record<string, unknown>).drainage = {
          ...existingDrainage,
          allow_slope_adjustment: true,
          max_slope_adjust: drainageMaxSlopeAdjust,
          autofix_action: "adjust_slope",
        };
      }

      if (token && (projectId || currentProjectId)) {
        const targetProjectId = projectId || currentProjectId || null;
        try {
          const queued = await postJson<{ job: JobSummary }>(
            "/api/jobs/drainage",
            {
              project_id: targetProjectId,
              request: drainagePayload,
            },
            { token },
          );
          const jobId = queued.job.job_id;
          setActiveJobId(jobId);
          appendChatMessage(
            "assistant",
            `Queued drainage autofix as ${jobId}. Civora will show queued/running progress here and refresh the review state when it completes.`,
            "status",
          );
          setStatusMessage(`Drainage autofix queued as ${jobId}.`);
          return true;
        } catch (error) {
          const message = error instanceof Error ? error.message : "Drainage autofix failed.";
          appendChatMessage("assistant", message, "status");
          setStatusMessage(message);
          return false;
        }
      } else {
        await executePlanAction({
          mode: "run",
          requestPayload: drainagePayload,
          assistantPrefix: "Applying drainage fix…",
        });
      }
      setSystemStatuses((prev) => ({ ...prev, drainage: "fresh" }));
      return true;
    },
    [
      appendChatMessage,
      buildPayloadFromOverrides,
      currentProjectId,
      drainageMaxSlopeAdjust,
      ensureSiteLocked,
      executePlanAction,
      projectId,
      setActiveJobId,
      setStatusMessage,
      setSystemStatuses,
      token,
      withReactiveRerunContext,
    ],
  );
}
