export type CadPoint2D = { x: number; y: number };
export type CadTuple2D = [number, number];
export type CadSnapKind = "endpoint" | "midpoint" | "intersection" | "perpendicular" | "nearest" | "grid" | "orthogonal";
export type CadSegment2D = { a: CadPoint2D; b: CadPoint2D; objectId?: string; segmentIndex?: number; closed?: boolean };
type CadBlockedResult = { ok: false; reason: string };
export type CadOperationResult<T> = { ok: true; value: T; warnings?: string[] } | CadBlockedResult;

const EPSILON = 1e-6;

const snapPriority: Record<CadSnapKind, number> = {
  endpoint: 0,
  midpoint: 1,
  intersection: 2,
  perpendicular: 3,
  nearest: 4,
  grid: 5,
  orthogonal: 6,
};

const tupleToPoint = ([x, y]: CadTuple2D): CadPoint2D => ({ x, y });
const pointToTuple = (point: CadPoint2D): CadTuple2D => [roundCoord(point.x), roundCoord(point.y)];
const roundCoord = (value: number) => Math.round(value * 1000) / 1000;
const distance = (a: CadPoint2D, b: CadPoint2D) => Math.hypot(a.x - b.x, a.y - b.y);
const vectorLength = (x: number, y: number) => Math.hypot(x, y);
const clamp = (value: number, min: number, max: number) => Math.min(Math.max(value, min), max);

const normalize = (x: number, y: number): CadPoint2D | null => {
  const len = vectorLength(x, y);
  if (len < EPSILON) return null;
  return { x: x / len, y: y / len };
};

const signedPolygonArea = (points: CadTuple2D[]) => {
  if (points.length < 3) return 0;
  return points.reduce((sum, point, index) => {
    const next = points[(index + 1) % points.length];
    return sum + point[0] * next[1] - next[0] * point[1];
  }, 0) / 2;
};

function segmentIntersection(
  a: CadPoint2D,
  b: CadPoint2D,
  c: CadPoint2D,
  d: CadPoint2D,
  options: { extendAB?: boolean; extendCD?: boolean } = {},
): CadPoint2D | null {
  const denominator = (a.x - b.x) * (c.y - d.y) - (a.y - b.y) * (c.x - d.x);
  if (Math.abs(denominator) < EPSILON) return null;
  const t = ((a.x - c.x) * (c.y - d.y) - (a.y - c.y) * (c.x - d.x)) / denominator;
  const u = -((a.x - b.x) * (a.y - c.y) - (a.y - b.y) * (a.x - c.x)) / denominator;
  if (!options.extendAB && (t < -EPSILON || t > 1 + EPSILON)) return null;
  if (!options.extendCD && (u < -EPSILON || u > 1 + EPSILON)) return null;
  return { x: a.x + t * (b.x - a.x), y: a.y + t * (b.y - a.y) };
}

function closestPointOnSegment(point: CadPoint2D, segment: CadSegment2D, allowExtension = false): CadPoint2D {
  const dx = segment.b.x - segment.a.x;
  const dy = segment.b.y - segment.a.y;
  const lenSq = dx * dx + dy * dy;
  if (lenSq < EPSILON) return { ...segment.a };
  const rawT = ((point.x - segment.a.x) * dx + (point.y - segment.a.y) * dy) / lenSq;
  const t = allowExtension ? rawT : clamp(rawT, 0, 1);
  return { x: segment.a.x + t * dx, y: segment.a.y + t * dy };
}

export function resolveCadSnap(
  point: CadPoint2D,
  segments: CadSegment2D[],
  options: {
    enabled: boolean;
    ortho: boolean;
    basePoint?: CadPoint2D | null;
    threshold: number;
    gridSize?: number;
  },
): CadPoint2D & { kind: CadSnapKind } {
  const candidates: Array<CadPoint2D & { kind: CadSnapKind; distance: number }> = [];
  const addCandidate = (candidate: CadPoint2D & { kind: CadSnapKind }) => {
    candidates.push({ ...candidate, distance: distance(point, candidate) });
  };

  if (options.enabled) {
    segments.forEach((segment, index) => {
      addCandidate({ ...segment.a, kind: "endpoint" });
      addCandidate({ ...segment.b, kind: "endpoint" });
      addCandidate({ x: (segment.a.x + segment.b.x) / 2, y: (segment.a.y + segment.b.y) / 2, kind: "midpoint" });
      addCandidate({ ...closestPointOnSegment(point, segment), kind: "nearest" });
      if (options.basePoint) addCandidate({ ...closestPointOnSegment(options.basePoint, segment), kind: "perpendicular" });
      for (let otherIndex = index + 1; otherIndex < segments.length; otherIndex += 1) {
        const hit = segmentIntersection(segment.a, segment.b, segments[otherIndex].a, segments[otherIndex].b);
        if (hit) addCandidate({ ...hit, kind: "intersection" });
      }
    });
    if (options.gridSize && options.gridSize > 0) {
      addCandidate({
        x: Math.round(point.x / options.gridSize) * options.gridSize,
        y: Math.round(point.y / options.gridSize) * options.gridSize,
        kind: "grid",
      });
    }
  }

  const inRange = candidates
    .filter((candidate) => candidate.distance <= options.threshold)
    .sort((a, b) => snapPriority[a.kind] - snapPriority[b.kind] || a.distance - b.distance)[0];
  if (inRange) return { x: inRange.x, y: inRange.y, kind: inRange.kind };

  if (options.ortho && options.basePoint) {
    const dx = Math.abs(point.x - options.basePoint.x);
    const dy = Math.abs(point.y - options.basePoint.y);
    return dx >= dy
      ? { x: point.x, y: options.basePoint.y, kind: "orthogonal" }
      : { x: options.basePoint.x, y: point.y, kind: "orthogonal" };
  }

  return { ...point, kind: options.enabled && options.gridSize ? "grid" : "nearest" };
}

export function transformGeometry(
  geometry: CadTuple2D[],
  kind: "move" | "rotate" | "scale",
  value: number,
  origin?: CadPoint2D,
): CadOperationResult<CadTuple2D[]> {
  if (!Array.isArray(geometry) || !geometry.length) return { ok: false, reason: "No editable geometry points are available." };
  const center = origin ?? geometry.reduce((sum, point) => ({ x: sum.x + point[0], y: sum.y + point[1] }), { x: 0, y: 0 });
  center.x /= geometry.length;
  center.y /= geometry.length;
  if (kind === "move") {
    return { ok: true, value: geometry.map(([x, y]) => [roundCoord(x + value), roundCoord(y + value)] as CadTuple2D) };
  }
  if (kind === "rotate") {
    const radians = (value * Math.PI) / 180;
    const cos = Math.cos(radians);
    const sin = Math.sin(radians);
    return {
      ok: true,
      value: geometry.map(([x, y]) => {
        const dx = x - center.x;
        const dy = y - center.y;
        return [roundCoord(center.x + dx * cos - dy * sin), roundCoord(center.y + dx * sin + dy * cos)] as CadTuple2D;
      }),
    };
  }
  if (value <= 0 || !Number.isFinite(value)) return { ok: false, reason: "Scale requires a positive factor." };
  return {
    ok: true,
    value: geometry.map(([x, y]) => [roundCoord(center.x + (x - center.x) * value), roundCoord(center.y + (y - center.y) * value)] as CadTuple2D),
  };
}

export function offsetGeometry(
  geometry: CadTuple2D[],
  distanceFt: number,
  closed: boolean,
): CadOperationResult<CadTuple2D[]> {
  if (!Number.isFinite(distanceFt) || Math.abs(distanceFt) < EPSILON) return { ok: false, reason: "Offset requires a non-zero distance." };
  if (geometry.length < 2) return { ok: false, reason: "Offset requires a line or polygon with at least two points." };
  const sign = closed && signedPolygonArea(geometry) < 0 ? -1 : 1;
  const shiftedSegments = geometry.map((point, index) => {
    if (!closed && index === geometry.length - 1) return null;
    const next = geometry[(index + 1) % geometry.length];
    const dir = normalize(next[0] - point[0], next[1] - point[1]);
    if (!dir) return null;
    const normal = { x: -dir.y * distanceFt * sign, y: dir.x * distanceFt * sign };
    return {
      a: { x: point[0] + normal.x, y: point[1] + normal.y },
      b: { x: next[0] + normal.x, y: next[1] + normal.y },
    };
  }).filter(Boolean) as Array<{ a: CadPoint2D; b: CadPoint2D }>;
  if (shiftedSegments.length < 1) return { ok: false, reason: "Offset blocked because the selected geometry has zero-length segment(s)." };
  if (!closed) {
    const out: CadTuple2D[] = [pointToTuple(shiftedSegments[0].a)];
    shiftedSegments.forEach((segment, index) => {
      if (index === shiftedSegments.length - 1) out.push(pointToTuple(segment.b));
      else {
        const hit = segmentIntersection(segment.a, segment.b, shiftedSegments[index + 1].a, shiftedSegments[index + 1].b, { extendAB: true, extendCD: true });
        out.push(pointToTuple(hit ?? segment.b));
      }
    });
    return { ok: true, value: out };
  }
  const out = shiftedSegments.map((segment, index) => {
    const prev = shiftedSegments[(index - 1 + shiftedSegments.length) % shiftedSegments.length];
    return pointToTuple(segmentIntersection(prev.a, prev.b, segment.a, segment.b, { extendAB: true, extendCD: true }) ?? segment.a);
  });
  return { ok: true, value: out, warnings: validatePolygon(out).issues };
}

export function trimOrExtendGeometry(
  geometry: CadTuple2D[],
  kind: "trim" | "extend",
  segments: CadSegment2D[],
  options: { amountFt: number; selectedObjectId?: string; siteWidth: number; siteHeight: number },
): CadOperationResult<CadTuple2D[]> {
  if (geometry.length < 2) return { ok: false, reason: `${kind} requires line geometry with at least two points.` };
  const nextGeometry = geometry.map((point) => [...point] as CadTuple2D);
  const last = tupleToPoint(nextGeometry[nextGeometry.length - 1]);
  const prev = tupleToPoint(nextGeometry[nextGeometry.length - 2]);
  const dx = last.x - prev.x;
  const dy = last.y - prev.y;
  const len = vectorLength(dx, dy);
  if (len < EPSILON) return { ok: false, reason: `${kind} blocked because the terminal segment has zero length.` };
  const targetSegments = segments.filter((segment) => segment.objectId !== options.selectedObjectId);
  const lineEnd = kind === "extend"
    ? { x: last.x + (dx / len) * Math.max(options.amountFt, 1), y: last.y + (dy / len) * Math.max(options.amountFt, 1) }
    : { x: last.x - (dx / len) * Math.max(options.amountFt, 1), y: last.y - (dy / len) * Math.max(options.amountFt, 1) };
  let bestHit: { point: CadPoint2D; distance: number } | null = null;
  for (const segment of targetSegments) {
    const hit = segmentIntersection(prev, lineEnd, segment.a, segment.b, { extendAB: kind === "extend" });
    if (!hit) continue;
    const hitDistance = distance(last, hit);
    if (hitDistance < EPSILON) continue;
    if (!bestHit || hitDistance < bestHit.distance) bestHit = { point: hit, distance: hitDistance };
  }
  const next = bestHit?.point ?? lineEnd;
  if (next.x < -EPSILON || next.y < -EPSILON || next.x > options.siteWidth + EPSILON || next.y > options.siteHeight + EPSILON) {
    return { ok: false, reason: `${kind} would leave the locked site extents.` };
  }
  nextGeometry[nextGeometry.length - 1] = pointToTuple(next);
  if (kind === "trim" && distance(prev, next) < 1) return { ok: false, reason: "Trim would collapse the selected segment." };
  return { ok: true, value: nextGeometry };
}

export function filletGeometry(
  geometry: CadTuple2D[],
  radiusFt: number,
  index: number,
  closed: boolean,
): CadOperationResult<CadTuple2D[]> {
  if (!Number.isFinite(radiusFt) || radiusFt <= 0) return { ok: false, reason: "Fillet requires a positive radius." };
  if (geometry.length < 3) return { ok: false, reason: "Fillet requires at least three vertices." };
  if (!closed && (index <= 0 || index >= geometry.length - 1)) return { ok: false, reason: "Fillet cannot be applied to an open endpoint." };
  const current = geometry[index];
  const prev = geometry[(index - 1 + geometry.length) % geometry.length];
  const next = geometry[(index + 1) % geometry.length];
  const v1 = normalize(prev[0] - current[0], prev[1] - current[1]);
  const v2 = normalize(next[0] - current[0], next[1] - current[1]);
  if (!v1 || !v2) return { ok: false, reason: "Fillet blocked by duplicate or zero-length adjacent vertices." };
  const len1 = distance(tupleToPoint(current), tupleToPoint(prev));
  const len2 = distance(tupleToPoint(current), tupleToPoint(next));
  const step = Math.min(radiusFt, len1 / 2, len2 / 2);
  if (step < EPSILON) return { ok: false, reason: "Fillet radius is too small for this corner." };
  const tangentA: CadTuple2D = [roundCoord(current[0] + v1.x * step), roundCoord(current[1] + v1.y * step)];
  const tangentB: CadTuple2D = [roundCoord(current[0] + v2.x * step), roundCoord(current[1] + v2.y * step)];
  const out = geometry.map((point) => [...point] as CadTuple2D);
  out.splice(index, 1, tangentA, tangentB);
  return { ok: true, value: out, warnings: ["Fillet is stored as tangent chord vertices for draft review, not a certified curve."] };
}

export function cleanupPolygon(points: CadTuple2D[], tolerance = 0.1): CadOperationResult<CadTuple2D[]> {
  if (points.length < 3) return { ok: false, reason: "Polygon needs at least three vertices." };
  const cleaned: CadTuple2D[] = [];
  points.forEach((point) => {
    const last = cleaned[cleaned.length - 1];
    if (!last || distance(tupleToPoint(last), tupleToPoint(point)) > tolerance) cleaned.push(pointToTuple(tupleToPoint(point)));
  });
  if (cleaned.length > 2 && distance(tupleToPoint(cleaned[0]), tupleToPoint(cleaned[cleaned.length - 1])) <= tolerance) {
    cleaned.pop();
  }
  if (cleaned.length < 3) return { ok: false, reason: "Polygon cleanup collapsed below three vertices." };
  const validation = validatePolygon(cleaned);
  if (validation.selfIntersections.length) return { ok: false, reason: `Polygon self-intersects at segment ${validation.selfIntersections[0].join("-")}.` };
  return { ok: true, value: cleaned, warnings: validation.issues };
}

export function validatePolygon(points: CadTuple2D[]) {
  const issues: string[] = [];
  const selfIntersections: Array<[number, number]> = [];
  if (points.length < 3) issues.push("polygon_requires_three_vertices");
  if (Math.abs(signedPolygonArea(points)) < EPSILON) issues.push("polygon_area_is_zero");
  for (let i = 0; i < points.length; i += 1) {
    const a = tupleToPoint(points[i]);
    const b = tupleToPoint(points[(i + 1) % points.length]);
    if (distance(a, b) < EPSILON) issues.push("duplicate_or_zero_length_polygon_edge");
    for (let j = i + 1; j < points.length; j += 1) {
      if (Math.abs(i - j) <= 1 || (i === 0 && j === points.length - 1)) continue;
      const hit = segmentIntersection(a, b, tupleToPoint(points[j]), tupleToPoint(points[(j + 1) % points.length]));
      if (hit) selfIntersections.push([i, j]);
    }
  }
  if (selfIntersections.length) issues.push("polygon_self_intersection");
  return { ok: issues.length === 0, issues: Array.from(new Set(issues)), selfIntersections };
}

export function validateTopology(objects: Array<{ id: string; type?: string; geometryType?: string; geometry?: CadTuple2D[]; x?: number; y?: number; w?: number; d?: number }>) {
  const issues: Array<{ code: string; objectIds: string[]; message: string }> = [];
  const lineObjects = objects.filter((item) => item.geometryType === "polyline" && Array.isArray(item.geometry) && item.geometry.length >= 2);
  const polygonObjects = objects.filter((item) => item.geometryType === "polygon" && Array.isArray(item.geometry));
  lineObjects.forEach((line) => {
    const pts = line.geometry ?? [];
    const connected = lineObjects.some((other) => other.id !== line.id && (other.geometry ?? []).some((pt) => pts.some((own) => distance(tupleToPoint(pt), tupleToPoint(own)) < 0.1)));
    if (!connected && String(line.type || "").toLowerCase().includes("utility")) {
      issues.push({ code: "disconnected_utility_segment", objectIds: [line.id], message: "Utility segment is disconnected from other visible utility geometry." });
    }
  });
  polygonObjects.forEach((polygon) => {
    const validation = validatePolygon(polygon.geometry ?? []);
    if (!validation.ok) {
      const kind = String(polygon.type || "").toLowerCase().includes("road") ? "invalid_road_loop" : String(polygon.type || "").toLowerCase().includes("basin") ? "invalid_basin_polygon" : "invalid_polygon";
      issues.push({ code: kind, objectIds: [polygon.id], message: validation.issues.join(", ") });
    }
  });
  objects.forEach((a, i) => {
    objects.slice(i + 1).forEach((b) => {
      const ax = a.x ?? 0;
      const ay = a.y ?? 0;
      const bx = b.x ?? 0;
      const by = b.y ?? 0;
      if (ax < bx + (b.w ?? 0) && ax + (a.w ?? 0) > bx && ay < by + (b.d ?? 0) && ay + (a.d ?? 0) > by) {
        issues.push({ code: "overlapping_site_objects", objectIds: [a.id, b.id], message: "Site object bounding boxes overlap and need review." });
      }
    });
  });
  return issues;
}
