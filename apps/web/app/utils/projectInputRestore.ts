import type {
  BuildingPlacement,
  ManualFields,
  ProjectInput,
  SiteInputs,
  SiteObjectType,
} from "../types";
import { isCustomGeometryMode, normalizeGeometryPoints } from "./objectGeometry";
import { requestedProgramToPendingPlacements, SITE_OBJECT_CATALOG } from "./siteObjectCatalog";

const numberFrom = (value: unknown) =>
  typeof value === "number" ? value : value !== undefined ? Number(value) : NaN;

const sourceBuildingHeight = (value: unknown) => {
  const properties = value && typeof value === "object" ? (value as Record<string, unknown>) : {};
  const osmTags = properties.osm_tags && typeof properties.osm_tags === "object"
    ? (properties.osm_tags as Record<string, unknown>)
    : {};
  const parseHeight = (raw: unknown, defaultMeters = false) => {
    if (raw === null || raw === undefined || raw === "") return null;
    const text = String(raw).trim().toLowerCase();
    const numeric = Number.parseFloat(text.replace(/,/g, ""));
    if (!Number.isFinite(numeric) || numeric <= 0) return null;
    const isMeters = /(?:^|\s)m(?:eters?)?$/.test(text) || text.includes("meter") || defaultMeters;
    const isFeet = text.includes("ft") || text.includes("feet") || text.includes("foot") || text.includes("'");
    return isMeters && !isFeet ? numeric * 3.280839895 : numeric;
  };
  const candidates: Array<{ value: unknown; defaultMeters?: boolean; source: string }> = [
    { value: properties.height_ft, source: "height_ft" },
    { value: properties.HEIGHT_FT, source: "HEIGHT_FT" },
    { value: properties.BLDGHEIGHT, source: "BLDGHEIGHT" },
    { value: properties.BUILDING_HEIGHT, source: "BUILDING_HEIGHT" },
    { value: osmTags.height, defaultMeters: true, source: "osm_tags.height" },
    { value: properties.height, source: "height" },
    { value: properties.HEIGHT, source: "HEIGHT" },
  ];
  for (const candidate of candidates) {
    const heightFt = parseHeight(candidate.value, candidate.defaultMeters);
    if (heightFt !== null) {
      return { heightFt: Math.max(8, Math.min(heightFt, 500)), source: candidate.source };
    }
  }
  const levels = Number(
    osmTags["building:levels"] ?? properties["building:levels"] ?? properties.NUMSTORIES ?? properties.STORIES ?? properties.FLOORS,
  );
  if (Number.isFinite(levels) && levels > 0) {
    return { heightFt: Math.max(8, Math.min(levels * 10, 500)), source: "levels_estimate" };
  }
  return { heightFt: null, source: "" };
};

const isSupportedPlacementSource = (value: unknown) =>
  value === "generated" ||
  value === "manual_drawn" ||
  value === "inferred" ||
  value === "detected_from_image" ||
  value === "detected_from_gis" ||
  value === "user_confirmed";

const readSystemDependencies = (value: unknown) =>
  Array.isArray(value) ? (value as BuildingPlacement["systemDependencies"]) : undefined;

const acceptedDraftType = (value: unknown): SiteObjectType => {
  const normalized = String(value ?? "").trim().toLowerCase();
  const mapped: Record<string, SiteObjectType> = {
    building: "building",
    building_footprint: "building",
    road: "road",
    road_or_drive: "road",
    road_row: "road",
    parking: "parking",
    parking_area: "parking",
    parking_object: "parking",
    sidewalk: "sidewalk",
    basin: "basin",
    open_space: "open_space",
    constraint_area: "no_build_zone",
    floodplain_wetland_constraint: "no_build_zone",
    existing_utility: "utility_corridor",
    utility: "utility_corridor",
    parcel_site_boundary: "lot_block",
    site_boundary_candidate: "lot_block",
    terrain_candidate: "custom",
    terrain_dem: "custom",
  };
  return mapped[normalized] ?? "custom";
};

const acceptedDraftDependencies = (
  type: SiteObjectType,
): BuildingPlacement["systemDependencies"] => {
  if (["building", "office_building", "retail_building", "multifamily_building", "industrial_building"].includes(type)) {
    return ["parking", "grading", "drainage", "utilities"];
  }
  if (["road", "driveway", "parking", "sidewalk"].includes(type)) {
    return ["roads", "parking", "grading", "drainage"];
  }
  if (["basin", "outfall", "inlet", "manhole"].includes(type)) return ["drainage"];
  if (type === "utility_corridor" || type === "hydrant") return ["utilities"];
  return ["roads", "parking", "grading", "drainage", "utilities"];
};

const geoJsonCoordinatePairs = (geometry: Record<string, unknown>): Array<[number, number]> => {
  const rawCoordinates = geometry.coordinates;
  if (!Array.isArray(rawCoordinates)) return [];
  const geometryType = String(geometry.type ?? "").toLowerCase();
  let coordinates: unknown[] = rawCoordinates;
  if (geometryType === "polygon") {
    coordinates = Array.isArray(rawCoordinates[0]) ? (rawCoordinates[0] as unknown[]) : [];
  } else if (geometryType === "multipolygon") {
    const firstPolygon = Array.isArray(rawCoordinates[0]) ? (rawCoordinates[0] as unknown[]) : [];
    coordinates = Array.isArray(firstPolygon[0]) ? (firstPolygon[0] as unknown[]) : [];
  } else if (geometryType === "point") {
    coordinates = [rawCoordinates];
  }
  return coordinates
    .map((value) => {
      if (!Array.isArray(value) || value.length < 2) return null;
      const x = Number(value[0]);
      const y = Number(value[1]);
      return Number.isFinite(x) && Number.isFinite(y) ? ([x, y] as [number, number]) : null;
    })
    .filter((value): value is [number, number] => Boolean(value));
};

const acceptedDraftGeometry = ({
  geometry,
  lot,
  viewportBounds,
  coordinateSpace,
}: {
  geometry: Record<string, unknown>;
  lot: { w?: number; h?: number };
  viewportBounds: SiteInputs["viewport_bounds"];
  coordinateSpace?: unknown;
}) => {
  const coordinates = geoJsonCoordinatePairs(geometry);
  if (!coordinates.length) return null;
  const west = Number(viewportBounds?.west);
  const east = Number(viewportBounds?.east);
  const south = Number(viewportBounds?.south);
  const north = Number(viewportBounds?.north);
  const lotWidth = Number(lot.w ?? viewportBounds?.width_ft);
  const lotHeight = Number(lot.h ?? viewportBounds?.height_ft);
  const canProject =
    Number.isFinite(west) &&
    Number.isFinite(east) &&
    Number.isFinite(south) &&
    Number.isFinite(north) &&
    east > west &&
    north > south &&
    Number.isFinite(lotWidth) &&
    Number.isFinite(lotHeight) &&
    lotWidth > 0 &&
    lotHeight > 0;
  const localCoordinateSpace = ["project_local", "local", "site", "feet", "ft"].includes(
    String(coordinateSpace ?? geometry.coordinate_space ?? geometry.units ?? "").trim().toLowerCase(),
  );
  const geographicCoordinates = coordinates.every(
    ([x, y]) => x >= -180 && x <= 180 && y >= -90 && y <= 90,
  );
  if (!localCoordinateSpace && (!canProject || !geographicCoordinates)) return null;
  const points = localCoordinateSpace
    ? coordinates
    : coordinates.map(
        ([lng, lat]) =>
          [
            ((lng - west) / (east - west)) * lotWidth,
            ((north - lat) / (north - south)) * lotHeight,
          ] as [number, number],
      );
  const xs = points.map(([x]) => x);
  const ys = points.map(([, y]) => y);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  if (Number.isFinite(lotWidth) && Number.isFinite(lotHeight) && lotWidth > 0 && lotHeight > 0) {
    const intersectsSite = maxX >= 0 && minX <= lotWidth && maxY >= 0 && minY <= lotHeight;
    const boundedNearSite =
      minX >= -lotWidth * 2 &&
      maxX <= lotWidth * 3 &&
      minY >= -lotHeight * 2 &&
      maxY <= lotHeight * 3;
    if (!intersectsSite || !boundedNearSite) return null;
  }
  const geometryType = String(geometry.type ?? "").toLowerCase();
  return {
    points,
    x: minX,
    y: minY,
    w: Math.max(4, maxX - minX),
    d: Math.max(4, maxY - minY),
    geometryType:
      geometryType.includes("polygon")
        ? ("polygon" as const)
        : geometryType.includes("line")
          ? ("polyline" as const)
          : ("point" as const),
  };
};

export const buildAcceptedCandidatePlacements = ({
  projectInput,
  siteInputs,
}: {
  projectInput: ProjectInput;
  siteInputs: SiteInputs;
}): BuildingPlacement[] => {
  const manualFields = projectInput.manual_fields ?? {};
  const lot = (manualFields.lot ?? {}) as { w?: number; h?: number };
  return (siteInputs.candidate_review_accepted_drafts_v1 ?? [])
    .flatMap((raw, index): BuildingPlacement[] => {
      if (!raw || typeof raw !== "object") return [];
      const record = raw as Record<string, unknown>;
      const type = acceptedDraftType(record.object_type ?? record.feature_type);
      const defaults = SITE_OBJECT_CATALOG[type] ?? SITE_OBJECT_CATALOG.custom;
      const geometry =
        record.geometry && typeof record.geometry === "object"
          ? acceptedDraftGeometry({
              geometry: record.geometry as Record<string, unknown>,
              lot,
              viewportBounds: siteInputs.viewport_bounds,
              coordinateSpace: record.correction_coordinate_space ?? record.coordinate_space,
            })
          : null;
      // Source-level candidates (for example a parcel service summary) can be
      // accepted as project context without containing an individual feature
      // geometry. Do not invent a default rectangle for those records. Only
      // accepted candidates with usable geometry belong on the canvas.
      if (!geometry) return [];
      const sourceCandidateId = String(record.source_candidate_id ?? record.candidate_id ?? `accepted-${index + 1}`);
      const sourceType = String(record.source_type ?? "");
      const sourceProperties = record.source_properties && typeof record.source_properties === "object"
        ? (record.source_properties as Record<string, unknown>)
        : record.properties && typeof record.properties === "object"
          ? (record.properties as Record<string, unknown>)
          : {};
      const sourceHeight = type === "building" ? sourceBuildingHeight(sourceProperties) : { heightFt: null, source: "" };
      const source =
        sourceType.includes("image") || sourceType.includes("imagery")
          ? "detected_from_image"
          : "detected_from_gis";
      const placement: BuildingPlacement = {
        id: String(record.object_id ?? `draft_${sourceCandidateId}`),
        label: String(record.label ?? record.source_name ?? `${defaults.label} candidate`),
        type,
        x: geometry?.x,
        y: geometry?.y,
        w: geometry.w,
        d: geometry.d,
        h: sourceHeight.heightFt ?? defaults.defaultH,
        placed: true,
        source,
        confidence:
          typeof record.confidence === "number" ? Math.max(0, Math.min(1, record.confidence)) : undefined,
        confirmed: true,
        geometryType: geometry.geometryType,
        geometry: geometry.points,
        systemDependencies: acceptedDraftDependencies(type),
        meta: {
          accepted_source_candidate: true,
          source_candidate_id: sourceCandidateId,
          source_type: record.source_type,
          source_url: record.source_url,
          source_name: record.source_name,
          source_geometry: record.geometry,
          source_properties: sourceProperties,
          source_height_ft: sourceHeight.heightFt,
          source_height_method: sourceHeight.source,
          review_required: true,
          acceptance_status: "accepted",
        },
      };
      return [placement];
    });
};

const parseBuildingPlacements = (
  manualFields: ManualFields,
  buildingsList: NonNullable<ManualFields["buildings"]>,
): BuildingPlacement[] =>
  buildingsList
    .map((raw, idx) => {
      if (!raw || typeof raw !== "object") return null;
      const rec = raw as Record<string, unknown>;
      const originRaw = (rec as { origin?: unknown }).origin;
      const origin = Array.isArray(originRaw) ? originRaw : [];
      const rawX = rec.x ?? origin[0];
      const rawY = rec.y ?? origin[1];
      const x = numberFrom(rawX);
      const y = numberFrom(rawY);
      const rawW = rec.w ?? rec.width ?? manualFields.building_width;
      const rawD = rec.d ?? rec.depth ?? manualFields.building_depth;
      const w = numberFrom(rawW);
      const d = numberFrom(rawD);
      if (!Number.isFinite(w) || !Number.isFinite(d)) return null;
      const placed = rec.placed === false ? false : Number.isFinite(x) && Number.isFinite(y);
      const geometryType = isCustomGeometryMode(rec.geometry_type) ? rec.geometry_type : undefined;
      const geometry = normalizeGeometryPoints(rec.geometry);
      return {
        id: typeof rec.id === "string" ? rec.id : `building-${Date.now()}-${idx}`,
        label:
          typeof rec.label === "string"
            ? rec.label
            : typeof rec.name === "string"
              ? rec.name
              : `Building ${idx + 1}`,
        type: (typeof rec.type === "string" ? rec.type : "building") as SiteObjectType,
        x: placed ? x : undefined,
        y: placed ? y : undefined,
        w,
        d,
        rotation: typeof rec.rotation === "number" ? rec.rotation : undefined,
        use: typeof rec.use === "string" ? rec.use : undefined,
        locked: Boolean(rec.locked),
        placed,
        source: isSupportedPlacementSource(rec.source) ? rec.source : "user",
        generated: Boolean(rec.generated),
        geometryType,
        geometry: geometry?.length ? geometry : undefined,
        meta: rec.meta && typeof rec.meta === "object" ? (rec.meta as Record<string, unknown>) : undefined,
        systemDependencies: readSystemDependencies(rec.systemDependencies),
      } as BuildingPlacement;
    })
    .filter(Boolean) as BuildingPlacement[];

const parsePondPlacements = (manualFields: ManualFields): BuildingPlacement[] =>
  (Array.isArray(manualFields.ponds) ? manualFields.ponds : [])
    .map((raw, idx) => {
      if (!raw || typeof raw !== "object") return null;
      const rec = raw as Record<string, unknown>;
      const x = numberFrom(rec.x);
      const y = numberFrom(rec.y);
      const w = numberFrom(rec.w ?? 60);
      const d = numberFrom(rec.d ?? 40);
      if (!Number.isFinite(w) || !Number.isFinite(d)) return null;
      const placed = rec.placed === false ? false : Number.isFinite(x) && Number.isFinite(y);
      return {
        id: typeof rec.id === "string" ? rec.id : `basin-${Date.now()}-${idx}`,
        label:
          typeof rec.label === "string"
            ? rec.label
            : typeof rec.name === "string"
              ? rec.name
              : "Basin",
        type: "basin" as SiteObjectType,
        x: placed ? x : undefined,
        y: placed ? y : undefined,
        w,
        d,
        rotation: typeof rec.rotation === "number" ? rec.rotation : undefined,
        locked: Boolean(rec.locked),
        placed,
        source: typeof rec.source === "string" ? rec.source : "generated",
        generated: Boolean(rec.generated),
        systemDependencies: Array.isArray(rec.systemDependencies)
          ? (rec.systemDependencies as string[])
          : ["drainage"],
      } as BuildingPlacement;
    })
    .filter(Boolean) as BuildingPlacement[];

const parseInletPlacements = (manualFields: ManualFields): BuildingPlacement[] =>
  (Array.isArray((manualFields.drainage ?? {}).forced_inlets)
    ? ((manualFields.drainage ?? {}).forced_inlets as Array<Record<string, unknown>>)
    : []
  )
    .map((raw, idx) => {
      if (!raw || typeof raw !== "object") return null;
      const rec = raw as Record<string, unknown>;
      const x = numberFrom(rec.x);
      const y = numberFrom(rec.y);
      if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
      return {
        id: typeof rec.id === "string" ? rec.id : `inlet-${Date.now()}-${idx}`,
        label:
          typeof rec.label === "string"
            ? rec.label
            : typeof rec.name === "string"
              ? rec.name
              : "Inlet",
        type: "inlet" as SiteObjectType,
        x,
        y,
        w: 8,
        d: 8,
        rotation: 0,
        locked: Boolean(rec.locked),
        placed: true,
        source: typeof rec.source === "string" ? rec.source : "generated",
        generated: Boolean(rec.generated),
        systemDependencies: ["drainage"],
      } as BuildingPlacement;
    })
    .filter(Boolean) as BuildingPlacement[];

const parseSiteObjectPlacements = (manualFields: ManualFields): BuildingPlacement[] =>
  (Array.isArray(manualFields.site_objects) ? manualFields.site_objects : [])
    .map((raw, idx) => {
      if (!raw || typeof raw !== "object") return null;
      const rec = raw as Record<string, unknown>;
      const x = numberFrom(rec.x);
      const y = numberFrom(rec.y);
      const w = numberFrom(rec.w ?? 10);
      const d = numberFrom(rec.d ?? 10);
      if (!Number.isFinite(w) || !Number.isFinite(d)) return null;
      const placed = rec.placed === false ? false : Number.isFinite(x) && Number.isFinite(y);
      const geometryType = isCustomGeometryMode(rec.geometry_type) ? rec.geometry_type : undefined;
      const geometry = normalizeGeometryPoints(rec.geometry);
      return {
        id: typeof rec.id === "string" ? rec.id : `site-object-${Date.now()}-${idx}`,
        label:
          typeof rec.label === "string"
            ? rec.label
            : typeof rec.name === "string"
              ? rec.name
              : `Object ${idx + 1}`,
        type: (typeof rec.type === "string" ? rec.type : "custom") as SiteObjectType,
        x: placed ? x : undefined,
        y: placed ? y : undefined,
        w,
        d,
        h: typeof rec.height_ft === "number" ? rec.height_ft : undefined,
        rotation: typeof rec.rotation === "number" ? rec.rotation : undefined,
        locked: Boolean(rec.locked),
        placed,
        source: isSupportedPlacementSource(rec.source) ? rec.source : "manual_drawn",
        generated: Boolean(rec.generated),
        geometryType,
        geometry: geometry?.length ? geometry : undefined,
        meta: rec.meta && typeof rec.meta === "object" ? (rec.meta as Record<string, unknown>) : undefined,
        systemDependencies:
          readSystemDependencies(rec.systemDependencies) ?? ["roads", "parking", "grading", "drainage", "utilities"],
      } as BuildingPlacement;
    })
    .filter(Boolean) as BuildingPlacement[];

const buildRestoredSiteBoundary = ({
  manualFields,
  lot,
  siteInputs,
  hasRestoredSiteObject,
}: {
  manualFields: ManualFields;
  lot: { w?: number; h?: number };
  siteInputs: SiteInputs;
  hasRestoredSiteObject: boolean;
}): BuildingPlacement[] => {
  const siteBoundaryGeometry = siteInputs?.site_boundary_geometry;
  return !hasRestoredSiteObject && lot.w && lot.h
    ? [{
        id: "restored-site-boundary",
        label: "Site Boundary",
        type: "site" as SiteObjectType,
        x: 0,
        y: 0,
        w: Number(lot.w),
        d: Number(lot.h),
        rotation: 0,
        locked: Boolean(siteInputs?.site_alignment_locked),
        placed: true,
        source: siteBoundaryGeometry?.source === "manual_drawn" ? "manual_drawn" : "user",
        generated: false,
        geometryType: siteBoundaryGeometry?.type === "polygon" ? "polygon" as const : undefined,
        geometry: Array.isArray(siteBoundaryGeometry?.vertices)
          ? siteBoundaryGeometry.vertices
              .map((point) => [Number(point.x), Number(point.y)] as [number, number])
              .filter(([x, y]) => Number.isFinite(x) && Number.isFinite(y))
          : undefined,
        capabilities: {
          movable: false,
          resizable: false,
          rotatable: false,
          deletable: false,
        },
        systemDependencies: ["roads", "parking", "grading", "drainage", "utilities"],
        meta: {
          category: "site",
          site_boundary_state: siteInputs?.site_boundary_state || (siteInputs?.site_alignment_locked ? "locked_canonical" : "draft_editable"),
          source: siteBoundaryGeometry?.source || "project_input",
          engineering_status: "review_required",
          construction_release_allowed: false,
          units: manualFields.units ?? "ft",
        },
      } satisfies BuildingPlacement]
    : [];
};

export const buildProjectInputPlacements = ({
  projectInput,
  siteInputs,
}: {
  projectInput: ProjectInput;
  siteInputs: SiteInputs;
}): BuildingPlacement[] => {
  const manualFields = projectInput.manual_fields ?? {};
  const lot = (manualFields.lot ?? {}) as { w?: number; h?: number };
  const requestedProgram = projectInput.meta?.requested_site_program_v1;
  const buildingsList = Array.isArray(manualFields.buildings) ? manualFields.buildings : [];
  const parsedPlacements = parseBuildingPlacements(manualFields, buildingsList);
  const pondPlacements = parsePondPlacements(manualFields);
  const inletPlacements = parseInletPlacements(manualFields);
  const siteObjectPlacements = parseSiteObjectPlacements(manualFields);
  const hasRestoredSiteObject = [...siteObjectPlacements, ...parsedPlacements, ...pondPlacements, ...inletPlacements]
    .some((item) => item.type === "site");
  const restoredSiteBoundary = buildRestoredSiteBoundary({
    manualFields,
    lot,
    siteInputs,
    hasRestoredSiteObject,
  });
  const baseRestoredPlacements = siteObjectPlacements.length
    ? siteObjectPlacements
    : [...restoredSiteBoundary, ...parsedPlacements, ...pondPlacements, ...inletPlacements];
  const acceptedCandidatePlacements = buildAcceptedCandidatePlacements({ projectInput, siteInputs });
  const acceptedCandidateIds = new Set(acceptedCandidatePlacements.map((item) => item.id));
  const restoredWithAccepted = [
    ...baseRestoredPlacements.filter((item) => !acceptedCandidateIds.has(item.id)),
    ...acceptedCandidatePlacements,
  ];
  const requestedProgramPlacements = requestedProgramToPendingPlacements(requestedProgram, restoredWithAccepted);
  return [...restoredWithAccepted, ...requestedProgramPlacements];
};
