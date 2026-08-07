import type { BuildingPlacement, SiteObjectType } from "../types";
import { parsePositiveNumber } from "./formatting";
import { SITE_OBJECT_CATALOG } from "./siteObjectCatalog";

type AddObjectOptions = {
  label?: string;
  style?: Record<string, string>;
  geometryType?: "polygon" | "polyline" | "rect";
  placed?: boolean;
  width?: number;
  depth?: number;
  stallCount?: number;
  meta?: Record<string, unknown>;
};

type LotBounds = {
  w: number;
  h: number;
};

type ParkingControls = {
  parkingCount: string;
  parkingStallWidth: string;
  parkingStallDepth: string;
  parkingAisleWidth: string;
  parkingAdaAisleWidth: string;
  parkingAdaCount: string;
  parkingCompactCount: string;
  parkingCompactWidth: string;
  parkingAngle: string;
  parkingLoading: "single" | "double";
};

type BuiltParkingParams = {
  stallWidth: number;
  stallDepth: number;
  aisleWidth: number;
  adaAisleWidth: number;
  adaCount: number;
  compactCount: number;
  compactWidth: number;
  angleDeg: number;
  loading: "single" | "double";
  autoResizeToFitCount: boolean;
  useMixedAngles: boolean;
  compactZone: boolean;
};

type BuildObjectPlacementInput = {
  type: SiteObjectType;
  options?: AddObjectOptions;
  lot: LotBounds;
  existingPlacements?: BuildingPlacement[];
  existingCount: number;
  defaultDimensions: { w: number; d: number };
  fallbackLabel: string;
  parkingControls: ParkingControls;
  computeParkingFootprint: (
    placement: BuildingPlacement,
    params: BuiltParkingParams,
    stallCount: number,
  ) => { maxStalls: number; moduleCols: number; moduleRows: number };
};

function createPlacementId(type: SiteObjectType) {
  return `${type}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function clampPlacement(value: number, size: number, total: number) {
  return Math.min(Math.max(value, 24), Math.max(24, total - size - 24));
}

function placementBounds(item: BuildingPlacement) {
  if (!item.placed || typeof item.x !== "number" || typeof item.y !== "number" || item.type === "site") {
    return null;
  }
  return {
    x: item.x,
    y: item.y,
    w: Math.max(item.w || 1, 1),
    d: Math.max(item.d || 1, 1),
  };
}

function overlapArea(
  a: { x: number; y: number; w: number; d: number },
  b: { x: number; y: number; w: number; d: number },
  padding: number,
) {
  const left = Math.max(a.x - padding, b.x - padding);
  const right = Math.min(a.x + a.w + padding, b.x + b.w + padding);
  const top = Math.max(a.y - padding, b.y - padding);
  const bottom = Math.min(a.y + a.d + padding, b.y + b.d + padding);
  return Math.max(0, right - left) * Math.max(0, bottom - top);
}

function clearPlacementScore(
  candidate: { x: number; y: number; w: number; d: number },
  existingPlacements: BuildingPlacement[],
  padding: number,
) {
  return existingPlacements.reduce((score, item) => {
    const bounds = placementBounds(item);
    if (!bounds) return score;
    return score + overlapArea(candidate, bounds, padding);
  }, 0);
}

function resolveSmartPlacement({
  type,
  lot,
  existingCount,
  width,
  depth,
  network,
  existingPlacements,
}: {
  type: SiteObjectType;
  lot: LotBounds;
  existingCount: number;
  width: number;
  depth: number;
  network: string;
  existingPlacements: BuildingPlacement[];
}) {
  const typeKey = type === "office_building" ? "building" : type;
  const offset = Math.max(0, existingCount - 1);
  const candidates: Array<{ x: number; y: number }> = [];
  const addCandidate = (x: number, y: number) => {
    candidates.push({
      x: clampPlacement(x, width, lot.w),
      y: clampPlacement(y, depth, lot.h),
    });
  };
  if (typeKey === "building") {
    addCandidate(lot.w * 0.36 + offset * 18, lot.h * 0.16 + offset * 14);
    addCandidate(lot.w * 0.56, lot.h * 0.18);
    addCandidate(lot.w * 0.16, lot.h * 0.18);
  } else if (typeKey === "parking") {
    addCandidate(lot.w * 0.18 + offset * 18, lot.h * 0.40 + offset * 10);
    addCandidate(lot.w * 0.46, lot.h * 0.42);
    addCandidate(lot.w * 0.18, lot.h * 0.66);
  } else if (typeKey === "basin") {
    addCandidate(lot.w * 0.66, lot.h * 0.50);
    addCandidate(lot.w * 0.70, lot.h * 0.68);
    addCandidate(lot.w * 0.08, lot.h * 0.68);
  } else if (typeKey === "outfall") {
    addCandidate(lot.w * 0.86, lot.h * 0.62);
    addCandidate(lot.w * 0.86, lot.h * 0.78);
  } else if (typeKey === "inlet" || typeKey === "manhole" || typeKey === "hydrant") {
    const defaultX =
      typeKey === "inlet" ? 0.58 : typeKey === "manhole" ? 0.72 : 0.30 + Math.min(offset, 3) * 0.10;
    addCandidate(lot.w * defaultX, lot.h * (typeKey === "hydrant" ? 0.30 : 0.46));
    addCandidate(lot.w * 0.78, lot.h * 0.72);
  } else if (typeKey === "driveway" || typeKey === "road" || typeKey === "entrance") {
    addCandidate(lot.w * 0.04, lot.h * 0.42);
    addCandidate(lot.w * 0.04, lot.h * 0.56);
  } else if (typeKey === "sidewalk") {
    addCandidate(lot.w * 0.18, lot.h * 0.40);
    addCandidate(lot.w * 0.16, lot.h * 0.58);
  } else if (typeKey === "utility_corridor") {
    const yFactor = network === "water" ? 0.28 : network === "sanitary" ? 0.78 : network === "storm" ? 0.58 : 0.68;
    addCandidate(lot.w * 0.08, lot.h * yFactor);
  } else {
    addCandidate(existingCount * 24, existingCount * 18);
  }

  [0.08, 0.30, 0.54, 0.74].forEach((xFactor) => {
    [0.12, 0.32, 0.54, 0.74].forEach((yFactor) => addCandidate(lot.w * xFactor, lot.h * yFactor));
  });

  let best = candidates[0] ?? { x: 24, y: 24 };
  let bestScore = Number.POSITIVE_INFINITY;
  candidates.forEach((candidate) => {
    const score = clearPlacementScore({ ...candidate, w: width, d: depth }, existingPlacements, 12);
    if (score < bestScore) {
      best = candidate;
      bestScore = score;
    }
  });
  return {
    x: best.x,
    y: best.y,
  };
}

export function buildDashboardSitePlacement({
  width,
  height,
}: {
  width: number;
  height: number;
}): BuildingPlacement {
  return {
    id: createPlacementId("site"),
    label: SITE_OBJECT_CATALOG.site.label,
    type: "site",
    w: width,
    d: height,
    x: 0,
    y: 0,
    rotation: 0,
    locked: true,
    placed: true,
    source: "user",
    generated: false,
    capabilities: {
      movable: false,
      resizable: false,
      rotatable: false,
      deletable: false,
    },
    systemDependencies: ["roads", "parking", "grading", "drainage", "utilities"],
    meta: { category: SITE_OBJECT_CATALOG.site.category },
  };
}

export function buildDashboardObjectPlacement({
  type,
  options,
  lot,
  existingPlacements = [],
  existingCount,
  defaultDimensions,
  fallbackLabel,
  parkingControls,
  computeParkingFootprint,
}: BuildObjectPlacementInput): BuildingPlacement {
  const catalog = SITE_OBJECT_CATALOG[type];
  const defaults = {
    ...defaultDimensions,
    ...(options?.width ? { w: options.width } : {}),
    ...(options?.depth ? { d: options.depth } : {}),
  };
  const network = String(options?.meta?.network || "").toLowerCase();
  const smartPlacement = resolveSmartPlacement({
    type,
    lot,
    existingCount,
    width: defaults.w,
    depth: defaults.d,
    network,
    existingPlacements,
  });
  const requestedParkingStalls = options?.meta?.requested_stalls;
  const parkingStalls =
    type === "parking"
      ? parsePositiveNumber(options?.stallCount)
        ?? parsePositiveNumber(
          typeof requestedParkingStalls === "number" || typeof requestedParkingStalls === "string"
            ? requestedParkingStalls
            : null,
        )
        ?? parsePositiveNumber(parkingControls.parkingCount)
        ?? 0
      : undefined;
  const parkingParams =
    type === "parking"
      ? {
          stallWidth: parsePositiveNumber(parkingControls.parkingStallWidth) ?? 9,
          stallDepth: parsePositiveNumber(parkingControls.parkingStallDepth) ?? 18,
          aisleWidth: parsePositiveNumber(parkingControls.parkingAisleWidth) ?? 24,
          adaAisleWidth: parsePositiveNumber(parkingControls.parkingAdaAisleWidth) ?? 8,
          adaCount: parsePositiveNumber(parkingControls.parkingAdaCount) ?? 0,
          compactCount: parsePositiveNumber(parkingControls.parkingCompactCount) ?? 0,
          compactWidth: parsePositiveNumber(parkingControls.parkingCompactWidth) ?? 8,
          angleDeg: parsePositiveNumber(parkingControls.parkingAngle) ?? 90,
          loading: parkingControls.parkingLoading,
          autoResizeToFitCount: false,
          useMixedAngles: false,
          compactZone: true,
        }
      : null;
  const nextPlacement: BuildingPlacement = {
    id: createPlacementId(type),
    label: options?.label ?? fallbackLabel,
    type,
    use: catalog.use,
    w: defaults.w,
    d: defaults.d,
    h: catalog.defaultH ?? 0,
    x: options?.placed ? smartPlacement.x : undefined,
    y: options?.placed ? smartPlacement.y : undefined,
    rotation: 0,
    stallCount: parkingStalls,
    locked: false,
    placed: Boolean(options?.placed),
    source: "user",
    generated: false,
    capabilities: {
      movable: true,
      resizable: true,
      rotatable: true,
      deletable: true,
    },
    systemDependencies: ["roads", "parking", "grading", "drainage", "utilities"],
    meta: {
      category: catalog.category,
      ...(parkingParams ? { parkingParams } : {}),
      ...(options?.style ? { style: options.style } : {}),
      ...(options?.meta ?? {}),
    },
  };
  if (type === "parking" && parkingParams) {
    const totalStalls = Math.max(
      parkingStalls ?? 0,
      parkingParams.adaCount + parkingParams.compactCount,
    );
    const footprint = computeParkingFootprint(nextPlacement, parkingParams, totalStalls);
    nextPlacement.meta = {
      ...nextPlacement.meta,
      parkingCapacity: footprint.maxStalls,
      parkingModuleCols: footprint.moduleCols,
      parkingModuleRows: footprint.moduleRows,
    };
  }
  if (["road", "driveway", "sidewalk"].includes(type)) {
    nextPlacement.geometryType = "polyline";
    const yFactor = type === "sidewalk" ? 0.42 : 0.72;
    const endXFactor = type === "sidewalk" ? 0.64 : 0.54;
    nextPlacement.geometry = [
      [lot.w * 0.04, lot.h * yFactor],
      [lot.w * 0.24, lot.h * yFactor],
      [lot.w * endXFactor, lot.h * (type === "sidewalk" ? 0.42 : 0.54)],
    ];
    nextPlacement.capabilities = {
      movable: true,
      resizable: false,
      rotatable: false,
      deletable: true,
    };
  }
  if (options?.geometryType === "polyline") {
    nextPlacement.geometryType = "polyline";
    const yFactor = network === "water" ? 0.28 : network === "sanitary" ? 0.78 : network === "storm" ? 0.58 : 0.68;
    const startX = network === "water" ? 0.08 : network === "sanitary" ? 0.10 : 0.52;
    const endX = network === "water" ? 0.88 : network === "sanitary" ? 0.86 : 0.86;
    const rightSideRun =
      network === "storm"
        ? ([
            [lot.w * endX, lot.h * yFactor],
            [lot.w * endX, lot.h * 0.62],
          ] as Array<[number, number]>)
        : [];
    nextPlacement.geometry = [
      [lot.w * startX, lot.h * yFactor],
      [lot.w * ((startX + endX) / 2), lot.h * yFactor],
      [lot.w * endX, lot.h * yFactor],
      ...rightSideRun,
    ];
    nextPlacement.capabilities = {
      movable: true,
      resizable: false,
      rotatable: false,
      deletable: true,
    };
  } else if (options?.geometryType === "polygon") {
    nextPlacement.geometryType = "polygon";
    const originX = nextPlacement.x ?? 0;
    const originY = nextPlacement.y ?? 0;
    nextPlacement.geometry = [
      [originX, originY],
      [originX + nextPlacement.w, originY],
      [originX + nextPlacement.w * 0.82, originY + nextPlacement.d],
      [originX + nextPlacement.w * 0.18, originY + nextPlacement.d],
    ];
  }
  return nextPlacement;
}
