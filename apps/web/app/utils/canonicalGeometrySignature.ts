type GeometrySignatureInput = {
  x?: number;
  y?: number;
  width?: number;
  depth?: number;
  rotation?: number;
  geometryType?: string;
  geometry?: Array<[number, number]>;
};

const normalizedNumber = (value: unknown) => {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return 0;
  return Number(numeric.toFixed(4));
};

const normalizedGeometry = (geometry: GeometrySignatureInput["geometry"]) =>
  Array.isArray(geometry)
    ? geometry
        .filter(
          (point): point is [number, number] =>
            Array.isArray(point) && Number.isFinite(Number(point[0])) && Number.isFinite(Number(point[1])),
        )
        .map(([x, y]) => [normalizedNumber(x), normalizedNumber(y)] as [number, number])
    : [];

export function buildCanonicalFootprintSignature(input: GeometrySignatureInput) {
  return JSON.stringify({
    type: String(input.geometryType || "rect").toLowerCase(),
    x: normalizedNumber(input.x),
    y: normalizedNumber(input.y),
    width: normalizedNumber(input.width),
    depth: normalizedNumber(input.depth),
    rotation: normalizedNumber(input.rotation),
    geometry: normalizedGeometry(input.geometry),
  });
}

export function canonicalPlacementFootprintSignature(input: {
  x?: number;
  y?: number;
  w?: number;
  d?: number;
  rotation?: number;
  geometryType?: string;
  geometry?: Array<[number, number]>;
}) {
  return buildCanonicalFootprintSignature({
    x: input.x,
    y: input.y,
    width: input.w,
    depth: input.d,
    rotation: input.rotation,
    geometryType: input.geometryType,
    geometry: input.geometry,
  });
}

export function canonicalPreview3DFootprintSignature(input: {
  x?: number;
  y?: number;
  w?: number;
  h?: number;
  rotation?: number;
  geometryType?: string;
  geometry?: Array<[number, number]>;
}) {
  return buildCanonicalFootprintSignature({
    x: input.x,
    y: input.y,
    width: input.w,
    depth: input.h,
    rotation: input.rotation,
    geometryType: input.geometryType,
    geometry: input.geometry,
  });
}
