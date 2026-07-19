export type DashboardHealthItem = {
  key: string;
  label: string;
  state: string;
  detail: string;
};

export function DashboardStatusPanels({
  systemHealthItems,
  attentionMessages,
  onOpenHealthItem,
  onOpenReview,
}: {
  systemHealthItems: DashboardHealthItem[];
  attentionMessages: string[];
  onOpenHealthItem: (key: string) => void;
  onOpenReview: () => void;
}) {
  return (
    <>
      <div className="rounded-2xl border border-slate-200 bg-white p-4">
        <div className="flex items-center justify-between">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Project readiness</p>
          <span className="text-[11px] font-semibold text-slate-500">
            {systemHealthItems.filter((item) => item.state === "complete").length}/{systemHealthItems.length}
          </span>
        </div>
        <div className="mt-3 space-y-2">
          {systemHealthItems.map((item) => (
            <button
              key={item.key}
              type="button"
              onClick={() => onOpenHealthItem(item.key)}
              className="flex w-full items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-left hover:bg-white"
            >
              <span>
                <span className="block text-sm font-semibold text-slate-800">{item.label}</span>
                <span className="block text-xs text-slate-500">{item.detail}</span>
              </span>
              <span
                className={`h-2.5 w-2.5 rounded-full ${
                  item.state === "complete"
                    ? "bg-emerald-500"
                    : item.state === "blocked"
                      ? "bg-red-500"
                      : "bg-amber-400"
                }`}
              />
            </button>
          ))}
        </div>
      </div>
      <div className="rounded-2xl border border-slate-200 bg-white p-4">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Attention</p>
        <div className="mt-3 space-y-2">
          {attentionMessages.slice(0, 3).map((message) => (
            <button
              key={message}
              type="button"
              onClick={onOpenReview}
              className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-left text-sm font-semibold text-slate-700 hover:bg-white"
            >
              {message}
            </button>
          ))}
          {!attentionMessages.length ? (
            <p className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-600">
              No active issues in the current workspace.
            </p>
          ) : null}
        </div>
      </div>
    </>
  );
}
