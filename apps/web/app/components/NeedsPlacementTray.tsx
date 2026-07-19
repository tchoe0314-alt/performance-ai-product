type PendingPlacementItem = {
  id: string;
  label: string;
  typeLabel: string;
  widthFt: number;
  depthFt: number;
};

type NeedsPlacementTrayProps = {
  items: PendingPlacementItem[];
  onPlace: (id: string) => void;
};

export function NeedsPlacementTray({ items, onPlace }: NeedsPlacementTrayProps) {
  return (
    <div className={`${items.length ? "" : "hidden"} rounded-2xl border border-amber-200 bg-amber-50 p-4`} data-testid="needs-placement-tray">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-amber-700">Needs placement</p>
          <p className="mt-1 text-sm font-semibold text-amber-950">
            {items.length
              ? `${items.length} draft object${items.length === 1 ? "" : "s"} must be placed before Generate can rely on them.`
              : "No pending placement objects."}
          </p>
        </div>
        <span className="rounded-full bg-white px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-amber-700">
          Pending {items.length}
        </span>
      </div>
      {items.length ? (
        <div className="mt-3 space-y-2">
          {items.map((item) => (
            <div key={item.id} className="flex items-center justify-between gap-3 rounded-xl border border-amber-200 bg-white px-3 py-2 text-sm">
              <div className="min-w-0">
                <p className="truncate font-semibold text-slate-900">{item.label}</p>
                <p className="text-xs font-medium text-slate-500">
                  {item.typeLabel} · {item.widthFt} ft x {item.depthFt} ft
                </p>
              </div>
              <button
                type="button"
                onClick={() => onPlace(item.id)}
                className="shrink-0 rounded-lg border border-slate-950 bg-slate-950 px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-white hover:bg-slate-800"
              >
                Place
              </button>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
