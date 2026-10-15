import type { ProjectInput } from "../types";
import { buildActiveBriefSummary } from "./activeBriefSummary";
import { classificationFor } from "./briefClassification";
import { withCanonicalCanvasSnapshot } from "./canonicalCanvasProject";
import { EDITABLE_BRIEF_FIELDS, validateBriefEditRecords, type EditableBriefField } from "./briefEditRecords";
import { validateBriefSources } from "./briefSources";
import { ADDITIONAL_BRIEF_FIELDS, validateAdditionalBriefRequirements, type AdditionalBriefField } from "./briefRequirements";
export { EDITABLE_BRIEF_FIELDS, validateBriefEditRecords } from "./briefEditRecords";
export type { EditableBriefField } from "./briefEditRecords";
export type BriefEditOptions = { override?: boolean; reset?: boolean; expectedValueKey?: string; expectedProtectionKey?: string; sourceId?: string; unit?: "sf" | "m2" | "ft" | "m" | "spaces" | "text" | "ac" | "storeys" | "spaces/ksf" | "%" };
export function briefInputUnits(input: ProjectInput, id: EditableBriefField): NonNullable<BriefEditOptions["unit"]>[] {
  if (id === "building-area") return ["sf", "m2"];
  if (id === "setbacks") return input.manual_fields?.units === "m" ? ["m", "ft"] : ["ft", "m"];
  if (id === "required-parking") return ["spaces"];
  if (id === "building-use") return ["text"];
  if (id === "height") return ["ft", "m"];
  if (id === "usable-acreage") return ["ac", "sf", "m2"];
  return [ADDITIONAL_BRIEF_FIELDS[id].unit];
}
export function briefProtectionKey(input: ProjectInput, id: EditableBriefField): string {
  const row = buildActiveBriefSummary(input).find(item => item.id === id)!;
  const classification = classificationFor(row, input.meta?.site_inputs?.active_brief_classifications_v1);
  const sources = input.meta?.site_inputs?.brief_sources_v1 === undefined ? [] : validateBriefSources(input.meta.site_inputs.brief_sources_v1).records;
  return JSON.stringify([row.valueKey, classification, sources.find(source => source.id === classification.source_reference) ?? null]);
}
export function briefRawValue(input: ProjectInput, id: EditableBriefField): string | number | null {
  if (Object.hasOwn(ADDITIONAL_BRIEF_FIELDS, id)) {
    const stored = input.meta?.site_inputs?.brief_requirements_v1;
    return stored === undefined ? null : validateAdditionalBriefRequirements(stored).fields[id as AdditionalBriefField]?.value ?? null;
  }
  const fields = input.manual_fields;
  const controls = input.meta?.edit_controls_v1 as Record<string, unknown> | undefined;
  const raw = id === "building-area" ? fields?.site_plan?.building_program_sf : id === "building-use" ? fields?.site_plan?.building_type : id === "setbacks" ? fields?.setback : controls?.parkingCount ?? fields?.site_plan?.parking_count;
  return typeof raw === "string" || typeof raw === "number" ? raw : null;
}
export function editBriefValue(input: ProjectInput, id: EditableBriefField, text: string, options: BriefEditOptions = {}): ProjectInput {
  if (!(EDITABLE_BRIEF_FIELDS as readonly string[]).includes(id)) throw new Error("This requirement is not directly editable.");
  const row = buildActiveBriefSummary(input).find(item => item.id === id)!;
  if (options.expectedValueKey !== undefined && options.expectedValueKey !== row.valueKey) throw new Error("This requirement changed. Reopen its editor.");
  if (options.expectedProtectionKey !== undefined && options.expectedProtectionKey !== briefProtectionKey(input, id)) throw new Error("This requirement's source or protection changed. Reopen its editor.");
  const sites = input.meta?.site_inputs ?? {};
  const classification = classificationFor(row, sites.active_brief_classifications_v1);
  const stored = sites.brief_edit_originals_v1;
  const originals = stored === undefined ? { version: 1 as const, fields: {} } : validateBriefEditRecords(stored);
  const original = originals.fields[id];
  const definition = Object.hasOwn(ADDITIONAL_BRIEF_FIELDS, id) ? ADDITIONAL_BRIEF_FIELDS[id as AdditionalBriefField] : undefined;
  const isText = id === "building-use" || definition?.kind === "text";
  if (options.reset && !original) throw new Error("No original value is recorded.");
  if (!options.reset && ["sourced", "externally_verified"].includes(classification.trust) && !options.override) throw new Error("Choose Override before changing a sourced requirement.");
  let value: string | number | null = options.reset ? original!.value : text.trim() || null;
  if (value === "") value = null;
  if (value !== null && !isText) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric) || numeric < 0 || id === "building-area" && numeric === 0 || (id === "required-parking" || definition?.kind === "integer") && !Number.isSafeInteger(numeric) || definition?.kind === "percentage" && numeric > 100) throw new Error("Enter a valid nonnegative value; counts must be whole numbers and percentages at most 100.");
    value = numeric;
  }
  if (typeof value === "string" && value.length > (id === "building-use" ? 200 : 2000)) throw new Error("Requirement text is too long.");
  if (id === "setbacks" && !["ft", "m"].includes(input.manual_fields?.units ?? "")) throw new Error("Set project units before editing setbacks.");
  if (!options.reset && options.unit !== undefined) {
    const allowed = briefInputUnits(input, id);
    if (!allowed.includes(options.unit)) throw new Error("These units do not match this requirement.");
    if (typeof value === "number") {
      if (id === "building-area" && options.unit === "m2") value /= 0.3048 ** 2;
      if (id === "setbacks" && options.unit !== input.manual_fields?.units) value *= options.unit === "ft" ? 0.3048 : 1 / 0.3048;
      if (id === "height" && options.unit === "m") value /= 0.3048;
      if (id === "usable-acreage" && options.unit !== "ac") value /= options.unit === "sf" ? 43560 : 4046.8564224;
      if (!Number.isFinite(value)) throw new Error("Converted value is out of range.");
    }
  }
  const currentRaw = briefRawValue(input, id);
  const currentValue = isText ? currentRaw : currentRaw === null || currentRaw === "" ? null : Number(currentRaw);
  if (!options.reset && !options.sourceId && value === currentValue) return input;
  const next = JSON.parse(JSON.stringify(input)) as ProjectInput;
  next.manual_fields ??= {};
  next.manual_fields.site_plan ??= {};
  next.meta ??= {};
  next.meta.site_inputs ??= {};
  const key = id === "building-area" ? "building_program_sf" : id === "building-use" ? "building_type" : "parking_count";
  if (definition) {
    const stored = sites.brief_requirements_v1;
    const requirements = stored === undefined ? { version: 1 as const, fields: {} } : validateAdditionalBriefRequirements(stored);
    next.meta.site_inputs.brief_requirements_v1 = validateAdditionalBriefRequirements({ version: 1, fields: { ...requirements.fields, [id]: { value, unit: definition.unit } } });
  }
  else if (id === "setbacks") { if (value === null) delete next.manual_fields.setback; else next.manual_fields.setback = value as number; }
  else if (value === null) delete next.manual_fields.site_plan[key];
  else Object.assign(next.manual_fields.site_plan, { [key]: value });
  if (id === "required-parking") next.meta.edit_controls_v1 = { ...(next.meta.edit_controls_v1 as Record<string, unknown> | undefined), parkingCount: value === null ? "" : String(value) };
  const existingClassifications = sites.active_brief_classifications_v1 as { version: 1; fields: Record<string, unknown> } | undefined;
  const fields = { ...existingClassifications?.fields };
  const sources = sites.brief_sources_v1 === undefined ? [] : validateBriefSources(sites.brief_sources_v1).records;
  const originalClassification = original?.classification as { source_reference?: string } | undefined;
  const originalSource = sources.find(source => source.id === originalClassification?.source_reference);
  if (options.reset && original!.classification !== undefined && !(originalSource && (!originalSource.accepted || originalSource.superseded || original!.source_record_key !== JSON.stringify(originalSource)))) fields[id] = original!.classification;
  else delete fields[id]; // A source confirmation never transfers to a changed value.
  if (options.sourceId && !options.reset) {
    const source = sources.find(item => item.id === options.sourceId);
    if (!source || !source.accepted || source.superseded) throw new Error("Choose an accepted, current source.");
    const editedRow = buildActiveBriefSummary(next).find(item => item.id === id)!;
    if (!editedRow.known) throw new Error("Enter a value before attaching a source.");
    fields[id] = { priority: classification.priority, trust: "sourced", value_key: editedRow.valueKey, source_reference: source.id };
    next.meta.site_inputs.brief_sources_v1 = { version: 1, records: sources.map(item => item.id === source.id ? { ...item, requirement_ids: [...new Set([...item.requirement_ids, id])] } : item) };
  }
  next.meta.site_inputs.active_brief_classifications_v1 = { version: 1, fields };
  const savedOriginal = options.sourceId && !original ? { value, classification: fields[id], source_record_key: JSON.stringify(validateBriefSources(next.meta.site_inputs.brief_sources_v1).records.find(source => source.id === options.sourceId)) } : original ?? { value: briefRawValue(input, id), ...(existingClassifications?.fields[id] !== undefined ? { classification: existingClassifications.fields[id] } : {}) };
  next.meta.site_inputs.brief_edit_originals_v1 = { version: 1, fields: { ...originals.fields, [id]: savedOriginal } };
  return withCanonicalCanvasSnapshot(next);
}
