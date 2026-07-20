import type { AiRealismArtifact } from "../components/previewPanelTypes";
import type { BuildingPlacement } from "../types";
import { stableHash } from "./previewGeometryTruth";

export type AiRealismSourceObject = {
  id: string;
  label: string;
  type: string;
  x: number;
  y: number;
  w: number;
  d: number;
  h: number;
  rotation: number;
  geometryType: string;
  geometry?: Array<[number, number]>;
  source: string;
  confidence: number | null;
};

export function buildAiRealismSourceObjects(items: BuildingPlacement[]) {
  return items
    .filter(
      (item) =>
        item.type !== "site" &&
        item.placed &&
        Number.isFinite(item.x) &&
        Number.isFinite(item.y),
    )
    .map((item) => ({
      id: item.id,
      label: item.label || item.type || item.id,
      type: item.type || "custom",
      x: Number(item.x ?? 0),
      y: Number(item.y ?? 0),
      w: Number(item.w ?? 0),
      d: Number(item.d ?? 0),
      h: Number(item.h ?? 0),
      rotation: Number(item.rotation ?? 0),
      geometryType: item.geometryType || "rect",
      geometry: Array.isArray(item.geometry) ? item.geometry : undefined,
      source: item.source || (item.generated ? "generated" : "user"),
      confidence: typeof item.confidence === "number" ? item.confidence : null,
    }))
    .sort((a, b) => a.id.localeCompare(b.id));
}

export function buildAiRealismLayoutHash({
  lotWidth,
  lotHeight,
  siteRotationDeg,
  hasTerrainSource,
  sourceObjects,
}: {
  lotWidth: string | number;
  lotHeight: string | number;
  siteRotationDeg?: number | null;
  hasTerrainSource: boolean;
  sourceObjects: AiRealismSourceObject[];
}) {
  return stableHash(
    JSON.stringify({
      site: {
        lotWidth,
        lotHeight,
        siteRotationDeg: siteRotationDeg ?? 0,
        terrain: hasTerrainSource ? "terrain-source" : "terrain-missing",
      },
      objects: sourceObjects,
    }),
  );
}

export function summarizeAiRealismSourceObjects(sourceObjects: AiRealismSourceObject[]) {
  const counts: Record<string, number> = {};
  sourceObjects.forEach((item) => {
    counts[item.type] = (counts[item.type] ?? 0) + 1;
  });
  return {
    total: sourceObjects.length,
    objects_included: sourceObjects.map((item) => `${item.label} (${item.type})`),
    counts_by_type: counts,
  };
}

export function aiRealismMissingInputs({
  sourceObjects,
  hasTerrainSource,
  geocode,
}: {
  sourceObjects: AiRealismSourceObject[];
  hasTerrainSource: boolean;
  geocode?: { lat?: number; lng?: number } | null;
}) {
  const missing: string[] = [];
  if (!hasTerrainSource) missing.push("terrain/source confidence");
  if (!geocode?.lat || !geocode?.lng) missing.push("source-backed map/geocode context");
  if (!sourceObjects.some((item) => item.type === "road" || item.type === "driveway")) {
    missing.push("roads/driveways");
  }
  if (!sourceObjects.some((item) => item.type === "utility_corridor" || item.type === "hydrant" || item.type === "manhole" || item.type === "inlet" || item.type === "outfall")) {
    missing.push("visible storm/sanitary/water utility context");
  }
  return missing;
}

export function createAiRealismArtifact({
  currentProjectId,
  planPreviewProjectId,
  sourceLayoutHash,
  sourceObjects,
  sourceSummary,
  missingInputs,
  hasTerrainSource,
  watermark,
}: {
  currentProjectId?: string | null;
  planPreviewProjectId?: string | null;
  sourceLayoutHash: string;
  sourceObjects: AiRealismSourceObject[];
  sourceSummary: AiRealismArtifact["source_objects_summary"];
  missingInputs: string[];
  hasTerrainSource: boolean;
  watermark: string;
}): AiRealismArtifact {
  const generated_timestamp = new Date().toISOString();
  const project_id = currentProjectId || planPreviewProjectId || "unsaved-review-layout";
  const counts = sourceSummary.counts_by_type;
  const promptSummary = [
    `${sourceObjects.length} review layout objects`,
    counts.building || counts.multifamily_building || counts.retail_building ? "building massing" : "",
    counts.parking ? "parking fields" : "",
    counts.road || counts.driveway ? "roads and driveways" : "",
    counts.basin ? "detention basin" : "",
    hasTerrainSource ? "terrain source present" : "terrain source missing",
  ]
    .filter(Boolean)
    .join(", ");
  const image_data_url = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 760" role="img" aria-label="Mock AI realism visualization from current review layout"><defs><linearGradient id="sky" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#dbeafe"/><stop offset="0.48" stop-color="#f8fafc"/><stop offset="1" stop-color="#b7d6b4"/></linearGradient><filter id="soft"><feGaussianBlur stdDeviation="0.45"/></filter></defs><rect width="1200" height="760" fill="url(#sky)"/><path d="M0 470 C220 390 390 480 610 410 C820 342 1010 412 1200 346 L1200 760 L0 760 Z" fill="#8bb17f"/><path d="M40 610 C230 520 390 576 578 502 C804 412 968 506 1180 418" fill="none" stroke="#4b5563" stroke-width="58" stroke-linecap="round"/><path d="M40 610 C230 520 390 576 578 502 C804 412 968 506 1180 418" fill="none" stroke="#e5e7eb" stroke-width="4" stroke-dasharray="24 18" opacity="0.85"/><rect x="195" y="214" width="176" height="82" rx="6" fill="#c7b897" stroke="#76664d" stroke-width="4" transform="skewY(-8)"/><rect x="535" y="188" width="176" height="82" rx="6" fill="#c7b897" stroke="#76664d" stroke-width="4" transform="skewY(-6)"/><rect x="188" y="540" width="128" height="68" rx="6" fill="#c7b897" stroke="#76664d" stroke-width="4" transform="skewY(-7)"/><rect x="410" y="352" width="310" height="128" rx="10" fill="#9ca3af" opacity="0.56"/><g stroke="#f8fafc" stroke-width="3" opacity="0.85">${Array.from({ length: 9 }).map((_, index) => `<line x1="${430 + index * 30}" y1="360" x2="${452 + index * 30}" y2="472"/>`).join("")}</g><ellipse cx="935" cy="598" rx="145" ry="68" fill="#7dd3fc" opacity="0.72" stroke="#0284c7" stroke-width="4"/><path d="M220 404 C350 378 508 392 635 360" fill="none" stroke="#f8fafc" stroke-width="18" opacity="0.82"/><text x="54" y="72" fill="#0f172a" font-family="Arial, sans-serif" font-size="26" font-weight="700">High Quality AI Realism Preview</text><text x="54" y="108" fill="#334155" font-family="Arial, sans-serif" font-size="18">${promptSummary}</text><rect x="48" y="676" width="1104" height="44" rx="8" fill="rgba(15,23,42,0.78)"/><text x="70" y="704" fill="#fff" font-family="Arial, sans-serif" font-size="18">${watermark}</text></svg>`,
  )}`;
  return {
    type: "high_quality_ai_render_v1",
    project_id,
    source_layout_hash: sourceLayoutHash,
    source_objects_summary: sourceSummary,
    missing_inputs: missingInputs,
    stale: false,
    generated_timestamp,
    review_only: true,
    not_site_evidence: true,
    construction_release_allowed: false,
    image_data_url,
  };
}
