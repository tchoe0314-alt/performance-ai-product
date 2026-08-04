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
  roofProfile: string;
  stallCount: number | null;
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
      roofProfile: String(item.meta?.roof_profile || "flat"),
      stallCount: typeof item.stallCount === "number" ? item.stallCount : null,
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

const isBuildingType = (type: string) => type === "building" || type.endsWith("_building");

function scaleGeometry(points: Array<[number, number]>, factor: number) {
  if (!points.length) return [];
  const center = points.reduce(
    (acc, [x, y]) => ({ x: acc.x + x / points.length, y: acc.y + y / points.length }),
    { x: 0, y: 0 },
  );
  return points.map(([x, y]) => [center.x + (x - center.x) * factor, center.y + (y - center.y) * factor] as [number, number]);
}

function buildAiRealismSvg({
  sourceObjects,
  promptSummary,
  watermark,
  lotWidth,
  lotHeight,
  mapContextAvailable,
}: {
  sourceObjects: AiRealismSourceObject[];
  promptSummary: string;
  watermark: string;
  lotWidth: number;
  lotHeight: number;
  mapContextAvailable: boolean;
}) {
  const visibleObjects = sourceObjects.filter((item) => item.type !== "site");
  const sourceW = Math.max(1, Number.isFinite(lotWidth) ? lotWidth : 1000);
  const sourceH = Math.max(1, Number.isFinite(lotHeight) ? lotHeight : 700);
  const scaleX = 1200 / sourceW;
  const scaleY = 760 / sourceH;
  const frameW = 1200;
  const frameH = 760;
  const offsetX = 0;
  const offsetY = 0;
  const sx = (x: number) => offsetX + x * scaleX;
  const sy = (y: number) => offsetY + y * scaleY;
  const rect = (item: AiRealismSourceObject) => ({
    x: sx(item.x),
    y: sy(item.y),
    w: Math.max(4, item.w * scaleX),
    h: Math.max(4, item.d * scaleY),
  });
  const hasPolygon = (item: AiRealismSourceObject) =>
    item.geometryType === "polygon" && Array.isArray(item.geometry) && item.geometry.length >= 3;
  const pointList = (item: AiRealismSourceObject, points = item.geometry || []) =>
    points.map(([x, y]) => `${sx(x).toFixed(1)},${sy(y).toFixed(1)}`).join(" ");
  const safeId = (value: string) => value.replace(/[^a-zA-Z0-9_-]/g, "-");
  const rectTransform = (item: AiRealismSourceObject, r: ReturnType<typeof rect>) =>
    !hasPolygon(item) && Math.abs(item.rotation) > 0.01
      ? ` transform="rotate(${item.rotation.toFixed(2)} ${(r.x + r.w / 2).toFixed(1)} ${(r.y + r.h / 2).toFixed(1)})"`
      : "";
  const polygonOrRect = (
    item: AiRealismSourceObject,
    r: ReturnType<typeof rect>,
    attributes: string,
  ) => hasPolygon(item)
    ? `<polygon data-geometry-kind="polygon" points="${pointList(item)}" ${attributes}/>`
    : `<rect data-geometry-kind="rect" x="${r.x.toFixed(1)}" y="${r.y.toFixed(1)}" width="${r.w.toFixed(1)}" height="${r.h.toFixed(1)}" ${attributes}/>`;
  const drawOrder = [...visibleObjects].sort((a, b) => {
    const priority = (item: AiRealismSourceObject) => {
      if (item.type === "lot_block") return 1;
      if (item.type === "road" || item.type === "driveway") return 2;
      if (item.type === "open_space" || item.type === "landscape") return 3;
      if (item.type === "parking") return 4;
      if (item.type === "utility_corridor") return 5;
      if (isBuildingType(item.type)) return 6;
      if (item.type === "basin" || item.type === "pond") return 7;
      return 8;
    };
    return priority(a) - priority(b);
  });
  const objectSvg = drawOrder.map((item, itemIndex) => {
    const type = String(item.type || "");
    const r = rect(item);
    const transform = rectTransform(item, r);
    const objectAttrs = `data-ai-object-id="${svgEscape(item.id)}" data-ai-object-type="${svgEscape(type)}"`;
    if ((type === "road" || type === "driveway") && item.geometry?.length) {
      return `<g ${objectAttrs}><polyline points="${pointList(item)}" fill="none" stroke="#475569" stroke-width="34" stroke-linecap="round" stroke-linejoin="round" opacity="0.72"/><polyline points="${pointList(item)}" fill="none" stroke="#f8fafc" stroke-width="4" stroke-dasharray="24 20" stroke-linecap="round" opacity="0.88"/></g>`;
    }
    if (type === "utility_corridor" && item.geometry?.length) {
      const color = item.label.toLowerCase().includes("water") ? "#0ea5e9" : item.label.toLowerCase().includes("sanitary") ? "#c026d3" : "#0284c7";
      return `<g ${objectAttrs}><polyline points="${pointList(item)}" fill="none" stroke="${color}" stroke-width="3" stroke-dasharray="10 8" opacity="0.78"/>${item.geometry.map(([x, y]) => `<circle cx="${sx(x).toFixed(1)}" cy="${sy(y).toFixed(1)}" r="4" fill="#fff" stroke="${color}" stroke-width="2"/>`).join("")}</g>`;
    }
    if ((type === "open_space" || type === "amenity") && hasPolygon(item)) {
      const fill = type === "amenity" ? "#d7b56b" : "#9fbc72";
      const stroke = type === "amenity" ? "#a16207" : "#4d7c0f";
      return `<g ${objectAttrs}><polygon data-geometry-kind="polygon" points="${pointList(item)}" fill="${fill}" fill-opacity="0.42" stroke="${stroke}" stroke-width="3"/><polygon points="${pointList(item)}" fill="url(#land)" opacity="0.18"/></g>`;
    }
    if (type === "lot_block") {
      return `<g ${objectAttrs}${transform}>${polygonOrRect(item, r, 'rx="6" fill="#f8fafc" fill-opacity="0.32" stroke="#0f766e" stroke-width="2"')}</g>`;
    }
    if (type === "parking") {
      const clipId = `ai-parking-clip-${safeId(item.id)}-${itemIndex}`;
      const stallCount = Math.max(4, Math.min(28, Math.round((item.stallCount || Math.max(item.w / 9, 8)) / 2)));
      const stalls = Array.from({ length: stallCount }).map((_, idx) => {
        const x = r.x + r.w * (0.08 + (idx / Math.max(stallCount - 1, 1)) * 0.84);
        return `<line x1="${x.toFixed(1)}" y1="${(r.y + r.h * 0.08).toFixed(1)}" x2="${x.toFixed(1)}" y2="${(r.y + r.h * 0.92).toFixed(1)}" stroke="#f8fafc" stroke-width="2" opacity="0.82"/>`;
      }).join("");
      const clipShape = hasPolygon(item)
        ? `<polygon points="${pointList(item)}"/>`
        : `<rect x="${r.x.toFixed(1)}" y="${r.y.toFixed(1)}" width="${r.w.toFixed(1)}" height="${r.h.toFixed(1)}"/>`;
      const boundary = polygonOrRect(item, r, 'fill="#475569" fill-opacity="0.54" stroke="#f59e0b" stroke-width="3"');
      return `<g ${objectAttrs}${transform}><defs><clipPath id="${clipId}">${clipShape}</clipPath></defs>${boundary}<g clip-path="url(#${clipId})">${stalls}<rect x="${r.x.toFixed(1)}" y="${(r.y + r.h * 0.42).toFixed(1)}" width="${r.w.toFixed(1)}" height="${Math.max(5, r.h * 0.16).toFixed(1)}" fill="#334155" fill-opacity="0.72"/></g><title>${svgEscape(item.label)} · ${item.stallCount || "layout"} stalls shown as a visual planning preview</title></g>`;
    }
    if (isBuildingType(type)) {
      const footprint = polygonOrRect(item, r, 'fill="#d6c8a8" fill-opacity="0.9" stroke="#374151" stroke-width="3" filter="url(#softShadow)"');
      return `<g ${objectAttrs}${transform}>${footprint}<title>${svgEscape(item.label)} · ${Math.round(item.h || 0)} ft high · ${svgEscape(item.roofProfile)} roof</title></g>`;
    }
    if (type === "basin" || type === "pond") {
      if (hasPolygon(item)) {
        return `<g ${objectAttrs}><polygon data-geometry-kind="polygon" points="${pointList(item)}" fill="#7dd3fc" fill-opacity="0.58" stroke="#0284c7" stroke-width="3"/><polygon points="${pointList(item, scaleGeometry(item.geometry || [], 0.62))}" fill="#38bdf8" fill-opacity="0.42" stroke="#0369a1" stroke-width="2"/></g>`;
      }
      return `<g ${objectAttrs}${transform}><ellipse cx="${(r.x + r.w / 2).toFixed(1)}" cy="${(r.y + r.h / 2).toFixed(1)}" rx="${(r.w / 2).toFixed(1)}" ry="${(r.h / 2).toFixed(1)}" fill="#7dd3fc" fill-opacity="0.58" stroke="#0284c7" stroke-width="3"/><ellipse cx="${(r.x + r.w / 2).toFixed(1)}" cy="${(r.y + r.h / 2).toFixed(1)}" rx="${(r.w * 0.32).toFixed(1)}" ry="${(r.h * 0.28).toFixed(1)}" fill="none" stroke="#0369a1" stroke-width="2" opacity="0.55"/></g>`;
    }
    if (type === "landscape") {
      return `<g ${objectAttrs}><circle cx="${(r.x + r.w / 2).toFixed(1)}" cy="${(r.y + r.h / 2).toFixed(1)}" r="${Math.max(5, Math.min(r.w, r.h) * 0.42).toFixed(1)}" fill="#4d7c0f" fill-opacity="0.46" stroke="#365314" stroke-width="2"/></g>`;
    }
    return `<g ${objectAttrs}${transform}>${polygonOrRect(item, r, 'fill="#94a3b8" fill-opacity="0.3" stroke="#475569" stroke-width="2"')}</g>`;
  }).join("");
  const siteFill = mapContextAvailable ? "#dff3db" : "url(#site)";
  const siteFillOpacity = mapContextAvailable ? "0.06" : "0.94";
  const hatchOpacity = mapContextAvailable ? "0.035" : "0.22";
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 760" preserveAspectRatio="none" role="img" aria-label="AI preview generated from current site layout" data-map-grounded="${mapContextAvailable ? "true" : "false"}"><title>${svgEscape(promptSummary)} · ${svgEscape(watermark)}</title><defs><linearGradient id="site" x1="0" x2="1" y1="0" y2="1"><stop offset="0" stop-color="#f6f7ef"/><stop offset="0.62" stop-color="#dce8d2"/><stop offset="1" stop-color="#c8dbbd"/></linearGradient><filter id="softShadow"><feDropShadow dx="0" dy="6" stdDeviation="7" flood-color="#0f172a" flood-opacity="0.24"/></filter><pattern id="land" width="30" height="30" patternUnits="userSpaceOnUse" patternTransform="rotate(-18)"><path d="M0 30 L30 0" stroke="#5f7f52" stroke-width="1" opacity="0.42"/></pattern></defs><rect width="1200" height="760" fill="transparent"/><rect data-ai-site-frame="true" x="${offsetX.toFixed(1)}" y="${offsetY.toFixed(1)}" width="${frameW.toFixed(1)}" height="${frameH.toFixed(1)}" fill="${siteFill}" fill-opacity="${siteFillOpacity}" stroke="#475569" stroke-opacity="0.45" stroke-width="1.25"/><rect x="${offsetX.toFixed(1)}" y="${offsetY.toFixed(1)}" width="${frameW.toFixed(1)}" height="${frameH.toFixed(1)}" fill="url(#land)" opacity="${hatchOpacity}"/><g data-ai-layout-preview="true">${objectSvg}</g></svg>`;
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
  const hasMapCoordinates =
    typeof geocode?.lat === "number" &&
    Number.isFinite(geocode.lat) &&
    typeof geocode?.lng === "number" &&
    Number.isFinite(geocode.lng);
  if (!hasTerrainSource) missing.push("terrain/source confidence");
  if (!hasMapCoordinates) missing.push("source-backed map/geocode context");
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
  lotWidth,
  lotHeight,
  mapContextAvailable,
  watermark,
}: {
  currentProjectId?: string | null;
  planPreviewProjectId?: string | null;
  sourceLayoutHash: string;
  sourceObjects: AiRealismSourceObject[];
  sourceSummary: AiRealismArtifact["source_objects_summary"];
  missingInputs: string[];
  hasTerrainSource: boolean;
  lotWidth: number;
  lotHeight: number;
  mapContextAvailable: boolean;
  watermark: string;
}): AiRealismArtifact {
  const generated_timestamp = new Date().toISOString();
  const project_id = currentProjectId || planPreviewProjectId || "unsaved-review-layout";
  const counts = sourceSummary.counts_by_type;
  const promptSummary = [
    `${sourceObjects.length} review layout objects`,
    Object.keys(counts).some(isBuildingType) ? "building massing" : "",
    counts.parking ? "parking fields" : "",
    counts.road || counts.driveway ? "roads and driveways" : "",
    counts.basin ? "detention basin" : "",
    hasTerrainSource ? "terrain source present" : "terrain source missing",
  ]
    .filter(Boolean)
    .join(", ");
  const image_data_url = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(
    buildAiRealismSvg({ sourceObjects, promptSummary, watermark, lotWidth, lotHeight, mapContextAvailable }),
  )}`;
  return {
    type: "high_quality_ai_render_v1",
    project_id,
    source_layout_hash: sourceLayoutHash,
    site_frame: {
      width_ft: Math.max(1, lotWidth),
      height_ft: Math.max(1, lotHeight),
      map_context_available: mapContextAvailable,
    },
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
