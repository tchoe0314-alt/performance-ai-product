import { PanelCard } from "./ui";

export type WorkspaceSettingsToggle = {
  label: string;
  checked: boolean;
  setter: (checked: boolean) => void;
};

export function WorkspaceSettingsPanel({
  previewQuality,
  leftSidebarOpen,
  assistedEnabled,
  releaseStatus,
  standardsStatus,
  disciplineToggles,
  onOpenStandards,
  onOpenDeliverables,
}: {
  previewQuality: string;
  leftSidebarOpen: boolean;
  assistedEnabled: boolean;
  releaseStatus: string;
  standardsStatus: string;
  disciplineToggles: WorkspaceSettingsToggle[];
  onOpenStandards: () => void;
  onOpenDeliverables: () => void;
}) {
  const settingsRows = [
    ["Appearance", previewQuality],
    ["Layout", leftSidebarOpen ? "Sidebar on" : "Sidebar off"],
    ["AI behavior", assistedEnabled ? "Assisted" : "Manual"],
    ["Exports", releaseStatus === "ready" ? "Review audit ready" : releaseStatus],
    ["Shortcuts", "Default"],
    ["Standards", standardsStatus === "ok" ? "Acceptance required" : standardsStatus],
  ];

  return (
    <div className="space-y-4">
      <PanelCard>
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Workspace settings</p>
        <div className="mt-3 grid grid-cols-2 gap-2 text-xs font-semibold uppercase tracking-[0.12em] text-slate-600">
          {settingsRows.map(([label, value]) => (
            <div key={label} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
              <p className="text-slate-400">{label}</p>
              <p className="mt-1 text-slate-800">{value}</p>
            </div>
          ))}
        </div>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <button
            type="button"
            onClick={onOpenStandards}
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50"
          >
            Standards
          </button>
          <button
            type="button"
            onClick={onOpenDeliverables}
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50"
          >
            Export settings
          </button>
        </div>
      </PanelCard>
      <PanelCard>
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Run defaults</p>
        <div className="mt-3 space-y-2">
          {disciplineToggles.map((toggle) => (
            <label
              key={toggle.label}
              className="flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-700"
            >
              <span>{toggle.label}</span>
              <input
                type="checkbox"
                checked={toggle.checked}
                onChange={(event) => toggle.setter(event.target.checked)}
                className="h-4 w-4 accent-slate-950"
              />
            </label>
          ))}
        </div>
      </PanelCard>
    </div>
  );
}
