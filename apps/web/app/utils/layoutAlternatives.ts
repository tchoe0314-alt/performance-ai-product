import type { BuildingPlacement } from "../types";
import { calculateParkingLayout, type ParkingLayoutInputs } from "./parkingLayoutEngine";
import type { ParkingParams } from "./previewGeometryTruth";
import { assessSiteInterference } from "./siteInterference";
import { canonicalControlState } from "./canonicalEditCommands";

export type LayoutAlternative = {
  id: string;
  label: string;
  description: string;
  placements: BuildingPlacement[];
  metrics: {
    requestedStalls: number;
    capacity: number;
    shortfall: number;
    conflicts: number;
    reviews: number;
    entranceDistance: number;
    roadLength: number;
    drainageMoved: number;
  };
  score: number;
  rank: number;
  scoreReasons: string[];
  goalLabels: string[];
  profile: "balanced" | "conservative" | "aggressive";
  differences: LayoutDifference[];
  fixedObjectCount: number;
  searchReport: {
    explored: number;
    accepted: number;
    rejected: number;
    rejectionReasons: string[];
  };
};

export type LayoutDifference = {
  id: string;
  label: string;
  before: BuildingPlacement;
  after: BuildingPlacement;
  moved: boolean;
  resized: boolean;
};

export type LayoutGoalKey =
  | "maximize_parking"
  | "minimize_conflicts"
  | "building_near_entrance"
  | "preserve_drainage"
  | "minimize_roadway";

export type LayoutGoal = {
  key: LayoutGoalKey;
  label: string;
  weight: number;
};

export type LayoutAlternativeRequest = {
  goals?: LayoutGoal[];
  profile?: "balanced" | "conservative" | "aggressive" | "mixed";
};

export type LayoutAlternativeSearch = {
  alternatives: LayoutAlternative[];
  candidatePool: LayoutAlternative[];
  requestedCount: number;
  searchReport: LayoutAlternative["searchReport"];
};

const GOAL_LABELS: Record<LayoutGoalKey, string> = {
  maximize_parking: "maximize parking",
  minimize_conflicts: "minimize conflicts",
  building_near_entrance: "keep buildings near the entrance",
  preserve_drainage: "preserve drainage features",
  minimize_roadway: "minimize roadway length",
};

export function parseLayoutGoals(message: string): LayoutAlternativeRequest {
  const normalized = message.toLowerCase().replace(/[-_]/g, " ").replace(/\s+/g, " ");
  const goals: LayoutGoal[] = [];
  const add = (key: LayoutGoalKey, weight = 1) => {
    if (!goals.some((goal) => goal.key === key)) goals.push({ key, label: GOAL_LABELS[key], weight });
  };
  if (/\b(maximi[sz]e|most|more|increase|fit)\b.{0,24}\bparking|\bparking\b.{0,20}\b(maximi[sz]e|priority|first)\b/.test(normalized)) add("maximize_parking", 1.25);
  if (/\b(minimi[sz]e|avoid|fewest|reduce|no)\b.{0,24}\b(conflicts?|collisions?|overlaps?)|\bconflict[- ]?free\b/.test(normalized)) add("minimize_conflicts", 1.35);
  if (/\b(buildings?|building)\b.{0,28}\b(near|close|by)\b.{0,16}\b(entrance|entry)|\b(entrance|entry)\b.{0,28}\b(buildings?)\b/.test(normalized)) add("building_near_entrance", 1);
  if (/\b(preserve|keep|protect|do not move|don't move)\b.{0,24}\b(drainage|detention|basin|pond|outfall)\b/.test(normalized)) add("preserve_drainage", 1.25);
  if (/\b(minimi[sz]e|shortest|reduce|less)\b.{0,24}\b(road|roadway|drive|pavement)\b/.test(normalized)) add("minimize_roadway", 1);
  const profile = /\bmix(?:ed)?\b|\bconservative\b.*\baggressive\b/.test(normalized)
    ? "mixed"
    : /\bconservative\b/.test(normalized)
      ? "conservative"
      : /\baggressive\b/.test(normalized)
        ? "aggressive"
        : "balanced";
  if (!goals.length) {
    add("minimize_conflicts", 1.2);
    add("maximize_parking", 1);
  }
  return { goals, profile };
}

const defaultParkingParams = (item: BuildingPlacement): ParkingLayoutInputs => {
  const params = (item.meta?.parkingParams as ParkingParams | undefined) ?? {};
  return {
    stallWidth: Number(params.stallWidth) || 9,
    stallDepth: Number(params.stallDepth) || 18,
    aisleWidth: Number(params.aisleWidth) || 24,
    adaAisleWidth: Number(params.adaAisleWidth) || 8,
    adaCount: Number(params.adaCount ?? item.meta?.adaCount) || 0,
    compactCount: Number(params.compactCount) || 0,
    compactWidth: Number(params.compactWidth) || 8,
    angleDeg: Number(params.angleDeg) || 90,
    loading: params.loading === "single" ? "single" : "double",
    autoResizeToFitCount: Boolean(params.autoResizeToFitCount),
    useMixedAngles: Boolean(params.useMixedAngles),
    compactZone: params.compactZone !== false,
  };
};

const clonePlacement = (item: BuildingPlacement): BuildingPlacement => ({
  ...item,
  geometry: item.geometry?.map(([x, y]) => [x, y] as [number, number]),
  meta: item.meta ? { ...item.meta } : item.meta,
  capabilities: item.capabilities ? { ...item.capabilities } : item.capabilities,
});

export function buildLayoutDifferences(source: BuildingPlacement[], preview: BuildingPlacement[]): LayoutDifference[] {
  const sourceById = new Map(source.map((item) => [item.id, item]));
  return preview.flatMap((after) => {
    const before = sourceById.get(after.id);
    if (!before) return [];
    const moved = Math.abs((after.x ?? 0) - (before.x ?? 0)) > 0.01 || Math.abs((after.y ?? 0) - (before.y ?? 0)) > 0.01;
    const resized = Math.abs(after.w - before.w) > 0.01 || Math.abs(after.d - before.d) > 0.01;
    return moved || resized ? [{ id: after.id, label: after.label, before: clonePlacement(before), after: clonePlacement(after), moved, resized }] : [];
  });
}

const centerOf = (item: BuildingPlacement) => ({ x: (item.x ?? 0) + item.w / 2, y: (item.y ?? 0) + item.d / 2 });
const distance = (a: { x: number; y: number }, b: { x: number; y: number }) => Math.hypot(a.x - b.x, a.y - b.y);
const isBuilding = (item: BuildingPlacement) => /building|office|retail|industrial|multifamily/.test(item.type ?? "");
const isDrainage = (item: BuildingPlacement) => ["basin", "outfall", "inlet"].includes(item.type ?? "");

function metricsFor(placements: BuildingPlacement[], source: BuildingPlacement[]) {
  const parkingReports = placements.filter((item) => item.type === "parking").map((item) =>
    calculateParkingLayout(item, defaultParkingParams(item), item.stallCount ?? 0),
  );
  const issues = assessSiteInterference(placements);
  const site = placements.find((item) => item.type === "site");
  const entrances = placements.filter((item) => item.type === "entrance");
  const fallbackEntrance = { x: (site?.x ?? 0) + (site?.w ?? 0) / 2, y: (site?.y ?? 0) + (site?.d ?? 0) };
  const entrancePoints = entrances.length ? entrances.map(centerOf) : [fallbackEntrance];
  const buildings = placements.filter(isBuilding);
  const entranceDistance = buildings.length
    ? buildings.reduce((sum, item) => sum + Math.min(...entrancePoints.map((point) => distance(centerOf(item), point))), 0) / buildings.length
    : 0;
  const roadLength = placements.filter((item) => item.type === "road" || item.type === "driveway").reduce((sum, item) => {
    if (item.geometry && item.geometry.length > 1) {
      return sum + item.geometry.slice(1).reduce((lineSum, point, index) => lineSum + distance({ x: point[0], y: point[1] }, { x: item.geometry![index][0], y: item.geometry![index][1] }), 0);
    }
    return sum + Math.max(item.w, item.d);
  }, 0);
  const sourceById = new Map(source.map((item) => [item.id, item]));
  const drainageMoved = placements.filter(isDrainage).filter((item) => {
    const original = sourceById.get(item.id);
    return original && (Math.abs((item.x ?? 0) - (original.x ?? 0)) > 0.01 || Math.abs((item.y ?? 0) - (original.y ?? 0)) > 0.01);
  }).length;
  return {
    requestedStalls: parkingReports.reduce((sum, report) => sum + report.requestedStalls, 0),
    capacity: parkingReports.reduce((sum, report) => sum + report.maxStalls, 0),
    shortfall: parkingReports.reduce((sum, report) => sum + report.shortfall, 0),
    conflicts: issues.filter((issue) => issue.severity === "conflict").length,
    reviews: issues.filter((issue) => issue.severity === "review").length,
    entranceDistance,
    roadLength,
    drainageMoved,
  };
}

function scoreAlternatives(alternatives: Omit<LayoutAlternative, "score" | "rank" | "scoreReasons">[], goals: LayoutGoal[]): LayoutAlternative[] {
  const ranges = <K extends keyof LayoutAlternative["metrics"]>(key: K) => {
    const values = alternatives.map((item) => item.metrics[key]);
    return { min: Math.min(...values), max: Math.max(...values) };
  };
  const capacityRange = ranges("capacity");
  const conflictRange = ranges("conflicts");
  const entranceRange = ranges("entranceDistance");
  const roadRange = ranges("roadLength");
  const drainageRange = ranges("drainageMoved");
  const higher = (value: number, range: { min: number; max: number }) => range.max === range.min ? 1 : (value - range.min) / (range.max - range.min);
  const lower = (value: number, range: { min: number; max: number }) => 1 - higher(value, range);
  const scored = alternatives.map((alternative) => {
    let weighted = 0;
    let totalWeight = 0;
    const reasons: string[] = [];
    goals.forEach((goal) => {
      let value = 0;
      let reason = "";
      if (goal.key === "maximize_parking") {
        value = higher(alternative.metrics.capacity, capacityRange);
        reason = `${alternative.metrics.capacity} calculated parking capacity`;
      } else if (goal.key === "minimize_conflicts") {
        value = lower(alternative.metrics.conflicts, conflictRange);
        reason = alternative.metrics.conflicts ? `${alternative.metrics.conflicts} geometry conflicts` : "no geometry conflicts found";
      } else if (goal.key === "building_near_entrance") {
        value = lower(alternative.metrics.entranceDistance, entranceRange);
        reason = `${Math.round(alternative.metrics.entranceDistance)} ft average building-to-entry distance`;
      } else if (goal.key === "preserve_drainage") {
        value = lower(alternative.metrics.drainageMoved, drainageRange);
        reason = alternative.metrics.drainageMoved ? `${alternative.metrics.drainageMoved} drainage features moved` : "drainage features preserved";
      } else if (goal.key === "minimize_roadway") {
        value = lower(alternative.metrics.roadLength, roadRange);
        reason = `${Math.round(alternative.metrics.roadLength)} ft conceptual roadway`;
      }
      weighted += value * goal.weight;
      totalWeight += goal.weight;
      reasons.push(reason);
    });
    return { ...alternative, score: Math.round(100 * weighted / Math.max(totalWeight, 1)), rank: 0, scoreReasons: reasons };
  });
  return scored.sort((a, b) => b.score - a.score || a.metrics.conflicts - b.metrics.conflicts || a.id.localeCompare(b.id, undefined, { numeric: true })).map((item, index) => ({ ...item, rank: index + 1 }));
}

export function rerankLayoutAlternatives(alternatives: LayoutAlternative[], requestedGoals: LayoutGoal[]): LayoutAlternative[] {
  const goals = requestedGoals.length ? requestedGoals : parseLayoutGoals("").goals!;
  return scoreAlternatives(
    alternatives.map((alternative) => ({
      ...alternative,
      goalLabels: goals.map((goal) => goal.label),
    })),
    goals,
  );
}

export function rerankLayoutSearch(search: LayoutAlternativeSearch, goals: LayoutGoal[]): LayoutAlternativeSearch {
  const candidatePool = rerankLayoutAlternatives(search.candidatePool, goals);
  return { ...search, candidatePool, alternatives: candidatePool.slice(0, search.requestedCount) };
}

function transformVariant(
  source: BuildingPlacement[],
  index: number,
  profile: "balanced" | "conservative" | "aggressive",
): BuildingPlacement[] {
  const site = source.find((item) => item.type === "site");
  const siteX = site?.x ?? 0;
  const siteY = site?.y ?? 0;
  const siteW = site?.w ?? 1000;
  const siteD = site?.d ?? 700;
  const clamp = (value: number, size: number, origin: number, span: number) =>
    Math.min(Math.max(value, origin + 12), Math.max(origin + 12, origin + span - size - 12));
  const intensity = profile === "conservative" ? 0.6 : profile === "aggressive" ? 1.4 : 1;
  return source.map((original, objectIndex) => {
    const item = clonePlacement(original);
    if (item.type === "site" || !item.placed || ["fixed", "existing", "reference"].includes(canonicalControlState(item))) return item;
    let dx = 0;
    let dy = 0;
    if (index === 1 && item.type === "parking") dy = 42 * intensity;
    if (index === 2 && item.type === "parking") dx = (objectIndex % 2 ? 48 : -48) * intensity;
    if (index === 3 && /building|office|retail|industrial|multifamily/.test(item.type ?? "")) dx = (objectIndex % 2 ? 34 : -34) * intensity;
    if (index === 4) {
      if (item.type === "parking") dy = (objectIndex % 2 ? -48 : 48) * intensity;
      if (/building|office|retail|industrial|multifamily/.test(item.type ?? "")) dx = (objectIndex % 2 ? -24 : 24) * intensity;
    }
    if (index >= VARIANTS.length) {
      const seed = (index + 1) * (objectIndex + 3);
      const waveX = Math.sin(seed * 12.9898) * 0.5 + Math.sin(seed * 3.17) * 0.5;
      const waveY = Math.cos(seed * 7.233) * 0.5 + Math.cos(seed * 2.41) * 0.5;
      if (item.type === "parking") {
        dx = waveX * 86 * intensity;
        dy = waveY * 72 * intensity;
      } else if (isBuilding(item)) {
        dx = waveX * 58 * intensity;
        dy = waveY * 46 * intensity;
      }
    }
    if (dx === 0 && dy === 0) return item;
    const rawX = (item.x ?? 0) + dx;
    const rawY = (item.y ?? 0) + dy;
    const nextX = clamp(rawX, item.w, siteX, siteW);
    const nextY = clamp(rawY, item.d, siteY, siteD);
    const moveX = nextX - (item.x ?? 0);
    const moveY = nextY - (item.y ?? 0);
    const parkingParams = item.type === "parking" && (index === 2 || index >= VARIANTS.length)
      ? { ...defaultParkingParams(item), angleDeg: index >= VARIANTS.length ? [45, 60, 90][index % 3] : 60, useMixedAngles: true }
      : null;
    return {
      ...item,
      x: nextX,
      y: nextY,
      geometry: item.geometry?.map(([x, y]) => [x + moveX, y + moveY] as [number, number]),
      meta: {
        ...(item.meta ?? {}),
        ...(parkingParams ? { parkingParams } : {}),
        alternative_preview: true,
        alternative_strategy: index,
        alternative_was_clamped: Math.abs(nextX - rawX) > 0.01 || Math.abs(nextY - rawY) > 0.01,
      },
    };
  });
}

const VARIANTS = [
  ["Balanced", "Preserves the current arrangement as the baseline."],
  ["Parking South", "Moves parking toward the lower site edge while preserving the program."],
  ["Angled Parking", "Tests 60-degree mixed parking and lateral circulation."],
  ["Building Shift", "Offsets building massing to test additional separation."],
  ["Distributed", "Spreads buildings and parking in opposite directions."],
] as const;

export function searchLayoutAlternatives(source: BuildingPlacement[], requestedCount: number, request: LayoutAlternativeRequest = {}): LayoutAlternativeSearch {
  const count = Math.max(2, Math.min(10, Math.floor(requestedCount) || 5));
  const invalidInputs: string[] = [];
  if (!source.some(item => item.type === "site" && item.placed)) invalidInputs.push("missing site boundary");
  const ids = new Set<string>();
  source.forEach(item => {
    if (!item.id || ids.has(item.id)) invalidInputs.push("missing or duplicate object identity");
    ids.add(item.id);
    if (!item.placed) return;
    if (![item.x ?? 0, item.y ?? 0, item.w, item.d, item.rotation ?? 0].every(Number.isFinite) || item.w <= 0 || item.d <= 0) invalidInputs.push(`invalid dimensions: ${item.id}`);
    if ((item.geometryType === "polygon" || item.geometryType === "polyline") && (!Array.isArray(item.geometry) || item.geometry.length < (item.geometryType === "polygon" ? 3 : 2) || item.geometry.some(point => !Array.isArray(point) || point.length < 2 || !point.slice(0, 2).every(Number.isFinite)))) invalidInputs.push(`invalid geometry: ${item.id}`);
  });
  if (invalidInputs.length) return {
    alternatives: [], candidatePool: [], requestedCount: count,
    searchReport: { explored: 0, accepted: 0, rejected: 0, rejectionReasons: [...new Set(invalidInputs)] },
  };
  const goals = request.goals?.length ? request.goals : parseLayoutGoals("").goals!;
  const requestProfile = request.profile ?? "balanced";
  const candidateCount = 32;
  const fixedObjectCount = source.filter((item) => ["fixed", "existing", "reference"].includes(canonicalControlState(item))).length;
  const candidates = Array.from({ length: candidateCount }, (_, index) => {
    const profile = requestProfile === "mixed" ? (index === 0 ? "conservative" : "aggressive") : requestProfile;
    const placements = transformVariant(source, index, profile);
    const preset = VARIANTS[index];
    return {
      id: `layout-alternative-${index + 1}`,
      label: preset?.[0] ?? `Search ${String(index - VARIANTS.length + 1).padStart(2, "0")}`,
      description: preset?.[1] ?? "A constraint-aware candidate explored by the feasibility search.",
      placements,
      metrics: metricsFor(placements, source),
      goalLabels: goals.map((goal) => goal.label),
      profile,
      differences: buildLayoutDifferences(source, placements),
      fixedObjectCount,
      searchReport: { explored: candidateCount, accepted: 0, rejected: 0, rejectionReasons: [] },
    };
  });
  const rejectionCounts = new Map<string, number>();
  const acceptable = candidates.filter((candidate) => {
    const reasons: string[] = [];
    if (candidate.placements.some((item) => item.meta?.alternative_was_clamped === true)) reasons.push("outside-site movement");
    if (candidate.metrics.conflicts > 0) reasons.push("modeled hard geometry conflicts");
    if (candidate.metrics.shortfall > 0) reasons.push(`required parking shortfall (${candidate.metrics.shortfall} stalls)`);
    reasons.forEach((reason) => rejectionCounts.set(reason, (rejectionCounts.get(reason) ?? 0) + 1));
    return reasons.length === 0;
  });
  const signatures = new Set<string>();
  const distinct = acceptable.filter((candidate) => {
    const signature = candidate.placements
      .filter((item) => item.type !== "site")
      .map((item) => `${item.id}:${Math.round(item.x ?? 0)}:${Math.round(item.y ?? 0)}:${Number((item.meta?.parkingParams as ParkingParams | undefined)?.angleDeg ?? 0)}`)
      .join("|");
    if (signatures.has(signature)) {
      rejectionCounts.set("near-duplicate layout", (rejectionCounts.get("near-duplicate layout") ?? 0) + 1);
      return false;
    }
    signatures.add(signature);
    return true;
  });
  const ranked = scoreAlternatives(distinct, goals);
  const rejected = candidateCount - distinct.length;
  const rejectionReasons = [...rejectionCounts.entries()].map(([reason, total]) => `${total} ${reason}`);
  const searchReport = { explored: candidateCount, accepted: distinct.length, rejected, rejectionReasons };
  const candidatePool = ranked.map((alternative, index) => ({
    ...alternative,
    rank: index + 1,
    searchReport,
  }));
  return { alternatives: candidatePool.slice(0, count), candidatePool, requestedCount: count, searchReport };
}

export function generateLayoutAlternatives(source: BuildingPlacement[], requestedCount: number, request: LayoutAlternativeRequest = {}): LayoutAlternative[] {
  return searchLayoutAlternatives(source, requestedCount, request).alternatives;
}
