import { validateBriefClassifications } from "./briefClassification";
import { ADDITIONAL_BRIEF_FIELDS, type AdditionalBriefField } from "./briefRequirements";

export type EditableBriefField = "building-area" | "building-use" | "required-parking" | "setbacks" | AdditionalBriefField;
export const EDITABLE_BRIEF_FIELDS: readonly EditableBriefField[] = ["building-area", "building-use", "required-parking", "setbacks", ...Object.keys(ADDITIONAL_BRIEF_FIELDS) as AdditionalBriefField[]];
type Original = { value: string | number | null; classification?: unknown; source_record_key?: string };
export type BriefEditRecords = { version: 1; fields: Partial<Record<EditableBriefField, Original>> };
const record = (value: unknown): value is Record<string, unknown> => !!value && typeof value === "object" && !Array.isArray(value);
export function validateBriefEditRecords(value: unknown): BriefEditRecords {
  if (!record(value) || value.version !== 1 || !record(value.fields) || Object.keys(value).some(key => !["version", "fields"].includes(key))) throw new Error("Invalid brief originals.");
  for (const [id, original] of Object.entries(value.fields)) {
    if (!(EDITABLE_BRIEF_FIELDS as readonly string[]).includes(id) || !record(original) || Object.keys(original).some(key => !["value", "classification", "source_record_key"].includes(key)) || !(original.value === null || typeof original.value === "string" || typeof original.value === "number" && Number.isFinite(original.value))) throw new Error("Invalid brief original.");
    if (original.source_record_key !== undefined && (typeof original.source_record_key !== "string" || !original.source_record_key || original.source_record_key.length > 200000)) throw new Error("Invalid original source binding.");
    const definition = ADDITIONAL_BRIEF_FIELDS[id as AdditionalBriefField];
    if (typeof original.value === "string" && original.value.length > (definition?.kind === "text" ? 2000 : 200)) throw new Error("Invalid brief original.");
    if (original.classification !== undefined) validateBriefClassifications({ version: 1, fields: { [id]: original.classification } });
  }
  return JSON.parse(JSON.stringify(value)) as BriefEditRecords;
}
