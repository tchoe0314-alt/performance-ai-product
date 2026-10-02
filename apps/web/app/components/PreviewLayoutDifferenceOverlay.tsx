import type { LayoutDifference } from "../utils/layoutAlternatives";
import type { BuildingPlacement } from "../types";

type RectPercent = { left: number; top: number; width: number; height: number };

type PreviewLayoutDifferenceOverlayProps = {
  differences: LayoutDifference[];
  mapAnchoredRectPercent: (item: BuildingPlacement) => RectPercent;
};

export function PreviewLayoutDifferenceOverlay({ differences, mapAnchoredRectPercent }: PreviewLayoutDifferenceOverlayProps) {
  if (!differences.length) return null;
  return (
    <g data-testid="layout-difference-overlay" aria-label={`${differences.length} changed layout objects`}>
      {differences.map((difference) => {
        const before = mapAnchoredRectPercent(difference.before);
        const after = mapAnchoredRectPercent(difference.after);
        const from = { x: before.left + before.width / 2, y: before.top + before.height / 2 };
        const to = { x: after.left + after.width / 2, y: after.top + after.height / 2 };
        const angle = Math.atan2(to.y - from.y, to.x - from.x);
        const arrowSize = 1.2;
        const arrow = [
          `${to.x},${to.y}`,
          `${to.x - arrowSize * Math.cos(angle - Math.PI / 6)},${to.y - arrowSize * Math.sin(angle - Math.PI / 6)}`,
          `${to.x - arrowSize * Math.cos(angle + Math.PI / 6)},${to.y - arrowSize * Math.sin(angle + Math.PI / 6)}`,
        ].join(" ");
        return (
          <g key={difference.id} data-testid="layout-difference-item">
            <title>{`${difference.label}: ${difference.moved ? "moved" : ""}${difference.moved && difference.resized ? " and " : ""}${difference.resized ? "resized" : ""}`}</title>
            <rect x={before.left} y={before.top} width={before.width} height={before.height} fill="rgba(100,116,139,0.06)" stroke="#64748b" strokeWidth="0.32" strokeDasharray="1.1 0.8" vectorEffect="non-scaling-stroke" />
            {difference.moved ? (
              <>
                <line x1={from.x} y1={from.y} x2={to.x} y2={to.y} stroke="#2563eb" strokeWidth="0.42" strokeDasharray="1.2 0.7" vectorEffect="non-scaling-stroke" />
                <polygon points={arrow} fill="#2563eb" />
              </>
            ) : null}
          </g>
        );
      })}
    </g>
  );
}
