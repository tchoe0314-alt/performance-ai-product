import type {
  BuildingPlacement,
  ManualFields,
  ProjectInput,
  SiteInputs,
  SiteObjectType,
} from "../types";
import { isCustomGeometryMode, normalizeGeometryPoints } from "./objectGeometry";
import { requestedProgramToPendingPlacements } from "./siteObjectCatalog";

const numberFrom = (value: unknown) =>
  typeof value === "number" ? value : value !== undefined ? Number(value) : NaN;

const isSupportedPlacementSource = (value: unknown) =>
  value === "generated" ||
  value === "manual_drawn" ||
  value === "inferred" ||
  value === "detected_from_image" ||
  value === "user_confirmed";

const readSystemDependencies = (value: unknown) =>
  Array.isArray(value) ? (value as BuildingPlacement["systemDependencies"]) : undefined;

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
  const requestedProgramPlacements = requestedProgramToPendingPlacements(requestedProgram, baseRestoredPlacements);
  return [...baseRestoredPlacements, ...requestedProgramPlacements];
};
