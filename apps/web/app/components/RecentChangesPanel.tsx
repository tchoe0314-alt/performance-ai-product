type RecentChangeRow = {
  id: string;
  label: string;
  detail: string;
  createdAt: number;
  canUndo: boolean;
  onAction: () => void;
};

type RecentChangesPanelProps = {
  changes: RecentChangeRow[];
  open: boolean;
  canUndoDraft: boolean;
  canRedoDraft: boolean;
  onToggleOpen: () => void;
  onUndoDraft: () => void;
  onRedoDraft: () => void;
};

export function RecentChangesPanel({
  changes,
  open,
  canUndoDraft,
  canRedoDraft,
  onToggleOpen,
  onUndoDraft,
  onRedoDraft,
}: RecentChangesPanelProps) {
  return (
    <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-3" data-testid="recent-changes-section">
      <div className="flex items-center justify-between gap-3">
        <button
          type="button"
          onClick={onToggleOpen}
          aria-expanded={open}
          className="min-w-0 text-left"
        >
          <span className="block text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
            Recent changes
          </span>
          <span className="mt-1 block truncate text-sm font-semibold text-slate-900">
            {changes[0]?.detail || "No draft changes recorded yet."}
          </span>
        </button>
        <div className="flex shrink-0 items-center gap-1.5">
          <button
            type="button"
            onClick={onUndoDraft}
            disabled={!canUndoDraft}
            data-testid="recent-changes-undo"
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Undo
          </button>
          <button
            type="button"
            onClick={onRedoDraft}
            disabled={!canRedoDraft}
            data-testid="recent-changes-redo"
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Redo
          </button>
        </div>
      </div>
      {open ? (
        <div className="mt-3 space-y-2" data-testid="recent-changes-list">
          {changes.length ? (
            changes.map((change) => (
              <div key={change.id} className="rounded-lg border border-slate-200 bg-white px-3 py-2">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-xs font-semibold text-slate-900">{change.label}</p>
                    <p className="mt-1 text-xs text-slate-500">{change.detail}</p>
                    <p className="mt-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-400">
                      {new Date(change.createdAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={change.onAction}
                    data-testid="recent-change-row-undo"
                    className="shrink-0 rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-600 hover:bg-white"
                  >
                    {change.canUndo ? "Undo" : "Why unavailable"}
                  </button>
                </div>
              </div>
            ))
          ) : (
            <p className="rounded-lg border border-dashed border-slate-300 bg-white px-3 py-3 text-xs font-semibold text-slate-500">
              Recent draft UI changes will appear here. Engineering outputs remain review-required.
            </p>
          )}
        </div>
      ) : null}
    </div>
  );
}
