/** Additional brief requirements are recorded inputs, not automatic code checks. */
export const ADDITIONAL_BRIEF_FIELDS = {
  "usable-acreage": { unit: "ac", kind: "number" },
  storeys: { unit: "storeys", kind: "integer" },
  "parking-ratio": { unit: "spaces/ksf", kind: "number" },
  "drive-aisles": { unit: "text", kind: "text" },
  access: { unit: "text", kind: "text" },
  egress: { unit: "text", kind: "text" },
  height: { unit: "ft", kind: "number" },
  "lot-coverage": { unit: "%", kind: "percentage" },
  impervious: { unit: "%", kind: "percentage" },
  "open-space": { unit: "%", kind: "percentage" },
  stormwater: { unit: "text", kind: "text" },
  priorities: { unit: "text", kind: "text" },
} as const;
export type AdditionalBriefField = keyof typeof ADDITIONAL_BRIEF_FIELDS;
export type AdditionalBriefRequirements = { version: 1; fields: Partial<Record<AdditionalBriefField, { value: string | number | null; unit: string }>> };
export function validateAdditionalBriefRequirements(value: unknown): AdditionalBriefRequirements {
  const record = (item: unknown): item is Record<string, unknown> => !!item && typeof item === "object" && !Array.isArray(item);
  if (!record(value) || value.version !== 1 || Object.keys(value).sort().join() !== "fields,version" || !record(value.fields)) throw new Error("Invalid additional brief requirements.");
  for (const [id, entry] of Object.entries(value.fields)) {
    if (!Object.hasOwn(ADDITIONAL_BRIEF_FIELDS, id) || !record(entry) || Object.keys(entry).sort().join() !== "unit,value") throw new Error("Invalid brief requirement.");
    const definition = ADDITIONAL_BRIEF_FIELDS[id as AdditionalBriefField];
    if (entry.unit !== definition.unit) throw new Error("Invalid requirement units.");
    if (entry.value === null) continue;
    if (definition.kind === "text") { if (typeof entry.value !== "string" || !entry.value.trim() || entry.value.length > 2000) throw new Error("Keep requirement notes between 1 and 2000 characters."); }
    else if (typeof entry.value !== "number" || !Number.isFinite(entry.value) || entry.value < 0 || definition.kind === "integer" && !Number.isSafeInteger(entry.value) || definition.kind === "percentage" && entry.value > 100) throw new Error("Enter a valid nonnegative requirement; percentages cannot exceed 100.");
  }
  return JSON.parse(JSON.stringify(value)) as AdditionalBriefRequirements;
}
