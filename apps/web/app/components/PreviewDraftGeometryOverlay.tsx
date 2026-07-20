import type { DrawMode } from "../utils/cadToolTypes";

type SiteSize = {
  width: number;
  height: number;
};

type RectPercent = {
  left: number;
  top: number;
  width: number;
  height: number;
};

type PreviewDraftGeometryOverlayProps = {
  activeSnapPoint: { x: number; y: number } | null;
  draftPoints: Array<[number, number]>;
  draftPreviewPoint: [number, number] | null;
  drawMode: DrawMode;
  drawingLotWidth: number;
  drawingLotHeight: number;
  lotWidth: number;
  lotHeight: number;
  sitePointToPreviewPercent: (point: [number, number]) => [number, number];
  siteTupleToPercent: (point: [number, number], siteSize: SiteSize) => [number, number];
  siteRectToPercent: (
    rect: { x: number; y: number; width: number; height: number },
    siteSize: SiteSize,
  ) => RectPercent;
};

export function PreviewDraftGeometryOverlay({
  activeSnapPoint,
  draftPoints,
  draftPreviewPoint,
  drawMode,
  drawingLotWidth,
  drawingLotHeight,
  lotWidth,
  lotHeight,
  sitePointToPreviewPercent,
  siteTupleToPercent,
  siteRectToPercent,
}: PreviewDraftGeometryOverlayProps) {
  const points =
    draftPreviewPoint && drawMode !== "point"
      ? [...draftPoints, draftPreviewPoint]
      : draftPoints;
  const effectiveLotWidth = drawMode === "site" ? drawingLotWidth : lotWidth;
  const effectiveLotHeight = drawMode === "site" ? drawingLotHeight : lotHeight;
  const effectiveSiteSize = { width: effectiveLotWidth, height: effectiveLotHeight };
  const pct = points.map((pt) => {
    const [x, y] = siteTupleToPercent(pt, effectiveSiteSize);
    return `${x},${y}`;
  });

  return (
    <>
      {activeSnapPoint ? (
        (() => {
          const [snapX, snapY] = sitePointToPreviewPercent([activeSnapPoint.x, activeSnapPoint.y]);
          return (
            <g>
              <circle
                cx={snapX}
                cy={snapY}
                r={0.82}
                fill="none"
                stroke="#f59e0b"
                strokeWidth={0.24}
              />
              <path
                d={`M ${snapX - 1.15} ${snapY} L ${snapX + 1.15} ${snapY} M ${snapX} ${snapY - 1.15} L ${snapX} ${snapY + 1.15}`}
                stroke="#f59e0b"
                strokeWidth={0.2}
                strokeLinecap="round"
              />
            </g>
          );
        })()
      ) : null}
      {points.length ? (
        (() => {
          if ((drawMode === "polygon" || drawMode === "site") && pct.length >= 3) {
            const draftColor = drawMode === "site" ? "#f59e0b" : "#0284c7";
            return (
              <g>
                <polygon
                  points={pct.join(" ")}
                  fill={drawMode === "site" ? "rgba(245,158,11,0.05)" : "rgba(14,165,233,0.045)"}
                  stroke={draftColor}
                  strokeWidth={0.36}
                  strokeDasharray="0.9 0.7"
                />
                {points.map((pt, idx) => (
                  <circle
                    key={`draft-poly-${idx}`}
                    cx={siteTupleToPercent(pt, effectiveSiteSize)[0]}
                    cy={siteTupleToPercent(pt, effectiveSiteSize)[1]}
                    r={0.42}
                    fill={draftColor}
                  />
                ))}
              </g>
            );
          }
          if (drawMode === "rect" && points.length >= 2) {
            const [a, b] = points;
            const rectPct = siteRectToPercent(
              {
                x: Math.min(a[0], b[0]),
                y: Math.min(a[1], b[1]),
                width: Math.abs(a[0] - b[0]),
                height: Math.abs(a[1] - b[1]),
              },
              effectiveSiteSize,
            );
            return (
              <rect
                x={rectPct.left}
                y={rectPct.top}
                width={rectPct.width}
                height={rectPct.height}
                fill="rgba(14,165,233,0.045)"
                stroke="#0284c7"
                strokeWidth={0.36}
                strokeDasharray="0.9 0.7"
              />
            );
          }
          if (pct.length >= 2) {
            return (
              <g>
                <polyline
                  points={pct.join(" ")}
                  fill="none"
                  stroke="#0284c7"
                  strokeWidth={0.36}
                  strokeDasharray="0.9 0.7"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                {points.map((pt, idx) => (
                  <circle
                    key={`draft-line-${idx}`}
                    cx={siteTupleToPercent(pt, effectiveSiteSize)[0]}
                    cy={siteTupleToPercent(pt, effectiveSiteSize)[1]}
                    r={0.42}
                    fill="#0284c7"
                  />
                ))}
              </g>
            );
          }
          const [pt] = points;
          return (
            <circle
              cx={siteTupleToPercent(pt, effectiveSiteSize)[0]}
              cy={siteTupleToPercent(pt, effectiveSiteSize)[1]}
              r={0.46}
              fill="#0284c7"
            />
          );
        })()
      ) : null}
    </>
  );
}
