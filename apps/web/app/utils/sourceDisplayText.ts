const KNOWN_SOURCE_NAMES: Record<string, string> = {
  civora_heuristic: "Civora imagery estimate",
  civora_vision: "Civora Vision",
  detected_from_gis: "GIS-detected item",
  fema_nfhl: "FEMA National Flood Hazard Layer",
  fema_nfhl_arcgis: "FEMA National Flood Hazard Layer",
  image_detected_candidate: "Image-detected item",
  mapbox_satellite: "Mapbox Satellite",
  osm_overpass: "OpenStreetMap",
  openstreetmap_overpass: "OpenStreetMap",
  usgs_3dep: "USGS 3DEP",
};

const ACRONYMS: Record<string, string> = {
  ada: "ADA",
  ai: "AI",
  api: "API",
  dem: "DEM",
  fema: "FEMA",
  gis: "GIS",
  lidar: "LiDAR",
  nfhl: "NFHL",
  osm: "OSM",
  row: "ROW",
  usgs: "USGS",
};

export function sourceDisplayName(value: unknown, fallback = "Source not available"): string {
  const raw = String(value ?? "").trim();
  if (!raw) return fallback;
  if (/^https?:\/\//i.test(raw)) return raw;
  const normalized = raw.toLowerCase();
  if (KNOWN_SOURCE_NAMES[normalized]) return KNOWN_SOURCE_NAMES[normalized];
  if (!/[_-]/.test(raw)) return raw;
  return raw
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .split(" ")
    .map((word) => ACRONYMS[word.toLowerCase()] ?? `${word.charAt(0).toUpperCase()}${word.slice(1)}`)
    .join(" ");
}

export function sourceDisplaySentence(value: unknown, fallback = "Source information is not available."): string {
  const raw = String(value ?? "").trim();
  if (!raw) return fallback;
  let result = raw;
  Object.entries(KNOWN_SOURCE_NAMES)
    .sort(([left], [right]) => right.length - left.length)
    .forEach(([key, label]) => {
      result = result.replaceAll(key, label);
    });
  return result.replaceAll("_", " ").replace(/\s+/g, " ").trim();
}
