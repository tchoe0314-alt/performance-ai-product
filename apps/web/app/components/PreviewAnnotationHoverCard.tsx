import type { PreviewAnnotationLabel, PreviewHoverDetail } from "../utils/previewHoverDetails";

type PreviewAnnotationHoverCardProps = {
  annotation: PreviewAnnotationLabel;
  details: PreviewHoverDetail[];
  point: { x: number; y: number };
  maxLeft: number;
  maxTop: number;
};

export function PreviewAnnotationHoverCard({
  annotation,
  details,
  point,
  maxLeft,
  maxTop,
}: PreviewAnnotationHoverCardProps) {
  return (
    <div
      className="pointer-events-none absolute z-20 min-w-[220px] max-w-[280px] rounded-2xl border border-slate-200 bg-white/95 p-3 text-xs text-slate-700 shadow-lg"
      style={{
        left: Math.min(Math.max(point.x + 16, 16), maxLeft),
        top: Math.min(Math.max(point.y + 16, 16), maxTop),
      }}
    >
      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
        {annotation.label}
      </p>
      <div className="mt-2 space-y-1">
        {details.length ? (
          details.map((detail) => (
            <div key={detail.label} className="flex items-center justify-between gap-2">
              <span className="text-slate-500">{detail.label}</span>
              <span className="font-semibold text-slate-900">{detail.value}</span>
            </div>
          ))
        ) : (
          <div className="space-y-1 text-slate-500">
            <div className="flex items-center justify-between gap-2">
              <span>Layer</span>
              <span className="font-semibold text-slate-900">{annotation.layer || "Unknown"}</span>
            </div>
            <div className="flex items-center justify-between gap-2">
              <span>Type</span>
              <span className="font-semibold text-slate-900">{annotation.meta?.entity_type || "Shape"}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
