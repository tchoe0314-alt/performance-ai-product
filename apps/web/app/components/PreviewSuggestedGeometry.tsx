import type { BuildingPlacement } from "../types";
import { resolvePreviewSvgVisualStyle } from "../utils/previewVisualStyles";

type PreviewSuggestedGeometryProps = {
  objects: BuildingPlacement[];
  selectedBuildingId: string | null;
  detectedStroke: string;
  detectedFill: string;
  sitePointToSvgPercent: (point: [number, number]) => string;
};

export function PreviewSuggestedGeometry({
  objects,
  selectedBuildingId,
  detectedStroke,
  detectedFill,
  sitePointToSvgPercent,
}: PreviewSuggestedGeometryProps) {
  return (
    <>
      {objects
        .filter((item) => item.geometryType && Array.isArray(item.geometry))
        .map((item) => {
          const points = (item.geometry || []).map(sitePointToSvgPercent);
          if (!points.length) return null;
          const isLine = item.geometryType === "polyline";
          const visualStyle = resolvePreviewSvgVisualStyle(item, { selected: selectedBuildingId === item.id });
          const stroke = item.source === "detected_from_image" ? detectedStroke : visualStyle.stroke;
          const fill = item.source === "detected_from_image" ? detectedFill : visualStyle.fill;
          return isLine ? (
            <polyline
              key={`geom-${item.id}`}
              points={points.join(" ")}
              fill="none"
              stroke={stroke}
              strokeWidth={visualStyle.strokeWidth}
              strokeDasharray={item.source === "detected_from_image" ? "2 2" : undefined}
            />
          ) : (
            <polygon
              key={`geom-${item.id}`}
              points={points.join(" ")}
              fill={fill}
              stroke={stroke}
              strokeWidth={visualStyle.strokeWidth}
              strokeDasharray={item.source === "detected_from_image" ? "2 2" : undefined}
            />
          );
        })}
    </>
  );
}
