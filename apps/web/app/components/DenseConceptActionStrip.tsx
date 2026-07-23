type DenseConceptActionStripProps = {
  active: boolean;
  rightRailCollapsed: boolean;
  objectCount: number;
  onEditObjects: () => void;
  onGenerate: () => void;
  onDeliver: () => void;
  onHighQuality: () => void;
};

export function DenseConceptActionStrip({
  active,
  rightRailCollapsed,
  objectCount,
  onEditObjects,
  onGenerate,
  onDeliver,
  onHighQuality,
}: DenseConceptActionStripProps) {
  if (!active) {
    return null;
  }

  return (
    <div
      data-testid="dense-concept-action-strip"
      className={`absolute bottom-4 left-4 z-[35] flex max-w-[calc(100vw-2rem)] flex-col gap-2 rounded-2xl border border-slate-200/90 bg-white/92 p-3 shadow-[0_24px_70px_-48px_rgba(15,23,42,0.72)] backdrop-blur-2xl lg:left-[128px] ${
        rightRailCollapsed ? "lg:max-w-[min(760px,calc(100vw-10rem))]" : "lg:max-w-[min(620px,calc(100vw-36rem))]"
      }`}
    >
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-slate-950">Dense concept ready</p>
          <p className="mt-0.5 truncate text-xs font-medium text-slate-500">
            {objectCount} editable draft objects. Edit the layout, then Generate.
          </p>
        </div>
        <div className="grid grid-cols-2 gap-2 sm:flex sm:shrink-0 sm:items-center">
          <button
            type="button"
            onClick={onEditObjects}
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-700 hover:bg-slate-50"
          >
            Edit objects
          </button>
          <button
            type="button"
            onClick={onGenerate}
            className="rounded-xl border border-slate-950 bg-slate-950 px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-white hover:bg-slate-800"
          >
            Generate
          </button>
          <button
            type="button"
            onClick={onDeliver}
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-700 hover:bg-slate-50"
          >
            Deliver
          </button>
          <button
            type="button"
            onClick={onHighQuality}
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-700 hover:bg-slate-50"
          >
            High quality
          </button>
        </div>
      </div>
    </div>
  );
}
