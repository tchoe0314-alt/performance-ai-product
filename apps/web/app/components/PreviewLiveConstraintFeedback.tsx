import type { BuildingPlacement } from "../types";
import type { LiveConstraintFeedback } from "../utils/liveConstraintFeedback";

type PreviewLiveConstraintGeometryProps = {
  feedback: LiveConstraintFeedback;
  objects: BuildingPlacement[];
  mapAnchoredRectPercent: (item: BuildingPlacement) => { left: number; top: number; width: number; height: number };
  sitePointToSvgPercent: (point: [number, number]) => string;
};

export function PreviewLiveConstraintGeometry({
  feedback,
  objects,
  mapAnchoredRectPercent,
  sitePointToSvgPercent,
}: PreviewLiveConstraintGeometryProps) {
  if (!feedback.objectIds.length) return null;
  const highlighted = objects.filter((item) => feedback.objectIds.includes(item.id));
  return (
    <g data-testid="live-constraint-geometry" pointerEvents="none">
      {highlighted.map((item) => {
        if (item.geometryType === "polygon" && item.geometry?.length) {
          return <polygon key={item.id} points={item.geometry.map(sitePointToSvgPercent).join(" ")} fill="rgba(239,68,68,0.12)" stroke="#dc2626" strokeWidth="0.9" strokeDasharray="1.4 0.8" vectorEffect="non-scaling-stroke" />;
        }
        if (item.geometryType === "polyline" && item.geometry?.length) {
          return <polyline key={item.id} points={item.geometry.map(sitePointToSvgPercent).join(" ")} fill="none" stroke="#dc2626" strokeWidth="1.2" strokeDasharray="1.4 0.8" vectorEffect="non-scaling-stroke" />;
        }
        const rect = mapAnchoredRectPercent(item);
        return <rect key={item.id} x={rect.left} y={rect.top} width={rect.width} height={rect.height} fill="rgba(239,68,68,0.12)" stroke="#dc2626" strokeWidth="0.9" strokeDasharray="1.4 0.8" vectorEffect="non-scaling-stroke" />;
      })}
    </g>
  );
}

export function PreviewLiveConstraintCard({ feedback }: { feedback: LiveConstraintFeedback }) {
  if (!feedback.issues.length) return null;
  const primary = feedback.issues[0];
  return (
    <aside data-testid="live-constraint-card" className="pointer-events-none absolute bottom-5 left-5 z-[58] max-w-sm rounded-xl border border-red-200 bg-white/95 px-3 py-2 shadow-lg backdrop-blur">
      <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-red-700">Live constraint warning</p>
      <p className="mt-1 text-xs font-semibold text-slate-900">{primary.message}</p>
      {feedback.issues.length > 1 ? <p className="mt-1 text-[11px] text-slate-500">+{feedback.issues.length - 1} additional issue{feedback.issues.length === 2 ? "" : "s"}</p> : null}
    </aside>
  );
}
