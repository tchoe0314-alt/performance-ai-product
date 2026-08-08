type DenseConceptActionStripProps = {
  active: boolean;
  previewMode: "2d" | "3d";
  rightRailCollapsed: boolean;
  objectCount: number;
  onEditObjects: () => void;
  onGenerate: () => void;
  onDeliver: () => void;
  onHighQuality: () => void;
};

export function DenseConceptActionStrip({
  active,
  previewMode,
  rightRailCollapsed,
  objectCount,
  onEditObjects,
  onGenerate,
  onDeliver,
  onHighQuality,
}: DenseConceptActionStripProps) {
  if (!active || previewMode === "3d") {
    return null;
  }

  return (
    <div
      data-testid="dense-concept-action-strip"
      className={`pointer-events-auto absolute bottom-4 left-4 z-[35] flex w-[min(252px,calc(100vw-2rem))] flex-col gap-2 rounded-2xl border border-slate-200/80 bg-white/88 p-2.5 shadow-[0_18px_54px_-44px_rgba(15,23,42,0.7)] backdrop-blur-2xl lg:left-[128px] ${
        rightRailCollapsed ? "" : "lg:w-[min(252px,calc(100vw-36rem))]"
      }`}
    >
      <div className="flex flex-col gap-2">
        <div className="min-w-0">
          <p className="truncate text-[13px] font-semibold text-slate-950">Dense concept ready</p>
          <p className="mt-0.5 truncate text-[10px] font-medium text-slate-500">
            {objectCount} editable draft objects. Refine, then Generate.
          </p>
        </div>
        <div className="grid grid-cols-2 gap-1.5">
          <button
            type="button"
            onClick={onEditObjects}
            className="rounded-xl border border-slate-200 bg-white/92 px-2.5 py-1.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-700 hover:bg-slate-50"
          >
            Edit objects
          </button>
          <button
            type="button"
            onClick={onGenerate}
            className="rounded-xl border border-slate-950 bg-slate-950 px-2.5 py-1.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-white hover:bg-slate-800"
          >
            Generate
          </button>
          <button
            type="button"
            onClick={onDeliver}
            className="rounded-xl border border-slate-200 bg-white/92 px-2.5 py-1.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-700 hover:bg-slate-50"
          >
            Deliver
          </button>
          <button
            type="button"
            onClick={onHighQuality}
            className="rounded-xl border border-slate-200 bg-white/92 px-2.5 py-1.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-700 hover:bg-slate-50"
          >
            High quality
          </button>
        </div>
      </div>
    </div>
  );
}
