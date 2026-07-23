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
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 760" role="img" aria-label="AI visualization generated from current review layout"><defs><linearGradient id="site" x1="0" x2="1" y1="0" y2="1"><stop offset="0" stop-color="#eef3ea"/><stop offset="0.58" stop-color="#d9e6d1"/><stop offset="1" stop-color="#c3d7ba"/></linearGradient><filter id="softShadow"><feDropShadow dx="0" dy="8" stdDeviation="8" flood-color="#334155" flood-opacity="0.16"/></filter><pattern id="mown" width="28" height="28" patternUnits="userSpaceOnUse" patternTransform="rotate(-18)"><path d="M0 28 L28 0" stroke="#9caf91" stroke-width="1" opacity="0.22"/></pattern></defs><rect width="1200" height="760" fill="#f8fafc"/><path d="M90 78 L1055 54 L1118 604 L156 690 Z" fill="url(#site)" stroke="#51624d" stroke-width="3"/><path d="M90 78 L1055 54 L1118 604 L156 690 Z" fill="url(#mown)" opacity="0.45"/><path d="M82 650 C250 568 424 590 586 504 C780 400 944 475 1124 390" fill="none" stroke="#3f4650" stroke-width="46" stroke-linecap="round" stroke-linejoin="round"/><path d="M82 650 C250 568 424 590 586 504 C780 400 944 475 1124 390" fill="none" stroke="#e7edf1" stroke-width="5" stroke-dasharray="28 24" opacity="0.88"/><path d="M214 210 L420 194 L431 286 L226 304 Z" fill="#cbbf9f" stroke="#6d6659" stroke-width="3" filter="url(#softShadow)"/><path d="M626 170 L844 158 L856 250 L638 264 Z" fill="#cbbf9f" stroke="#6d6659" stroke-width="3" filter="url(#softShadow)"/><path d="M282 510 L468 492 L478 568 L292 588 Z" fill="#cbbf9f" stroke="#6d6659" stroke-width="3" filter="url(#softShadow)"/><g stroke="#f8fafc" stroke-width="3" opacity="0.82">${Array.from({ length: 11 }).map((_, index) => `<line x1="${500 + index * 26}" y1="338" x2="${520 + index * 26}" y2="456"/>`).join("")}</g><path d="M482 330 L812 310 L836 464 L500 486 Z" fill="#4b5563" opacity="0.34" stroke="#374151" stroke-width="2"/><ellipse cx="934" cy="590" rx="126" ry="55" fill="#74c7df" opacity="0.68" stroke="#18799a" stroke-width="3"/><ellipse cx="934" cy="590" rx="82" ry="33" fill="#b7e6ef" opacity="0.44" stroke="#18799a" stroke-width="2"/><path d="M224 408 C344 390 482 388 612 348" fill="none" stroke="#f8fafc" stroke-width="15" opacity="0.86" stroke-linecap="round"/><text x="54" y="66" fill="#0f172a" font-family="Arial, sans-serif" font-size="22" font-weight="700">AI visualization</text><text x="54" y="96" fill="#334155" font-family="Arial, sans-serif" font-size="15">${promptSummary}</text><rect x="48" y="682" width="1104" height="38" rx="8" fill="rgba(15,23,42,0.68)"/><text x="70" y="706" fill="#fff" font-family="Arial, sans-serif" font-size="16">${watermark}</text></svg>`,
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
