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
  return "rgba(148,163,184,0.045)";
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
            return (
              <g key={`parking-mod-${item.id}-${idx}`}>
                {showParkingAnalysis ? (
                  <polygon
                    points={module.bounds.map(toPct).join(" ")}
                    fill={moduleFillColor(module)}
                    stroke="rgba(15,23,42,0.08)"
                    strokeWidth={0.08}
                  />
                ) : null}
                {module.stallPolygons.map((stall, polyIdx) => {
                  const stroke =
                    showParkingAnalysis && stall.kind !== "standard"
                      ? "rgba(15,23,42,0.34)"
                      : "rgba(71,85,105,0.24)";
                  const strokeWidth = showParkingAnalysis && stall.kind !== "standard" ? 0.12 : 0.045;
                  return (
                    <polygon
                      key={`stall-${polyIdx}`}
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
                {module.stripeLines.map((line, stripeIdx) => (
                  <polyline
                    key={`stripe-${stripeIdx}`}
                    points={line.map(toPct).join(" ")}
                    fill="none"
                    stroke="rgba(71,85,105,0.2)"
                    strokeWidth={0.045}
                  />
                ))}
              </g>
            );
          }),
        )}
    </>
  );
}
