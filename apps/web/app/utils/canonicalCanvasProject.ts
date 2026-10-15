import type { ProjectInput } from "../types";
import type { BuildingPlacement } from "../types";
import { validateBriefClassifications } from "./briefClassification";
import { validateBriefEditRecords } from "./briefEditRecords";
import { validateBriefSources } from "./briefSources";
import { validateAdditionalBriefRequirements } from "./briefRequirements";
import { dependencyRecords, validateDependencyGraph } from "./dependencyGraph";
import { objectDefinition, placementFromDefinition, validateObjectGroups, validateCustomTypeDefinition, type ObjectDefinition } from "./siteObjectDefinition";

export const CANONICAL_PROJECT_VERSION = "civora_project_v1";
export function hasCanonicalCanvasSnapshot(input: ProjectInput): boolean {
  const doc = input.canonical_project_v1;
  return record(doc) && record(doc.extensions) && doc.extensions.canvas_workspace_v1 !== undefined;
}
const mappings = ["project", "client", "site", "units", "coordinate_system", "parcel_geometry", "extensions"] as const;
const collections = [
  "buildings", "roads", "access_points", "cul_de_sacs", "parking", "sidewalks", "setbacks", "easements",
  "landscape_areas", "stormwater_features", "grading_concepts", "utilities", "annotations", "constraints",
  "dependencies", "sources", "assumptions", "calculation_results", "quantities", "alternatives", "revisions", "export_history",
] as const;
type RecordValue = Record<string, unknown>;
export type CanonicalProjectDocument = Record<string, unknown> & { schema_version: typeof CANONICAL_PROJECT_VERSION };
const record = (value: unknown): value is RecordValue => !!value && typeof value === "object" && !Array.isArray(value);
const clone = <T>(value: T): T => JSON.parse(JSON.stringify(value, (_key, item) => {
  if (typeof item === "number" && !Number.isFinite(item)) throw new Error("Saved project contains non-finite numbers.");
  return item;
})) as T;

function checkJson(value: unknown): void {
  if (value === null || typeof value === "string" || typeof value === "boolean") return;
  if (typeof value === "number" && Number.isFinite(value)) return;
  if (Array.isArray(value)) { value.forEach(checkJson); return; }
  if (record(value) && Object.getPrototypeOf(value) === Object.prototype) { Object.values(value).forEach(checkJson); return; }
  throw new Error("Saved project contains unsupported data.");
}

export function validateCanonicalProject(value: unknown): CanonicalProjectDocument {
  if (!record(value) || value.schema_version !== CANONICAL_PROJECT_VERSION) throw new Error("Unsupported saved project version.");
  const expected = ["schema_version", ...mappings, ...collections];
  if (Object.keys(value).length !== expected.length || expected.some(key => !(key in value))) throw new Error("Saved project sections are incomplete.");
  if (mappings.some(key => !record(value[key])) || collections.some(key => !Array.isArray(value[key]) || !(value[key] as unknown[]).every(record))) {
    throw new Error("Saved project sections are invalid.");
  }
  checkJson(value);
  const storedBrief = (value.site as RecordValue).site_inputs_v1 as RecordValue | undefined;
  if (storedBrief?.active_brief_classifications_v1 !== undefined) validateBriefClassifications(storedBrief.active_brief_classifications_v1);
  if (storedBrief?.brief_edit_originals_v1 !== undefined) validateBriefEditRecords(storedBrief.brief_edit_originals_v1);
  if (storedBrief?.brief_sources_v1 !== undefined) validateBriefSources(storedBrief.brief_sources_v1);
  if (storedBrief?.brief_requirements_v1 !== undefined) validateAdditionalBriefRequirements(storedBrief.brief_requirements_v1);
  const library = (value.extensions as RecordValue).object_type_library_v1;
  if (library !== undefined) {
    if (!record(library)) throw new Error("Saved object type library is invalid.");
    Object.entries(library).forEach(([id,type])=>{if(validateCustomTypeDefinition(type).id!==id) throw new Error("Saved object type reference is invalid.");});
  }
  return clone(value) as CanonicalProjectDocument;
}

function emptyDocument(): CanonicalProjectDocument {
  return {
    schema_version: CANONICAL_PROJECT_VERSION,
    ...Object.fromEntries(mappings.map(key => [key, {}])),
    ...Object.fromEntries(collections.map(key => [key, []])),
    units: { length: null, area: null, volume: null },
    coordinate_system: { horizontal_crs: null, vertical_datum: null, origin: null },
  };
}

const groups: Record<string, string> = {
  building: "buildings", retail_building: "buildings", multifamily_building: "buildings",
  industrial_building: "buildings", office_building: "buildings", pad: "buildings",
  road: "roads", driveway: "roads", entrance: "access_points", parking: "parking", sidewalk: "sidewalks",
  setback_zone: "setbacks", landscape: "landscape_areas", open_space: "landscape_areas",
  basin: "stormwater_features", inlet: "stormwater_features", outfall: "stormwater_features",
  utility_corridor: "utilities", hydrant: "utilities", manhole: "utilities",
};
const owned = (value: unknown): value is RecordValue => record(value) && record(value.canvas_placement_v1);
function bucket(doc: CanonicalProjectDocument, section: string): RecordValue[] {
  if (section === "parcel_geometry") return (doc.parcel_geometry as RecordValue).canvas_placements_v1 as RecordValue[];
  if (section === "other") return (doc.extensions as RecordValue).canvas_other_placements_v1 as RecordValue[];
  return doc[section] as RecordValue[];
}

/** Compile at the existing serialized save boundary, not into a second React store. */
export function withCanonicalCanvasSnapshot(input: ProjectInput, previous?: unknown): ProjectInput {
  if (input.meta?.site_inputs?.active_brief_classifications_v1 !== undefined) validateBriefClassifications(input.meta.site_inputs.active_brief_classifications_v1);
  if (input.meta?.site_inputs?.brief_edit_originals_v1 !== undefined) validateBriefEditRecords(input.meta.site_inputs.brief_edit_originals_v1);
  if (input.meta?.site_inputs?.brief_sources_v1 !== undefined) validateBriefSources(input.meta.site_inputs.brief_sources_v1);
  if (input.meta?.site_inputs?.brief_requirements_v1 !== undefined) validateAdditionalBriefRequirements(input.meta.site_inputs.brief_requirements_v1);
  const base = previous ?? input.canonical_project_v1;
  const doc = base === undefined ? emptyDocument() : validateCanonicalProject(base);
  const clean = clone({ ...input, canonical_project_v1: undefined }) as ProjectInput;
  delete clean.canonical_project_v1;
  const model = (doc.extensions as RecordValue).project_record_v1;
  if (record(model)) {
    const meta = { ...(clean.meta ?? {}) };
    const siteInputs = meta.site_inputs ?? {};
    delete meta.site_inputs;
    model.input_controls = Object.fromEntries(Object.entries(clean).filter(([key]) => key !== "manual_fields" && key !== "meta"));
    model.input_meta = meta;
    (doc.site as RecordValue).site_inputs_v1 = siteInputs;
    if (!(doc.extensions as RecordValue).canvas_workspace_v1) {
      model.legacy_manual_fields = clean.manual_fields ?? {};
      if (clean.manual_fields && "units" in clean.manual_fields) (doc.units as RecordValue).length = clean.manual_fields.units;
    }
  }
  const objects = clean.manual_fields?.site_objects;
  // Legacy building-program-only inputs stay legacy until actual canvas objects exist.
  if (!Array.isArray(objects)) return record(model) ? { ...clean, canonical_project_v1: validateCanonicalProject(doc) } : input;
  validateObjectGroups(objects as BuildingPlacement[]);
  const graph=dependencyRecords(objects as BuildingPlacement[]);
  doc.dependencies=[...(doc.dependencies as RecordValue[]).filter(item=>item.owner!=="dependency_graph_v1"),...graph];
  const previousObjects = new Map<string, ObjectDefinition>();
  [...collections, "parcel_geometry", "other"].forEach(section => {
    (bucket(doc, section) ?? []).forEach(wrapper => {
      if (owned(wrapper) && record(wrapper.object_v1)) previousObjects.set(String((wrapper.canvas_placement_v1 as RecordValue).id), wrapper.object_v1 as ObjectDefinition);
    });
  });
  collections.forEach(key => { doc[key] = (doc[key] as RecordValue[]).filter(item => !owned(item)); });
  const parcel = doc.parcel_geometry as RecordValue;
  parcel.canvas_placements_v1 = [];
  const extensions = doc.extensions as RecordValue;
  const library = record(extensions.object_type_library_v1) ? extensions.object_type_library_v1 : {};
  objects.forEach(object => {
    const custom = object.meta?.custom_type_definition_v1;
    if (custom != null) { const definition=validateCustomTypeDefinition(custom); library[definition.id] = clone(definition); }
  });
  extensions.object_type_library_v1 = library;
  extensions.canvas_other_placements_v1 = [];
  const order: Array<{ section: string; index: number }> = [];
  objects.forEach(object => {
    const meta = record(object.meta) ? object.meta : {};
    const section = object.type === "site" ? "parcel_geometry"
      : record(meta.cul_de_sac_v1) ? "cul_de_sacs" : Object.hasOwn(groups,object.type ?? "") ? groups[object.type!] : "other";
    const target = bucket(doc, section);
    order.push({ section, index: target.length });
    target.push({ canvas_placement_v1: object, object_v1: objectDefinition(object as BuildingPlacement, clean.manual_fields?.units ?? null, previousObjects.get(object.id ?? "")) });
  });
  delete clean.manual_fields!.site_objects;
  extensions.canvas_workspace_v1 = { version: 1, manual_fields: clean.manual_fields, object_order: order };
  doc.project = { ...(doc.project as RecordValue), name: clean.manual_fields?.project_name ?? "" };
  doc.units = { ...(doc.units as RecordValue), length: clean.manual_fields?.units ?? null };
  return { ...clone({ ...input, canonical_project_v1: undefined }), canonical_project_v1: validateCanonicalProject(doc) };
}

/** Canonical canvas snapshots win over conflicting legacy shadows on reopen. */
export function resolveCanonicalCanvasInput(input: ProjectInput): ProjectInput {
  if (input.canonical_project_v1 === undefined) return input;
  const doc = validateCanonicalProject(input.canonical_project_v1);
  const model = (doc.extensions as RecordValue).project_record_v1;
  if (record(model)) {
    if (model.version !== 1 || !record(model.input_controls) || !record(model.input_meta)) throw new Error("Saved project model adapter is invalid.");
    input = { ...clone(model.input_controls), canonical_project_v1: doc,
      meta: { ...clone(model.input_meta), site_inputs: clone((doc.site as RecordValue).site_inputs_v1 ?? {}) },
      manual_fields: record(model.legacy_manual_fields) ? clone(model.legacy_manual_fields) : input.manual_fields,
    } as ProjectInput;
    if (record(model.legacy_manual_fields) && ("units" in model.legacy_manual_fields || (doc.units as RecordValue).length != null)) {
      input = { ...input, manual_fields: { ...input.manual_fields, units: (doc.units as RecordValue).length } } as ProjectInput;
    }
  }
  const workspace = (doc.extensions as RecordValue).canvas_workspace_v1;
  // Foundation-only documents have not adopted this adapter; keep their legacy UI.
  if (workspace === undefined) return input;
  if (!record(workspace) || workspace.version !== 1 || !record(workspace.manual_fields) || !Array.isArray(workspace.object_order)) {
    throw new Error("Saved canvas adapter is invalid.");
  }
  const allowed = new Set<string>([...collections, "parcel_geometry", "other"]);
  const seen = new Set<string>();
  const objects = workspace.object_order.map(reference => {
    if (!record(reference) || typeof reference.section !== "string" || !allowed.has(reference.section) || !Number.isInteger(reference.index) || Number(reference.index) < 0) {
      throw new Error("Saved canvas object reference is invalid.");
    }
    const key = `${reference.section}:${reference.index}`;
    const target = bucket(doc, reference.section);
    const item = Array.isArray(target) ? target[Number(reference.index)] : undefined;
    if (seen.has(key) || !owned(item)) throw new Error("Saved canvas object reference is missing or duplicated.");
    seen.add(key);
    return "object_v1" in item ? placementFromDefinition(item.canvas_placement_v1 as BuildingPlacement, item.object_v1) : clone(item.canvas_placement_v1);
  });
  let total = 0;
  allowed.forEach(section => {
    const items = bucket(doc, section);
    if (Array.isArray(items)) total += items.filter(owned).length;
  });
  if (total !== objects.length) throw new Error("Saved canvas object references are incomplete.");
  validateObjectGroups(objects as BuildingPlacement[]);
  validateDependencyGraph(objects as BuildingPlacement[]);
  const fields = clone(workspace.manual_fields);
  const lengthUnit = (doc.units as RecordValue).length;
  if (lengthUnit != null && typeof lengthUnit !== "string") throw new Error("Saved project length units are invalid.");
  if (typeof lengthUnit === "string" && lengthUnit.trim()) fields.units = lengthUnit;
  else delete fields.units;
  return { ...input, canonical_project_v1: doc, manual_fields: {
    ...fields,
    site_objects: objects as NonNullable<ProjectInput["manual_fields"]>["site_objects"],
  } };
}
