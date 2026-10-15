import type { ManualFields, ProjectInput } from "../types";
import { validateBriefEditRecords } from "./briefEditRecords";
import { buildActiveBriefSummary } from "./activeBriefSummary";
import { classificationFor } from "./briefClassification";
import { resolveCanonicalCanvasInput } from "./canonicalCanvasProject";

/** Preserve explicit program targets, never geometry or parking quantities.
 * An edited brief target outranks a drawn object's older requested-area tag. */
export function preserveExplicitBriefProgram(fields: ManualFields, saved?: ProjectInput): ManualFields {
  if (saved) saved = resolveCanonicalCanvasInput(saved);
  // Terrain has no equivalent dimension control. Rebuilding the canvas payload
  // must not silently discard an entered source description.
  if (fields.terrain === undefined && saved?.manual_fields?.terrain !== undefined) {
    fields = { ...fields, terrain: saved.manual_fields.terrain };
  }
  const previous = saved?.manual_fields?.site_plan;
  const stored = saved?.meta?.site_inputs?.brief_edit_originals_v1;
  const edited = stored === undefined ? {} : validateBriefEditRecords(stored).fields;
  const protectedIds = new Set(saved ? buildActiveBriefSummary(saved).filter(row => ["building-area", "building-use"].includes(row.id) && ["sourced", "externally_verified"].includes(classificationFor(row, saved.meta?.site_inputs?.active_brief_classifications_v1).trust)).map(row => row.id) : []);
  if (!previous && !edited["building-area"] && !edited["building-use"]) return fields;
  const plan = {
    ...(previous?.building_program_sf !== undefined ? { building_program_sf: previous.building_program_sf } : {}),
    ...(previous?.building_type !== undefined ? { building_type: previous.building_type } : {}),
    ...fields.site_plan,
  };
  if (edited["building-area"] || protectedIds.has("building-area")) { if (previous?.building_program_sf === undefined) delete plan.building_program_sf; else plan.building_program_sf = previous.building_program_sf; }
  if (edited["building-use"] || protectedIds.has("building-use")) { if (previous?.building_type === undefined) delete plan.building_type; else plan.building_type = previous.building_type; }
  return { ...fields, site_plan: plan };
}
