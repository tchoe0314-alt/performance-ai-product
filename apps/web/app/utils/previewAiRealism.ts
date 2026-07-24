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

function svgEscape(value: string) {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function buildAiRealismSvg({
  sourceObjects,
  promptSummary,
  watermark,
}: {
  sourceObjects: AiRealismSourceObject[];
  promptSummary: string;
  watermark: string;
}) {
  const visibleObjects = sourceObjects.filter((item) => item.type !== "site");
  const bounds = visibleObjects.reduce(
    (acc, item) => {
      const points = Array.isArray(item.geometry) && item.geometry.length ? item.geometry : [[item.x, item.y], [item.x + item.w, item.y + item.d]];
      points.forEach(([x, y]) => {
        acc.minX = Math.min(acc.minX, x);
        acc.minY = Math.min(acc.minY, y);
        acc.maxX = Math.max(acc.maxX, x);
        acc.maxY = Math.max(acc.maxY, y);
      });
      return acc;
    },
    { minX: Infinity, minY: Infinity, maxX: -Infinity, maxY: -Infinity },
  );
  const safeBounds = Number.isFinite(bounds.minX)
    ? bounds
    : { minX: 0, minY: 0, maxX: 1000, maxY: 700 };
  const sourceW = Math.max(1, safeBounds.maxX - safeBounds.minX);
  const sourceH = Math.max(1, safeBounds.maxY - safeBounds.minY);
  const pad = 76;
  const scale = Math.min((1200 - pad * 2) / sourceW, (760 - pad * 2) / sourceH);
  const offsetX = (1200 - sourceW * scale) / 2;
  const offsetY = (760 - sourceH * scale) / 2;
  const sx = (x: number) => offsetX + (x - safeBounds.minX) * scale;
  const sy = (y: number) => offsetY + (y - safeBounds.minY) * scale;
  const rect = (item: AiRealismSourceObject) => ({
    x: sx(item.x),
    y: sy(item.y),
    w: Math.max(4, item.w * scale),
    h: Math.max(4, item.d * scale),
  });
  const pointList = (item: AiRealismSourceObject) =>
    (item.geometry || []).map(([x, y]) => `${sx(x).toFixed(1)},${sy(y).toFixed(1)}`).join(" ");
  const drawOrder = [...visibleObjects].sort((a, b) => {
    const priority = (item: AiRealismSourceObject) => {
      if (item.type === "lot_block") return 1;
      if (item.type === "road" || item.type === "driveway") return 2;
      if (item.type === "open_space" || item.type === "landscape") return 3;
      if (item.type === "parking") return 4;
      if (item.type === "utility_corridor") return 5;
      if (item.type === "building") return 6;
      if (item.type === "basin" || item.type === "pond") return 7;
      return 8;
    };
    return priority(a) - priority(b);
  });
  const objectSvg = drawOrder.map((item) => {
    const type = String(item.type || "");
    const r = rect(item);
    if ((type === "road" || type === "driveway") && item.geometry?.length) {
      return `<polyline points="${pointList(item)}" fill="none" stroke="#475569" stroke-width="34" stroke-linecap="round" stroke-linejoin="round" opacity="0.78"/><polyline points="${pointList(item)}" fill="none" stroke="#f8fafc" stroke-width="4" stroke-dasharray="24 20" stroke-linecap="round" opacity="0.9"/>`;
    }
    if (type === "utility_corridor" && item.geometry?.length) {
      const color = item.label.toLowerCase().includes("water") ? "#0ea5e9" : item.label.toLowerCase().includes("sanitary") ? "#c026d3" : "#0284c7";
      return `<polyline points="${pointList(item)}" fill="none" stroke="${color}" stroke-width="3" stroke-dasharray="10 8" opacity="0.72"/>${(item.geometry || []).map(([x, y]) => `<circle cx="${sx(x).toFixed(1)}" cy="${sy(y).toFixed(1)}" r="4" fill="#fff" stroke="${color}" stroke-width="2"/>`).join("")}`;
    }
    if ((type === "open_space" || type === "amenity") && item.geometry?.length) {
      const fill = type === "amenity" ? "#d7b56b" : "#9fbc72";
      const stroke = type === "amenity" ? "#a16207" : "#4d7c0f";
      return `<polygon points="${pointList(item)}" fill="${fill}" fill-opacity="0.5" stroke="${stroke}" stroke-width="3"/><polygon points="${pointList(item)}" fill="url(#land)" opacity="0.28"/>`;
    }
    if (type === "lot_block") {
      return `<rect x="${r.x.toFixed(1)}" y="${r.y.toFixed(1)}" width="${r.w.toFixed(1)}" height="${r.h.toFixed(1)}" rx="6" fill="#f8fafc" fill-opacity="0.52" stroke="#0f766e" stroke-width="2"/>`;
    }
    if (type === "parking") {
      const stalls = Array.from({ length: 10 }).map((_, idx) => {
        const x = r.x + r.w * (0.12 + idx * 0.084);
        return `<line x1="${x.toFixed(1)}" y1="${(r.y + r.h * 0.12).toFixed(1)}" x2="${x.toFixed(1)}" y2="${(r.y + r.h * 0.88).toFixed(1)}" stroke="#e2e8f0" stroke-width="2"/>`;
      }).join("");
      return `<rect x="${r.x.toFixed(1)}" y="${r.y.toFixed(1)}" width="${r.w.toFixed(1)}" height="${r.h.toFixed(1)}" fill="#475569" fill-opacity="0.42" stroke="#f59e0b" stroke-width="3"/>${stalls}`;
    }
    if (type === "building") {
      const roof = item.label.toLowerCase().includes("civic") ? "#111827" : "#6b7280";
      return `<rect x="${r.x.toFixed(1)}" y="${r.y.toFixed(1)}" width="${r.w.toFixed(1)}" height="${r.h.toFixed(1)}" fill="#d6c8a8" stroke="#4b5563" stroke-width="3" filter="url(#softShadow)"/><path d="M ${r.x.toFixed(1)} ${(r.y + r.h * 0.12).toFixed(1)} L ${(r.x + r.w).toFixed(1)} ${(r.y + r.h * 0.12).toFixed(1)}" stroke="${roof}" stroke-width="2" opacity="0.6"/>`;
    }
    if (type === "basin" || type === "pond") {
      return `<ellipse cx="${(r.x + r.w / 2).toFixed(1)}" cy="${(r.y + r.h / 2).toFixed(1)}" rx="${(r.w / 2).toFixed(1)}" ry="${(r.h / 2).toFixed(1)}" fill="#7dd3fc" fill-opacity="0.64" stroke="#0284c7" stroke-width="3"/><ellipse cx="${(r.x + r.w / 2).toFixed(1)}" cy="${(r.y + r.h / 2).toFixed(1)}" rx="${(r.w * 0.32).toFixed(1)}" ry="${(r.h * 0.28).toFixed(1)}" fill="none" stroke="#0369a1" stroke-width="2" opacity="0.55"/>`;
    }
    if (type === "landscape") {
      return `<circle cx="${(r.x + r.w / 2).toFixed(1)}" cy="${(r.y + r.h / 2).toFixed(1)}" r="${Math.max(5, Math.min(r.w, r.h) * 0.42).toFixed(1)}" fill="#4d7c0f" fill-opacity="0.46" stroke="#365314" stroke-width="2"/>`;
    }
    return `<rect x="${r.x.toFixed(1)}" y="${r.y.toFixed(1)}" width="${r.w.toFixed(1)}" height="${r.h.toFixed(1)}" fill="#94a3b8" fill-opacity="0.32" stroke="#475569" stroke-width="2"/>`;
  }).join("");
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 760" role="img" aria-label="AI visualization generated from current review layout"><defs><linearGradient id="site" x1="0" x2="1" y1="0" y2="1"><stop offset="0" stop-color="#f6f7ef"/><stop offset="0.62" stop-color="#dce8d2"/><stop offset="1" stop-color="#c8dbbd"/></linearGradient><filter id="softShadow"><feDropShadow dx="0" dy="8" stdDeviation="8" flood-color="#334155" flood-opacity="0.15"/></filter><pattern id="land" width="30" height="30" patternUnits="userSpaceOnUse" patternTransform="rotate(-18)"><path d="M0 30 L30 0" stroke="#5f7f52" stroke-width="1" opacity="0.42"/></pattern></defs><rect width="1200" height="760" fill="#f8fafc"/><rect x="36" y="36" width="1128" height="688" rx="22" fill="url(#site)" stroke="#556651" stroke-width="3"/><rect x="36" y="36" width="1128" height="688" rx="22" fill="url(#land)" opacity="0.32"/>${objectSvg}<text x="58" y="72" fill="#0f172a" font-family="Arial, sans-serif" font-size="22" font-weight="700">AI visualization</text><text x="58" y="100" fill="#334155" font-family="Arial, sans-serif" font-size="14">${svgEscape(promptSummary).slice(0, 150)}</text><rect x="52" y="678" width="1096" height="36" rx="8" fill="rgba(15,23,42,0.66)"/><text x="72" y="701" fill="#fff" font-family="Arial, sans-serif" font-size="15">${svgEscape(watermark)}</text></svg>`;
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
    buildAiRealismSvg({ sourceObjects, promptSummary, watermark }),
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
