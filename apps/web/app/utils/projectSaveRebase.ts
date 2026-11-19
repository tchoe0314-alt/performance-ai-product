import type { ProjectRecord } from "../types";
import { resolveCanonicalCanvasInput } from "./canonicalCanvasProject";
import { semanticEditKey, stableJson } from "./editTransactions";

/**
 * A completed calculation may advance the server revision without editing the
 * design. Retry only when the latest server record still has the exact editable
 * baseline the browser acknowledged; real concurrent edits must remain a
 * conflict instead of being overwritten.
 */
export function canRebaseCalculationRevision(
  baseline: ProjectRecord | undefined,
  latest: ProjectRecord,
): boolean {
  if (!baseline || baseline.project_id !== latest.project_id || baseline.name !== latest.name) return false;
  const before = resolveCanonicalCanvasInput(baseline.project_input ?? {});
  const after = resolveCanonicalCanvasInput(latest.project_input ?? {});
  const metadata = (project: ProjectRecord) => {
    const value = { ...project.metadata };
    delete value.design_save_generation_v1;
    return value;
  };
  const sourceControls = (input: typeof before) => {
    const value: Record<string, unknown> = { ...input };
    for (const key of [
      "canonical_project_v1", "manual_fields", "request_payload", "persist_trace_metadata", "meta",
      "prompt", "units", "image_width_px", "image_height_px", "pixels_per_unit", "plan_type_hint",
    ]) delete value[key];
    value.units = (input as Record<string, unknown>).units ?? input.manual_fields?.units;
    const meta: Record<string, unknown> = { ...input.meta };
    for (const key of [
      "generate_notes", "user_layout_context_summary", "requested_system",
      "calculation_omit_fields_v1", "auto_site_context_review_summary",
    ]) delete meta[key];
    return { ...value, meta };
  };
  return stableJson(sourceControls(before)) === stableJson(sourceControls(after))
    && semanticEditKey(before) === semanticEditKey(after)
    && stableJson(before.meta?.project_identity_v1) === stableJson(after.meta?.project_identity_v1)
    && stableJson((baseline as ProjectRecord & { tags?: string[] }).tags) === stableJson((latest as ProjectRecord & { tags?: string[] }).tags)
    && baseline.description === latest.description
    && stableJson(metadata(baseline)) === stableJson(metadata(latest));
}
