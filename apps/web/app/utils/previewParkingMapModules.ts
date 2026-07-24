import type { BuildingPlacement } from "../types";
import {
  supportsParkingModuleRendering,
  type ParkingParams,
} from "./previewGeometryTruth";

export type PreviewParkingMapModule = {
  id: string;
  angle: number;
  isAdaModule: boolean;
  isCompactModule: boolean;
  bounds: Array<[number, number]>;
  aisleLine: Array<[number, number]>;
  stallPolygons: Array<{ points: Array<[number, number]>; kind: "standard" | "ada" | "compact" | "ada_aisle" }>;
  stripeLines: Array<Array<[number, number]>>;
};

export function buildPreviewParkingMapModules(
  item: BuildingPlacement,
  accessPoints: Array<{ x: number; y: number }>,
): PreviewParkingMapModule[] {
  if (!supportsParkingModuleRendering(item)) return [];
  const x = item.x ?? 0;
  const y = item.y ?? 0;
  const params = (item.meta as { parkingParams?: ParkingParams })?.parkingParams ?? {};
  const stallWidth = Number.isFinite(params.stallWidth) ? Number(params.stallWidth) : 9;
  const stallDepth = Number.isFinite(params.stallDepth) ? Number(params.stallDepth) : 18;
  const aisleWidth = Number.isFinite(params.aisleWidth) ? Number(params.aisleWidth) : 24;
  const adaAisleWidth = Number.isFinite(params.adaAisleWidth) ? Number(params.adaAisleWidth) : 8;
  const adaCount = Number.isFinite(params.adaCount) ? Number(params.adaCount) : 0;
  const compactCount = Number.isFinite(params.compactCount) ? Number(params.compactCount) : 0;
  const compactWidth = Number.isFinite(params.compactWidth) ? Number(params.compactWidth) : 8;
  const angleDeg = Number.isFinite(params.angleDeg) ? Number(params.angleDeg) : 90;
  const loading = params.loading === "single" ? "single" : "double";
  const useMixedAngles = Boolean(params.useMixedAngles);
  const compactZone = params.compactZone !== false;
  const angleRad = (Math.max(Math.min(angleDeg, 89), 0) * Math.PI) / 180;
  const depthAdj = stallDepth / Math.cos(angleRad || 0.0001);
  const moduleDepth = depthAdj * (loading === "double" ? 2 : 1) + aisleWidth;
  const scale = item.d < moduleDepth ? item.d / moduleDepth : 1;
  const scaledStall = depthAdj * scale;
  const scaledAisle = aisleWidth * scale;
  const rows = loading === "double" ? 2 : 1;
  const desiredStalls = Math.max(item.stallCount ?? 0, adaCount + compactCount);
  const shift = Math.tan(angleRad || 0.0001) * scaledStall;
  let moduleCount = 1;
  if (desiredStalls > 0) {
    for (let candidate = 1; candidate <= 6; candidate += 1) {
      const moduleWidth = item.w / candidate;
      const stallsPerRow = Math.max(1, Math.floor((moduleWidth - Math.abs(shift)) / stallWidth));
      const capacity = stallsPerRow * rows * candidate;
      if (capacity >= desiredStalls) {
        moduleCount = candidate;
        break;
      }
      moduleCount = candidate;
    }
  }
  const modules: PreviewParkingMapModule[] = [];
  const metaCols = Number((item.meta as { parkingModuleCols?: number })?.parkingModuleCols || 0);
  const metaRows = Number((item.meta as { parkingModuleRows?: number })?.parkingModuleRows || 0);
  const cols = metaCols > 0 ? metaCols : Math.max(1, Math.ceil(Math.sqrt(moduleCount)));
  const rowsOfModules = metaRows > 0 ? metaRows : Math.max(1, Math.ceil(moduleCount / cols));
  const gapScale = Math.max(0.02, Math.min(0.06, (stallWidth + aisleWidth) / Math.max(item.w, 1)));
  const moduleGapX = Math.min(8, Math.max(3, item.w * gapScale));
  const moduleGapY = Math.min(10, Math.max(4, item.d * gapScale));
  const totalGapX = cols > 1 ? moduleGapX * (cols - 1) : 0;
  const totalGapY = rowsOfModules > 1 ? moduleGapY * (rowsOfModules - 1) : 0;
  const availableW = Math.max(item.w - totalGapX, item.w * 0.7);
  const availableD = Math.max(item.d - totalGapY, item.d * 0.7);
  const moduleWidth = availableW / cols;
  const moduleDepthLocal = availableD / rowsOfModules;
  const offsetX = x + (item.w - (moduleWidth * cols + totalGapX)) / 2;
  const offsetY = y + (item.d - (moduleDepthLocal * rowsOfModules + totalGapY)) / 2;
  const totalModules = cols * rowsOfModules;
  const moduleAngles: number[] = [];
  for (let row = 0; row < rowsOfModules; row += 1) {
    for (let col = 0; col < cols; col += 1) {
      if (!useMixedAngles) {
        moduleAngles.push(angleDeg);
        continue;
      }
      const edge = col === 0 || col === cols - 1;
      const inner = col === 1 || col === cols - 2;
      const angle = edge ? 45 : inner ? 60 : angleDeg;
      moduleAngles.push(angle);
    }
  }
  const moduleCenters: Array<{ x: number; y: number }> = [];
  for (let r = 0; r < rowsOfModules; r += 1) {
    for (let c = 0; c < cols; c += 1) {
      moduleCenters.push({
        x: offsetX + c * (moduleWidth + moduleGapX) + moduleWidth / 2,
        y: offsetY + r * (moduleDepthLocal + moduleGapY) + moduleDepthLocal / 2,
      });
    }
  }
  const sortedModuleIdxByAccess = moduleCenters
    .map((center, idx) => {
      const minDist = accessPoints.length
        ? Math.min(...accessPoints.map((pt) => Math.hypot(center.x - pt.x, center.y - pt.y)))
        : 0;
      return { idx, dist: minDist };
    })
    .sort((a, b) => a.dist - b.dist)
    .map((entry) => entry.idx);
  const moduleCapacities = moduleAngles.map((angle) => {
    const angleRadModule = (Math.max(Math.min(angle, 89), 0) * Math.PI) / 180;
    const shiftModule = Math.tan(angleRadModule || 0.0001) * scaledStall;
    const stallsPerRow = Math.max(1, Math.floor((moduleWidth - Math.abs(shiftModule)) / stallWidth));
    return stallsPerRow * rows;
  });
  const buildModuleSet = (count: number, order: number[], fromEnd = false) => {
    const indices = fromEnd ? [...order].reverse() : order;
    let remaining = count;
    const set = new Set<number>();
    indices.forEach((idx) => {
      if (remaining <= 0) return;
      set.add(idx);
      remaining -= moduleCapacities[idx] ?? 0;
    });
    return set;
  };
  const adaPreferredModules = adaCount > 0 ? buildModuleSet(adaCount, sortedModuleIdxByAccess) : new Set<number>();
  const compactPreferredModules =
    compactCount > 0 && compactZone ? buildModuleSet(compactCount, sortedModuleIdxByAccess, true) : new Set<number>();
  let remainingAda = adaCount;
  let remainingCompact = compactCount;
  for (let m = 0; m < totalModules; m += 1) {
    const row = Math.floor(m / cols);
    const col = m % cols;
    const moduleX = offsetX + col * (moduleWidth + moduleGapX);
    const moduleY = offsetY + row * (moduleDepthLocal + moduleGapY);
    const angleForModule = moduleAngles[m] ?? angleDeg;
    const angleRadModule = (Math.max(Math.min(angleForModule, 89), 0) * Math.PI) / 180;
    const depthVecTop = {
      x: Math.sin(angleRadModule) * scaledStall,
      y: Math.cos(angleRadModule) * scaledStall,
    };
    const depthVecBottom = {
      x: -Math.sin(angleRadModule) * scaledStall,
      y: Math.cos(angleRadModule) * scaledStall,
    };
    const shiftModule = depthVecTop.x;
    const stallsPerRow = Math.max(1, Math.floor((moduleWidth - Math.abs(shiftModule)) / stallWidth));
    const stallW = (moduleWidth - Math.abs(shiftModule)) / stallsPerRow;
    const aisleY =
      loading === "double"
        ? moduleY + (moduleDepthLocal - scaledAisle) / 2
        : moduleY + scaledStall + scaledAisle / 2;
    const aisleLine: Array<[number, number]> = [
      [moduleX + 2, aisleY],
      [moduleX + moduleWidth - 2, aisleY],
    ];
    const stallPolygons: PreviewParkingMapModule["stallPolygons"] = [];
    const stripeLines: Array<Array<[number, number]>> = [];
    const moduleBounds: Array<[number, number]> = [
      [moduleX, moduleY],
      [moduleX + moduleWidth, moduleY],
      [moduleX + moduleWidth, moduleY + moduleDepthLocal],
      [moduleX, moduleY + moduleDepthLocal],
      [moduleX, moduleY],
    ];
    const isAdaModule = adaPreferredModules.has(m);
    const isCompactModule = compactZone ? compactPreferredModules.has(m) : false;
    const depthLen = Math.hypot(depthVecTop.x, depthVecTop.y) || 1;
    const depthUnitTop = { x: depthVecTop.x / depthLen, y: depthVecTop.y / depthLen };
    const depthUnitBottom = { x: depthVecBottom.x / depthLen, y: depthVecBottom.y / depthLen };
    const inset = Math.min(0.35, stallW * 0.06);
    const clampWidth = (value: number) => Math.max(Math.min(value, stallW - inset * 2), stallW * 0.7);
    const buildStallPoly = (
      baseX: number,
      baseY: number,
      width: number,
      depthUnit: { x: number; y: number },
      depth: number,
    ): Array<[number, number]> => {
      const ux = 1;
      const uy = 0;
      const w = Math.max(width - inset * 2, width * 0.8);
      const d = Math.max(depth - inset * 2, depth * 0.8);
      const startX = baseX + inset * (ux + depthUnit.x);
      const startY = baseY + inset * (uy + depthUnit.y);
      const p0: [number, number] = [startX, startY];
      const p1: [number, number] = [startX + w * ux, startY + w * uy];
      const p2: [number, number] = [p1[0] + d * depthUnit.x, p1[1] + d * depthUnit.y];
      const p3: [number, number] = [p0[0] + d * depthUnit.x, p0[1] + d * depthUnit.y];
      return [p0, p1, p2, p3, p0];
    };
    for (let i = 0; i < stallsPerRow; i += 1) {
      let useAda = false;
      let useCompact = false;
      let includeAdaAisle = false;
      if (remainingAda > 0 && isAdaModule) {
        useAda = true;
        includeAdaAisle = true;
        remainingAda -= 1;
      } else if (remainingCompact > 0 && isCompactModule) {
        useCompact = true;
        remainingCompact -= 1;
      } else if (remainingAda > 0 && !adaPreferredModules.size) {
        useAda = true;
        includeAdaAisle = true;
        remainingAda -= 1;
      } else if (remainingCompact > 0 && !compactZone) {
        useCompact = true;
        remainingCompact -= 1;
      }
      const rowOffsetTop = depthVecTop.x > 0 ? 0 : Math.abs(depthVecTop.x);
      const rowOffsetBottom = depthVecBottom.x > 0 ? 0 : Math.abs(depthVecBottom.x);
      const baseXTop = moduleX + rowOffsetTop + i * stallW;
      const baseXBottom = moduleX + rowOffsetBottom + i * stallW;
      const baseYTop = moduleY;
      const baseYBottom = moduleY + moduleDepthLocal - scaledStall;
      const adaAisleReserve = useAda ? Math.max(Math.min(adaAisleWidth, stallW * 0.36), stallW * 0.18) : 0;
      const adaStallWidth = useAda ? Math.max(stallW - adaAisleReserve, stallW * 0.56) : stallW;
      const stallWidthUsed = useAda ? adaStallWidth : useCompact ? clampWidth(compactWidth) : clampWidth(stallW);
      const topPoly = buildStallPoly(baseXTop, baseYTop, stallWidthUsed, depthUnitTop, scaledStall);
      stallPolygons.push({
        points: topPoly,
        kind: useAda ? "ada" : useCompact ? "compact" : "standard",
      });
      stripeLines.push([
        [baseXTop + stallWidthUsed, baseYTop],
        [baseXTop + stallWidthUsed + depthVecTop.x, baseYTop + depthVecTop.y],
      ]);
      if (useAda && includeAdaAisle) {
        const accessibleAisleWidth = Math.max(Math.min(adaAisleWidth, stallW - stallWidthUsed), stallW * 0.12);
        if (accessibleAisleWidth > 0.1) {
          const aislePoly = buildStallPoly(
            baseXTop + stallWidthUsed,
            baseYTop,
            accessibleAisleWidth,
            depthUnitTop,
            scaledStall,
          );
          stallPolygons.push({ points: aislePoly, kind: "ada_aisle" });
        }
      }
      if (loading === "double") {
        const bottomPoly = buildStallPoly(baseXBottom, baseYBottom, stallWidthUsed, depthUnitBottom, scaledStall);
        stallPolygons.push({
          points: bottomPoly,
          kind: useAda ? "ada" : useCompact ? "compact" : "standard",
        });
        stripeLines.push([
          [baseXBottom + stallWidthUsed, baseYBottom],
          [baseXBottom + stallWidthUsed + depthVecBottom.x, baseYBottom + depthVecBottom.y],
        ]);
        if (useAda && includeAdaAisle) {
          const accessibleAisleWidth = Math.max(Math.min(adaAisleWidth, stallW - stallWidthUsed), stallW * 0.12);
          if (accessibleAisleWidth > 0.1) {
            const bottomAisle = buildStallPoly(
              baseXBottom + stallWidthUsed,
              baseYBottom,
              accessibleAisleWidth,
              depthUnitBottom,
              scaledStall,
            );
            stallPolygons.push({ points: bottomAisle, kind: "ada_aisle" });
          }
        }
      }
    }
    const moduleId = `${item.id}-module-${m}`;
    modules.push({
      id: moduleId,
      angle: angleForModule,
      isAdaModule,
      isCompactModule,
      bounds: moduleBounds,
      aisleLine,
      stallPolygons,
      stripeLines,
    });
  }
  return modules;
}
