import type { PreviewAnnotationLabel } from "../utils/previewHoverDetails";

type PreviewAnnotationLabelMarkersProps = {
  labels: PreviewAnnotationLabel[];
  selectedIssueLabel: string;
  showHover: boolean;
};

export function PreviewAnnotationLabelMarkers({
  labels,
  selectedIssueLabel,
  showHover,
}: PreviewAnnotationLabelMarkersProps) {
  if (!showHover) return null;

  return (
    <>
      {labels.map((item, idx) => (
        <div
          key={`${item.label}-${idx}`}
          className="group pointer-events-auto absolute"
          style={{
            left: `${Math.min(Math.max(item.x * 100, 0), 100)}%`,
            top: `${Math.min(Math.max(item.y * 100, 0), 100)}%`,
            transform: "translate(-50%, -50%)",
          }}
        >
          <div
            className={`h-2 w-2 rounded-full transition ${
              item.label === selectedIssueLabel
                ? "bg-rose-500/80 shadow-[0_0_0_6px_rgba(244,63,94,0.15)]"
                : "bg-slate-900/30 opacity-0 group-hover:opacity-100"
            }`}
          />
          <div className="pointer-events-none absolute left-1/2 top-0 z-10 hidden -translate-x-1/2 -translate-y-full whitespace-nowrap rounded-full border border-slate-200 bg-white px-2 py-1 text-[11px] font-semibold text-slate-700 shadow-sm group-hover:block">
            {item.label}
          </div>
        </div>
      ))}
    </>
  );
}
