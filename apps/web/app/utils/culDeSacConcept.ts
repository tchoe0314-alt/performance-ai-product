/** Isolated concept model. No approvals, setbacks or production project writes. */
export type ConceptLayout = {
  schemaVersion: 1; units: "ft"; kind: "cul-de-sac-study";
  roadWidth: number; bulbRadius: number; islandRadius: number; transitionRadius: number;
  position: { x: number; y: number };
  building: { x: number; y: number; w: number; d: number };
};
export type ConceptState = ConceptLayout & { revision: number; isStale: boolean };
export type ConceptIssue = { code: "pavement_contact" | "island_contact"; objectIds: string[]; message: string };
type Point = { x: number; y: number };
type Rect = Point & { w: number; d: number };
type Arc = Point & { r: number; start: number; sweep: number };
const EPS = 1e-7; // feet, floating-point contact tolerance, not a design setback
const TAU = Math.PI * 2;

export function defaultLayout(): ConceptLayout {
  return { schemaVersion: 1, units: "ft", kind: "cul-de-sac-study", roadWidth: 30,
    bulbRadius: 50, islandRadius: 15, transitionRadius: 20,
    position: { x: 0, y: 0 }, building: { x: 60, y: 0, w: 20, d: 20 } };
}

/** Strict, bounded input; copy known fields, never accept cached results. */
export function parseLayout(value: unknown): ConceptLayout {
  if (!value || typeof value !== "object") throw new Error("Layout must be an object.");
  const s = value as Record<string, unknown>;
  const number = (v: unknown, min: number, max: number) => typeof v === "number" && Number.isFinite(v) && v >= min && v <= max;
  const p = s.position as Point | undefined, b = s.building as Rect | undefined;
  if (s.schemaVersion !== 1 || s.units !== "ft" || s.kind !== "cul-de-sac-study" ||
      !number(s.roadWidth, 20, 48) || !number(s.bulbRadius, 35, 80) ||
      s.islandRadius !== 15 || s.transitionRadius !== 20 ||
      !p || !number(p.x, -100, 100) || !number(p.y, -80, 80) ||
      !b || !number(b.x, -150, 150) || !number(b.y, -120, 300) || b.w !== 20 || b.d !== 20) {
    throw new Error("Unsupported schema, units, or dimensions. Expected a version 1 feet-based concept layout.");
  }
  return { schemaVersion: 1, units: "ft", kind: "cul-de-sac-study", roadWidth: s.roadWidth as number,
    bulbRadius: s.bulbRadius as number, islandRadius: 15, transitionRadius: 20,
    position: { x: p.x, y: p.y }, building: { x: b.x, y: b.y, w: 20, d: 20 } };
}

export function serializeLayout(state: ConceptLayout): string { return JSON.stringify(parseLayout(state), null, 2); }

export function geometry(R: number, W: number, f = 20) {
  const a = W / 2, x = a + f, y = Math.sqrt((R + f) ** 2 - x * x), theta = Math.atan2(y, x);
  return { R, W, f, a, x, y, theta, tx: R * x / (R + f), ty: R * y / (R + f), bottom: y + 110 };
}

function contains(rect: Rect, point: Point) {
  return point.x >= rect.x - EPS && point.x <= rect.x + rect.w + EPS &&
    point.y >= rect.y - EPS && point.y <= rect.y + rect.d + EPS;
}

function onArc(arc: Arc, point: Point) {
  const angle = Math.atan2(point.y - arc.y, point.x - arc.x);
  const distance = arc.sweep >= 0 ? angle - arc.start : arc.start - angle;
  const progress = ((distance % TAU) + TAU) % TAU;
  return progress <= Math.abs(arc.sweep) + EPS / arc.r || TAU - progress <= EPS / arc.r;
}

function arcTouchesRect(arc: Arc, rect: Rect) {
  const start = { x: arc.x + arc.r * Math.cos(arc.start), y: arc.y + arc.r * Math.sin(arc.start) };
  const end = { x: arc.x + arc.r * Math.cos(arc.start + arc.sweep), y: arc.y + arc.r * Math.sin(arc.start + arc.sweep) };
  if (contains(rect, start) || contains(rect, end)) return true;
  for (const x of [rect.x, rect.x + rect.w]) {
    const h2 = arc.r ** 2 - (x - arc.x) ** 2;
    if (h2 < -EPS * arc.r * 2) continue;
    for (const y of [arc.y - Math.sqrt(Math.max(0, h2)), arc.y + Math.sqrt(Math.max(0, h2))]) {
      if (contains(rect, { x, y }) && onArc(arc, { x, y })) return true;
    }
  }
  for (const y of [rect.y, rect.y + rect.d]) {
    const h2 = arc.r ** 2 - (y - arc.y) ** 2;
    if (h2 < -EPS * arc.r * 2) continue;
    for (const x of [arc.x - Math.sqrt(Math.max(0, h2)), arc.x + Math.sqrt(Math.max(0, h2))]) {
      if (contains(rect, { x, y }) && onArc(arc, { x, y })) return true;
    }
  }
  return false;
}

export function pointInRoad(point: Point, layout: ConceptLayout, includeIsland = false) {
  const g = geometry(layout.bulbRadius, layout.roadWidth, layout.transitionRadius);
  const x = point.x - layout.position.x, y = point.y - layout.position.y;
  if (y < -g.R - EPS || y > g.bottom + EPS) return false;
  const extent = y <= g.ty ? Math.sqrt(Math.max(0, g.R ** 2 - y ** 2)) :
    y < g.y ? g.x - Math.sqrt(Math.max(0, g.f ** 2 - (y - g.y) ** 2)) : g.a;
  return Math.abs(x) <= extent + EPS && (includeIsland || Math.hypot(x, y) >= layout.islandRadius - EPS);
}

/** Analytic line/arc contact, not sampled polylines or rendered pixels. */
export function checkConcept(layout: ConceptLayout): ConceptIssue[] {
  const g = geometry(layout.bulbRadius, layout.roadWidth, layout.transitionRadius);
  const b = { ...layout.building, x: layout.building.x - layout.position.x, y: layout.building.y - layout.position.y };
  const arcs: Arc[] = [
    { x: -g.x, y: g.y, r: g.f, start: 0, sweep: -g.theta },
    { x: 0, y: 0, r: g.R, start: Math.PI - g.theta, sweep: Math.PI + 2 * g.theta },
    { x: g.x, y: g.y, r: g.f, start: -Math.PI + g.theta, sweep: -g.theta },
  ];
  const corners = [{ x: b.x, y: b.y }, { x: b.x + b.w, y: b.y },
    { x: b.x, y: b.y + b.d }, { x: b.x + b.w, y: b.y + b.d }];
  const local = { ...layout, position: { x: 0, y: 0 } };
  const verticalHit = (x: number) => x >= b.x - EPS && x <= b.x + b.w + EPS &&
    g.y <= b.y + b.d + EPS && g.bottom >= b.y - EPS;
  const bottomHit = g.bottom >= b.y - EPS && g.bottom <= b.y + b.d + EPS &&
    -g.a <= b.x + b.w + EPS && g.a >= b.x - EPS;
  const island: Arc = { x: 0, y: 0, r: layout.islandRadius, start: 0, sweep: TAU };
  const pavement = corners.some(p => pointInRoad(p, local)) || arcs.some(a => arcTouchesRect(a, b)) ||
    verticalHit(-g.a) || verticalHit(g.a) || bottomHit || arcTouchesRect(island, b);
  const nearX = Math.max(b.x, Math.min(0, b.x + b.w));
  const nearY = Math.max(b.y, Math.min(0, b.y + b.d));
  const islandContact = Math.hypot(nearX, nearY) <= layout.islandRadius + EPS;
  const issues: ConceptIssue[] = [];
  if (pavement) issues.push({ code: "pavement_contact", objectIds: ["concept-road", "test-building"], message: "Building touches or overlaps the asphalt pavement boundary." });
  if (islandContact) issues.push({ code: "island_contact", objectIds: ["concept-island", "test-building"], message: "Building touches or overlaps the landscaped island." });
  return issues;
}
