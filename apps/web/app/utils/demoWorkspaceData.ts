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
    label: "Pinecrest Site",
    type: "site",
    w: 760,
    d: 520,
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
    label: "Multifamily Building A",
    type: "multifamily_building",
    w: 110,
    d: 58,
    h: 36,
    x: 120,
    y: 95,
    rotation: 0,
    placed: true,
    source: "user_confirmed",
  },
  {
    id: "demo-building-b",
    label: "Multifamily Building B",
    type: "multifamily_building",
    w: 110,
    d: 58,
    h: 36,
    x: 330,
    y: 82,
    rotation: 0,
    placed: true,
    source: "user_confirmed",
  },
  {
    id: "demo-retail",
    label: "Retail Building",
    type: "retail_building",
    w: 70,
    d: 45,
    h: 24,
    x: 96,
    y: 350,
    rotation: 0,
    placed: true,
    source: "user_confirmed",
  },
  {
    id: "demo-loop-road",
    label: "Internal Loop Road",
    type: "road",
    w: 590,
    d: 28,
    x: 70,
    y: 275,
    rotation: 0,
    placed: true,
    source: "user_confirmed",
    geometryType: "polyline",
    geometry: [
      [82, 294],
      [210, 320],
      [500, 320],
      [668, 330],
      [704, 498],
      [126, 498],
      [82, 294],
    ],
  },
  {
    id: "demo-parking-north",
    label: "Residential Parking Court",
    type: "parking",
    w: 210,
    d: 104,
    x: 255,
    y: 190,
    rotation: 0,
    stallCount: 72,
    placed: true,
    source: "user_confirmed",
  },
  {
    id: "demo-parking-retail",
    label: "Retail Parking Field",
    type: "parking",
    w: 165,
    d: 92,
    x: 185,
    y: 345,
    rotation: 0,
    stallCount: 44,
    placed: true,
    source: "user_confirmed",
  },
  {
    id: "demo-basin-a",
    label: "Detention Basin A",
    type: "basin",
    w: 150,
    d: 86,
    x: 540,
    y: 380,
    rotation: 0,
    placed: true,
    source: "user_confirmed",
  },
  {
    id: "demo-sidewalk",
    label: "ADA Pedestrian Route",
    type: "sidewalk",
    w: 410,
    d: 8,
    x: 120,
    y: 305,
    placed: true,
    source: "user_confirmed",
    geometryType: "polyline",
    geometry: [
      [122, 314],
      [255, 314],
      [365, 246],
      [500, 246],
      [592, 388],
    ],
  },
  {
    id: "demo-inlet-1",
    label: "Storm Inlet S-15",
    type: "inlet",
    w: 12,
    d: 12,
    x: 472,
    y: 312,
    placed: true,
    source: "generated",
  },
  {
    id: "demo-hydrant-1",
    label: "Hydrant W-12",
    type: "hydrant",
    w: 10,
    d: 10,
    x: 238,
    y: 270,
    placed: true,
    source: "generated",
  },
];

export const createDenseCommercialConceptPlacements = (lot: { w: number; h: number }): BuildingPlacement[] => {
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
    meta: {
      dense_concept_generated: true,
      draft_review_required: true,
      construction_release_allowed: false,
      source_confidence: "user_confirmed_review_geometry",
      ...(extra.meta ?? {}),
    },
    ...extra,
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
  const buildingW = Math.min(205, siteW * 0.22);
  const buildingD = Math.min(86, siteH * 0.09);
  const parkingW = Math.min(310, siteW * 0.32);
  const parkingD = Math.min(118, siteH * 0.12);
  return [
    place("office-main", "Office Building - 28,000 sf", "office_building", siteW * 0.38, siteH * 0.18, buildingW, buildingD, {
      h: 34,
      meta: { requested_area_sf: 28000, dense_concept_generated: true },
    }),
    place("office-flex", "Future Flex / Service Pad", "building", siteW * 0.16, siteH * 0.21, buildingW * 0.72, buildingD * 0.7, {
      h: 24,
      meta: { dense_concept_generated: true },
    }),
    place("parking-north", "Parking Field - 84 stalls", "parking", siteW * 0.34, siteH * 0.34, parkingW, parkingD, {
      stallCount: 84,
      meta: { requested_stalls: 84, parkingCapacity: 96, parkingModuleCols: 12, parkingModuleRows: 4, dense_concept_generated: true },
    }),
    place("parking-south", "Parking Field - 56 stalls", "parking", siteW * 0.20, siteH * 0.63, parkingW * 0.86, parkingD * 0.92, {
      stallCount: 56,
      meta: { requested_stalls: 56, parkingCapacity: 64, parkingModuleCols: 8, parkingModuleRows: 4, dense_concept_generated: true },
    }),
    place("basin", "Detention Basin A", "basin", siteW * 0.68, siteH * 0.66, siteW * 0.18, siteH * 0.12, {
      meta: { normal_pool_elevation_ft: 1012.4, bottom_elevation_ft: 1007.2, dense_concept_generated: true },
    }),
    line("loop-road", "Internal Loop Drive", "road", [
      [siteW * 0.13, siteH * 0.54],
      [siteW * 0.27, siteH * 0.50],
      [siteW * 0.68, siteH * 0.50],
      [siteW * 0.80, siteH * 0.58],
      [siteW * 0.70, siteH * 0.79],
      [siteW * 0.22, siteH * 0.79],
      [siteW * 0.13, siteH * 0.54],
    ], { corridor_width_ft: 28, dense_concept_generated: true }),
    line("driveway", "Driveway Connection", "driveway", [
      [siteW * 0.03, siteH * 0.55],
      [siteW * 0.13, siteH * 0.54],
      [siteW * 0.27, siteH * 0.50],
    ], { corridor_width_ft: 30, dense_concept_generated: true }),
    line("ada-route", "Sidewalk / ADA Route", "sidewalk", [
      [siteW * 0.20, siteH * 0.36],
      [siteW * 0.36, siteH * 0.36],
      [siteW * 0.48, siteH * 0.27],
      [siteW * 0.60, siteH * 0.36],
      [siteW * 0.72, siteH * 0.66],
    ], { routeKind: "ada_review_route", dense_concept_generated: true }),
    line("water-main", "Public Water Line", "utility_corridor", [
      [siteW * 0.06, siteH * 0.31],
      [siteW * 0.25, siteH * 0.31],
      [siteW * 0.48, siteH * 0.28],
      [siteW * 0.74, siteH * 0.39],
    ], { network: "water", dense_concept_generated: true }),
    line("sanitary-main", "Public Sanitary Line", "utility_corridor", [
      [siteW * 0.08, siteH * 0.86],
      [siteW * 0.42, siteH * 0.86],
      [siteW * 0.66, siteH * 0.80],
      [siteW * 0.84, siteH * 0.74],
    ], { network: "sanitary", dense_concept_generated: true }),
    line("storm-main", "Storm Sewer", "utility_corridor", [
      [siteW * 0.43, siteH * 0.47],
      [siteW * 0.62, siteH * 0.51],
      [siteW * 0.73, siteH * 0.62],
      [siteW * 0.78, siteH * 0.72],
    ], { network: "storm", dense_concept_generated: true }),
    place("inlet-a", "Storm Inlet S-1", "inlet", siteW * 0.46, siteH * 0.46, 12, 12, { meta: { dense_concept_generated: true } }),
    place("inlet-b", "Storm Inlet S-2", "inlet", siteW * 0.66, siteH * 0.57, 12, 12, { meta: { dense_concept_generated: true } }),
    place("outfall", "Outfall OF-1", "outfall", siteW * 0.78, siteH * 0.72, 12, 12, { meta: { dense_concept_generated: true } }),
    place("hydrant-a", "Hydrant W-1", "hydrant", siteW * 0.24, siteH * 0.31, 10, 10, { meta: { dense_concept_generated: true } }),
    place("hydrant-b", "Hydrant W-2", "hydrant", siteW * 0.70, siteH * 0.43, 10, 10, { meta: { dense_concept_generated: true } }),
    place("manhole-a", "Sanitary Manhole SS-1", "manhole", siteW * 0.52, siteH * 0.82, 12, 12, { meta: { network: "sanitary", dense_concept_generated: true } }),
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
      code: "DEMO_WATER_CLEARANCE",
      message: "Water line W-12 conflicts with proposed building clearance envelope.",
    },
    {
      severity: "warning",
      code: "DEMO_ROAD_GRADE",
      message: "Roadway R-03 exceeds target max grade in one localized segment.",
    },
  ],
  final_plan: {
    actions: [
      { label: "Multifamily Building A", layer: "BUILDING", task: "rectangle", origin: [120, 95], width: 110, height: 58, meta: { preview_role: "final" } } as Record<string, unknown>,
      { label: "Multifamily Building B", layer: "BUILDING", task: "rectangle", origin: [330, 82], width: 110, height: 58, meta: { preview_role: "final" } } as Record<string, unknown>,
      { label: "Retail Building", layer: "BUILDING", task: "rectangle", origin: [96, 350], width: 70, height: 45, meta: { preview_role: "final" } } as Record<string, unknown>,
      { label: "Residential Parking", layer: "PARKING", task: "rectangle", origin: [255, 190], width: 210, height: 104, meta: { preview_role: "final", system: "parking" } } as Record<string, unknown>,
      { label: "Detention Basin A", layer: "POND", task: "rectangle", origin: [540, 380], width: 150, height: 86, meta: { preview_role: "final", system: "drainage" } } as Record<string, unknown>,
    ] as unknown as NonNullable<NonNullable<PlanResponse["final_plan"]>["actions"]>,
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
        existing_surface: {
          range_z: 6.8,
          high_points: [{ x: 60, y: 60, z: 648.0 }],
          low_points: [{ x: 690, y: 460, z: 641.2 }],
          terrain_profile: {
            source_quality: "demo_surface",
            source_detail: "Synthetic surface for visual QA only.",
            terrain_stats: { sample_count: 144, missing_count: 0 },
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
