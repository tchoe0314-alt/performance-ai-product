import type {
  ChatMessage,
  ManualFields,
  PlanRequestPayload,
  PlanResponse,
  PreviewRequestPayload,
  ProjectRecord,
  SiteInputs,
} from "../types";
import type { SystemStatus } from "./workflowConstants";
import { preserveExplicitBriefProgram } from "./briefProgramPreservation";

type BuildDashboardPayloadPreviewOptions = {
  projectId: string;
  assistedEnabled: boolean;
  prompt: string;
  imageName: string;
  chatMessages: ChatMessage[];
  currentProject?: ProjectRecord | null;
  systemStatuses: Record<string, SystemStatus>;
  reactiveEditPolicyPreference: NonNullable<PlanRequestPayload["meta"]>["reactive_edit_policy_preference"];
  siteObjectId?: string | null;
  manualFields: ManualFields;
};

export function buildDashboardPayloadPreview({
  projectId,
  assistedEnabled,
  prompt,
  imageName,
  chatMessages,
  currentProject,
  systemStatuses,
  reactiveEditPolicyPreference,
  siteObjectId,
  manualFields,
}: BuildDashboardPayloadPreviewOptions): PlanRequestPayload {
  return {
    project_id: projectId || null,
    full_design_mode: true,
    input_mode: assistedEnabled ? "assisted" : "user",
    strict_mode: false,
    prompt_text: prompt || null,
    image_path: imageName || null,
    meta: {
      chat_thread: chatMessages,
      site_inputs: (currentProject?.project_input?.meta?.site_inputs ?? {}) as SiteInputs,
      requested_site_program_v1: currentProject?.project_input?.meta?.requested_site_program_v1,
      project_identity_v1: currentProject?.project_input?.meta?.project_identity_v1,
      system_dirty_state: systemStatuses,
      reactive_edit_policy_preference: reactiveEditPolicyPreference,
      site_object_id: siteObjectId ?? null,
      assisted_enabled: assistedEnabled,
    },
    manual_fields: preserveExplicitBriefProgram(manualFields, currentProject?.project_input),
    allow_ai_fill_for_blanks: assistedEnabled,
  };
}

export function buildDashboardArtifactPayload({
  backendResult,
  projectId,
  currentProject,
  fileName,
  siteName,
}: {
  backendResult: PlanResponse | null;
  projectId: string;
  currentProject?: ProjectRecord | null;
  fileName: string;
  siteName: string;
}): PreviewRequestPayload {
  const payload: PreviewRequestPayload = {
    project_id: projectId || currentProject?.project_id || null,
    filename_stem: currentProject?.name || fileName || siteName,
  };
  if (backendResult && typeof backendResult === "object" && Object.keys(backendResult).length) {
    payload.result = backendResult;
  }
  return payload;
}

/**
 * Project-bound preview requests are resolved from the tenant-scoped saved
 * project on the server. Sending a client copy of the result in that case is
 * both redundant and misleading: the backend deliberately ignores it in
 * favour of the authoritative saved result. Keep the inline result fallback
 * for previews which do not have a project identity.
 */
export function buildAuthoritativePreviewTransportPayload(
  payload: PreviewRequestPayload,
): PreviewRequestPayload {
  if (!String(payload.project_id ?? "").trim()) return payload;
  const { result: _ignoredResult, final_plan: _ignoredFinalPlan, ...authoritativePayload } = payload;
  return authoritativePayload;
}

export function buildPreviewRequestIdentity({
  payload,
  jobId,
  jobUpdatedAt,
}: {
  payload: PreviewRequestPayload;
  jobId?: string | null;
  jobUpdatedAt?: number | string | null;
}): unknown {
  const projectId = String(payload.project_id ?? "").trim();
  if (!projectId) return { projectId: null, result: payload.result ?? payload.final_plan ?? null };

  const metadata = (payload.result?.metadata ?? {}) as Record<string, unknown>;
  const checkpoint = (metadata.runtime_phase_checkpoint ?? {}) as Record<string, unknown>;
  const calculation = (metadata.calculation_save_v1 ?? {}) as Record<string, unknown>;
  const binding = (metadata.canvas_result_binding_v1 ?? {}) as Record<string, unknown>;
  return {
    projectId,
    jobId: jobId ?? null,
    jobUpdatedAt: jobUpdatedAt ?? null,
    workflowRunId: metadata._workflow_run_id ?? null,
    calculationId: calculation.calculation_id ?? null,
    inputSignature: binding.input_signature ?? null,
    checkpointStage: checkpoint.stage_name ?? null,
    checkpointYielded: checkpoint.yielded === true,
  };
}
