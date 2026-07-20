export type WorkspaceShortcutRow = [keys: string, label: string];

type WorkspaceShortcutsOverlayProps = {
  shortcuts: WorkspaceShortcutRow[];
  onClose: () => void;
};

export function WorkspaceShortcutsOverlay({
  shortcuts,
  onClose,
}: WorkspaceShortcutsOverlayProps) {
  return (
    <div
      data-testid="shortcuts-help-overlay"
      className="fixed inset-0 z-[60] flex items-start justify-center bg-slate-950/18 px-4 pt-[12vh] backdrop-blur-[2px]"
      role="dialog"
      aria-modal="true"
      aria-label="Keyboard shortcuts"
    >
      <div className="w-full max-w-md rounded-xl border border-slate-200 bg-white/96 p-4 shadow-[0_28px_90px_-44px_rgba(15,23,42,0.72)] backdrop-blur-xl">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">Shortcuts</p>
            <p className="mt-1 text-sm font-semibold text-slate-950">Active workspace commands</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-600 hover:bg-slate-50"
          >
            Close
          </button>
        </div>
        <div className="mt-4 space-y-2">
          {shortcuts.map(([keys, label]) => (
            <div key={keys} className="flex items-center justify-between gap-4 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
              <span className="text-sm font-semibold text-slate-700">{label}</span>
              <span className="shrink-0 rounded-md border border-slate-200 bg-white px-2 py-1 text-[11px] font-semibold text-slate-600">
                {keys}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
