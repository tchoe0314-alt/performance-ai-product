import type { BuildingPlacement, RequestedSiteProgramV1, SiteObjectType } from "../types";

export const ADD_MENU_SECTIONS: Array<{
  title: string;
  key: string;
  items: SiteObjectType[];
  collapsible?: boolean;
}> = [
  {
    title: "Site",
    key: "site",
    items: ["site", "setback_zone", "no_build_zone"],
  },
  {
    title: "Buildings & Program",
    key: "buildings",
    items: [
      "building",
      "retail_building",
      "multifamily_building",
      "industrial_building",
      "office_building",
      "pad",
      "pool",
      "amenity",
      "open_space",
      "landscape",
    ],
  },
  {
    title: "Access & Parking",
    key: "access",
    items: ["entrance", "driveway", "road", "parking", "sidewalk"],
  },
  {
    title: "Drainage & Water",
    key: "drainage",
    items: ["basin", "outfall", "inlet", "manhole", "hydrant"],
  },
  {
    title: "Advanced",
    key: "advanced",
    items: ["utility_corridor", "lot_block", "bridge"],
    collapsible: true,
  },
];

export const SITE_OBJECT_CATALOG: Record<
  SiteObjectType,
  { label: string; category: string; defaultW: number; defaultD: number; defaultH?: number; use?: string }
> = {
  site: { label: "Site", category: "site", defaultW: 400, defaultD: 300 },
  setback_zone: { label: "Setback Zone", category: "site", defaultW: 200, defaultD: 120 },
  no_build_zone: { label: "No-Build Zone", category: "site", defaultW: 160, defaultD: 120 },
  building: { label: "Building", category: "buildings", defaultW: 80, defaultD: 50, defaultH: 30 },
  retail_building: {
    label: "Retail Building",
    category: "buildings",
    defaultW: 70,
    defaultD: 45,
    defaultH: 24,
    use: "retail",
  },
  multifamily_building: {
    label: "Multifamily Building",
    category: "buildings",
    defaultW: 110,
    defaultD: 58,
    defaultH: 36,
    use: "multifamily",
  },
  industrial_building: {
    label: "Industrial Building",
    category: "buildings",
    defaultW: 140,
    defaultD: 90,
    defaultH: 36,
    use: "industrial",
  },
  office_building: {
    label: "Office Building",
    category: "buildings",
    defaultW: 100,
    defaultD: 60,
    defaultH: 30,
    use: "office",
  },
  pad: { label: "Pad", category: "buildings", defaultW: 60, defaultD: 40, defaultH: 4 },
  pool: { label: "Pool", category: "buildings", defaultW: 50, defaultD: 30, defaultH: 6 },
  amenity: { label: "Amenity Area", category: "buildings", defaultW: 80, defaultD: 40, defaultH: 12 },
  open_space: { label: "Open Space", category: "buildings", defaultW: 120, defaultD: 80, defaultH: 0 },
  landscape: { label: "Landscape / Tree", category: "buildings", defaultW: 18, defaultD: 18, defaultH: 10 },
  entrance: { label: "Entrance / Access", category: "access", defaultW: 24, defaultD: 24 },
  driveway: { label: "Driveway", category: "access", defaultW: 60, defaultD: 16 },
  road: { label: "Road / Drive Aisle", category: "access", defaultW: 120, defaultD: 28 },
  parking: { label: "Parking Field", category: "access", defaultW: 140, defaultD: 60 },
  sidewalk: { label: "Sidewalk / Path", category: "access", defaultW: 80, defaultD: 12 },
  basin: { label: "Basin / Detention Pond", category: "drainage", defaultW: 90, defaultD: 60 },
  outfall: { label: "Outfall Point", category: "drainage", defaultW: 18, defaultD: 18 },
  inlet: { label: "Inlet", category: "drainage", defaultW: 12, defaultD: 12 },
  manhole: { label: "Manhole", category: "drainage", defaultW: 12, defaultD: 12 },
  hydrant: { label: "Hydrant", category: "drainage", defaultW: 10, defaultD: 10 },
  utility_corridor: { label: "Utility Corridor", category: "advanced", defaultW: 140, defaultD: 24 },
  lot_block: { label: "Lot / Subdivision Block", category: "advanced", defaultW: 160, defaultD: 120 },
  bridge: { label: "Bridge", category: "advanced", defaultW: 80, defaultD: 24 },
  custom: { label: "Custom Geometry", category: "advanced", defaultW: 40, defaultD: 40 },
};

const REQUESTED_PROGRAM_OBJECT_TYPE_MAP: Record<string, SiteObjectType> = {
  office_building: "office_building",
  building: "building",
  parking: "parking",
  detention_basin: "basin",
  basin: "basin",
  driveway: "driveway",
  road: "road",
  sidewalk: "sidewalk",
  ada_route: "sidewalk",
  water: "utility_corridor",
  sanitary: "utility_corridor",
  storm: "utility_corridor",
};

export const requestedProgramToPendingPlacements = (
  program: RequestedSiteProgramV1 | undefined,
  existing: BuildingPlacement[] = [],
): BuildingPlacement[] => {
  if (!program || typeof program !== "object") return [];
  const existingKeys = new Set(
    existing
      .map((item) => `${item.type ?? "custom"}:${String(item.meta?.requested_program_key ?? item.label).toLowerCase()}`)
      .filter(Boolean),
  );
  const pending: BuildingPlacement[] = [];
  const addPending = (
    rawType: string,
    label: string,
    extra: Partial<BuildingPlacement> = {},
    meta: Record<string, unknown> = {},
  ) => {
    const type = REQUESTED_PROGRAM_OBJECT_TYPE_MAP[rawType] ?? "custom";
    const catalog = SITE_OBJECT_CATALOG[type] ?? SITE_OBJECT_CATALOG.custom;
    const key = `${type}:${label.toLowerCase()}`;
    if (existingKeys.has(key) || pending.some((item) => `${item.type}:${item.label.toLowerCase()}` === key)) {
      return;
    }
    pending.push({
      id: `requested-${rawType}-${pending.length + 1}`,
      label,
      type,
      w: extra.w ?? catalog.defaultW,
      d: extra.d ?? catalog.defaultD,
      h: extra.h ?? catalog.defaultH,
      stallCount: extra.stallCount,
      rotation: 0,
      placed: false,
      locked: false,
      source: "user",
      generated: false,
      capabilities: {
        movable: true,
        resizable: true,
        rotatable: true,
        deletable: true,
      },
      systemDependencies: extra.systemDependencies ?? ["roads", "parking", "grading", "drainage", "utilities"],
      meta: {
        requested_program_key: label,
        requested_program_source: program.source || "chat_natural_language",
        draft_review_required: true,
        construction_release_allowed: false,
        ...meta,
      },
    });
  };

  (program.requested_objects ?? []).forEach((item) => {
    const rawType = String(item.type || "").trim();
    if (!rawType) return;
    if (rawType === "office_building") {
      const area = typeof item.area_sf === "number" ? item.area_sf : undefined;
      const depth = area ? Math.round(Math.sqrt(area / 1.8)) : SITE_OBJECT_CATALOG.office_building.defaultD;
      const width = area ? Math.round(area / Math.max(depth, 1)) : SITE_OBJECT_CATALOG.office_building.defaultW;
      addPending(
        rawType,
        area ? `Office Building - ${Math.round(area).toLocaleString()} sf` : item.label || "Office Building",
        { w: width, d: depth, h: SITE_OBJECT_CATALOG.office_building.defaultH, systemDependencies: ["parking", "grading", "drainage", "utilities"] },
        area ? { requested_area_sf: Math.round(area) } : {},
      );
      return;
    }
    if (rawType === "parking") {
      const stalls = typeof item.stall_count === "number" ? item.stall_count : undefined;
      addPending(
        rawType,
        stalls ? `Parking Field - ${Math.round(stalls)} stalls` : item.label || "Parking Field",
        { stallCount: stalls, w: SITE_OBJECT_CATALOG.parking.defaultW, d: SITE_OBJECT_CATALOG.parking.defaultD, systemDependencies: ["parking", "grading", "drainage"] },
        stalls ? { requested_stalls: Math.round(stalls) } : {},
      );
      return;
    }
    const fallbackLabel =
      rawType === "detention_basin"
        ? "Detention Basin"
        : rawType === "driveway"
          ? "Driveway Connection"
          : rawType === "sidewalk" || rawType === "ada_route"
            ? "Sidewalk / ADA Route"
            : SITE_OBJECT_CATALOG[REQUESTED_PROGRAM_OBJECT_TYPE_MAP[rawType] ?? "custom"]?.label || rawType;
    addPending(rawType, fallbackLabel);
  });

  (program.requested_systems ?? []).forEach((system) => {
    const key = String(system || "").toLowerCase();
    if (key === "water") {
      addPending("water", "Public Water Line", { systemDependencies: ["utilities"] }, { network: "water" });
    } else if (key === "sanitary") {
      addPending("sanitary", "Public Sanitary Line", { systemDependencies: ["utilities"] }, { network: "sanitary" });
    } else if (key === "storm") {
      addPending("storm", "Storm Sewer", { systemDependencies: ["drainage", "utilities"] }, { network: "storm" });
    }
  });

  return pending;
};
