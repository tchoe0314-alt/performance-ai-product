type ObjectManagerHiddenStateProps = {
  hiddenCount: number;
  onShowAll: () => void;
};

export function ObjectManagerHiddenState({ hiddenCount, onShowAll }: ObjectManagerHiddenStateProps) {
  return (
    <div className="mt-3 flex items-center justify-between gap-3 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2" data-testid="object-manager-hidden-state">
      <p className="text-xs font-semibold text-slate-700">
        {hiddenCount} hidden object{hiddenCount === 1 ? "" : "s"}{hiddenCount ? " are excluded from the preview." : "."}
      </p>
      {hiddenCount ? (
        <button
          type="button"
          onClick={onShowAll}
          data-testid="object-manager-show-all"
          className="shrink-0 rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-600 hover:bg-slate-50"
        >
          Show all
        </button>
      ) : null}
    </div>
  );
}
