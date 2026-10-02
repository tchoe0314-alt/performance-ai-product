import type { BuildingPlacement } from "../types";
import type { ParkingParams } from "./previewGeometryTruth";

export type ParkingLayoutInputs = Required<Pick<ParkingParams,
  "stallWidth" | "stallDepth" | "aisleWidth" | "adaAisleWidth" | "adaCount" | "compactCount" |
  "compactWidth" | "angleDeg" | "loading" | "autoResizeToFitCount" | "useMixedAngles" | "compactZone"
>>;

export type ParkingLayoutResult = {
  w: number;
  d: number;
  maxStalls: number;
  moduleCount: number;
  stallsPerRow: number;
  moduleCols: number;
  moduleRows: number;
  requestedStalls: number;
  generatedStalls: number;
  shortfall: number;
  excessCapacity: number;
  status: "fits" | "shortfall" | "invalid";
  requiredWidth: number;
  requiredDepth: number;
  adaCount: number;
  compactCount: number;
};

export function calculateParkingLayout(
  target: Pick<BuildingPlacement, "w" | "d">,
  params: ParkingLayoutInputs,
  requestedStalls: number,
): ParkingLayoutResult {
  const requested = Math.max(0, Math.floor(requestedStalls));
  const angle = Math.max(30, Math.min(90, Number(params.angleDeg) || 90));
  const angleRad = angle * Math.PI / 180;
  const stallWidth = Math.max(6, Number(params.stallWidth) || 9);
  const stallDepth = Math.max(12, Number(params.stallDepth) || 18);
  const aisleWidth = Math.max(10, Number(params.aisleWidth) || 24);
  const rowsPerModule = params.loading === "single" ? 1 : 2;
  const rowDepth = stallDepth * Math.sin(angleRad) + stallWidth * Math.cos(angleRad);
  const stallPitch = stallWidth / Math.max(Math.sin(angleRad), 0.5);
  const longitudinalShift = stallDepth * Math.cos(angleRad);
  const moduleDepth = rowDepth * rowsPerModule + aisleWidth;
  const footprintWidth = Math.max(0, target.w);
  const footprintDepth = Math.max(0, target.d);
  const stallsPerRow = Math.max(0, Math.floor((footprintWidth - longitudinalShift) / stallPitch));
  const moduleRows = Math.max(0, Math.floor(footprintDepth / moduleDepth));
  const rawCapacity = stallsPerRow * rowsPerModule * moduleRows;
  const adaCount = Math.max(0, Math.floor(params.adaCount));
  const compactCount = Math.max(0, Math.floor(params.compactCount));
  const adaAisleSlots = Math.ceil((adaCount * Math.max(0, params.adaAisleWidth)) / Math.max(stallPitch, 1));
  const maxStalls = Math.max(0, rawCapacity - adaAisleSlots);
  const requestedWithSpecials = Math.max(requested, adaCount + compactCount);
  const invalid = adaCount + compactCount > requested || footprintWidth <= 0 || footprintDepth <= 0;
  const generatedStalls = Math.min(requestedWithSpecials, maxStalls);
  const shortfall = Math.max(0, requestedWithSpecials - maxStalls);
  const minimumPositions = requestedWithSpecials + adaAisleSlots;
  const neededPerRow = Math.max(1, Math.ceil(minimumPositions / rowsPerModule));
  const requiredWidth = neededPerRow * stallPitch + longitudinalShift;
  const requiredDepth = moduleDepth;
  return {
    w: requiredWidth,
    d: requiredDepth,
    maxStalls,
    moduleCount: Math.max(1, moduleRows),
    stallsPerRow,
    moduleCols: 1,
    moduleRows: Math.max(1, moduleRows),
    requestedStalls: requestedWithSpecials,
    generatedStalls,
    shortfall,
    excessCapacity: Math.max(0, maxStalls - requestedWithSpecials),
    status: invalid ? "invalid" : shortfall > 0 ? "shortfall" : "fits",
    requiredWidth,
    requiredDepth,
    adaCount,
    compactCount,
  };
}
