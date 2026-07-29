type ObjectManagerOverviewProps = {
  totalCount: number;
  placedCount: number;
  pendingCount: number;
  selectedCount: number;
  hiddenCount: number;
  typeLabels: string[];
  clipboardLabels: string[];
  onSelectVisibleDraft: () => void;
  onInvertSelection: () => void;
  onPaste: () => void;
};

export function ObjectManagerOverview({
  totalCount,
  placedCount,
  pendingCount,
  selectedCount,
  hiddenCount,
  typeLabels,
  clipboardLabels,
  onSelectVisibleDraft,
  onInvertSelection,
  onPaste,
}: ObjectManagerOverviewProps) {
  const pasteLabel =
    clipboardLabels.length === 1
      ? `Paste ${clipboardLabels[0]}`
      : clipboardLabels.length > 1
        ? `Paste ${clipboardLabels.length} objects`
        : "Paste";

  return (
    <>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
            Object List
          </p>
          <p className="mt-1 text-sm font-semibold text-slate-900" data-testid="object-manager-summary">
            {totalCount} object{totalCount === 1 ? "" : "s"} · {placedCount} placed · {pendingCount} pending
          </p>
          {typeLabels.length ? (
            <p className="mt-1 truncate text-[11px] font-medium text-slate-500">
              {typeLabels.slice(0, 5).join(", ")}
            </p>
          ) : null}
        </div>
        <span
          className="shrink-0 rounded-full bg-slate-50 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500"
          data-testid="object-manager-selected-count"
        >
          Selected {selectedCount}
        </span>
      </div>
      <div className="mt-3 grid grid-cols-3 gap-2 text-[11px]" data-testid="object-manager-quick-stats">
        <div className="rounded-xl border border-slate-200 bg-slate-50 px-2.5 py-2">
          <p className="font-semibold uppercase tracking-[0.12em] text-slate-400">Visible</p>
          <p className="mt-1 font-semibold text-slate-900">{Math.max(0, totalCount - hiddenCount)}</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-slate-50 px-2.5 py-2">
          <p className="font-semibold uppercase tracking-[0.12em] text-slate-400">Selected</p>
          <p className="mt-1 font-semibold text-slate-900">{selectedCount}</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-slate-50 px-2.5 py-2">
          <p className="font-semibold uppercase tracking-[0.12em] text-slate-400">Hidden</p>
          <p className="mt-1 font-semibold text-slate-900">{hiddenCount}</p>
        </div>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-2" data-testid="object-manager-clipboard-actions">
        <button
          type="button"
          onClick={onSelectVisibleDraft}
          data-testid="object-manager-select-visible"
          className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-700 transition hover:bg-slate-50"
        >
          Select visible draft
        </button>
        <button
          type="button"
          onClick={onInvertSelection}
          data-testid="object-manager-invert-selection"
          className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-700 transition hover:bg-slate-50"
        >
          Invert selection
        </button>
        <button
          type="button"
          onClick={onPaste}
          disabled={!clipboardLabels.length}
          data-testid="object-manager-paste"
          className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {pasteLabel}
        </button>
        <span className="text-[11px] font-medium text-slate-500">
          Copy, paste, rotate, and flip work on editable draft objects.
        </span>
      </div>
    </>
  );
}
