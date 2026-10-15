import type { BriefSummaryRow } from "./activeBriefSummary";

export const BRIEF_CLASSIFICATION_KEY = "active_brief_classifications_v1";
export const BRIEF_FIELD_IDS = ["gross-acreage", "usable-acreage", "building-area", "storeys", "building-use", "parking-ratio", "required-parking", "drive-aisles", "access", "egress", "setbacks", "height", "lot-coverage", "impervious", "open-space", "stormwater", "protected", "priorities"] as const;
export const REQUIREMENT_CLASSES = ["required", "preferred", "assumed", "unknown"] as const;
export const TRUST_STATUSES = ["user_entered", "user_confirmed", "sourced", "calculated", "externally_verified", "unverified"] as const;
export type RequirementClass = typeof REQUIREMENT_CLASSES[number];
export type BriefTrust = typeof TRUST_STATUSES[number];
export type BriefClassification = { priority: RequirementClass; trust: BriefTrust; value_key: string; source_reference?: string };
export type BriefClassifications = { version: 1; fields: Record<string, BriefClassification> };
const record = (value: unknown): value is Record<string, unknown> => !!value && typeof value === "object" && !Array.isArray(value);

export function validateBriefClassifications(value: unknown): BriefClassifications {
  if (!record(value) || value.version !== 1 || Object.keys(value).sort().join() !== "fields,version" || !record(value.fields)) throw new Error("Invalid brief classifications.");
  for (const [id, entry] of Object.entries(value.fields)) {
    if (!(BRIEF_FIELD_IDS as readonly string[]).includes(id) || !record(entry) || Object.keys(entry).some(key => !["priority", "trust", "value_key", "source_reference"].includes(key)) || !(REQUIREMENT_CLASSES as readonly unknown[]).includes(entry.priority) || !(TRUST_STATUSES as readonly unknown[]).includes(entry.trust) || typeof entry.value_key !== "string" || !entry.value_key || entry.value_key.length > 200000 || (entry.source_reference !== undefined && (typeof entry.source_reference !== "string" || !entry.source_reference.trim() || entry.source_reference.length > 2000)) || (["sourced", "externally_verified"].includes(String(entry.trust)) && !entry.source_reference)) throw new Error("Invalid brief classification entry.");
  }
  return JSON.parse(JSON.stringify(value)) as BriefClassifications;
}

export function classificationFor(row: BriefSummaryRow, stored: unknown): BriefClassification & { needsReview: boolean } {
  const entries = stored === undefined ? { version: 1 as const, fields: {} as Record<string, BriefClassification> } : validateBriefClassifications(stored);
  const saved = entries.fields[row.id];
  let sameParkingValue = false;
  if (row.id === "required-parking" && saved && row.valueKey) {
    try {
      const before = JSON.parse(saved.value_key), after = JSON.parse(row.valueKey);
      const labels = ["Entered parking target; unverified", "Stored parking count; requirement unconfirmed"];
      sameParkingValue = Array.isArray(before) && Array.isArray(after) && before.length === 4 && after.length === 4 && labels.includes(before[3]) && labels.includes(after[3]) && JSON.stringify(before.slice(0, 3)) === JSON.stringify(after.slice(0, 3));
    } catch { /* Malformed legacy keys remain unverified. */ }
  }
  // Loading saved controls changes presentation wording, not the requirement.
  // Only these two known parking labels may differ; values/identity must match.
  const current = row.known && (saved?.value_key === row.valueKey || sameParkingValue);
  return current ? { ...saved, needsReview: false } : {
    priority: "unknown", trust: row.known && row.id === "gross-acreage" ? "calculated" : "unverified",
    value_key: row.valueKey ?? "", needsReview: !!saved,
  };
}

export function changeBriefClassification(row: BriefSummaryRow, stored: unknown, priority: RequirementClass, confirm = false, override = false): BriefClassifications {
  if (!row.known || !(REQUIREMENT_CLASSES as readonly string[]).includes(priority) || (confirm && priority === "unknown")) throw new Error("Enter a value and choose its requirement before confirming.");
  const existing = stored === undefined ? { version: 1 as const, fields: {} } : validateBriefClassifications(stored);
  const current = classificationFor(row, stored);
  const protectedChange = ["sourced", "externally_verified"].includes(current.trust) && current.priority !== "unknown" && priority !== current.priority;
  if (protectedChange && !override) throw new Error("Choose Override before changing a sourced requirement's priority.");
  return validateBriefClassifications({ version: 1, fields: { ...existing.fields, [row.id]: {
    priority, trust: confirm ? "user_confirmed" : protectedChange ? "unverified" : current.trust,
    value_key: row.valueKey,
    ...(current.source_reference ? { source_reference: current.source_reference } : {}),
  } } });
}
