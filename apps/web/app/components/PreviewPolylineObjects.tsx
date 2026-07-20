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
  currentSiteSize: {
    width: number;
    height: number;
  };
  sitePointToSvgPercent: (point: [number, number]) => string;
};

export function PreviewPolylineObjects({
  objects,
  selectedBuildingId,
  isHighQuality,
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
              ? Math.max(0.38, Math.min(1.85, (corridorWidthFt / Math.max(currentSiteSize.width, currentSiteSize.height, 1)) * 100 * 0.48))
              : visualStyle.strokeWidth;

          return (
            <g key={`poly-${item.id}`}>
              {isHighQuality && isCorridorLine ? (
                <polyline
                  data-testid="plan-road-corridor"
                  points={points.join(" ")}
                  fill="none"
                  stroke={sourceState === "fallback" ? "rgba(100,116,139,0.13)" : "rgba(15, 23, 42, 0.11)"}
                  strokeWidth={corridorStrokeWidth}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeDasharray={sourceState === "fallback" ? "1.4 1" : undefined}
                />
              ) : null}
              {isSelectedPolyline ? (
                <polyline
                  points={points.join(" ")}
                  fill="none"
                  stroke="rgba(15,118,110,0.42)"
                  strokeWidth={0.82}
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
                    ? 0.045
                    : isCorridorLine && isHighQuality
                      ? Math.max(0.1, corridorStrokeWidth * 0.07)
                      : visualStyle.strokeWidth
                }
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeDasharray={visualStyle.strokeDasharray || (isUtilityLine ? "0.46 0.42" : undefined)}
                opacity={isUtilityLine && isHighQuality ? 0.72 : visualStyle.opacity}
              />
              {isHighQuality && isCorridorLine ? (
                <polyline
                  points={points.join(" ")}
                  fill="none"
                  stroke="url(#cad-asphalt-light)"
                  strokeWidth={Math.max(0.12, corridorStrokeWidth * 0.2)}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  opacity={sourceState === "fallback" ? 0.28 : 0.72}
                />
              ) : null}
              {isHighQuality && isUtilityLine ? (
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
                        strokeWidth={0.1}
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
                          strokeWidth={0.07}
                        />
                        <text
                          x={Math.min(82, x + 8.4)}
                          y={Math.max(5, y - 4.2)}
                          fontSize="0.8"
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
