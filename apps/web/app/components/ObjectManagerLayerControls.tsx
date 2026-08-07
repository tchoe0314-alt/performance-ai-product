import type { SiteObjectType } from "../types";

export type ObjectManagerLayerRow = {
  type: SiteObjectType;
  label: string;
  count: number;
  hiddenCount: number;
  lockedCount: number;
  allHidden: boolean;
  allLocked: boolean;
};

type ObjectManagerLayerControlsProps = {
  rows: ObjectManagerLayerRow[];
  onSelectLayer: (type: SiteObjectType) => void;
  onIsolateLayer: (type: SiteObjectType) => void;
  onSetLayerHidden: (type: SiteObjectType, hidden: boolean) => void;
  onSetLayerLocked: (type: SiteObjectType, locked: boolean) => void;
};

export function ObjectManagerLayerControls({
  rows,
  onSelectLayer,
  onIsolateLayer,
  onSetLayerHidden,
  onSetLayerLocked,
}: ObjectManagerLayerControlsProps) {
  if (!rows.length) return null;

  return (
    <div className="mt-3 rounded-xl border border-slate-200 bg-white p-3" data-testid="object-manager-layer-controls">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
            Layers
          </p>
          <p className="mt-1 text-xs font-medium text-slate-500">
            Hide/show or lock entire object layers.
          </p>
        </div>
        <span className="rounded-full bg-slate-50 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500">
          {rows.length}
        </span>
      </div>
      <div className="mt-3 space-y-2">
        {rows.map((layer) => (
          <div
            key={`object-layer-${layer.type}`}
            data-testid="object-manager-layer-row"
            className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2"
          >
            <div className="min-w-0">
              <div className="min-w-0">
                <p className="text-xs font-semibold text-slate-900">{layer.label}</p>
                <p className="mt-1 text-[11px] font-medium text-slate-500">
                  {layer.count} object{layer.count === 1 ? "" : "s"} · {layer.hiddenCount} hidden · {layer.lockedCount} locked
                </p>
              </div>
              <div className="mt-2 grid grid-cols-4 gap-1.5">
                <button
                  type="button"
                  onClick={() => onSelectLayer(layer.type)}
                  data-testid="object-manager-layer-select"
                  className="min-w-0 rounded-md border border-slate-200 bg-white px-1.5 py-1 text-[10px] font-semibold uppercase tracking-[0.08em] text-slate-600 hover:bg-slate-50"
                >
                  Select
                </button>
                <button
                  type="button"
                  onClick={() => onIsolateLayer(layer.type)}
                  data-testid="object-manager-layer-isolate"
                  className="min-w-0 rounded-md border border-slate-200 bg-white px-1.5 py-1 text-[10px] font-semibold uppercase tracking-[0.08em] text-slate-600 hover:bg-slate-50"
                >
                  Only
                </button>
                <button
                  type="button"
                  onClick={() => onSetLayerHidden(layer.type, !layer.allHidden)}
                  data-testid="object-manager-layer-visibility"
                  className="min-w-0 rounded-md border border-slate-200 bg-white px-1.5 py-1 text-[10px] font-semibold uppercase tracking-[0.08em] text-slate-600 hover:bg-slate-50"
                >
                  {layer.allHidden ? "Show" : "Hide"}
                </button>
                <button
                  type="button"
                  onClick={() => onSetLayerLocked(layer.type, !layer.allLocked)}
                  data-testid="object-manager-layer-lock"
                  className="min-w-0 rounded-md border border-slate-200 bg-white px-1.5 py-1 text-[10px] font-semibold uppercase tracking-[0.08em] text-slate-600 hover:bg-slate-50"
                >
                  {layer.allLocked ? "Unlock" : "Lock"}
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
