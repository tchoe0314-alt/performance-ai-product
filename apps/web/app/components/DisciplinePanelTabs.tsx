type DisciplinePanelTab = {
  label: string;
  panel: string;
};

type DisciplinePanelTabsProps<TPanel extends string> = {
  items: Array<DisciplinePanelTab & { panel: TPanel }>;
  activePanel: TPanel | string | null;
  onOpenPanel: (panel: TPanel) => void;
};

export function DisciplinePanelTabs<TPanel extends string>({
  items,
  activePanel,
  onOpenPanel,
}: DisciplinePanelTabsProps<TPanel>) {
  return (
    <div className="mb-4 rounded-xl border border-slate-200 bg-slate-50 p-2">
      <p className="px-1 pb-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500">
        Discipline controls
      </p>
      <div className="grid grid-cols-2 gap-1.5">
        {items.map((item) => {
          const isActive = activePanel === item.panel;
          return (
            <button
              key={item.panel}
              type="button"
              onClick={() => onOpenPanel(item.panel)}
              aria-current={isActive ? "page" : undefined}
              className={`rounded-lg border px-2 py-1.5 text-left text-[11px] font-semibold uppercase tracking-[0.12em] transition ${
                isActive
                  ? "border-slate-950 bg-slate-950 text-white"
                  : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
              }`}
            >
              {item.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
