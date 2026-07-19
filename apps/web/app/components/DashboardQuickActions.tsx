import type { SidePanelKey } from "../utils/workspaceShell";

type DashboardQuickActionsProps = {
  onOpenPanel: (panel: SidePanelKey) => void;
};

const quickActions: Array<{ label: string; panel: SidePanelKey }> = [
  { label: "Objects", panel: "objects" },
  { label: "Review", panel: "analysis" },
  { label: "Deliver", panel: "deliverables" },
];

export function DashboardQuickActions({ onOpenPanel }: DashboardQuickActionsProps) {
  return (
    <div className="grid grid-cols-3 gap-2">
      {quickActions.map((action) => (
        <button
          key={action.label}
          type="button"
          onClick={() => onOpenPanel(action.panel)}
          className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50"
        >
          {action.label}
        </button>
      ))}
    </div>
  );
}
