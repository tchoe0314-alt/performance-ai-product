import type { BuildingPlacement } from "../types";
import {
  hasParkingGeometryEvidence,
  resolveSourceState,
  sourceStateLabel,
} from "../utils/previewGeometryTruth";
import {
  cadHatchPatternForPreviewItem,
  rectCorridorAxis,
  resolvePreviewSvgVisualStyle,
  resolvePreviewVisualKind,
  roundedSiteShapePath,
} from "../utils/previewVisualStyles";

type PreviewRect = {
  left: number;
  top: number;
  width: number;
  height: number;
};

type PreviewRectObjectsProps = {
  objects: BuildingPlacement[];
  selectedBuildingId: string | null;
  isHighQuality: boolean;
  cadReferenceMode?: boolean;
  mapAnchoredRectPercent: (item: BuildingPlacement) => PreviewRect;
};

export function PreviewRectObjects({
  objects,
  selectedBuildingId,
  isHighQuality,
  cadReferenceMode = false,
  mapAnchoredRectPercent,
}: PreviewRectObjectsProps) {
  return (
    <>
      {objects
        .filter((item) => !item.meta?.unsupported_entity_placeholder && (!item.geometryType || item.geometryType === "rect") && item.type !== "site")
        .map((item) => {
          const rect = mapAnchoredRectPercent(item);
          const selected = selectedBuildingId === item.id;
          const visualKind = resolvePreviewVisualKind(item);
          const visualStyle = resolvePreviewSvgVisualStyle(item, { selected, highQuality: isHighQuality, cadReferenceMode });
          const hatchFill = cadHatchPatternForPreviewItem(item);
          const sourceState = resolveSourceState(item);
          const isFallbackBounds = sourceState === "fallback";
          const useShapePath = ["water", "landscape", "sidewalk"].includes(visualKind);
          const shapePath = useShapePath
            ? roundedSiteShapePath(rect, visualKind as "water" | "landscape" | "road" | "sidewalk")
            : null;
          const corridorAxis = visualKind === "road" ? rectCorridorAxis(rect) : null;
          const cornerRadius =
            visualKind === "road" || visualKind === "parking" || visualKind === "sidewalk"
              ? 0.35
              : visualKind === "building"
                ? 0.18
                : 0.7;

          return (
            <g key={`rect-plan-${item.id}`} data-testid="plan-rect-object">
              {corridorAxis ? (
                <>
                  <polyline
                    data-testid="plan-road-corridor"
                    points={`${corridorAxis.x1},${corridorAxis.y1} ${corridorAxis.x2},${corridorAxis.y2}`}
                    fill="none"
                    stroke={visualStyle.fill}
                    strokeWidth={Math.max(0.18, corridorAxis.width * 0.3)}
                    strokeLinecap="round"
                    opacity={Math.min(0.72, visualStyle.opacity)}
                  >
                    <title>{sourceStateLabel(sourceState)}</title>
                  </polyline>
                  {isHighQuality ? (
                    <polyline
                      points={`${corridorAxis.x1},${corridorAxis.y1} ${corridorAxis.x2},${corridorAxis.y2}`}
                      fill="none"
                      stroke="url(#cad-asphalt-light)"
                      strokeWidth={Math.max(0.038, corridorAxis.width * 0.085)}
                      strokeLinecap="round"
                      opacity={sourceState === "fallback" ? 0.28 : 0.75}
                    />
                  ) : null}
                  <polyline
                    points={`${corridorAxis.x1},${corridorAxis.y1} ${corridorAxis.x2},${corridorAxis.y2}`}
                    fill="none"
                    stroke={visualStyle.stroke}
                    strokeWidth={Math.max(0.06, visualStyle.strokeWidth)}
                    strokeLinecap="round"
                    strokeDasharray={visualStyle.strokeDasharray}
                    opacity={visualStyle.opacity}
                  />
                  {isHighQuality && sourceState !== "fallback" ? (
                    <polyline
                      points={`${corridorAxis.x1},${corridorAxis.y1} ${corridorAxis.x2},${corridorAxis.y2}`}
                      fill="none"
                      stroke="rgba(248,250,252,0.7)"
                      strokeWidth={0.034}
                      strokeDasharray={item.type === "driveway" ? undefined : "1.25 1"}
                      strokeLinecap="round"
                    />
                  ) : null}
                </>
              ) : shapePath ? (
                <>
                  <path
                    d={shapePath}
                    fill={isFallbackBounds ? "rgba(248,250,252,0.04)" : visualStyle.fill}
                    stroke={visualStyle.stroke}
                    strokeWidth={isFallbackBounds ? 0.2 : visualStyle.strokeWidth}
                    strokeDasharray={isFallbackBounds ? "1.2 1" : visualStyle.strokeDasharray}
                    strokeLinejoin="round"
                  >
                    <title>{sourceStateLabel(sourceState)}</title>
                  </path>
                  {hatchFill ? (
                    <path
                      data-testid="cad-hatch-fill"
                      d={shapePath}
                      fill={hatchFill}
                      stroke="none"
                      opacity={0.72}
                    >
                      <title>Draft hatch fill, review required.</title>
                    </path>
                  ) : null}
                </>
              ) : (
                <>
                  <rect
                    data-testid={
                      visualKind === "building"
                        ? "professional-building-footprint"
                        : visualKind === "parking"
                          ? "professional-parking-field"
                          : undefined
                    }
                    x={rect.left}
                    y={rect.top}
                    width={rect.width}
                    height={rect.height}
                    rx={isFallbackBounds ? 0.18 : cornerRadius}
                    fill={isFallbackBounds ? "rgba(248,250,252,0.035)" : visualStyle.fill}
                    stroke={visualStyle.stroke}
                    strokeWidth={isFallbackBounds ? 0.2 : visualStyle.strokeWidth}
                    strokeDasharray={isFallbackBounds ? "1.2 1" : visualStyle.strokeDasharray}
                    strokeLinejoin="round"
                  >
                    <title>{sourceStateLabel(sourceState)}</title>
                  </rect>
                  {hatchFill ? (
                    <rect
                      data-testid="cad-hatch-fill"
                      x={rect.left}
                      y={rect.top}
                      width={rect.width}
                      height={rect.height}
                      rx={cornerRadius}
                      fill={hatchFill}
                      stroke="none"
                      opacity={0.72}
                    >
                      <title>Draft hatch fill, review required.</title>
                    </rect>
                  ) : null}
                </>
              )}
              {isHighQuality && visualKind === "water" ? (
                <g data-testid="plan-basin-shelf-cues">
                  <path
                    d={roundedSiteShapePath(
                      {
                        left: rect.left + rect.width * 0.1,
                        top: rect.top + rect.height * 0.14,
                        width: rect.width * 0.78,
                        height: rect.height * 0.62,
                      },
                      "water",
                    )}
                    fill="none"
                    stroke="rgba(2,132,199,0.34)"
                    strokeWidth={0.055}
                  />
                  <path
                    data-testid="professional-basin-footprint"
                    d={roundedSiteShapePath(
                      {
                        left: rect.left + rect.width * 0.24,
                        top: rect.top + rect.height * 0.32,
                        width: rect.width * 0.5,
                        height: rect.height * 0.32,
                      },
                      "water",
                    )}
                    fill="rgba(125,211,252,0.08)"
                    stroke="rgba(2,132,199,0.28)"
                    strokeWidth={0.045}
                  />
                  <path
                    d={`M ${rect.left + rect.width * 0.18} ${rect.top + rect.height * 0.55} C ${rect.left + rect.width * 0.35} ${rect.top + rect.height * 0.46} ${rect.left + rect.width * 0.58} ${rect.top + rect.height * 0.64} ${rect.left + rect.width * 0.82} ${rect.top + rect.height * 0.5}`}
                    fill="none"
                    stroke="rgba(14,116,144,0.24)"
                    strokeWidth={0.05}
                    strokeLinecap="round"
                  />
                </g>
              ) : null}
              {isHighQuality && visualKind === "building" && !isFallbackBounds ? (
                <g data-testid="professional-building-cues" opacity={selected ? 0.74 : 0.38}>
                  <rect
                    x={rect.left + rect.width * 0.06}
                    y={rect.top + rect.height * 0.08}
                    width={rect.width * 0.88}
                    height={rect.height * 0.84}
                    rx={0.12}
                    fill="url(#cad-building-poche)"
                    stroke="none"
                  />
                  <line
                    x1={rect.left + rect.width * 0.43}
                    y1={rect.top + rect.height}
                    x2={rect.left + rect.width * 0.57}
                    y2={rect.top + rect.height}
                    stroke="rgba(15,23,42,0.62)"
                    strokeWidth={0.065}
                  />
                </g>
              ) : null}
              {isHighQuality && visualKind === "parking" && hasParkingGeometryEvidence(item) ? (
                <g data-testid="plan-parking-stall-cues" opacity={cadReferenceMode ? 0.86 : sourceState === "fallback" ? 0.42 : 0.72}>
                  <line
                    x1={rect.left + rect.width * 0.08}
                    y1={rect.top + rect.height * 0.5}
                    x2={rect.left + rect.width * 0.92}
                    y2={rect.top + rect.height * 0.5}
                    stroke={cadReferenceMode ? "rgba(248,250,252,0.72)" : "rgba(71,85,105,0.18)"}
                    strokeWidth={0.022}
                    strokeDasharray="0.42 0.34"
                  />
                  {Array.from({ length: Math.min(10, Math.max(3, Math.round(rect.width / 3.6))) }).map((_, stallIdx, stalls) => {
                    const x = rect.left + rect.width * (0.12 + (stallIdx / Math.max(stalls.length - 1, 1)) * 0.76);
                    return (
                      <line
                        key={`parking-stall-${item.id}-${stallIdx}`}
                        x1={x}
                        y1={rect.top + rect.height * 0.16}
                        x2={x}
                        y2={rect.top + rect.height * 0.84}
                        stroke={cadReferenceMode ? "rgba(248,250,252,0.68)" : "rgba(71,85,105,0.16)"}
                        strokeWidth={0.018}
                      />
                    );
                  })}
                </g>
              ) : null}
              {selected ? (
                corridorAxis ? (
                  <polyline
                    points={`${corridorAxis.x1},${corridorAxis.y1} ${corridorAxis.x2},${corridorAxis.y2}`}
                    fill="none"
                    stroke="rgba(15,118,110,0.34)"
                    strokeWidth={Math.max(0.26, corridorAxis.width * 0.46)}
                    strokeLinecap="round"
                    opacity={0.48}
                  />
                ) : (
                  <rect
                    x={rect.left - 0.28}
                    y={rect.top - 0.28}
                    width={rect.width + 0.56}
                    height={rect.height + 0.56}
                    rx={0.7}
                    fill="none"
                    stroke={isHighQuality ? "rgba(15,23,42,0.32)" : "rgba(15,118,110,0.58)"}
                    strokeWidth={isHighQuality ? 0.12 : 0.22}
                    strokeDasharray="1.2 0.9"
                  />
                )
              ) : null}
              {cadReferenceMode && isHighQuality && visualKind === "lot" && rect.width >= 1.8 && rect.height >= 1.2 ? (
                <text
                  x={rect.left + rect.width / 2}
                  y={rect.top + rect.height / 2 + 0.26}
                  textAnchor="middle"
                  fontSize={Math.max(0.42, Math.min(0.72, rect.height * 0.18))}
                  fontWeight={800}
                  fill="#f8fafc"
                  opacity={0.95}
                  pointerEvents="none"
                >
                  {String(item.label || "").slice(0, 7)}
                </text>
              ) : null}
            </g>
          );
        })}
    </>
  );
}
