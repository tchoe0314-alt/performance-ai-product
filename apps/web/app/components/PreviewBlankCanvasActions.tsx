type PreviewBlankCanvasActionsProps = {
  hasDrawableSiteSize: boolean;
  onEnterAddress?: () => void;
  onDrawBoundary: () => void;
};

export function blankCanvasNextAction(hasDrawableSiteSize: boolean) {
  return hasDrawableSiteSize
    ? "Next: draw the boundary, then add the first design object."
    : "Next: enter an address or draw the boundary to establish site scale.";
}

export function PreviewBlankCanvasActions({
  hasDrawableSiteSize,
  onEnterAddress,
  onDrawBoundary,
}: PreviewBlankCanvasActionsProps) {
  return (
    <section
      data-testid="blank-canvas-actions"
      aria-label="Start the site plan"
      className="pointer-events-auto relative z-30 mx-4 max-w-lg rounded-xl border border-slate-200 bg-white/96 p-5 text-center shadow-[0_18px_55px_-34px_rgba(15,23,42,0.75)] backdrop-blur"
      onMouseDown={(event) => event.stopPropagation()}
      onClick={(event) => event.stopPropagation()}
    >
      <h2 className="text-base font-semibold text-slate-950">Start the site plan</h2>
      <p className="mt-1 text-sm text-slate-600">
        Add real site context, draw the boundary, or inspect the separate sample workspace.
      </p>
      <div className="mt-4 flex flex-wrap justify-center gap-2">
        {onEnterAddress ? (
          <button type="button" data-testid="blank-canvas-enter-address" onClick={onEnterAddress} className="h-9 rounded-lg border border-slate-300 bg-white px-3 text-xs font-semibold text-slate-800 hover:bg-slate-50">
            Enter address
          </button>
        ) : null}
        <button type="button" data-testid="blank-canvas-draw-boundary" onClick={onDrawBoundary} className="h-9 rounded-lg border border-blue-600 bg-blue-600 px-3 text-xs font-semibold text-white hover:bg-blue-700">
          Draw boundary
        </button>
        <a href="/demo/workspace" target="_blank" rel="noopener noreferrer" data-testid="blank-canvas-open-sample" className="inline-flex h-9 items-center rounded-lg border border-slate-300 bg-white px-3 text-xs font-semibold text-slate-800 hover:bg-slate-50">
          Open sample
        </a>
      </div>
      <p className="mt-3 text-xs font-medium text-slate-500" data-testid="blank-canvas-next-action">
        {blankCanvasNextAction(hasDrawableSiteSize)}
      </p>
      <p className="mt-1 text-[11px] text-slate-400">The sample opens separately and does not replace this project.</p>
    </section>
  );
}
