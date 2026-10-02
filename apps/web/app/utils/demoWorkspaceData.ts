import type { BuildingPlacement, PlanResponse, SiteObjectType } from "../types";

export const DEMO_PROJECT_ID = "demo-pinecrest-mixed-use";

export function isSeededDemoProjectId(value?: string | null) {
  return String(value || "").trim() === DEMO_PROJECT_ID;
}

export function hasPreviewablePlanResult(result?: PlanResponse | null) {
  const actions = Array.isArray(result?.final_plan?.actions)
    ? result.final_plan.actions
    : [];
  return actions.some((item) => item && typeof item === "object");
}

export function isDemoWorkspaceQuery() {
  if (typeof window === "undefined") return false;
  if (window.location.pathname === "/demo/workspace") return true;
  const query = window.location.search || (window.location.href.includes("?") ? `?${window.location.href.split("?")[1]}` : "");
  const params = new URLSearchParams(query);
  const demoValue = params.get("demo") || params.get("ui_demo");
  return demoValue === "workspace" || demoValue === "1" || demoValue === "true";
}

export function isSeededDemoWorkspaceQuery() {
  if (typeof window === "undefined") return false;
  const query = window.location.search || (window.location.href.includes("?") ? `?${window.location.href.split("?")[1]}` : "");
  const params = new URLSearchParams(query);
  const explicitSeed =
    params.get("seedDemo") ||
    params.get("seededDemo") ||
    params.get("demoSeed") ||
    params.get("demo_seed");
  if (["1", "true", "yes", "pinecrest"].includes(String(explicitSeed || "").toLowerCase())) {
    return true;
  }
  const demoValue = params.get("demo") || params.get("ui_demo");
  return window.location.pathname !== "/demo/workspace" && (demoValue === "workspace" || demoValue === "1" || demoValue === "true");
}

export const createDemoPlacements = (): BuildingPlacement[] => [
  {
    id: "demo-site",
    label: "Pinecrest Commerce Center",
    type: "site",
    w: 1000,
    d: 700,
    x: 0,
    y: 0,
    rotation: 0,
    locked: true,
    placed: true,
    source: "user",
    generated: false,
    capabilities: { movable: false, resizable: false, rotatable: false, deletable: false },
    systemDependencies: ["roads", "parking", "grading", "drainage", "utilities"],
  },
  {
    id: "demo-building-a",
    label: "Office Headquarters",
    type: "office_building",
    w: 300,
    d: 108,
    h: 42,
    x: 350,
    y: 105,
    rotation: 0,
    placed: true,
    source: "user_confirmed",
    geometryType: "polygon",
    geometry: [
      [350, 105],
      [650, 105],
      [650, 213],
      [555, 213],
      [555, 190],
      [445, 190],
      [445, 213],
      [350, 213],
      [350, 105],
    ],
    meta: {
      requested_area_sf: 29200,
      roof_profile: "flat",
      entrance_side: "south",
      canonical_relationships: {
        parking: {
          policy: "ask",
          object_ids: ["demo-parking-north", "demo-parking-retail"],
        },
      },
    },
  },
  {
    id: "demo-building-b",
    label: "Future Flex Building",
    type: "building",
    w: 145,
    d: 76,
    h: 28,
    x: 735,
    y: 128,
    rotation: 0,
    placed: true,
    source: "user_confirmed",
    geometryType: "polygon",
    geometry: [
      [735, 128],
      [880, 128],
      [880, 204],
      [830, 204],
      [830, 188],
      [785, 188],
      [785, 204],
      [735, 204],
      [735, 128],
    ],
    meta: { requested_area_sf: 9800, roof_profile: "flat", future_phase: true },
  },
  {
    id: "demo-retail",
    label: "Amenity Pavilion",
    type: "retail_building",
    w: 115,
    d: 64,
    h: 22,
    x: 120,
    y: 130,
    rotation: 0,
    placed: true,
    source: "user_confirmed",
    geometryType: "polygon",
    geometry: [
      [120, 130],
      [220, 130],
      [235, 145],
      [235, 194],
      [120, 194],
      [120, 130],
    ],
  },
  {
    id: "demo-loop-road",
    label: "Internal Loop Road R-03",
    type: "road",
    w: 760,
    d: 300,
    x: 120,
    y: 245,
    rotation: 0,
    placed: true,
    source: "user_confirmed",
    geometryType: "polyline",
    geometry: [
      [150, 270],
      [850, 270],
      [875, 315],
      [875, 500],
      [835, 540],
      [165, 540],
      [125, 500],
      [125, 315],
      [150, 270],
    ],
    meta: { corridor_width_ft: 28, road_class: "private commercial drive" },
  },
  {
    id: "demo-entry-drive",
    label: "Main Entry Drive",
    type: "driveway",
    w: 30,
    d: 135,
    x: 485,
    y: 535,
    rotation: 0,
    placed: true,
    source: "user_confirmed",
    geometryType: "polyline",
    geometry: [[500, 660], [500, 585], [500, 540]],
    meta: { corridor_width_ft: 30, access_kind: "primary" },
  },
  {
    id: "demo-frontage-road",
    label: "Pinecrest Parkway",
    type: "road",
    w: 900,
    d: 42,
    x: 50,
    y: 640,
    rotation: 0,
    locked: true,
    placed: true,
    source: "user_confirmed",
    geometryType: "polyline",
    geometry: [[50, 660], [360, 654], [650, 654], [950, 660]],
    meta: { corridor_width_ft: 42, public_row_edge: true },
  },
  {
    id: "demo-parking-north",
    label: "West Parking Field — 88 stalls",
    type: "parking",
    w: 320,
    d: 185,
    x: 165,
    y: 320,
    rotation: 0,
    stallCount: 88,
    placed: true,
    source: "user_confirmed",
    meta: { parkingModuleCols: 4, parkingModuleRows: 2, parkingCapacity: 88, adaCount: 5, canonical_parent_id: "demo-building-a" },
  },
  {
    id: "demo-parking-retail",
    label: "East Parking Field — 82 stalls",
    type: "parking",
    w: 320,
    d: 185,
    x: 515,
    y: 320,
    rotation: 0,
    stallCount: 82,
    placed: true,
    source: "user_confirmed",
    meta: { parkingModuleCols: 4, parkingModuleRows: 2, parkingCapacity: 82, adaCount: 4, canonical_parent_id: "demo-building-a" },
  },
  {
    id: "demo-basin-a",
    label: "Detention Basin A — Preliminary",
    type: "basin",
    w: 150,
    d: 78,
    x: 770,
    y: 555,
    rotation: 0,
    placed: true,
    source: "user_confirmed",
    geometryType: "polygon",
    geometry: [
      [785, 555],
      [855, 548],
      [910, 572],
      [920, 605],
      [895, 628],
      [830, 632],
      [780, 610],
      [770, 578],
      [785, 555],
    ],
  },
  {
    id: "demo-sidewalk",
    label: "Accessible Pedestrian Route",
    type: "sidewalk",
    w: 550,
    d: 8,
    x: 225,
    y: 220,
    placed: true,
    source: "user_confirmed",
    geometryType: "polyline",
    geometry: [
      [225, 225],
      [350, 225],
      [500, 245],
      [650, 225],
      [775, 225],
    ],
    meta: { corridor_width_ft: 6, routeKind: "ada_review_route" },
  },
  {
    id: "demo-storm-main",
    label: "Storm Collector",
    type: "utility_corridor",
    w: 380,
    d: 190,
    x: 500,
    y: 390,
    placed: true,
    source: "generated",
    geometryType: "polyline",
    geometry: [[500, 410], [650, 455], [790, 520], [850, 575]],
    meta: { network: "storm", ui_color: "#0284c7" },
  },
  {
    id: "demo-water-main",
    label: "Water Line W-12",
    type: "utility_corridor",
    w: 800,
    d: 250,
    x: 90,
    y: 400,
    placed: true,
    source: "generated",
    geometryType: "polyline",
    geometry: [[90, 620], [500, 620], [500, 370]],
    meta: { network: "water", ui_color: "#2563eb" },
  },
  {
    id: "demo-sanitary-main",
    label: "Sanitary Main SS-01",
    type: "utility_corridor",
    w: 780,
    d: 175,
    x: 110,
    y: 470,
    placed: true,
    source: "generated",
    geometryType: "polyline",
    geometry: [[110, 635], [500, 605], [890, 570]],
    meta: { network: "sanitary", ui_color: "#c026d3" },
  },
  {
    id: "demo-inlet-1",
    label: "Storm Inlet S-01",
    type: "inlet",
    w: 12,
    d: 12,
    x: 494,
    y: 404,
    placed: true,
    source: "generated",
  },
  {
    id: "demo-hydrant-1",
    label: "Hydrant W-01",
    type: "hydrant",
    w: 10,
    d: 10,
    x: 470,
    y: 590,
    placed: true,
    source: "generated",
  },
  ...Array.from({ length: 10 }).map((_, index) => ({
    id: `demo-tree-${index + 1}`,
    label: `Landscape Tree ${index + 1}`,
    type: "landscape" as const,
    w: 12,
    d: 12,
    x: 210 + index * 62,
    y: index % 2 === 0 ? 292 : 525,
    rotation: 0,
    placed: true,
    source: "user_confirmed" as const,
    meta: { landscape_symbol: "tree", ui_color: "#365314" },
  })),
];

export type CommercialConceptSpec = {
  buildingAreaSf?: number;
  buildingUse?: "office" | "retail" | "industrial" | "commercial";
  parkingStalls?: number;
  aisleWidthFt?: number;
  includeLoadingArea?: boolean;
};

export const parseCommercialConceptSpec = (message: string): CommercialConceptSpec & { siteWidth?: number; siteHeight?: number } => {
  const lower = message.toLowerCase();
  const areaMatch = lower.match(/(\d{1,3}(?:,\d{3})+|\d{3,8})\s*(?:sf|sq\s*ft|sqft|square\s*feet)\s+(?:retail|office|industrial|commercial|building)/) ??
    lower.match(/(?:retail|office|industrial|commercial|building)[^\d]{0,24}(\d{1,3}(?:,\d{3})+|\d{3,8})\s*(?:sf|sq\s*ft|sqft|square\s*feet)/);
  const parkingMatch = lower.match(/(\d{1,5})\s+(?:parking\s+)?(?:spaces|stalls|spots?)/);
  const aisleMatch = lower.match(/(\d{1,3}(?:\.\d+)?)\s*(?:ft|foot|feet|-foot)\s+(?:drive\s+)?aisles?/);
  const dimensionsMatch = lower.match(/(\d{2,5}(?:\.\d+)?)\s*(?:ft|feet|')?\s*(?:x|by|×)\s*(\d{2,5}(?:\.\d+)?)\s*(?:ft|feet|')?/);
  const acresMatch = lower.match(/(?:approximately\s+|approx\.?\s+|about\s+|near\s+)?(\d+(?:\.\d+)?)\s*(?:-|\s)?acres?\b/);
  let siteWidth: number | undefined;
  let siteHeight: number | undefined;
  if (dimensionsMatch) {
    siteWidth = Number(dimensionsMatch[1]);
    siteHeight = Number(dimensionsMatch[2]);
  } else if (acresMatch) {
    const squareFeet = Number(acresMatch[1]) * 43_560;
    siteWidth = Math.round(Math.sqrt(squareFeet * 1.25));
    siteHeight = Math.round(squareFeet / siteWidth);
  }
  const buildingUse = /\bretail\b/.test(lower)
    ? "retail"
    : /\bindustrial\b/.test(lower)
      ? "industrial"
      : /\boffice\b/.test(lower)
        ? "office"
        : /\bcommercial\b/.test(lower)
          ? "commercial"
          : undefined;
  return {
    buildingAreaSf: areaMatch ? Number(areaMatch[1].replace(/,/g, "")) : undefined,
    buildingUse,
    parkingStalls: parkingMatch ? Number(parkingMatch[1]) : undefined,
    aisleWidthFt: aisleMatch ? Number(aisleMatch[1]) : undefined,
    includeLoadingArea: /\b(load(?:ing)?|service area|service yard|delivery)\b/.test(lower) || undefined,
    siteWidth,
    siteHeight,
  };
};

export const createDenseCommercialConceptPlacements = (
  lot: { w: number; h: number },
  spec: CommercialConceptSpec = {},
): BuildingPlacement[] => {
  const now = Date.now();
  const siteW = Math.max(lot.w || 1000, 200);
  const siteH = Math.max(lot.h || 1000, 200);
  const place = (
    id: string,
    label: string,
    type: SiteObjectType,
    x: number,
    y: number,
    w: number,
    d: number,
    extra: Partial<BuildingPlacement> = {},
  ): BuildingPlacement => ({
    id: `dense-${id}-${now}`,
    label,
    type,
    w,
    d,
    x: Math.max(16, Math.min(siteW - w - 16, x)),
    y: Math.max(16, Math.min(siteH - d - 16, y)),
    rotation: 0,
    locked: false,
    placed: true,
    source: "user_confirmed",
    generated: false,
    capabilities: { movable: true, resizable: true, rotatable: true, deletable: true },
    systemDependencies: ["roads", "parking", "grading", "drainage", "utilities"],
    ...extra,
    meta: {
      dense_concept_generated: true,
      draft_review_required: true,
      construction_release_allowed: false,
      source_confidence: "user_confirmed_review_geometry",
      ...(extra.meta ?? {}),
    },
  });
  const line = (
    id: string,
    label: string,
    type: SiteObjectType,
    geometry: Array<[number, number]>,
    meta: Record<string, unknown> = {},
  ) => {
    const bounds = geometry.reduce(
      (acc, [x, y]) => ({
        minX: Math.min(acc.minX, x),
        minY: Math.min(acc.minY, y),
        maxX: Math.max(acc.maxX, x),
        maxY: Math.max(acc.maxY, y),
      }),
      { minX: siteW, minY: siteH, maxX: 0, maxY: 0 },
    );
    return place(
      id,
      label,
      type,
      bounds.minX,
      bounds.minY,
      Math.max(10, bounds.maxX - bounds.minX),
      Math.max(10, bounds.maxY - bounds.minY),
      {
        geometryType: "polyline",
        geometry,
        capabilities: { movable: true, resizable: false, rotatable: false, deletable: true },
        meta,
      },
    );
  };
  const polygon = (
    id: string,
    label: string,
    type: SiteObjectType,
    geometry: Array<[number, number]>,
    extra: Partial<BuildingPlacement> = {},
  ) => {
    const bounds = geometry.reduce(
      (acc, [x, y]) => ({
        minX: Math.min(acc.minX, x),
        minY: Math.min(acc.minY, y),
        maxX: Math.max(acc.maxX, x),
        maxY: Math.max(acc.maxY, y),
      }),
      { minX: siteW, minY: siteH, maxX: 0, maxY: 0 },
    );
    return place(
      id,
      label,
      type,
      bounds.minX,
      bounds.minY,
      Math.max(10, bounds.maxX - bounds.minX),
      Math.max(10, bounds.maxY - bounds.minY),
      {
        geometryType: "polygon",
        geometry,
        ...extra,
        meta: {
          dense_concept_generated: true,
          true_footprint_geometry: true,
          ...(extra.meta ?? {}),
        },
      },
    );
  };
  const notchedBuilding = (
    x: number,
    y: number,
    w: number,
    d: number,
    entrySide: "north" | "south" = "south",
  ): Array<[number, number]> => {
    const entry = Math.min(w * 0.14, 34);
    const notch = Math.min(d * 0.2, 18);
    const wing = Math.min(w * 0.16, 38);
    if (entrySide === "north") {
      return [
        [x, y],
        [x + w * 0.42, y],
        [x + w * 0.42, y + notch],
        [x + w * 0.42 + entry, y + notch],
        [x + w * 0.42 + entry, y],
        [x + w, y],
        [x + w, y + d * 0.55],
        [x + w - wing, y + d * 0.55],
        [x + w - wing, y + d * 0.55 + notch],
        [x + w, y + d * 0.55 + notch],
        [x + w, y + d],
        [x, y + d],
      ];
    }
    return [
      [x, y],
      [x + w, y],
      [x + w, y + d],
      [x + w * 0.58 + entry, y + d],
      [x + w * 0.58 + entry, y + d - notch],
      [x + w * 0.58, y + d - notch],
      [x + w * 0.58, y + d],
      [x, y + d],
      [x, y + d * 0.46 + notch],
      [x + wing, y + d * 0.46 + notch],
      [x + wing, y + d * 0.46],
      [x, y + d * 0.46],
    ];
  };
  const buildingAreaSf = Math.max(2_000, spec.buildingAreaSf ?? 28_000);
  const buildingUse = spec.buildingUse ?? "office";
  const buildingDepth = Math.sqrt(buildingAreaSf / 1.8);
  const buildingW = Math.min(Math.max(buildingDepth * 1.8, 80), siteW * 0.42);
  const buildingD = Math.min(Math.max(buildingAreaSf / buildingW, 45), siteH * 0.24);
  const totalParkingStalls = Math.max(1, Math.round(spec.parkingStalls ?? 140));
  const northParkingStalls = Math.ceil(totalParkingStalls * 0.6);
  const southParkingStalls = totalParkingStalls - northParkingStalls;
  const aisleWidthFt = spec.aisleWidthFt ?? 24;
  const buildingUseLabel = `${buildingUse.charAt(0).toUpperCase()}${buildingUse.slice(1)}`;
  const parkingW = Math.min(300, siteW * 0.30);
  const parkingD = Math.min(126, siteH * 0.13);
  const contours = Array.from({ length: 7 }).map((_, idx) => {
    const y = siteH * (0.18 + idx * 0.105);
    const grade = 1025 - idx * 2;
    return line(
      `grading-contour-${idx}`,
      `Contour ${grade}`,
      "custom",
      [
        [siteW * 0.04, y + Math.sin(idx * 0.8) * siteH * 0.012],
        [siteW * 0.22, y + siteH * 0.018],
        [siteW * 0.42, y - siteH * 0.008],
        [siteW * 0.62, y + siteH * 0.026],
        [siteW * 0.86, y + Math.cos(idx * 0.9) * siteH * 0.016],
        [siteW * 0.96, y + siteH * 0.034],
      ],
      { preview_kind: "contour", ui_color: "#ca8a04", dense_concept_generated: true, contour_elevation_ft: grade },
    );
  });
  return [
    line("frontage-road", "Public Frontage Road", "road", [
      [siteW * 0.02, siteH * 0.12],
      [siteW * 0.36, siteH * 0.10],
      [siteW * 0.72, siteH * 0.11],
      [siteW * 0.98, siteH * 0.13],
    ], { corridor_width_ft: 42, dense_concept_generated: true, public_row_edge: true }),
    polygon("office-main", `${buildingUseLabel} Building - ${Math.round(buildingAreaSf).toLocaleString()} sf`, buildingUse === "office" ? "office_building" : "building", notchedBuilding(siteW * 0.43, siteH * 0.39, buildingW, buildingD), {
      h: 34,
      meta: { requested_area_sf: Math.round(buildingAreaSf), building_use: buildingUse, dense_concept_generated: true, roof_profile: "flat", entrance_side: "south" },
    }),
    polygon("office-flex", spec.includeLoadingArea ? "Rear Loading / Service Area" : "Future Flex / Service Pad", "building", notchedBuilding(siteW * 0.66, siteH * 0.29, buildingW * 0.64, buildingD * 0.64, "north"), {
      h: 24,
      meta: { dense_concept_generated: true, roof_profile: "flat", service_pad: true, loading_area: Boolean(spec.includeLoadingArea) },
    }),
    place("parking-north", `Parking Field - ${northParkingStalls} stalls`, "parking", siteW * 0.30, siteH * 0.23, parkingW, parkingD, {
      stallCount: northParkingStalls,
      meta: {
        requested_stalls: northParkingStalls,
        parkingCapacity: northParkingStalls,
        parkingModuleCols: 4,
        parkingModuleRows: 2,
        parkingParams: {
          stallWidth: 9,
          stallDepth: 18,
          aisleWidth: aisleWidthFt,
          loading: "double",
          adaCount: 5,
          adaAisleWidth: 8,
          compactCount: 8,
          compactWidth: 8,
          angleDeg: 90,
          useMixedAngles: true,
        },
        dense_concept_generated: true,
      },
    }),
    place("parking-south", `Parking Field - ${southParkingStalls} stalls`, "parking", siteW * 0.30, siteH * 0.58, parkingW * 0.88, parkingD * 0.92, {
      stallCount: southParkingStalls,
      meta: {
        requested_stalls: southParkingStalls,
        parkingCapacity: southParkingStalls,
        parkingModuleCols: 3,
        parkingModuleRows: 2,
        parkingParams: {
          stallWidth: 9,
          stallDepth: 18,
          aisleWidth: aisleWidthFt,
          loading: "double",
          adaCount: 3,
          adaAisleWidth: 8,
          compactCount: 6,
          compactWidth: 8,
          angleDeg: 90,
        },
        dense_concept_generated: true,
      },
    }),
    place("basin", "Detention Basin A", "basin", siteW * 0.69, siteH * 0.67, siteW * 0.18, siteH * 0.12, {
      meta: { normal_pool_elevation_ft: 1012.4, bottom_elevation_ft: 1007.2, dense_concept_generated: true },
    }),
    line("loop-road", "Internal Loop Drive", "road", [
      [siteW * 0.24, siteH * 0.28],
      [siteW * 0.70, siteH * 0.28],
      [siteW * 0.80, siteH * 0.40],
      [siteW * 0.78, siteH * 0.78],
      [siteW * 0.24, siteH * 0.78],
      [siteW * 0.18, siteH * 0.56],
      [siteW * 0.24, siteH * 0.28],
    ], { corridor_width_ft: 28, dense_concept_generated: true }),
    line("driveway", "Driveway Connection", "driveway", [
      [siteW * 0.49, siteH * 0.12],
      [siteW * 0.49, siteH * 0.21],
      [siteW * 0.44, siteH * 0.28],
    ], { corridor_width_ft: 30, dense_concept_generated: true }),
    line("service-drive", "Rear Service Drive", "driveway", [
      [siteW * 0.62, siteH * 0.34],
      [siteW * 0.73, siteH * 0.36],
      [siteW * 0.79, siteH * 0.46],
    ], { corridor_width_ft: 22, dense_concept_generated: true, service_access: true }),
    line("ada-route", "Sidewalk / ADA Route", "sidewalk", [
      [siteW * 0.32, siteH * 0.36],
      [siteW * 0.43, siteH * 0.36],
      [siteW * 0.51, siteH * 0.48],
      [siteW * 0.58, siteH * 0.58],
      [siteW * 0.68, siteH * 0.68],
    ], { routeKind: "ada_review_route", dense_concept_generated: true }),
    line("frontage-sidewalk", "Frontage Sidewalk", "sidewalk", [
      [siteW * 0.05, siteH * 0.18],
      [siteW * 0.33, siteH * 0.17],
      [siteW * 0.64, siteH * 0.18],
      [siteW * 0.93, siteH * 0.21],
    ], { routeKind: "public_frontage_walk", corridor_width_ft: 6, dense_concept_generated: true }),
    line("crosswalk-main", "Main Entry Crosswalk", "sidewalk", [
      [siteW * 0.49, siteH * 0.28],
      [siteW * 0.49, siteH * 0.39],
    ], { routeKind: "crosswalk_review", corridor_width_ft: 10, cad_hatch_enabled: true, dense_concept_generated: true }),
    line("water-main", "Public Water Line", "utility_corridor", [
      [siteW * 0.08, siteH * 0.18],
      [siteW * 0.34, siteH * 0.18],
      [siteW * 0.49, siteH * 0.21],
      [siteW * 0.78, siteH * 0.34],
    ], { network: "water", dense_concept_generated: true }),
    line("water-lateral-office", "Office Water Service Lateral", "utility_corridor", [
      [siteW * 0.55, siteH * 0.34],
      [siteW * 0.55, siteH * 0.39],
    ], { network: "water", service_lateral: true, dense_concept_generated: true }),
    line("sanitary-main", "Public Sanitary Line", "utility_corridor", [
      [siteW * 0.12, siteH * 0.86],
      [siteW * 0.40, siteH * 0.84],
      [siteW * 0.63, siteH * 0.80],
      [siteW * 0.84, siteH * 0.73],
    ], { network: "sanitary", dense_concept_generated: true }),
    line("sanitary-lateral-office", "Office Sanitary Lateral", "utility_corridor", [
      [siteW * 0.54, siteH * 0.80],
      [siteW * 0.54, siteH * 0.48],
    ], { network: "sanitary", service_lateral: true, dense_concept_generated: true }),
    line("storm-main", "Storm Sewer", "utility_corridor", [
      [siteW * 0.43, siteH * 0.36],
      [siteW * 0.58, siteH * 0.46],
      [siteW * 0.70, siteH * 0.61],
      [siteW * 0.78, siteH * 0.72],
    ], { network: "storm", dense_concept_generated: true }),
    line("storm-parking-collector", "Parking Court Storm Collector", "utility_corridor", [
      [siteW * 0.42, siteH * 0.53],
      [siteW * 0.56, siteH * 0.54],
      [siteW * 0.70, siteH * 0.61],
    ], { network: "storm", dense_concept_generated: true }),
    polygon("landscape-buffer", "Frontage Landscape Buffer", "landscape", [
      [siteW * 0.07, siteH * 0.19],
      [siteW * 0.84, siteH * 0.20],
      [siteW * 0.86, siteH * 0.25],
      [siteW * 0.12, siteH * 0.25],
    ], { meta: { ui_color: "#65a30d", cad_hatch_enabled: true, cad_hatch_pattern: "landscape", dense_concept_generated: true } }),
    place("inlet-a", "Storm Inlet S-1", "inlet", siteW * 0.43, siteH * 0.36, 12, 12, { meta: { dense_concept_generated: true } }),
    place("inlet-b", "Storm Inlet S-2", "inlet", siteW * 0.58, siteH * 0.46, 12, 12, { meta: { dense_concept_generated: true } }),
    place("inlet-c", "Storm Inlet S-3", "inlet", siteW * 0.42, siteH * 0.53, 12, 12, { meta: { dense_concept_generated: true } }),
    place("outfall", "Outfall OF-1", "outfall", siteW * 0.78, siteH * 0.72, 12, 12, { meta: { dense_concept_generated: true } }),
    place("hydrant-a", "Hydrant W-1", "hydrant", siteW * 0.34, siteH * 0.18, 10, 10, { meta: { dense_concept_generated: true } }),
    place("hydrant-b", "Hydrant W-2", "hydrant", siteW * 0.78, siteH * 0.34, 10, 10, { meta: { dense_concept_generated: true } }),
    place("manhole-a", "Sanitary Manhole SS-1", "manhole", siteW * 0.54, siteH * 0.80, 12, 12, { meta: { network: "sanitary", dense_concept_generated: true } }),
    ...Array.from({ length: 16 }).map((_, idx) =>
      place(
        `landscape-tree-${idx}`,
        `Parking Island Tree ${idx + 1}`,
        "landscape",
        siteW * (0.26 + (idx % 8) * 0.055),
        siteH * (0.58 + Math.floor(idx / 8) * 0.095),
        12,
        12,
        { meta: { dense_concept_generated: true, landscape_symbol: "tree", ui_color: "#365314" } },
      ),
    ),
    ...contours,
  ];
};

export const createDenseSubdivisionCadPlanPlacements = (lot: { w: number; h: number }): BuildingPlacement[] => {
  const now = Date.now();
  const siteW = Math.max(lot.w || 1200, 800);
  const siteH = Math.max(lot.h || 820, 620);
  const baseMeta = {
    dense_concept_generated: true,
    subdivision_cad_recreation: true,
    dense_subdivision_cad_plan: true,
    cad_reference_recreation: true,
    draft_review_required: true,
    construction_release_allowed: false,
    source_confidence: "user_requested_cad_style_review_geometry",
  };
  const clamp = (value: number, min: number, max: number) => Math.min(Math.max(value, min), max);
  const place = (
    id: string,
    label: string,
    type: SiteObjectType,
    x: number,
    y: number,
    w: number,
    d: number,
    extra: Partial<BuildingPlacement> = {},
  ): BuildingPlacement => ({
    id: `subdiv-${id}-${now}`,
    label,
    type,
    w,
    d,
    x: clamp(x, 8, siteW - w - 8),
    y: clamp(y, 8, siteH - d - 8),
    rotation: 0,
    locked: false,
    placed: true,
    source: "user_confirmed",
    generated: false,
    capabilities: { movable: true, resizable: true, rotatable: true, deletable: true },
    systemDependencies: ["roads", "parking", "grading", "drainage", "utilities"],
    ...extra,
    meta: {
      ...baseMeta,
      ...(extra.meta ?? {}),
    },
  });
  const line = (
    id: string,
    label: string,
    type: SiteObjectType,
    geometry: Array<[number, number]>,
    meta: Record<string, unknown> = {},
  ) => {
    const bounds = geometry.reduce(
      (acc, [x, y]) => ({
        minX: Math.min(acc.minX, x),
        minY: Math.min(acc.minY, y),
        maxX: Math.max(acc.maxX, x),
        maxY: Math.max(acc.maxY, y),
      }),
      { minX: siteW, minY: siteH, maxX: 0, maxY: 0 },
    );
    return place(
      id,
      label,
      type,
      bounds.minX,
      bounds.minY,
      Math.max(8, bounds.maxX - bounds.minX),
      Math.max(8, bounds.maxY - bounds.minY),
      {
        geometryType: "polyline",
        geometry,
        capabilities: { movable: true, resizable: false, rotatable: false, deletable: true },
        meta,
      },
    );
  };
  const polygon = (
    id: string,
    label: string,
    type: SiteObjectType,
    geometry: Array<[number, number]>,
    meta: Record<string, unknown> = {},
  ) => {
    const bounds = geometry.reduce(
      (acc, [x, y]) => ({
        minX: Math.min(acc.minX, x),
        minY: Math.min(acc.minY, y),
        maxX: Math.max(acc.maxX, x),
        maxY: Math.max(acc.maxY, y),
      }),
      { minX: siteW, minY: siteH, maxX: 0, maxY: 0 },
    );
    return place(
      id,
      label,
      type,
      bounds.minX,
      bounds.minY,
      Math.max(8, bounds.maxX - bounds.minX),
      Math.max(8, bounds.maxY - bounds.minY),
      {
        geometryType: "polygon",
        geometry,
        meta,
      },
    );
  };

  const lots: BuildingPlacement[] = [];
  const addLotBlock = (prefix: string, startX: number, startY: number, cols: number, rows: number, cellW: number, cellH: number, gap = 5) => {
    for (let row = 0; row < rows; row += 1) {
      for (let col = 0; col < cols; col += 1) {
        const offset = row % 2 ? cellW * 0.12 : 0;
        lots.push(
          place(
            `${prefix}-${row}-${col}`,
            `${prefix}${row + 1}-${col + 1}`,
            "lot_block",
            startX + col * (cellW + gap) + offset,
            startY + row * (cellH + gap),
            cellW,
            cellH,
            { meta: { ...baseMeta, lot_label: `${prefix}${row + 1}-${col + 1}` } },
          ),
        );
      }
    }
  };

  addLotBlock("B", siteW * 0.16, siteH * 0.08, 13, 3, siteW * 0.038, siteH * 0.044);
  addLotBlock("C", siteW * 0.73, siteH * 0.17, 5, 6, siteW * 0.044, siteH * 0.048);
  addLotBlock("D", siteW * 0.68, siteH * 0.42, 7, 5, siteW * 0.042, siteH * 0.044);
  addLotBlock("E", siteW * 0.05, siteH * 0.20, 5, 7, siteW * 0.047, siteH * 0.046);
  addLotBlock("F", siteW * 0.08, siteH * 0.63, 6, 4, siteW * 0.045, siteH * 0.042);
  addLotBlock("G", siteW * 0.42, siteH * 0.72, 6, 3, siteW * 0.046, siteH * 0.044);
  addLotBlock("H", siteW * 0.30, siteH * 0.30, 6, 5, siteW * 0.041, siteH * 0.042);

  const contours = Array.from({ length: 13 }).map((_, idx) => {
    const y = siteH * (0.02 + idx * 0.075);
    return line(
      `contour-${idx}`,
      `Contour ${710 - idx * 5}`,
      "custom",
      [
        [siteW * 0.02, y + Math.sin(idx) * siteH * 0.02],
        [siteW * 0.18, y + siteH * 0.06 + Math.cos(idx) * siteH * 0.018],
        [siteW * 0.36, y + siteH * 0.015],
        [siteW * 0.56, y + siteH * 0.07],
        [siteW * 0.78, y + siteH * 0.025],
        [siteW * 0.98, y + siteH * 0.08 + Math.sin(idx * 1.8) * siteH * 0.02],
      ],
      { preview_kind: "contour", ui_color: "#ca8a04", dense_concept_generated: true },
    );
  });

  return [
    ...lots,
    line("north-collector", "North Collector Road", "road", [
      [siteW * 0.02, siteH * 0.10],
      [siteW * 0.22, siteH * 0.08],
      [siteW * 0.58, siteH * 0.05],
      [siteW * 0.96, siteH * 0.03],
    ], { corridor_width_ft: 34, dense_concept_generated: true }),
    line("west-collector", "West Collector Road", "road", [
      [siteW * 0.06, siteH * 0.08],
      [siteW * 0.06, siteH * 0.95],
    ], { corridor_width_ft: 30, dense_concept_generated: true }),
    line("east-collector", "East Edge Road", "road", [
      [siteW * 0.90, siteH * 0.04],
      [siteW * 0.93, siteH * 0.26],
      [siteW * 0.88, siteH * 0.62],
      [siteW * 0.82, siteH * 0.95],
    ], { corridor_width_ft: 32, dense_concept_generated: true }),
    line("main-loop", "Central Loop Road", "road", [
      [siteW * 0.18, siteH * 0.24],
      [siteW * 0.41, siteH * 0.20],
      [siteW * 0.69, siteH * 0.22],
      [siteW * 0.82, siteH * 0.38],
      [siteW * 0.69, siteH * 0.62],
      [siteW * 0.42, siteH * 0.64],
      [siteW * 0.18, siteH * 0.52],
      [siteW * 0.18, siteH * 0.24],
    ], { corridor_width_ft: 30, dense_concept_generated: true }),
    line("south-diagonal", "South Diagonal Road", "road", [
      [siteW * 0.04, siteH * 0.86],
      [siteW * 0.32, siteH * 0.78],
      [siteW * 0.58, siteH * 0.72],
      [siteW * 0.82, siteH * 0.68],
    ], { corridor_width_ft: 28, dense_concept_generated: true }),
    polygon("central-park", "Central Amenity Green", "open_space", [
      [siteW * 0.38, siteH * 0.31],
      [siteW * 0.58, siteH * 0.27],
      [siteW * 0.68, siteH * 0.42],
      [siteW * 0.61, siteH * 0.58],
      [siteW * 0.39, siteH * 0.59],
      [siteW * 0.31, siteH * 0.45],
    ], { ui_color: "#16a34a", dense_concept_generated: true }),
    polygon("amenity-plaza", "Amenity Plaza / Clubhouse", "amenity", [
      [siteW * 0.45, siteH * 0.40],
      [siteW * 0.54, siteH * 0.37],
      [siteW * 0.58, siteH * 0.47],
      [siteW * 0.50, siteH * 0.53],
      [siteW * 0.42, siteH * 0.48],
    ], { ui_color: "#64748b", dense_concept_generated: true }),
    place("north-blue-hatch", "North Blue Hatched Parking", "parking", siteW * 0.43, siteH * 0.27, siteW * 0.14, siteH * 0.046, {
      stallCount: 36,
      meta: { ...baseMeta, cad_hatch_enabled: true, cad_hatch_pattern: "diagonal", ui_color: "#2563eb" },
    }),
    place("south-blue-hatch", "South Blue Hatched Parking", "parking", siteW * 0.49, siteH * 0.60, siteW * 0.16, siteH * 0.05, {
      stallCount: 42,
      meta: { ...baseMeta, cad_hatch_enabled: true, cad_hatch_pattern: "diagonal", ui_color: "#2563eb" },
    }),
    place("red-feature-a", "Red Feature Court A", "no_build_zone", siteW * 0.57, siteH * 0.27, siteW * 0.09, siteH * 0.042, {
      meta: { ...baseMeta, ui_color: "#dc2626", cad_hatch_enabled: true },
    }),
    place("red-feature-b", "Red Feature Court B", "no_build_zone", siteW * 0.49, siteH * 0.43, siteW * 0.06, siteH * 0.06, {
      meta: { ...baseMeta, ui_color: "#dc2626", cad_hatch_enabled: true },
    }),
    place("pond-a", "Amenity Pond A", "basin", siteW * 0.34, siteH * 0.58, siteW * 0.052, siteH * 0.042, {
      meta: { ...baseMeta, normal_pool_elevation_ft: 688.2, bottom_elevation_ft: 684.1 },
    }),
    place("pond-b", "Amenity Pond B", "basin", siteW * 0.61, siteH * 0.35, siteW * 0.055, siteH * 0.042, {
      meta: { ...baseMeta, normal_pool_elevation_ft: 689.4, bottom_elevation_ft: 685.8 },
    }),
    line("storm-trunk", "Storm Trunk Sewer", "utility_corridor", [
      [siteW * 0.36, siteH * 0.34],
      [siteW * 0.52, siteH * 0.43],
      [siteW * 0.63, siteH * 0.56],
      [siteW * 0.70, siteH * 0.65],
    ], { network: "storm", dense_concept_generated: true }),
    line("water-loop", "Water Main Loop", "utility_corridor", [
      [siteW * 0.28, siteH * 0.22],
      [siteW * 0.68, siteH * 0.22],
      [siteW * 0.78, siteH * 0.43],
      [siteW * 0.58, siteH * 0.65],
      [siteW * 0.28, siteH * 0.58],
      [siteW * 0.28, siteH * 0.22],
    ], { network: "water", dense_concept_generated: true }),
    line("sanitary-spine", "Sanitary Sewer Spine", "utility_corridor", [
      [siteW * 0.20, siteH * 0.72],
      [siteW * 0.40, siteH * 0.67],
      [siteW * 0.64, siteH * 0.61],
      [siteW * 0.82, siteH * 0.56],
    ], { network: "sanitary", dense_concept_generated: true }),
    place("feature-ring", "Roundabout Feature", "amenity", siteW * 0.34, siteH * 0.50, siteW * 0.045, siteH * 0.045, {
      meta: { ...baseMeta, cad_entity_type: "circle", cad_radius: 28 },
    }),
    ...contours,
  ];
};

export const createUrbanizationCampusPlanPlacements = (lot: { w: number; h: number }): BuildingPlacement[] => {
  const now = Date.now();
  const siteW = Math.max(lot.w || 1120, 900);
  const siteH = Math.max(lot.h || 720, 560);
  const baseMeta = {
    dense_concept_generated: true,
    urbanization_campus_plan: true,
    draft_review_required: true,
    construction_release_allowed: false,
    source_confidence: "user_requested_urbanization_review_geometry",
  };
  const clamp = (value: number, min: number, max: number) => Math.min(Math.max(value, min), max);
  const place = (
    id: string,
    label: string,
    type: SiteObjectType,
    x: number,
    y: number,
    w: number,
    d: number,
    extra: Partial<BuildingPlacement> = {},
  ): BuildingPlacement => ({
    id: `urban-${id}-${now}`,
    label,
    type,
    w,
    d,
    x: clamp(x, 8, siteW - w - 8),
    y: clamp(y, 8, siteH - d - 8),
    rotation: 0,
    locked: false,
    placed: true,
    source: "user_confirmed",
    generated: false,
    capabilities: { movable: true, resizable: true, rotatable: true, deletable: true },
    systemDependencies: ["roads", "parking", "grading", "drainage", "utilities"],
    ...extra,
    meta: {
      ...baseMeta,
      ...(extra.meta ?? {}),
    },
  });
  const line = (
    id: string,
    label: string,
    type: SiteObjectType,
    geometry: Array<[number, number]>,
    meta: Record<string, unknown> = {},
  ) => {
    const bounds = geometry.reduce(
      (acc, [x, y]) => ({
        minX: Math.min(acc.minX, x),
        minY: Math.min(acc.minY, y),
        maxX: Math.max(acc.maxX, x),
        maxY: Math.max(acc.maxY, y),
      }),
      { minX: siteW, minY: siteH, maxX: 0, maxY: 0 },
    );
    return place(
      id,
      label,
      type,
      bounds.minX,
      bounds.minY,
      Math.max(8, bounds.maxX - bounds.minX),
      Math.max(8, bounds.maxY - bounds.minY),
      {
        geometryType: "polyline",
        geometry,
        capabilities: { movable: true, resizable: false, rotatable: false, deletable: true },
        meta: { ...baseMeta, ...meta },
      },
    );
  };
  const polygon = (
    id: string,
    label: string,
    type: SiteObjectType,
    geometry: Array<[number, number]>,
    meta: Record<string, unknown> = {},
  ) => {
    const bounds = geometry.reduce(
      (acc, [x, y]) => ({
        minX: Math.min(acc.minX, x),
        minY: Math.min(acc.minY, y),
        maxX: Math.max(acc.maxX, x),
        maxY: Math.max(acc.maxY, y),
      }),
      { minX: siteW, minY: siteH, maxX: 0, maxY: 0 },
    );
    return place(
      id,
      label,
      type,
      bounds.minX,
      bounds.minY,
      Math.max(8, bounds.maxX - bounds.minX),
      Math.max(8, bounds.maxY - bounds.minY),
      { geometryType: "polygon", geometry, meta: { ...baseMeta, ...meta } },
    );
  };
  const parcels: BuildingPlacement[] = [];
  const addParcelRow = (prefix: string, startX: number, startY: number, count: number, cellW: number, cellH: number, skew = 0) => {
    for (let idx = 0; idx < count; idx += 1) {
      const x = startX + idx * (cellW + 8);
      const y = startY + Math.sin(idx * 0.9) * skew;
      parcels.push(
        place(`${prefix}-parcel-${idx}`, `${prefix}-${idx + 1}`, "lot_block", x, y, cellW, cellH, {
          meta: { ...baseMeta, ui_color: "#0f766e", lot_label: `${prefix}-${idx + 1}` },
        }),
      );
      parcels.push(
        place(`${prefix}-house-${idx}`, `${prefix} BLDG ${idx + 1}`, "building", x + cellW * 0.36, y + cellH * 0.34, cellW * 0.22, cellH * 0.24, {
          h: 18 + (idx % 3) * 4,
          meta: { ...baseMeta, cad_solid_symbol: true, roof_profile: idx % 4 === 0 ? "gable" : "flat" },
        }),
      );
    }
  };
  addParcelRow("ASVEA", siteW * 0.08, siteH * 0.10, 13, siteW * 0.048, siteH * 0.10, 7);
  addParcelRow("ORQ", siteW * 0.18, siteH * 0.33, 9, siteW * 0.052, siteH * 0.11, 9);
  addParcelRow("LAMB", siteW * 0.07, siteH * 0.55, 8, siteW * 0.052, siteH * 0.12, 12);
  addParcelRow("APROV", siteW * 0.79, siteH * 0.13, 4, siteW * 0.052, siteH * 0.12, 6);
  addParcelRow("EAST", siteW * 0.72, siteH * 0.38, 6, siteW * 0.047, siteH * 0.10, 7);

  const trees = Array.from({ length: 24 }).map((_, idx) =>
    place(
      `tree-${idx}`,
      `Tree ${idx + 1}`,
      "landscape",
      siteW * (0.34 + (idx % 6) * 0.044 + Math.sin(idx) * 0.01),
      siteH * (0.54 + Math.floor(idx / 6) * 0.07 + Math.cos(idx) * 0.015),
      16,
      16,
      { meta: { ...baseMeta, cad_entity_type: "circle", ui_color: "#365314", landscape_symbol: "tree" } },
    ),
  );
  const contours = Array.from({ length: 9 }).map((_, idx) => {
    const y = siteH * (0.13 + idx * 0.085);
    const elevation = 720 - idx * 3;
    return line(
      `campus-contour-${idx}`,
      `Contour ${elevation}`,
      "custom",
      [
        [siteW * 0.03, y + Math.sin(idx * 0.7) * siteH * 0.018],
        [siteW * 0.20, y + siteH * 0.026],
        [siteW * 0.42, y - siteH * 0.012],
        [siteW * 0.61, y + siteH * 0.022],
        [siteW * 0.82, y - siteH * 0.006],
        [siteW * 0.97, y + Math.cos(idx * 0.8) * siteH * 0.018],
      ],
      { preview_kind: "contour", ui_color: "#ca8a04", contour_elevation_ft: elevation },
    );
  });

  return [
    ...parcels,
    line("north-boulevard", "Boulevard Lambramani", "road", [
      [siteW * 0.06, siteH * 0.08],
      [siteW * 0.40, siteH * 0.08],
      [siteW * 0.72, siteH * 0.10],
      [siteW * 0.93, siteH * 0.15],
    ], { corridor_width_ft: 36, ui_color: "#a855f7" }),
    line("inner-loop", "Inner Urbanization Drive", "road", [
      [siteW * 0.10, siteH * 0.30],
      [siteW * 0.30, siteH * 0.25],
      [siteW * 0.66, siteH * 0.25],
      [siteW * 0.76, siteH * 0.42],
      [siteW * 0.58, siteH * 0.58],
      [siteW * 0.23, siteH * 0.55],
      [siteW * 0.10, siteH * 0.30],
    ], { corridor_width_ft: 32, ui_color: "#a855f7" }),
    line("south-avenue", "Av. Los Incas", "road", [
      [siteW * 0.02, siteH * 0.86],
      [siteW * 0.24, siteH * 0.78],
      [siteW * 0.50, siteH * 0.72],
      [siteW * 0.88, siteH * 0.69],
    ], { corridor_width_ft: 30, ui_color: "#a855f7" }),
    polygon("municipal-park", "Municipal Park", "open_space", [
      [siteW * 0.31, siteH * 0.48],
      [siteW * 0.54, siteH * 0.44],
      [siteW * 0.60, siteH * 0.68],
      [siteW * 0.40, siteH * 0.78],
      [siteW * 0.26, siteH * 0.66],
    ], { ui_color: "#84a84a", cad_hatch_enabled: true, cad_hatch_pattern: "landscape" }),
    polygon("main-plaza", "Central Plaza", "amenity", [
      [siteW * 0.44, siteH * 0.27],
      [siteW * 0.64, siteH * 0.28],
      [siteW * 0.67, siteH * 0.41],
      [siteW * 0.48, siteH * 0.45],
    ], { ui_color: "#f59e0b", cad_hatch_enabled: true, cad_hatch_pattern: "diagonal", roof_profile: "plaza" }),
    place("civic-hall", "Civic Hall", "building", siteW * 0.48, siteH * 0.17, siteW * 0.10, siteH * 0.12, {
      h: 54,
      meta: { ...baseMeta, ui_color: "#111827", roof_profile: "tower", hero_massing: true },
    }),
    place("library", "Library / Community Building", "building", siteW * 0.68, siteH * 0.25, siteW * 0.12, siteH * 0.12, {
      h: 34,
      meta: { ...baseMeta, ui_color: "#374151", roof_profile: "dome", hero_massing: true },
    }),
    place("market-hall", "Market Hall", "building", siteW * 0.16, siteH * 0.70, siteW * 0.18, siteH * 0.09, {
      h: 28,
      meta: { ...baseMeta, ui_color: "#374151", roof_profile: "gable", hero_massing: true },
    }),
    place("linear-building", "Linear Mixed Use", "building", siteW * 0.51, siteH * 0.68, siteW * 0.22, siteH * 0.07, {
      h: 30,
      meta: { ...baseMeta, ui_color: "#374151", roof_profile: "flat", hero_massing: true },
    }),
    place("west-parking", "West Parking Court", "parking", siteW * 0.11, siteH * 0.42, siteW * 0.11, siteH * 0.08, {
      stallCount: 34,
      meta: { ...baseMeta, ui_color: "#f59e0b", cad_hatch_enabled: true, cad_hatch_pattern: "diagonal" },
    }),
    place("east-parking", "East Parking Court", "parking", siteW * 0.74, siteH * 0.56, siteW * 0.11, siteH * 0.08, {
      stallCount: 38,
      meta: { ...baseMeta, ui_color: "#f59e0b", cad_hatch_enabled: true, cad_hatch_pattern: "diagonal" },
    }),
    line("water-network", "Cyan Water Service Network", "utility_corridor", [
      [siteW * 0.08, siteH * 0.18],
      [siteW * 0.26, siteH * 0.22],
      [siteW * 0.56, siteH * 0.20],
      [siteW * 0.78, siteH * 0.31],
      [siteW * 0.88, siteH * 0.55],
    ], { network: "water", ui_color: "#06b6d4" }),
    line("sanitary-network", "Magenta Sanitary / Parcel Service", "utility_corridor", [
      [siteW * 0.06, siteH * 0.74],
      [siteW * 0.26, siteH * 0.62],
      [siteW * 0.52, siteH * 0.57],
      [siteW * 0.76, siteH * 0.50],
    ], { network: "sanitary", ui_color: "#c026d3" }),
    line("storm-network", "Blue Storm Drainage", "utility_corridor", [
      [siteW * 0.18, siteH * 0.18],
      [siteW * 0.35, siteH * 0.33],
      [siteW * 0.46, siteH * 0.50],
      [siteW * 0.55, siteH * 0.66],
    ], { network: "storm", ui_color: "#0284c7" }),
    ...trees,
    ...contours,
  ];
};

export const createDemoPlanResponse = (): PlanResponse => ({
  success: true,
  message: "Demo workspace loaded for UI QA.",
  assumptions: [
    {
      field_name: "demo_mode",
      assumed_value: "UI-only seeded project",
      reason: "Allows dashboard and canvas review without authenticating.",
    },
  ],
  issues: [
    {
      severity: "warning",
      code: "DEMO_ENTRY_GEOMETRY",
      message: "Main entry curb returns need vehicle-turning review before the concept advances.",
    },
    {
      severity: "warning",
      code: "DEMO_BASIN_OUTLET",
      message: "Detention outlet elevation needs confirmation against controlled terrain.",
    },
  ],
  final_plan: {
    // The editable site-object model is the visual source of truth for this
    // demonstration. Keeping stale generated actions out prevents duplicate
    // geometry after a live object is edited.
    actions: [] as unknown as NonNullable<NonNullable<PlanResponse["final_plan"]>["actions"]>,
    meta: {
      engineering_status: { success: true, status: "demo_ready", trust_score: 82 },
      manager_export: {
        metrics: {
          storm_pipe_length_ft: 1240,
          pipe_capacity_total_cfs: 18.7,
          earthwork_net_cf: -8640,
        },
      },
      quantities: {
        totals: {
          lot_area_sf: 395200,
          building_area_sf: 17590,
          parking_area_sf: 36990,
          road_length_ft: 890,
          pipe_length_ft: 1240,
          utility_length_ft: 1510,
          sanitary_length_ft: 1080,
          estimated_impervious_area_sf: 112450,
          estimated_parking_stalls: 116,
          pond_count: 1,
          inlet_count: 5,
        },
      },
      storm_pipes: {
        total_system_flow_cfs: 18.7,
        total_system_capacity_cfs: 25.2,
        segments: [
          {
            id: "STM-1",
            pipe: "STM-1",
            from: "IN-1",
            to: "MH-1",
            length_ft: 320,
            slope_pct: 0.62,
            diameter_in: 18,
            flow_cfs: 4.8,
            capacity_cfs: 6.2,
            velocity_fps: 4.1,
            start_invert_ft: 638.1,
            end_invert_ft: 636.1,
            hgl_upstream_ft: 640.4,
            hgl_downstream_ft: 639.2,
            egl_upstream_ft: 640.9,
            egl_downstream_ft: 639.7,
            path: [[210, 245], [360, 302]],
          },
          {
            id: "STM-2",
            pipe: "STM-2",
            from: "MH-1",
            to: "MH-2",
            length_ft: 460,
            slope_pct: 0.48,
            diameter_in: 24,
            flow_cfs: 8.6,
            capacity_cfs: 11.4,
            velocity_fps: 4.7,
            start_invert_ft: 636.1,
            end_invert_ft: 633.9,
            hgl_upstream_ft: 639.2,
            hgl_downstream_ft: 637.6,
            egl_upstream_ft: 639.7,
            egl_downstream_ft: 638.0,
            path: [[360, 302], [510, 360]],
          },
          {
            id: "STM-3",
            pipe: "STM-3",
            from: "MH-2",
            to: "BASIN-A",
            length_ft: 460,
            slope_pct: 0.52,
            diameter_in: 30,
            flow_cfs: 18.7,
            capacity_cfs: 25.2,
            velocity_fps: 5.2,
            start_invert_ft: 633.9,
            end_invert_ft: 631.5,
            hgl_upstream_ft: 637.6,
            hgl_downstream_ft: 635.8,
            egl_upstream_ft: 638.0,
            egl_downstream_ft: 636.2,
            path: [[510, 360], [620, 420]],
          },
        ],
        hgl_profile: [
          { segment_id: "STM-1", station_ft: 0, invert_ft: 638.1, ground_ft: 643.8, hgl_ft: 640.4, egl_ft: 640.9 },
          { segment_id: "STM-1", station_ft: 320, invert_ft: 636.1, ground_ft: 642.2, hgl_ft: 639.2, egl_ft: 639.7 },
          { segment_id: "STM-2", station_ft: 780, invert_ft: 633.9, ground_ft: 640.0, hgl_ft: 637.6, egl_ft: 638.0 },
          { segment_id: "STM-3", station_ft: 1240, invert_ft: 631.5, ground_ft: 637.1, hgl_ft: 635.8, egl_ft: 636.2 },
        ],
        egl_profile: [
          { segment_id: "STM-1", station_ft: 0, egl_ft: 640.9 },
          { segment_id: "STM-1", station_ft: 320, egl_ft: 639.7 },
          { segment_id: "STM-2", station_ft: 780, egl_ft: 638.0 },
          { segment_id: "STM-3", station_ft: 1240, egl_ft: 636.2 },
        ],
        inlet_spread_checks: [
          { inlet_id: "IN-1", name: "IN-1", x: 210, y: 245, spread_ft: 6.2, allowable_spread_ft: 8, capture_efficiency: 0.86, bypass_cfs: 0.4, status: "ok" },
          { inlet_id: "IN-2", name: "IN-2", x: 472, y: 312, spread_ft: 8.7, allowable_spread_ft: 8, capture_efficiency: 0.74, bypass_cfs: 0.9, status: "review", warnings: ["Spread exceeds target by 0.7 ft."] },
        ],
        storm_depth_blocker_details: [
          {
            code: "inlet_spread_over_target",
            message: "IN-2 spread exceeds target by 0.7 ft.",
            exact_fix: "Add a nearby inlet, increase throat/grate capacity, or lower gutter bypass into STM-2 and rerun drainage.",
            can_civora_fix: true,
          },
        ],
      },
      drainage: {
        basins: [{ area_sf: 12900, footprint_area_sf: 12900 }],
        low_points: [{ x: 618, y: 428, z: 641.2 }],
        surface_guidance: { downhill_vector: { dx: 0.45, dy: -0.7 } },
        detention_routing: [
          { time_min: 0, inflow_cfs: 0, outflow_cfs: 0, stage_ft: 0, storage_cf: 0 },
          { time_min: 15, inflow_cfs: 24.5, outflow_cfs: 4.2, stage_ft: 1.4, storage_cf: 18000 },
          { time_min: 30, inflow_cfs: 18.7, outflow_cfs: 5.8, stage_ft: 2.6, storage_cf: 34200 },
          { time_min: 60, inflow_cfs: 7.4, outflow_cfs: 6.1, stage_ft: 2.1, storage_cf: 27600 },
          { time_min: 120, inflow_cfs: 1.2, outflow_cfs: 2.4, stage_ft: 0.8, storage_cf: 9600 },
        ],
        overflow_paths: [
          {
            id: "OF-1",
            name: "Emergency overflow",
            capacity_valid: true,
            capacity_cfs: 31.2,
            required_capacity_cfs: 24.5,
            freeboard_ft: 1.1,
            source: "demo_spillway_check",
            path: [[620, 420], [690, 450], [735, 468]],
          },
        ],
      },
      grading: {
        grading_source_quality: "demo_surface",
        grading_source_detail: "Seeded northwest-to-southeast slope for UI QA.",
        // Supply the samples claimed by this synthetic fixture, not surveyed terrain.
        surface_model: {
          source: "Synthetic demo surface — visual QA only, not survey/control",
          spot_elevations: Array.from({ length: 64 }, (_, index) => {
            const xRatio = (index % 8) / 7;
            const yRatio = Math.floor(index / 8) / 7;
            return { x: xRatio * 1000, y: yRatio * 700, z: 648 - 6.8 * (xRatio + yRatio) / 2 };
          }),
        },
        existing_surface: {
          range_z: 6.8,
          high_points: [{ x: 60, y: 60, z: 648.0 }],
          low_points: [{ x: 920, y: 630, z: 641.2 }],
          terrain_profile: {
            source_quality: "demo_surface",
            source_detail: "Synthetic surface for visual QA only.",
            terrain_stats: { sample_count: 64, missing_count: 0 },
            downhill_dx: 0.45,
            downhill_dy: -0.7,
          },
        },
        earthwork: { net_cf: -8640 },
      },
      truth_audit: { success: true },
    },
  },
});
