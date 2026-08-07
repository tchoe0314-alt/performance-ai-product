const CANONICAL_PREVIEW_3D_LAYERS = new Set([
  "BUILDING",
  "STRUCTURE",
  "ROAD",
  "PARKING",
  "LOT",
  "SIDEWALK",
  "DRAINAGE",
  "UTILITY",
  "CONSTRAINT",
  "TERRAIN",
  "LANDSCAPE",
  "OBJECT",
]);

const cleanLayer = (value: unknown) => String(value || "").trim().toUpperCase();

export function normalizePreview3DLayer(layer: unknown, hints: unknown[] = []) {
  const explicit = cleanLayer(layer);
  const withoutCivilPrefix = explicit.startsWith("C-") ? explicit.slice(2) : explicit;
  if (CANONICAL_PREVIEW_3D_LAYERS.has(withoutCivilPrefix)) return withoutCivilPrefix;

  const key = [explicit, ...hints.map(cleanLayer)].filter(Boolean).join(" ");
  if (/\b[A-Z]\d{1,2}-\d{1,3}\b/.test(key) || /\bLOT\s*\d/.test(key) || /\bBLOCK\s*\d/.test(key)) return "LOT";
  if (key.includes("BUILDING") || key.includes("PAD")) return "BUILDING";
  if (key.includes("STRUCTURE")) return "STRUCTURE";
  if (key.includes("PARK")) return "PARKING";
  if (key.includes("LOT") || key.includes("BLOCK")) return "LOT";
  if (key.includes("SIDEWALK") || key.includes("WALK")) return "SIDEWALK";

  // An explicit utility layer wins over words such as "storm" in the label.
  // Without an explicit layer, storm pipes/mains are utilities while basins,
  // inlets, outfalls, and drainage areas remain drainage objects.
  if (
    key.includes("UTILITY") ||
    key.includes("WATER") ||
    key.includes("SANITARY") ||
    key.includes("HYDRANT") ||
    key.includes("MANHOLE") ||
    (/\bSTORM\b/.test(key) && /\b(MAIN|SEWER|PIPE|LINE|LATERAL|COLLECTOR|TRUNK|NETWORK)\b/.test(key))
  ) return "UTILITY";
  if (
    key.includes("DRAINAGE") ||
    key.includes("BASIN") ||
    key.includes("POND") ||
    key.includes("OUTFALL") ||
    key.includes("INLET") ||
    key.includes("CATCHMENT") ||
    key.includes("STORM") ||
    key.includes("DRAIN")
  ) return "DRAINAGE";
  if (key.includes("EASEMENT") || key.includes("CONSTRAINT") || key.includes("SETBACK")) return "CONSTRAINT";
  if (key.includes("LANDSCAPE") || key.includes("OPEN") || key.includes("GREEN")) return "LANDSCAPE";
  if (key.includes("TERRAIN") || key.includes("SITE")) return "TERRAIN";
  if (key.includes("ROAD") || key.includes("DRIVE")) return "ROAD";
  if (key.includes("OBJECT") || key.includes("CUSTOM") || key.includes("C-DRAFT") || key.includes("NOTE") || key.includes("TEXT")) return "OBJECT";
  return withoutCivilPrefix || "OBJECT";
}
