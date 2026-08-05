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
      system_dirty_state: systemStatuses,
      reactive_edit_policy_preference: reactiveEditPolicyPreference,
      site_object_id: siteObjectId ?? null,
      assisted_enabled: assistedEnabled,
    },
    manual_fields: manualFields,
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
