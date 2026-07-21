import { useCallback, type Dispatch, type SetStateAction } from "react";

import type { BuildingPlacement, ProjectRecord } from "../types";
import { SITE_OBJECT_CATALOG } from "../utils/siteObjectCatalog";
import { parsePositiveNumber } from "../utils/formatting";
import type { ParkingParams } from "../utils/previewGeometryTruth";

type UseDashboardSiteGeometryActionsInput = {
  buildingDepth: string;
  buildingPlacements: BuildingPlacement[];
  buildingWidth: string;
  currentProject: ProjectRecord | null;
  lotHeight: string;
  lotWidth: string;
  setBuildingPlacements: Dispatch<SetStateAction<BuildingPlacement[]>>;
  setLotHeight: Dispatch<SetStateAction<string>>;
  setLotWidth: Dispatch<SetStateAction<string>>;
  setStatusMessage: Dispatch<SetStateAction<string>>;
};

export type DashboardParkingParams = {
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

export type DashboardParkingFootprintParams = Pick<
  DashboardParkingParams,
  | "stallWidth"
  | "stallDepth"
  | "aisleWidth"
  | "adaAisleWidth"
  | "adaCount"
  | "compactCount"
  | "compactWidth"
  | "angleDeg"
  | "loading"
>;

export function useDashboardSiteGeometryActions({
  buildingDepth,
  buildingPlacements,
  buildingWidth,
  currentProject,
  lotHeight,
  lotWidth,
  setBuildingPlacements,
  setLotHeight,
  setLotWidth,
  setStatusMessage,
}: UseDashboardSiteGeometryActionsInput) {
  const resolveLotBounds = useCallback(() => {
    const width = parsePositiveNumber(lotWidth) ?? 0;
    const height = parsePositiveNumber(lotHeight) ?? 0;
    if (!width || !height) {
      const manualLotRaw =
        currentProject?.project_input &&
        typeof currentProject.project_input === "object" &&
        (currentProject.project_input as {
          manual_fields?: { lot?: { x?: number; y?: number; w?: number; h?: number } | false };
        }).manual_fields?.lot;
      const manualLot: { x?: number; y?: number; w?: number; h?: number } | null =
        manualLotRaw && typeof manualLotRaw === "object" ? manualLotRaw : null;
      if (manualLot?.w && manualLot?.h) {
        return {
          x: typeof manualLot.x === "number" ? manualLot.x : 0,
          y: typeof manualLot.y === "number" ? manualLot.y : 0,
          w: manualLot.w,
          h: manualLot.h,
        };
      }
      const site = buildingPlacements.find((item) => item.type === "site");
      if (site?.w && site?.d) {
        return { x: site.x ?? 0, y: site.y ?? 0, w: site.w, h: site.d };
      }
    }
    const site = buildingPlacements.find((item) => item.type === "site");
    return { x: site?.x ?? 0, y: site?.y ?? 0, w: width, h: height };
  }, [buildingPlacements, currentProject, lotHeight, lotWidth]);

  const resolveDefaultBuildingDims = useCallback(() => {
    const width = parsePositiveNumber(buildingWidth) ?? SITE_OBJECT_CATALOG.building.defaultW;
    const depth = parsePositiveNumber(buildingDepth) ?? SITE_OBJECT_CATALOG.building.defaultD;
    return { w: width, d: depth };
  }, [buildingDepth, buildingWidth]);

  const hasSiteBoundary = useCallback(() => {
    const lot = resolveLotBounds();
    return Boolean(lot.w && lot.h);
  }, [resolveLotBounds]);

  const ensureSiteBoundary = useCallback(
    (reason: string) => {
      const hasSite = buildingPlacements.some((item) => item.type === "site");
      if (hasSite) return true;
      const width = parsePositiveNumber(lotWidth) ?? SITE_OBJECT_CATALOG.site.defaultW;
      const height = parsePositiveNumber(lotHeight) ?? SITE_OBJECT_CATALOG.site.defaultD;
      if (!parsePositiveNumber(lotWidth)) setLotWidth(String(width));
      if (!parsePositiveNumber(lotHeight)) setLotHeight(String(height));
      setBuildingPlacements((prev) => {
        const filtered = prev.filter((item) => item.type !== "site");
        const sitePlacement: BuildingPlacement = {
          id: `site-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
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
        return [sitePlacement, ...filtered];
      });
      setStatusMessage(`Site boundary initialized at ${width} ft by ${height} ft. ${reason}`);
      return true;
    },
    [buildingPlacements, lotHeight, lotWidth, setBuildingPlacements, setLotHeight, setLotWidth, setStatusMessage],
  );

  const resolveParkingParams = useCallback(
    (target: BuildingPlacement, overrides?: Partial<BuildingPlacement>): DashboardParkingParams => {
      const currentMeta = (target.meta as { parkingParams?: ParkingParams })?.parkingParams ?? {};
      const nextMeta = (overrides?.meta as { parkingParams?: ParkingParams })?.parkingParams ?? {};
      const loading =
        nextMeta.loading === "single"
          ? "single"
          : nextMeta.loading === "double"
            ? "double"
            : currentMeta.loading === "single"
              ? "single"
              : "double";
      return {
        stallWidth: Number.isFinite(nextMeta.stallWidth) ? Number(nextMeta.stallWidth) : Number(currentMeta.stallWidth) || 9,
        stallDepth: Number.isFinite(nextMeta.stallDepth) ? Number(nextMeta.stallDepth) : Number(currentMeta.stallDepth) || 18,
        aisleWidth: Number.isFinite(nextMeta.aisleWidth) ? Number(nextMeta.aisleWidth) : Number(currentMeta.aisleWidth) || 24,
        adaAisleWidth: Number.isFinite(nextMeta.adaAisleWidth) ? Number(nextMeta.adaAisleWidth) : Number(currentMeta.adaAisleWidth) || 8,
        adaCount: Number.isFinite(nextMeta.adaCount) ? Number(nextMeta.adaCount) : Number(currentMeta.adaCount) || 0,
        compactCount: Number.isFinite(nextMeta.compactCount) ? Number(nextMeta.compactCount) : Number(currentMeta.compactCount) || 0,
        compactWidth: Number.isFinite(nextMeta.compactWidth) ? Number(nextMeta.compactWidth) : Number(currentMeta.compactWidth) || 8,
        angleDeg: Number.isFinite(nextMeta.angleDeg) ? Number(nextMeta.angleDeg) : Number(currentMeta.angleDeg) || 90,
        loading,
        autoResizeToFitCount:
          typeof nextMeta.autoResizeToFitCount === "boolean"
            ? nextMeta.autoResizeToFitCount
            : Boolean(currentMeta.autoResizeToFitCount),
        useMixedAngles:
          typeof nextMeta.useMixedAngles === "boolean"
            ? nextMeta.useMixedAngles
            : Boolean(currentMeta.useMixedAngles),
        compactZone:
          typeof nextMeta.compactZone === "boolean"
            ? nextMeta.compactZone
            : Boolean(currentMeta.compactZone),
      };
    },
    [],
  );

  const computeParkingFootprint = useCallback(
    (target: BuildingPlacement, params: DashboardParkingFootprintParams, stallCount: number) => {
      const rows = params.loading === "double" ? 2 : 1;
      const angleRad = (Math.max(Math.min(params.angleDeg, 89), 0) * Math.PI) / 180;
      const depthAdj = params.stallDepth / Math.cos(angleRad || 0.0001);
      const shift = Math.tan(angleRad || 0.0001) * depthAdj;
      const moduleDepth = depthAdj * rows + params.aisleWidth;
      const perModuleWidth = (stallsPerRow: number) =>
        stallsPerRow * params.stallWidth + Math.abs(shift);
      const totalStalls = Math.max(stallCount, params.adaCount + params.compactCount);
      const stallsPerRow = Math.max(1, Math.ceil(totalStalls / rows));
      const moduleWidth = perModuleWidth(stallsPerRow);
      const modulesNeeded = Math.max(1, Math.ceil(totalStalls / (stallsPerRow * rows)));
      let cols = Math.max(1, Math.ceil(Math.sqrt(modulesNeeded)));
      let rowsOfModules = Math.max(1, Math.ceil(modulesNeeded / cols));
      if (totalStalls === 0) {
        cols = 1;
        rowsOfModules = 1;
      }
      if (target.w > 0) {
        const maxCols = Math.max(1, Math.floor(target.w / moduleWidth));
        cols = Math.max(1, Math.min(cols, maxCols || 1));
      }
      if (target.d > 0) {
        const maxRows = Math.max(1, Math.floor(target.d / moduleDepth));
        rowsOfModules = Math.max(1, Math.min(rowsOfModules, maxRows || 1));
      }
      const totalCapacity = stallsPerRow * rows * cols * rowsOfModules;
      const totalWidth = moduleWidth * cols;
      const totalDepth = moduleDepth * rowsOfModules;
      return {
        w: totalWidth,
        d: totalDepth,
        maxStalls: totalCapacity,
        moduleCount: cols * rowsOfModules,
        stallsPerRow,
        moduleCols: cols,
        moduleRows: rowsOfModules,
      };
    },
    [],
  );

  return {
    computeParkingFootprint,
    ensureSiteBoundary,
    hasSiteBoundary,
    resolveDefaultBuildingDims,
    resolveLotBounds,
    resolveParkingParams,
  };
}
