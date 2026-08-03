import type {
  BuildingPlacement,
  CanonicalGeometryHandoffV1,
  ManualFields,
  SiteObjectType,
  SurveySlopeResponse,
} from "../types";
import { buildCanonicalGeometryHandoffV1, isCustomGeometryMode } from "./objectGeometry";
import { parsePositiveNumber } from "./formatting";

export function buildDashboardManualFields({
    nextSiteName,
    nextFileName,
    nextUnits,
    nextProjectType,
    nextLotWidth,
    nextLotHeight,
    nextSetback,
    nextBuildingWidth,
    nextBuildingDepth,
    nextBuildingCount,
    nextParkingCount,
    nextMinSlopePct,
    nextPipeMinSlopePct,
    nextMaxParkingSlopePct,
    nextMaxRoadGradePct,
    nextMaxAdaCrossSlopePct,
    nextRoads,
    nextGrading,
    nextDrainage,
    nextUtilities,
    placementsOverride,
    buildingPlacements,
    surveySlopeEstimate,
    drainageForcedInlets,
    drainageConnectOrphans,
    drainageAllowSlopeAdjust,
    drainageMaxSlopeAdjust,
  }: {
    nextSiteName: string;
    nextFileName: string;
    nextUnits: string;
    nextProjectType: string;
    nextLotWidth: string | number | null | undefined;
    nextLotHeight: string | number | null | undefined;
    nextSetback: string | number | null | undefined;
    nextBuildingWidth: string | number | null | undefined;
    nextBuildingDepth: string | number | null | undefined;
    nextBuildingCount: string | number | null | undefined;
    nextParkingCount: string | number | null | undefined;
    nextMinSlopePct: string | number | null | undefined;
    nextPipeMinSlopePct: string | number | null | undefined;
    nextMaxParkingSlopePct: string | number | null | undefined;
    nextMaxRoadGradePct: string | number | null | undefined;
    nextMaxAdaCrossSlopePct: string | number | null | undefined;
    nextRoads: boolean;
    nextGrading: boolean;
    nextDrainage: boolean;
    nextUtilities: boolean;
    placementsOverride?: BuildingPlacement[];
    buildingPlacements: BuildingPlacement[];
    surveySlopeEstimate?: SurveySlopeResponse | null;
    drainageForcedInlets: Array<Record<string, unknown>>;
    drainageConnectOrphans: boolean;
    drainageAllowSlopeAdjust: boolean;
    drainageMaxSlopeAdjust: number;
  }) {
    const lotWidthValue = parsePositiveNumber(nextLotWidth);
    const lotHeightValue = parsePositiveNumber(nextLotHeight);
    const setbackValue = parsePositiveNumber(nextSetback);
    const buildingWidthValue = parsePositiveNumber(nextBuildingWidth);
    const buildingDepthValue = parsePositiveNumber(nextBuildingDepth);
    const buildingCountValue = parsePositiveNumber(nextBuildingCount);
    const parkingCountValue = parsePositiveNumber(nextParkingCount);
    const minSlopeValue = parsePositiveNumber(nextMinSlopePct);
    const pipeMinSlopeValue = parsePositiveNumber(nextPipeMinSlopePct);
    const maxParkingSlopeValue = parsePositiveNumber(nextMaxParkingSlopePct);
    const maxRoadGradeValue = parsePositiveNumber(nextMaxRoadGradePct);
    const maxAdaSlopeValue = parsePositiveNumber(nextMaxAdaCrossSlopePct);

    const manualFields: ManualFields = {
      project_name: nextSiteName,
      file_name: nextFileName,
      units: nextUnits,
      project_type: nextProjectType,
      disciplines: [
        nextRoads ? "corridor" : null,
        nextGrading ? "grading" : null,
        nextDrainage ? "drainage" : null,
        nextUtilities ? "utility" : null,
      ].filter((item): item is string => Boolean(item)),
    };

    if (lotWidthValue !== null && lotHeightValue !== null) {
      manualFields.lot = {
        x: 0,
        y: 0,
        w: lotWidthValue,
        h: lotHeightValue,
      };
    }

    if (setbackValue !== null) {
      manualFields.setback = setbackValue;
    }

    if (buildingWidthValue !== null) {
      manualFields.building_width = buildingWidthValue;
    }

    if (buildingDepthValue !== null) {
      manualFields.building_depth = buildingDepthValue;
    }

    const allPlacementSnapshots = (placementsOverride ?? buildingPlacements)
      .map((placement) => ({
        id: placement.id,
        name: placement.label,
        label: placement.label,
        type: placement.type ?? "building",
        x: placement.x,
        y: placement.y,
        w: placement.w,
        d: placement.d,
        height_ft: placement.h,
        rotation: placement.rotation,
        use: placement.use,
        stall_count: placement.stallCount,
        locked: placement.locked,
        placed: Boolean(placement.placed),
        source: placement.source,
        confirmed: placement.confirmed,
        generated: placement.generated,
        geometry_type: placement.geometryType,
        geometry: placement.geometry,
        meta: placement.meta,
        systemDependencies: placement.systemDependencies,
      }));
    const placementOverrides = allPlacementSnapshots
      .filter((placement) => placement.placed && Number.isFinite(placement.x) && Number.isFinite(placement.y))
      .map((placement) => placement);
    const canonicalGeometryHandoffs = placementOverrides
      .filter((placement) => {
        if (placement.type === "site" || placement.generated) return false;
        if (placement.source === "detected_from_gis" || placement.source === "detected_from_image" || placement.source === "inferred") {
          return placement.confirmed === true || placement.meta?.acceptance_status === "accepted";
        }
        return true;
      })
      .map((placement) =>
        buildCanonicalGeometryHandoffV1(
          {
            id: placement.id,
            label: placement.label,
            type: placement.type as SiteObjectType,
            x: placement.x,
            y: placement.y,
            w: placement.w,
            d: placement.d,
            h: placement.height_ft,
            rotation: placement.rotation,
            locked: placement.locked,
            placed: true,
            source: placement.source ?? "manual_drawn",
            generated: false,
            geometryType: isCustomGeometryMode(placement.geometry_type)
              ? placement.geometry_type
              : undefined,
            geometry: placement.geometry,
            meta: placement.meta,
            systemDependencies: placement.systemDependencies,
          },
          nextUnits || "ft",
        ),
      )
      .filter((handoff): handoff is CanonicalGeometryHandoffV1 => Boolean(handoff));
    const basinOverrides = placementOverrides.filter((placement) => placement.type === "basin");
    const entranceOverrides = placementOverrides.filter((placement) => placement.type === "entrance");
    const parkingOverrides = placementOverrides.filter((placement) => placement.type === "parking");
    const buildingTypes = new Set<SiteObjectType>([
      "building",
      "retail_building",
      "multifamily_building",
      "industrial_building",
      "office_building",
      "pad",
      "pool",
      "amenity",
      "open_space",
    ]);
    const buildingOverrides = placementOverrides.filter((placement) =>
      buildingTypes.has(placement.type as SiteObjectType),
    );

    if (buildingOverrides.length) {
      manualFields.buildings = buildingOverrides.map((placement) => ({
        ...placement,
        height_ft: placement.height_ft,
      }));
    }
    if (basinOverrides.length) {
      manualFields.ponds = basinOverrides.map((placement) => ({
        id: placement.id,
        name: placement.label,
        x: placement.x,
        y: placement.y,
        w: placement.w,
        d: placement.d,
        rotation: placement.rotation,
        locked: placement.locked,
        source: placement.source,
        generated: placement.generated,
        systemDependencies: placement.systemDependencies,
      }));
    }
    if (entranceOverrides.length) {
      manualFields.access_points = entranceOverrides.map((placement) => ({
        id: placement.id,
        name: placement.label,
        x: placement.x,
        y: placement.y,
        w: placement.w,
        d: placement.d,
        rotation: placement.rotation,
        locked: placement.locked,
        source: placement.source,
        generated: placement.generated,
        systemDependencies: placement.systemDependencies,
      }));
    }

    if (!buildingOverrides.length && buildingCountValue !== null) {
      manualFields.buildings = Array.from({ length: Math.max(1, Math.round(buildingCountValue)) }).map(
        (_, idx) => ({
          name: `Building ${idx + 1}`,
          w: buildingWidthValue ?? undefined,
          d: buildingDepthValue ?? undefined,
        }),
      );
    }

    const parkingFromPlacements = parkingOverrides.reduce((sum, placement) => {
      const value =
        typeof placement.stall_count === "number"
          ? placement.stall_count
          : parsePositiveNumber(placement.stall_count);
      return sum + (value ?? 0);
    }, 0);
    const resolvedParkingCount =
      parkingFromPlacements > 0 ? parkingFromPlacements : parkingCountValue;
    const requestedOfficeArea = buildingOverrides
      .map((placement) => Number(placement.meta?.requested_area_sf))
      .find((value) => Number.isFinite(value) && value > 0);

    if (resolvedParkingCount !== null || requestedOfficeArea) {
      manualFields.site_plan = {
        ...(resolvedParkingCount !== null ? { parking_count: resolvedParkingCount } : {}),
        ...(requestedOfficeArea ? { building_program_sf: requestedOfficeArea, building_type: "office" } : {}),
      };
    }

    if (allPlacementSnapshots.length) {
      manualFields.site_objects = allPlacementSnapshots.map((placement) => ({
        id: placement.id,
        name: placement.label,
        label: placement.label,
        type: placement.type,
        x: placement.x,
        y: placement.y,
        w: placement.w,
        d: placement.d,
        height_ft: placement.height_ft,
        rotation: placement.rotation,
        locked: placement.locked,
        placed: placement.placed,
        source: placement.source,
        generated: placement.generated,
        geometry_type: placement.geometry_type,
        geometry: placement.geometry,
        meta: placement.meta,
        canonical_geometry_handoff_v1: canonicalGeometryHandoffs.find((handoff) => handoff.object_id === placement.id),
        systemDependencies: placement.systemDependencies,
      }));
    }

    if (canonicalGeometryHandoffs.length) {
      manualFields.canonical_geometry_handoff_v1 = canonicalGeometryHandoffs;
    }

    if (minSlopeValue !== null) {
      manualFields.grading = {
        ...(manualFields.grading ?? {}),
        min_slope_pct: minSlopeValue,
      };
    }

    if (maxParkingSlopeValue !== null) {
      manualFields.grading = {
        ...(manualFields.grading ?? {}),
        max_parking_slope_pct: maxParkingSlopeValue,
      };
    }

    if (maxRoadGradeValue !== null) {
      manualFields.grading = {
        ...(manualFields.grading ?? {}),
        max_road_grade_pct: maxRoadGradeValue,
      };
    }

    if (maxAdaSlopeValue !== null) {
      manualFields.grading = {
        ...(manualFields.grading ?? {}),
        max_ada_cross_slope_pct: maxAdaSlopeValue,
      };
    }
    if (surveySlopeEstimate?.slope_percent && Number(surveySlopeEstimate.point_count ?? 0) === 0) {
      manualFields.grading = {
        ...(manualFields.grading ?? {}),
        assumed_terrain_source: true,
        assumed_terrain_slope_pct: surveySlopeEstimate.slope_percent,
      } as ManualFields["grading"] & Record<string, unknown>;
    }

    if (pipeMinSlopeValue !== null) {
      manualFields.drainage = {
        ...(manualFields.drainage ?? {}),
        min_pipe_slope_pct: pipeMinSlopeValue,
      };
    }
    if (drainageForcedInlets.length) {
      manualFields.drainage = {
        ...(manualFields.drainage ?? {}),
        forced_inlets: drainageForcedInlets,
      };
    }
    if (drainageConnectOrphans) {
      manualFields.drainage = {
        ...(manualFields.drainage ?? {}),
        connect_orphans: true,
      };
    }
    if (drainageAllowSlopeAdjust) {
      manualFields.drainage = {
        ...(manualFields.drainage ?? {}),
        allow_slope_adjustment: true,
        max_slope_adjust: drainageMaxSlopeAdjust,
      };
    }

    return manualFields;
}
