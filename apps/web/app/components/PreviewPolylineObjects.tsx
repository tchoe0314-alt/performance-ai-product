import type { BuildingPlacement } from "../types";
import { firstMetaNumber, resolveSourceState, sourceStateLabel } from "../utils/previewGeometryTruth";
import {
  resolvePreviewSvgVisualStyle,
  resolvePreviewVisualKind,
} from "../utils/previewVisualStyles";

type PreviewPolylineObjectsProps = {
  objects: BuildingPlacement[];
  selectedBuildingId: string | null;
  isHighQuality: boolean;
  cadReferenceMode?: boolean;
  currentSiteSize: {
    width: number;
    height: number;
  };
  sitePointToSvgPercent: (point: [number, number]) => string;
};

function parseSvgPoint(point: string) {
  const [x, y] = point.split(",").map((value) => Number(value));
  return Number.isFinite(x) && Number.isFinite(y) ? { x, y } : null;
}

export function PreviewPolylineObjects({
  objects,
  selectedBuildingId,
  isHighQuality,
  cadReferenceMode = false,
  currentSiteSize,
  sitePointToSvgPercent,
}: PreviewPolylineObjectsProps) {
  return (
    <>
      {objects
        .filter((item) => !item.meta?.unsupported_entity_placeholder && item.geometryType === "polyline" && Array.isArray(item.geometry))
        .map((item) => {
          const points = (item.geometry || []).map(sitePointToSvgPercent);
          if (points.length < 2) return null;
          const visualKind = resolvePreviewVisualKind(item);
          const visualStyle = resolvePreviewSvgVisualStyle(item, {
            selected: selectedBuildingId === item.id,
            highQuality: isHighQuality,
            cadReferenceMode,
          });
          const isSelectedPolyline = selectedBuildingId === item.id;
          const sourceState = resolveSourceState(item);
          const isCorridorLine = visualKind === "road" || item.type === "driveway";
          const isUtilityLine = visualKind === "utility";
          const corridorWidthFt =
            firstMetaNumber(item, ["corridor_width_ft", "pavement_width_ft", "width_ft", "road_width_ft"]) ??
            (isCorridorLine ? Math.max(Math.min(item.w, item.d), 18) : null);
          const corridorStrokeWidth =
            corridorWidthFt && isCorridorLine
              ? Math.max(0.24, Math.min(1.12, (corridorWidthFt / Math.max(currentSiteSize.width, currentSiteSize.height, 1)) * 100 * 0.3))
              : visualStyle.strokeWidth;
          const parsedPoints = points.map(parseSvgPoint).filter((point): point is { x: number; y: number } => Boolean(point));
          const roadEdgeSegments =
            isHighQuality && isCorridorLine && parsedPoints.length >= 2
              ? parsedPoints.slice(0, -1).flatMap((point, idx) => {
                  const next = parsedPoints[idx + 1];
                  const dx = next.x - point.x;
                  const dy = next.y - point.y;
                  const length = Math.hypot(dx, dy) || 1;
                  const nx = (-dy / length) * corridorStrokeWidth * 0.34;
                  const ny = (dx / length) * corridorStrokeWidth * 0.34;
                  return [
                    { x1: point.x + nx, y1: point.y + ny, x2: next.x + nx, y2: next.y + ny },
                    { x1: point.x - nx, y1: point.y - ny, x2: next.x - nx, y2: next.y - ny },
                  ];
                })
              : [];

          return (
            <g key={`poly-${item.id}`}>
              {isHighQuality && isCorridorLine ? (
                <polyline
                  data-testid="plan-road-corridor"
                  points={points.join(" ")}
                  fill="none"
                  stroke={cadReferenceMode ? "rgba(248,250,252,0.18)" : sourceState === "fallback" ? "rgba(100,116,139,0.12)" : "rgba(15, 23, 42, 0.052)"}
                  strokeWidth={cadReferenceMode ? Math.max(0.24, corridorStrokeWidth * 0.72) : corridorStrokeWidth}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeDasharray={sourceState === "fallback" ? "1.4 1" : undefined}
                />
              ) : null}
              {roadEdgeSegments.length ? (
                <g data-testid="plan-road-edge-lines" opacity={cadReferenceMode ? 0.9 : 0.62}>
                  {roadEdgeSegments.map((segment, idx) => (
                    <line
                      key={`road-edge-${item.id}-${idx}`}
                      x1={segment.x1}
                      y1={segment.y1}
                      x2={segment.x2}
                      y2={segment.y2}
                      stroke={cadReferenceMode ? "rgba(248,250,252,0.78)" : "rgba(51,65,85,0.26)"}
                      strokeWidth={cadReferenceMode ? 0.035 : 0.026}
                      strokeLinecap="round"
                    />
                  ))}
                </g>
              ) : null}
              {isSelectedPolyline ? (
                <polyline
                  points={points.join(" ")}
                  fill="none"
                  stroke="rgba(15,118,110,0.42)"
                  strokeWidth={0.48}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeDasharray="1.8 1.2"
                />
              ) : null}
              <polyline
                data-testid="plan-polyline-object"
                points={points.join(" ")}
                fill="none"
                stroke={visualStyle.stroke}
                strokeWidth={
                  isUtilityLine && isHighQuality
                    ? 0.026
                    : isCorridorLine && isHighQuality
                      ? Math.max(0.075, corridorStrokeWidth * 0.06)
                      : visualStyle.strokeWidth
                }
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeDasharray={visualStyle.strokeDasharray || (isUtilityLine ? "0.46 0.42" : undefined)}
                opacity={isUtilityLine && isHighQuality && !isSelectedPolyline ? 0.58 : isUtilityLine && isHighQuality ? 0.78 : visualStyle.opacity}
              />
              {isHighQuality && isCorridorLine ? (
                <polyline
                  points={points.join(" ")}
                  fill="none"
                  stroke={cadReferenceMode ? "rgba(248,250,252,0.82)" : "url(#cad-asphalt-light)"}
                  strokeWidth={cadReferenceMode ? Math.max(0.035, corridorStrokeWidth * 0.05) : Math.max(0.036, corridorStrokeWidth * 0.085)}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  opacity={sourceState === "fallback" ? 0.36 : 0.72}
                />
              ) : null}
              {isHighQuality && isUtilityLine && isSelectedPolyline ? (
                <g>
                  {points.map((point, idx) => {
                    const [x, y] = String(point).split(",").map((value) => Number(value));
                    if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
                    return (
                      <circle
                        key={`utility-node-${item.id}-${idx}`}
                        cx={x}
                        cy={y}
                        r={0.24}
                        fill="#ffffff"
                        stroke={visualStyle.stroke}
                        strokeWidth={0.065}
                      >
                        <title>{sourceStateLabel(sourceState)}</title>
                      </circle>
                    );
                  })}
                  {(() => {
                    const midPoint = points[Math.floor(points.length / 2)];
                    const [x, y] = String(midPoint || "").split(",").map((value) => Number(value));
                    if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
                    const text = `${item.label || ""} ${item.meta?.network || ""}`.toLowerCase();
                    const label = text.includes("water")
                      ? "8\" DIP WATER MAIN"
                      : text.includes("sanitary")
                        ? "8\" PVC SANITARY SEWER"
                        : text.includes("storm")
                          ? "18\" RCP STORM SEWER"
                          : item.label || "UTILITY";
                    return (
                      <g data-testid="survey-utility-callout" pointerEvents="none">
                        <line
                          x1={x}
                          y1={y}
                          x2={Math.min(82, x + 8)}
                          y2={Math.max(5, y - 4)}
                          stroke={visualStyle.stroke}
                          strokeWidth={0.045}
                        />
                        <text
                          x={Math.min(82, x + 8.4)}
                          y={Math.max(5, y - 4.2)}
                          fontSize="0.68"
                          fill={visualStyle.stroke}
                          fontWeight={700}
                        >
                          {label}
                        </text>
                      </g>
                    );
                  })()}
                </g>
              ) : null}
            </g>
          );
        })}
    </>
  );
}
