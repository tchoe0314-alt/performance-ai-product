import type { SidePanelKey } from "../utils/workspaceShell";

export type DashboardGuidanceChecklistItem = {
  label: string;
  status: "done" | "missing" | "blocked";
  panel: SidePanelKey;
  action: string;
  detail: string;
};

type DashboardGuidancePanelProps = {
  stats: Array<[string, number]>;
  checklistItems: DashboardGuidanceChecklistItem[];
  onOpenPanel: (panel: SidePanelKey) => void;
};

const statusMeanings = [
  ["Ready", "Enough current, traceable evidence exists for review."],
  ["Needs Review", "A user or licensed engineer must check the output, source, or assumption."],
  ["Needs input", "Something important is missing before the next review step can continue."],
  ["Missing input", "Helpful information is absent, such as a locked site, survey/control, outlet, tie-in, datum, or accepted standards."],
  ["Draft/review-required", "A draft value or geometry item is carried forward only so review can continue."],
  ["Visual preview only", "The view is a visual aid and is not evidence by itself."],
  ["Engineer review required", "A qualified user or licensed engineer must review before reliance."],
  ["Field use", "Remains outside Civora and requires independent licensed-professional review."],
];

export function DashboardGuidancePanel({ stats, checklistItems, onOpenPanel }: DashboardGuidancePanelProps) {
  return (
    <>
      <div className="grid grid-cols-2 gap-2">
        {stats.map(([label, value]) => (
          <div key={label} className="rounded-xl border border-slate-200 bg-white px-3 py-3">
            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">{label}</p>
            <p className="mt-1 text-xl font-semibold text-slate-900">{value}</p>
          </div>
        ))}
      </div>
      <details className="rounded-2xl border border-slate-200 bg-white p-4">
        <summary className="cursor-pointer text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
          Onboarding checklist
        </summary>
        <div className="mt-3 space-y-2">
          {checklistItems.map((item) => (
            <button
              key={item.label}
              type="button"
              onClick={() => onOpenPanel(item.panel)}
              className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-left transition hover:bg-white"
            >
              <div className="flex items-start justify-between gap-3">
                <span className="text-sm font-semibold text-slate-800">{item.label}</span>
                <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.12em] ${
                  item.status === "done"
                    ? "bg-emerald-50 text-emerald-700"
                    : item.status === "blocked"
                      ? "bg-red-50 text-red-600"
                      : "bg-amber-50 text-amber-700"
                }`}>
                  {item.status}
                </span>
              </div>
              <p className="mt-1 text-xs text-slate-500">{item.action}</p>
              <p className="mt-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-400">{item.detail}</p>
            </button>
          ))}
        </div>
      </details>
      <details className="rounded-2xl border border-slate-200 bg-white p-4">
        <summary className="cursor-pointer text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
          What do statuses mean?
        </summary>
        <div className="mt-3 space-y-2 text-sm text-slate-600">
          {statusMeanings.map(([label, desc]) => (
            <div key={label} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
              <p className="font-semibold text-slate-800">{label}</p>
              <p className="mt-1 text-xs leading-5 text-slate-500">{desc}</p>
            </div>
          ))}
        </div>
      </details>
    </>
  );
}
