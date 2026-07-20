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

function resolveSmartPlacement({
  type,
  lot,
  existingCount,
  width,
  depth,
  network,
}: {
  type: SiteObjectType;
  lot: LotBounds;
  existingCount: number;
  width: number;
  depth: number;
  network: string;
}) {
  const typeKey = type === "office_building" ? "building" : type;
  const offset = Math.max(0, existingCount - 1);
  if (typeKey === "building") {
    return {
      x: clampPlacement(lot.w * 0.36 + offset * 18, width, lot.w),
      y: clampPlacement(lot.h * 0.16 + offset * 14, depth, lot.h),
    };
  }
  if (typeKey === "parking") {
    return {
      x: clampPlacement(lot.w * 0.18 + offset * 18, width, lot.w),
      y: clampPlacement(lot.h * 0.40 + offset * 10, depth, lot.h),
    };
  }
  if (typeKey === "basin") {
    return {
      x: clampPlacement(lot.w * 0.66, width, lot.w),
      y: clampPlacement(lot.h * 0.50, depth, lot.h),
    };
  }
  if (typeKey === "outfall") {
    return {
      x: clampPlacement(lot.w * 0.86, width, lot.w),
      y: clampPlacement(lot.h * 0.62, depth, lot.h),
    };
  }
  if (typeKey === "inlet" || typeKey === "manhole" || typeKey === "hydrant") {
    const defaultX =
      typeKey === "inlet" ? 0.58 : typeKey === "manhole" ? 0.72 : 0.30 + Math.min(offset, 3) * 0.10;
    return {
      x: clampPlacement(lot.w * defaultX, width, lot.w),
      y: clampPlacement(lot.h * (typeKey === "hydrant" ? 0.30 : 0.46), depth, lot.h),
    };
  }
  if (typeKey === "driveway" || typeKey === "road" || typeKey === "entrance") {
    return {
      x: clampPlacement(lot.w * 0.04, width, lot.w),
      y: clampPlacement(lot.h * 0.42, depth, lot.h),
    };
  }
  if (typeKey === "sidewalk") {
    return {
      x: clampPlacement(lot.w * 0.18, width, lot.w),
      y: clampPlacement(lot.h * 0.40, depth, lot.h),
    };
  }
  if (typeKey === "utility_corridor") {
    const yFactor = network === "water" ? 0.28 : network === "sanitary" ? 0.78 : network === "storm" ? 0.58 : 0.68;
    return {
      x: clampPlacement(lot.w * 0.08, width, lot.w),
      y: clampPlacement(lot.h * yFactor, depth, lot.h),
    };
  }
  return {
    x: Math.min(Math.max(24, existingCount * 24), Math.max(24, lot.w - width - 24)),
    y: Math.min(Math.max(24, existingCount * 18), Math.max(24, lot.h - depth - 24)),
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
  });
  const parkingStalls =
    type === "parking" ? parsePositiveNumber(parkingControls.parkingCount) ?? 0 : undefined;
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
    nextPlacement.geometry = [
      [0, 0],
      [nextPlacement.w, 0],
      [nextPlacement.w * 0.82, nextPlacement.d],
      [nextPlacement.w * 0.18, nextPlacement.d],
    ];
  }
  return nextPlacement;
}
