import type { BuildingPlacement } from "../types";
import { boundsForSiteGeometry } from "../utils/geometryTransforms";
import {
  firstMetaNumber,
  resolveSourceState,
  scalePolygonTowardCenter,
  sourceStateLabel,
  supportsParkingModuleRendering,
} from "../utils/previewGeometryTruth";
import {
  cadHatchPatternForPreviewItem,
  resolvePreviewSvgVisualStyle,
  resolvePreviewVisualKind,
} from "../utils/previewVisualStyles";
import { semanticLayerForPlacement } from "../utils/previewSemanticLayers";

type PreviewPolygonObjectsProps = {
  objects: BuildingPlacement[];
  selectedBuildingId: string | null;
  isHighQuality: boolean;
  cadReferenceMode?: boolean;
  sitePointToSvgPercent: (point: [number, number]) => string;
};

function parseSvgPoint(point: string) {
  const [x, y] = point.split(",").map((value) => Number(value));
  return Number.isFinite(x) && Number.isFinite(y) ? { x, y } : null;
}

export function PreviewPolygonObjects({
  objects,
  selectedBuildingId,
  isHighQuality,
  cadReferenceMode = false,
  sitePointToSvgPercent,
}: PreviewPolygonObjectsProps) {
  return (
    <>
      {objects
        .filter(
          (item) =>
            !item.meta?.unsupported_entity_placeholder &&
            item.geometryType === "polygon" &&
            Array.isArray(item.geometry),
        )
        .map((item) => {
          const points = (item.geometry || []).map(sitePointToSvgPercent);
          if (points.length < 3) return null;

          const visualKind = resolvePreviewVisualKind(item);
          const sourceState = resolveSourceState(item);
          const visualStyle = resolvePreviewSvgVisualStyle(item, {
            selected: selectedBuildingId === item.id,
            highQuality: isHighQuality,
            cadReferenceMode,
          });
          const isFallbackBounds = sourceState === "fallback";
          const hatchFill = cadHatchPatternForPreviewItem(item);
          const geometry = (item.geometry || []) as Array<[number, number]>;
          const bounds = points.reduce(
            (acc, point) => {
              const parsed = parseSvgPoint(point);
              if (!parsed) return acc;
              return {
                minX: Math.min(acc.minX, parsed.x),
                maxX: Math.max(acc.maxX, parsed.x),
                minY: Math.min(acc.minY, parsed.y),
                maxY: Math.max(acc.maxY, parsed.y),
              };
            },
            { minX: 100, maxX: 0, minY: 100, maxY: 0 },
          );
          const stripeCount = Math.min(12, Math.max(4, Math.round((bounds.maxX - bounds.minX) / 3.2)));
          const innerPolygonPoints = points
            .map((point) => {
              const parsed = parseSvgPoint(point);
              if (!parsed) return null;
              const centerX = (bounds.minX + bounds.maxX) / 2;
              const centerY = (bounds.minY + bounds.maxY) / 2;
              const inset = visualKind === "water" ? 0.82 : 0.88;
              return `${centerX + (parsed.x - centerX) * inset},${centerY + (parsed.y - centerY) * inset}`;
            })
            .filter(Boolean)
            .join(" ");
          const innerShelf = visualKind === "water" ? scalePolygonTowardCenter(geometry, 0.78) : [];
          const bottomShelf = visualKind === "water" ? scalePolygonTowardCenter(geometry, 0.48) : [];
          const waterSurface =
            visualKind === "water" &&
            firstMetaNumber(item, ["normal_pool_elevation_ft", "water_surface_elevation_ft", "normal_pool_ft"]) !== null
              ? scalePolygonTowardCenter(geometry, 0.62)
              : [];
          const roadAxis =
            visualKind === "road"
              ? (() => {
                  const shapeBounds = boundsForSiteGeometry(geometry);
                  const y = shapeBounds.minY + shapeBounds.height / 2;
                  const x = shapeBounds.minX + shapeBounds.width / 2;
                  return shapeBounds.width >= shapeBounds.height
                    ? ([[shapeBounds.minX, y], [shapeBounds.maxX, y]] as Array<[number, number]>)
                    : ([[x, shapeBounds.minY], [x, shapeBounds.maxY]] as Array<[number, number]>);
                })()
              : [];
          const isBuildingSurface = visualKind === "building";
          const isAmenitySurface = item.type === "amenity";
          const isLandscapeSurface = visualKind === "landscape";

          return (
            <g key={`custom-poly-${item.id}`} data-semantic-layer={semanticLayerForPlacement(item)}>
              <polygon
                data-testid={isBuildingSurface ? "professional-building-footprint" : "plan-polygon-object"}
                points={points.join(" ")}
                fill={isFallbackBounds ? "rgba(248,250,252,0.035)" : visualStyle.fill}
                stroke={visualStyle.stroke}
                strokeWidth={isFallbackBounds ? 0.13 : visualStyle.strokeWidth}
                strokeDasharray={isFallbackBounds ? "1.2 1" : visualStyle.strokeDasharray}
                opacity={visualStyle.opacity}
                strokeLinejoin="round"
              >
                <title>{sourceStateLabel(sourceState)}</title>
              </polygon>
              {isFallbackBounds ? (
                <polyline
                  points={points.join(" ")}
                  fill="none"
                  stroke="#94a3b8"
                  strokeWidth={0.05}
                  strokeDasharray="0.4 1.2"
                  opacity={0.5}
                />
              ) : null}
              {hatchFill ? (
                <polygon data-testid="cad-hatch-fill" points={points.join(" ")} fill={hatchFill} stroke="none" opacity={0.72}>
                  <title>Draft hatch fill, review required.</title>
                </polygon>
              ) : null}
              {isHighQuality && visualKind === "parking" && supportsParkingModuleRendering(item) ? (
                <g data-testid="plan-parking-stall-cues" opacity={cadReferenceMode ? 0.86 : sourceState === "fallback" ? 0.4 : 0.68}>
                  <line
                    x1={bounds.minX + (bounds.maxX - bounds.minX) * 0.1}
                    y1={(bounds.minY + bounds.maxY) / 2}
                    x2={bounds.maxX - (bounds.maxX - bounds.minX) * 0.1}
                    y2={(bounds.minY + bounds.maxY) / 2}
                    stroke={cadReferenceMode ? "rgba(248,250,252,0.72)" : "rgba(71,85,105,0.18)"}
                    strokeWidth={0.022}
                    strokeDasharray="0.42 0.34"
                  />
                  {Array.from({ length: stripeCount }).map((_, stripeIdx) => {
                    const x =
                      bounds.minX +
                      (bounds.maxX - bounds.minX) * (0.12 + (stripeIdx / Math.max(stripeCount - 1, 1)) * 0.76);
                    return (
                      <line
                        key={`poly-parking-stall-${item.id}-${stripeIdx}`}
                        x1={x}
                        y1={bounds.minY + (bounds.maxY - bounds.minY) * 0.16}
                        x2={x}
                        y2={bounds.maxY - (bounds.maxY - bounds.minY) * 0.16}
                        stroke={cadReferenceMode ? "rgba(248,250,252,0.68)" : "rgba(71,85,105,0.16)"}
                        strokeWidth={0.018}
                      />
                    );
                  })}
                </g>
              ) : null}
              {isHighQuality && visualKind === "water" && innerPolygonPoints ? (
                <g data-testid="plan-basin-shelf-cues">
                  <polygon
                    points={innerShelf.length ? innerShelf.map(sitePointToSvgPercent).join(" ") : innerPolygonPoints}
                    fill="none"
                    stroke="rgba(2,132,199,0.34)"
                    strokeWidth={0.052}
                    strokeLinejoin="round"
                  />
                  {bottomShelf.length ? (
                    <polygon
                      points={bottomShelf.map(sitePointToSvgPercent).join(" ")}
                      fill="rgba(2,132,199,0.055)"
                      stroke="rgba(3,105,161,0.34)"
                      strokeWidth={0.048}
                      strokeLinejoin="round"
                    />
                  ) : null}
                  {waterSurface.length ? (
                    <polygon
                      points={waterSurface.map(sitePointToSvgPercent).join(" ")}
                      fill="rgba(125,211,252,0.12)"
                      stroke="rgba(14,165,233,0.34)"
                      strokeWidth={0.042}
                      strokeLinejoin="round"
                    />
                  ) : null}
                </g>
              ) : null}
              {isHighQuality && visualKind === "road" && roadAxis.length === 2 ? (
                <polyline
                  points={roadAxis.map(sitePointToSvgPercent).join(" ")}
                  fill="none"
                  stroke={cadReferenceMode ? "rgba(248,250,252,0.82)" : "rgba(248,250,252,0.62)"}
                  strokeWidth={0.07}
                  strokeDasharray={item.type === "driveway" ? undefined : "1.25 1"}
                  strokeLinecap="round"
                />
              ) : null}
              {isHighQuality && isBuildingSurface ? (
                <g data-testid="plan-building-entry-cues" opacity={cadReferenceMode ? 0.86 : 0.52} pointerEvents="none">
                  <polyline
                    points={innerPolygonPoints}
                    fill="none"
                    stroke={cadReferenceMode ? "rgba(248,250,252,0.72)" : "rgba(15,23,42,0.2)"}
                    strokeWidth={cadReferenceMode ? 0.04 : 0.032}
                    strokeLinejoin="round"
                  />
                  <line
                    x1={bounds.minX + (bounds.maxX - bounds.minX) * 0.42}
                    y1={bounds.maxY}
                    x2={bounds.minX + (bounds.maxX - bounds.minX) * 0.58}
                    y2={bounds.maxY}
                    stroke={cadReferenceMode ? "rgba(248,250,252,0.9)" : "rgba(15,23,42,0.42)"}
                    strokeWidth={cadReferenceMode ? 0.055 : 0.045}
                    strokeLinecap="round"
                  />
                  <line
                    x1={bounds.minX + (bounds.maxX - bounds.minX) * 0.5}
                    y1={bounds.minY + (bounds.maxY - bounds.minY) * 0.14}
                    x2={bounds.minX + (bounds.maxX - bounds.minX) * 0.5}
                    y2={bounds.minY + (bounds.maxY - bounds.minY) * 0.86}
                    stroke={cadReferenceMode ? "rgba(248,250,252,0.32)" : "rgba(15,23,42,0.12)"}
                    strokeWidth={0.024}
                    strokeDasharray="0.5 0.34"
                  />
                </g>
              ) : null}
              {isHighQuality && isAmenitySurface ? (
                <g data-testid="plan-plaza-module-lines" opacity={cadReferenceMode ? 0.78 : 0.42} pointerEvents="none">
                  {Array.from({ length: 6 }).map((_, idx) => {
                    const t = (idx + 1) / 7;
                    return (
                      <line
                        key={`poly-plaza-x-${item.id}-${idx}`}
                        x1={bounds.minX + (bounds.maxX - bounds.minX) * t}
                        y1={bounds.minY + (bounds.maxY - bounds.minY) * 0.1}
                        x2={bounds.minX + (bounds.maxX - bounds.minX) * t}
                        y2={bounds.maxY - (bounds.maxY - bounds.minY) * 0.1}
                        stroke={cadReferenceMode ? "rgba(248,250,252,0.5)" : "rgba(120,53,15,0.36)"}
                        strokeWidth={0.022}
                      />
                    );
                  })}
                  {Array.from({ length: 4 }).map((_, idx) => {
                    const t = (idx + 1) / 5;
                    return (
                      <line
                        key={`poly-plaza-y-${item.id}-${idx}`}
                        x1={bounds.minX + (bounds.maxX - bounds.minX) * 0.08}
                        y1={bounds.minY + (bounds.maxY - bounds.minY) * t}
                        x2={bounds.maxX - (bounds.maxX - bounds.minX) * 0.08}
                        y2={bounds.minY + (bounds.maxY - bounds.minY) * t}
                        stroke={cadReferenceMode ? "rgba(248,250,252,0.5)" : "rgba(120,53,15,0.36)"}
                        strokeWidth={0.022}
                      />
                    );
                  })}
                </g>
              ) : null}
              {isHighQuality && isLandscapeSurface ? (
                <g data-testid="plan-landscape-contour-cues" opacity={cadReferenceMode ? 0.74 : 0.48} pointerEvents="none">
                  {[0.82, 0.64].map((scale, idx) => {
                    const inset = scalePolygonTowardCenter(geometry, scale);
                    return inset.length ? (
                      <polygon
                        key={`landscape-inner-${item.id}-${idx}`}
                        points={inset.map(sitePointToSvgPercent).join(" ")}
                        fill="none"
                        stroke={cadReferenceMode ? "rgba(34,197,94,0.65)" : "rgba(21,128,61,0.28)"}
                        strokeWidth={0.03}
                        strokeDasharray={idx === 1 ? "0.6 0.36" : undefined}
                      />
                    ) : null;
                  })}
                </g>
              ) : null}
            </g>
          );
        })}
    </>
  );
}
