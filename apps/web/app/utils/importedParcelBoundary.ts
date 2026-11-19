export type ImportedParcelBoundary = {
  featureId: string;
  points: Array<[number, number]>;
  units: "ft" | "m";
  crs: string;
  sourceFile: string;
};

export type ImportedParcelBoundaryResult =
  | { status: "ready"; candidate: ImportedParcelBoundary }
  | { status: "unavailable" | "ambiguous" | "invalid"; reason: string };

const record = (value: unknown): Record<string, unknown> => value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
const finitePoint = (value: unknown): [number, number] | null => {
  if (!Array.isArray(value) || value.length < 2) return null;
  const x = Number(value[0]), y = Number(value[1]);
  return Number.isFinite(x) && Number.isFinite(y) ? [x, y] : null;
};
const same = (a: [number, number], b: [number, number]) => a[0] === b[0] && a[1] === b[1];
const orientation = (a: [number, number], b: [number, number], c: [number, number]) => Math.sign((b[1] - a[1]) * (c[0] - b[0]) - (b[0] - a[0]) * (c[1] - b[1]));
const intersects = (a: [number, number], b: [number, number], c: [number, number], d: [number, number]) => orientation(a, b, c) !== orientation(a, b, d) && orientation(c, d, a) !== orientation(c, d, b);

export function importedParcelBoundaryFromProjectInput(input: unknown): ImportedParcelBoundaryResult {
  const root = record(input), meta = record(root.meta);
  const canonical = record(meta.canonical_existing_conditions);
  const model = record(meta.canonical_existing_conditions_model);
  const layers = record(canonical.gis_layers ?? model.gis_layers);
  const parcels = Array.isArray(layers.parcels) ? layers.parcels : [];
  if (!parcels.length) return { status: "unavailable", reason: "No imported parcel polygon is available." };
  if (parcels.length !== 1) return { status: "ambiguous", reason: `The import contains ${parcels.length} parcel features. Select or isolate one parcel before applying a boundary.` };

  const feature = record(parcels[0]), geometry = record(feature.geometry), properties = record(feature.properties);
  if (geometry.type !== "Polygon") return { status: "invalid", reason: "Only one Polygon parcel can become the active boundary; MultiPolygon and non-polygon features require explicit parcel selection." };
  const rings = Array.isArray(geometry.coordinates) ? geometry.coordinates : [];
  if (rings.length !== 1) return { status: "invalid", reason: "Parcel polygons with interior holes require explicit engineering review and cannot be flattened into one boundary." };
  const rawRing = Array.isArray(rings[0]) ? rings[0] : [];
  const parsed = rawRing.map(finitePoint);
  if (parsed.some(point => point === null)) return { status: "invalid", reason: "The parcel contains invalid coordinates." };
  const closed = parsed as Array<[number, number]>;
  const points = closed.length > 1 && same(closed[0], closed[closed.length - 1]) ? closed.slice(0, -1) : closed;
  if (points.length < 3 || new Set(points.map(point => `${point[0]}:${point[1]}`)).size < 3) return { status: "invalid", reason: "The parcel must contain at least three distinct vertices." };
  const area2 = points.reduce((sum, point, index) => { const next = points[(index + 1) % points.length]; return sum + point[0] * next[1] - next[0] * point[1]; }, 0);
  if (!Number.isFinite(area2) || Math.abs(area2) < 1e-6) return { status: "invalid", reason: "The parcel polygon has no usable area." };
  for (let i = 0; i < points.length; i += 1) for (let j = i + 1; j < points.length; j += 1) {
    if (j === i + 1 || (i === 0 && j === points.length - 1)) continue;
    if (intersects(points[i], points[(i + 1) % points.length], points[j], points[(j + 1) % points.length])) return { status: "invalid", reason: "The parcel polygon self-intersects and cannot become a canonical boundary." };
  }

  const coordinateSystem = record(canonical.coordinate_system ?? model.coordinate_system);
  const crs = String(coordinateSystem.epsg ?? coordinateSystem.name ?? coordinateSystem.crs ?? "").trim();
  if (!crs) return { status: "invalid", reason: "The parcel has no explicit projected CRS. Define its coordinate reference system before applying it." };
  const rawUnits = String(properties.units ?? coordinateSystem.units ?? "").toLowerCase();
  const units = ["ft", "foot", "feet", "us_survey_ft"].includes(rawUnits) ? "ft" : ["m", "meter", "meters", "metre", "metres"].includes(rawUnits) ? "m" : null;
  if (!units) return { status: "invalid", reason: "The parcel has no explicit engineering distance units. Confirm feet or metres in the source before applying it." };
  if (coordinateSystem.is_geographic === true || rawUnits.includes("degree")) return { status: "invalid", reason: "Geographic degree coordinates must be projected before they can become a site boundary." };
  const source = record(meta.site_inputs), imported = record(source.existing_conditions_import);
  return { status: "ready", candidate: { featureId: String(feature.id ?? "parcel-1"), points, units, crs, sourceFile: String(imported.filename ?? feature.source ?? "imported parcel") } };
}
