type ModelReviewPanelProps = {
  previewMode: "2d" | "3d";
  previewQuality: string;
  hasGradingSurface: boolean;
  hasHardSystemBlock: boolean;
  placedObjectCount: number;
  issueCount: number;
};

export function ModelReviewPanel({
  previewMode,
  previewQuality,
  hasGradingSurface,
  hasHardSystemBlock,
  placedObjectCount,
  issueCount,
}: ModelReviewPanelProps) {
  return (
    <div className="space-y-4">
      {previewMode === "3d" ? (
        <div className="rounded-2xl border border-slate-200 bg-white p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">3D engineering review</p>
          <p className="mt-2 text-sm text-slate-600">
            Use the canvas toolbar for 2D/3D and quality. Review geometry, grading surface, annotations, and needs-input systems before export.
          </p>
          <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
            {[
              ["Mode", previewMode.toUpperCase()],
              ["Quality", previewQuality],
              ["Surface", hasGradingSurface ? "Grading surface" : "No grading surface"],
              ["Needs input", hasHardSystemBlock ? "Review required" : "None recorded"],
            ].map(([label, value]) => (
              <div key={label} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
                <p className="font-semibold uppercase tracking-[0.14em] text-slate-400">{label}</p>
                <p className="mt-1 font-semibold text-slate-800">{value}</p>
              </div>
            ))}
          </div>
        </div>
      ) : null}
      <div className="rounded-2xl border border-slate-200 bg-white p-4">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Canvas</p>
        <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
          <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
            <p className="font-semibold uppercase tracking-[0.14em] text-slate-400">Objects</p>
            <p className="mt-1 text-lg font-semibold text-slate-900">{placedObjectCount}</p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
            <p className="font-semibold uppercase tracking-[0.14em] text-slate-400">Issues</p>
            <p className="mt-1 text-lg font-semibold text-slate-900">{issueCount}</p>
          </div>
        </div>
      </div>
    </div>
  );
}
