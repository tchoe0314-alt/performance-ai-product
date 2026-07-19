import { PanelCard } from "./ui";

export type LibraryPanelItem = {
  type: string;
  label: string;
};

export type LibraryPanelSection = {
  key: string;
  title: string;
  items: LibraryPanelItem[];
};

export function LibrariesPanel({
  sections,
  onAddObject,
}: {
  sections: LibraryPanelSection[];
  onAddObject: (type: string) => void;
}) {
  return (
    <div className="space-y-4">
      {sections.map((group) => (
        <PanelCard key={group.key}>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">{group.title}</p>
          <div className="mt-3 grid grid-cols-2 gap-2">
            {group.items.map((item) => (
              <button
                key={item.type}
                type="button"
                onClick={() => onAddObject(item.type)}
                className="rounded-xl border border-slate-200 bg-white px-3 py-3 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50"
              >
                {item.label}
              </button>
            ))}
          </div>
        </PanelCard>
      ))}
    </div>
  );
}
