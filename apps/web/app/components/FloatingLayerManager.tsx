export type PreviewLayerVisibility = {
  buildings: boolean;
  roads: boolean;
  grading: boolean;
  drainage: boolean;
  utilities: boolean;
  structures: boolean;
  lots: boolean;
};

type FloatingLayerManagerProps = {
  layers: PreviewLayerVisibility;
  rightRailCollapsed: boolean;
  onClose: () => void;
  onApplyPreset: (layers: PreviewLayerVisibility) => void;
  onToggleLayer: (key: keyof PreviewLayerVisibility, visible: boolean) => void;
  onOpenFullDetails: () => void;
};

const layerPresets: Array<{ label: string; layers: PreviewLayerVisibility }> = [
  { label: "Show all", layers: { buildings: true, roads: true, grading: true, drainage: true, utilities: true, structures: true, lots: true } },
  { label: "Proposed", layers: { buildings: true, roads: true, grading: false, drainage: true, utilities: true, structures: true, lots: false } },
  { label: "Utilities", layers: { buildings: false, roads: true, grading: false, drainage: true, utilities: true, structures: true, lots: false } },
  { label: "Clean", layers: { buildings: true, roads: true, grading: false, drainage: false, utilities: false, structures: false, lots: false } },
];

export function FloatingLayerManager({
  layers,
  rightRailCollapsed,
  onClose,
  onApplyPreset,
  onToggleLayer,
  onOpenFullDetails,
}: FloatingLayerManagerProps) {
  const visibleLayerCount = Object.values(layers).filter(Boolean).length;

  return (
    <div
      data-testid="floating-layer-manager"
      className={`pointer-events-auto absolute right-3 top-[9.75rem] z-40 w-[min(360px,calc(100vw-1.5rem))] rounded-xl border border-slate-200 bg-white/94 p-3 shadow-[0_22px_70px_-42px_rgba(15,23,42,0.72)] backdrop-blur-xl lg:top-[9rem] ${rightRailCollapsed ? "lg:right-4" : "lg:right-[416px]"}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">Layers</p>
          <p className="mt-1 text-xs font-semibold text-slate-700">
            {visibleLayerCount}/{Object.keys(layers).length} visible
          </p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded-md border border-slate-200 bg-white px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500 hover:bg-slate-50"
        >
          Close
        </button>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2">
        {layerPresets.map((preset) => (
          <button
            key={preset.label}
            type="button"
            onClick={() => onApplyPreset(preset.layers)}
            className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-700 hover:bg-white"
          >
            {preset.label}
          </button>
        ))}
      </div>
      <div className="mt-3 space-y-1.5">
        {Object.entries(layers).map(([key, value]) => (
          <label
            key={`floating-layer-${key}`}
            className="flex items-center justify-between rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold capitalize text-slate-700"
          >
            <span>{key.replace("_", " ")}</span>
            <span className="flex items-center gap-2">
              <span className={`h-2 w-2 rounded-full ${value ? "bg-emerald-500" : "bg-slate-300"}`} />
              <input
                type="checkbox"
                aria-label={`${value ? "Hide" : "Show"} ${key.replace("_", " ")} layer`}
                checked={Boolean(value)}
                onChange={(event) => onToggleLayer(key as keyof PreviewLayerVisibility, event.target.checked)}
                className="h-4 w-4 accent-slate-950"
              />
              <span className="w-12 text-right text-[10px] uppercase tracking-[0.1em] text-slate-500">
                {value ? "Shown" : "Hidden"}
              </span>
            </span>
          </label>
        ))}
      </div>
      <button
        type="button"
        onClick={onOpenFullDetails}
        className="mt-3 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-600 hover:bg-slate-50"
      >
        Open full layer details
      </button>
    </div>
  );
}
