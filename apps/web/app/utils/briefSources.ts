import { BRIEF_FIELD_IDS } from "./briefClassification";

export const BRIEF_SOURCE_TYPES = ["survey", "parcel", "gis", "aerial", "terrain", "contours", "zoning", "municipal_standard", "easement", "right_of_way", "wetland", "flood", "geotechnical", "traffic", "utility"] as const;
export type BriefSource = {
  id: string; name: string; type: typeof BRIEF_SOURCE_TYPES[number]; origin: string;
  jurisdiction: string; effective_date: string; imported_at: string; version: string;
  accepted: boolean; verification: "unverified" | "review_needed" | "verification_recorded";
  verified_by: string; verification_reference: string; superseded: boolean;
  rights: "unknown" | "permission_recorded" | "restricted"; rights_reference: string;
  object_ids: string[]; calculation_ids: string[]; requirement_ids: string[];
};
export type BriefSources = { version: 1; records: BriefSource[] };
const record = (value: unknown): value is Record<string, unknown> => !!value && typeof value === "object" && !Array.isArray(value);
const keys = ["id", "name", "type", "origin", "jurisdiction", "effective_date", "imported_at", "version", "accepted", "verification", "verified_by", "verification_reference", "superseded", "rights", "rights_reference", "object_ids", "calculation_ids", "requirement_ids"];
export function validateBriefSources(value: unknown): BriefSources {
  if (!record(value) || value.version !== 1 || Object.keys(value).sort().join() !== "records,version" || !Array.isArray(value.records) || value.records.length > 200) throw new Error("Invalid source register.");
  const ids = new Set<string>();
  for (const source of value.records) {
    if (!record(source) || Object.keys(source).length !== keys.length || keys.some(key => !(key in source))) throw new Error("Incomplete source record.");
    for (const key of keys.filter(key => !["accepted", "superseded", "object_ids", "calculation_ids", "requirement_ids"].includes(key))) {
      if (typeof source[key] !== "string" || (source[key] as string).length > 2000) throw new Error("Invalid source text.");
    }
    const id = source.id as string;
    if (!id.trim() || ids.has(id) || !(source.name as string).trim() || !(source.origin as string).trim() || !(BRIEF_SOURCE_TYPES as readonly unknown[]).includes(source.type) || typeof source.accepted !== "boolean" || typeof source.superseded !== "boolean" || !["unverified", "review_needed", "verification_recorded"].includes(source.verification as string) || !["unknown", "permission_recorded", "restricted"].includes(source.rights as string)) throw new Error("Invalid source status.");
    ids.add(id);
    if (!Number.isFinite(Date.parse(source.imported_at as string)) || source.effective_date !== "" && (!/^\d{4}-\d{2}-\d{2}$/.test(source.effective_date as string) || !Number.isFinite(Date.parse(source.effective_date as string)) || new Date(source.effective_date as string).toISOString().slice(0, 10) !== source.effective_date)) throw new Error("Invalid source date.");
    if (source.verification === "verification_recorded" && (!(source.verified_by as string).trim() || !(source.verification_reference as string).trim())) throw new Error("Record who verified this source and its evidence reference.");
    if (source.rights === "permission_recorded" && !(source.rights_reference as string).trim()) throw new Error("Record the source permission reference.");
    for (const key of ["object_ids", "calculation_ids", "requirement_ids"]) {
      const list = source[key];
      if (!Array.isArray(list) || list.length > 500 || list.some(item => typeof item !== "string" || !item.trim() || item.length > 200) || new Set(list).size !== list.length) throw new Error("Invalid source dependency references.");
    }
    if ((source.requirement_ids as string[]).some(id => !(BRIEF_FIELD_IDS as readonly string[]).includes(id))) throw new Error("Unknown source requirement.");
  }
  return JSON.parse(JSON.stringify(value)) as BriefSources;
}

/** Source records are evidence references, not extracted requirements or approvals. */
export function upsertBriefSource(stored: unknown, source: BriefSource): BriefSources {
  const current = stored === undefined ? { version: 1 as const, records: [] } : validateBriefSources(stored);
  return validateBriefSources({ version: 1, records: [...current.records.filter(item => item.id !== source.id), source] });
}
