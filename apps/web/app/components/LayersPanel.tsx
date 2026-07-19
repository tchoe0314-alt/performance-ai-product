type PreviewLayers = Record<string, boolean>;

type LayersPanelProps = {
  layers: PreviewLayers;
  onLayersChange: (updater: (previous: PreviewLayers) => PreviewLayers) => void;
};

export function LayersPanel({ layers, onLayersChange }: LayersPanelProps) {
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-2">
        <button
          type="button"
          onClick={() =>
            onLayersChange((previous) =>
              Object.fromEntries(Object.keys(previous).map((key) => [key, true])),
            )
          }
          className="rounded-xl border border-slate-200 bg-white px-3 py-3 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50"
        >
          Show all
        </button>
        <button
          type="button"
          onClick={() =>
            onLayersChange((previous) => ({
              ...Object.fromEntries(Object.keys(previous).map((key) => [key, false])),
              buildings: true,
            }))
          }
          className="rounded-xl border border-slate-200 bg-white px-3 py-3 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50"
        >
          Buildings only
        </button>
      </div>
      {Object.entries(layers).map(([key, value]) => (
        <label
          key={key}
          className="flex items-center justify-between rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm font-semibold capitalize text-slate-700"
        >
          <span>{key.replace("_", " ")}</span>
          <input
            type="checkbox"
            checked={Boolean(value)}
            onChange={(event) => onLayersChange((previous) => ({ ...previous, [key]: event.target.checked }))}
            className="h-4 w-4 accent-slate-950"
          />
        </label>
      ))}
    </div>
  );
}
