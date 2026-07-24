import type { BuildingPlacement } from "../types";
import { hasParkingGeometryEvidence } from "../utils/previewGeometryTruth";

type ParkingAccessPoint = {
  x: number;
  y: number;
};

type ParkingModulePreview = {
  id: string;
  angle: number;
  isAdaModule: boolean;
  isCompactModule: boolean;
  bounds: Array<[number, number]>;
  aisleLine: Array<[number, number]>;
  stallPolygons: Array<{
    points: Array<[number, number]>;
    kind: "standard" | "ada" | "compact" | "ada_aisle";
  }>;
  stripeLines: Array<Array<[number, number]>>;
};

type PreviewParkingModulesProps = {
  objects: BuildingPlacement[];
  accessPoints: ParkingAccessPoint[];
  showParkingAnalysis: boolean;
  buildParkingModules: (item: BuildingPlacement, accessPoints: ParkingAccessPoint[]) => ParkingModulePreview[];
  sitePointToSvgPercent: (point: [number, number]) => string;
};

function moduleFillColor(module: ParkingModulePreview) {
  if (module.isAdaModule) return "rgba(16,185,129,0.06)";
  if (module.isCompactModule) return "rgba(168,85,247,0.055)";
  if (module.angle === 45) return "rgba(56,189,248,0.045)";
  if (module.angle === 60) return "rgba(129,140,248,0.045)";
  return "rgba(148,163,184,0.035)";
}

function stallFillColor(kind: ParkingModulePreview["stallPolygons"][number]["kind"], showParkingAnalysis: boolean) {
  if (showParkingAnalysis && kind === "ada") return "rgba(16,185,129,0.2)";
  if (showParkingAnalysis && kind === "ada_aisle") return "rgba(52,211,153,0.14)";
  if (showParkingAnalysis && kind === "compact") return "rgba(168,85,247,0.18)";
  if (kind === "ada") return "rgba(16,185,129,0.12)";
  if (kind === "ada_aisle") return "rgba(52,211,153,0.08)";
  if (kind === "compact") return "rgba(168,85,247,0.1)";
  return "rgba(148,163,184,0.045)";
}

function polygonCenter(points: Array<[number, number]>): [number, number] {
  if (!points.length) return [0, 0];
  const sum = points.reduce(
    (acc, [x, y]) => {
      acc.x += x;
      acc.y += y;
      return acc;
    },
    { x: 0, y: 0 },
  );
  return [sum.x / points.length, sum.y / points.length];
}

export function PreviewParkingModules({
  objects,
  accessPoints,
  showParkingAnalysis,
  buildParkingModules,
  sitePointToSvgPercent,
}: PreviewParkingModulesProps) {
  return (
    <>
      {objects
        .filter((item) => item.type === "parking" && item.placed && hasParkingGeometryEvidence(item))
        .flatMap((item) =>
          buildParkingModules(item, accessPoints).map((module, idx) => {
            const toPct = (pt: [number, number]) => sitePointToSvgPercent(pt);
            const aisleStart = module.aisleLine[0];
            const aisleEnd = module.aisleLine[module.aisleLine.length - 1];
            const aisleMid: [number, number] =
              aisleStart && aisleEnd
                ? [(aisleStart[0] + aisleEnd[0]) / 2, (aisleStart[1] + aisleEnd[1]) / 2]
                : [0, 0];
            const [aisleMidX, aisleMidY] = toPct(aisleMid).split(",").map((value) => Number(value));
            const adaStalls = module.stallPolygons.filter((stall) => stall.kind === "ada");
            const compactStalls = module.stallPolygons.filter((stall) => stall.kind === "compact");
            return (
              <g key={`parking-mod-${item.id}-${idx}`} data-testid="plan-parking-module-detail">
                <polygon
                  points={module.bounds.map(toPct).join(" ")}
                  fill={moduleFillColor(module)}
                  stroke="rgba(15,23,42,0.1)"
                  strokeWidth={showParkingAnalysis ? 0.08 : 0.04}
                  strokeDasharray={module.angle !== 90 ? "0.7 0.42" : undefined}
                  opacity={showParkingAnalysis ? 1 : 0.68}
                />
                {module.stallPolygons.map((stall, polyIdx) => {
                  const stroke =
                    showParkingAnalysis && stall.kind !== "standard"
                      ? "rgba(15,23,42,0.34)"
                      : "rgba(71,85,105,0.24)";
                  const strokeWidth = showParkingAnalysis && stall.kind !== "standard" ? 0.12 : 0.045;
                  return (
                    <polygon
                      key={`stall-${polyIdx}`}
                      data-testid={
                        stall.kind === "ada"
                          ? "plan-parking-ada-stall"
                          : stall.kind === "ada_aisle"
                            ? "plan-parking-ada-aisle"
                            : stall.kind === "compact"
                              ? "plan-parking-compact-stall"
                              : undefined
                      }
                      points={stall.points.map(toPct).join(" ")}
                      fill={stallFillColor(stall.kind, showParkingAnalysis)}
                      stroke={stroke}
                      strokeWidth={strokeWidth}
                    />
                  );
                })}
                <polyline
                  points={module.aisleLine.map(toPct).join(" ")}
                  fill="none"
                  stroke="rgba(71,85,105,0.24)"
                  strokeWidth={0.08}
                />
                <g data-testid="plan-parking-aisle-cue" pointerEvents="none" opacity={0.58}>
                  <circle
                    cx={aisleMidX}
                    cy={aisleMidY}
                    r={0.32}
                    fill="rgba(255,255,255,0.72)"
                    stroke="rgba(71,85,105,0.28)"
                    strokeWidth={0.04}
                  />
                  <text
                    x={aisleMidX}
                    y={aisleMidY + 0.18}
                    textAnchor="middle"
                    fontSize="0.55"
                    fontWeight={800}
                    fill="rgba(71,85,105,0.72)"
                  >
                    →
                  </text>
                </g>
                {module.stripeLines.map((line, stripeIdx) => (
                  <polyline
                    key={`stripe-${stripeIdx}`}
                    points={line.map(toPct).join(" ")}
                    fill="none"
                    stroke="rgba(71,85,105,0.2)"
                    strokeWidth={0.045}
                  />
                ))}
                {adaStalls.map((stall, adaIdx) => {
                  const center = polygonCenter(stall.points);
                  const [x, y] = toPct(center).split(",").map((value) => Number(value));
                  if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
                  return (
                    <text
                      key={`ada-mark-${item.id}-${idx}-${adaIdx}`}
                      data-testid="plan-parking-ada-symbol"
                      x={x}
                      y={y + 0.18}
                      textAnchor="middle"
                      fontSize="0.62"
                      fontWeight={900}
                      fill="rgba(5,150,105,0.78)"
                      pointerEvents="none"
                    >
                      ADA
                    </text>
                  );
                })}
                {compactStalls.slice(0, 4).map((stall, compactIdx) => {
                  const center = polygonCenter(stall.points);
                  const [x, y] = toPct(center).split(",").map((value) => Number(value));
                  if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
                  return (
                    <text
                      key={`compact-mark-${item.id}-${idx}-${compactIdx}`}
                      data-testid="plan-parking-compact-symbol"
                      x={x}
                      y={y + 0.16}
                      textAnchor="middle"
                      fontSize="0.5"
                      fontWeight={800}
                      fill="rgba(126,34,206,0.68)"
                      pointerEvents="none"
                    >
                      C
                    </text>
                  );
                })}
              </g>
            );
          }),
        )}
    </>
  );
}
