import type { SourceConfidenceEntry } from "../types";
import type { SidePanelKey } from "../utils/workspaceShell";

type SourceHubMetric = readonly [string, string | number];

type SourceHubLink = readonly [SidePanelKey, string];

export function SourceHubPanel({
  links,
  metrics,
  entryCount,
  entries,
  onOpenPanel,
}: {
  links: SourceHubLink[];
  metrics: SourceHubMetric[];
  entryCount: number;
  entries: SourceConfidenceEntry[];
  onOpenPanel: (panel: SidePanelKey) => void;
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4">
      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Source hub</p>
      <div className="mt-3 grid grid-cols-2 gap-2">
        {links.map(([panel, label]) => (
          <button
            key={panel}
            type="button"
            onClick={() => onOpenPanel(panel)}
            className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-left text-xs font-semibold uppercase tracking-[0.12em] text-slate-600 hover:bg-white"
          >
            {label}
          </button>
        ))}
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
        {metrics.map(([label, value]) => (
          <div key={label} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
            <p className="font-semibold uppercase tracking-[0.14em] text-slate-400">{label}</p>
            <p className="mt-1 truncate font-semibold text-slate-800">{value}</p>
          </div>
        ))}
      </div>
      <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-3" data-testid="source-confidence-map">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Source Confidence Map</p>
            <p className="mt-1 text-xs font-medium text-slate-500">{entryCount} visible source/object/layer entries. Review only.</p>
          </div>
          <span className="shrink-0 rounded-full bg-red-50 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-red-700">
            review only
          </span>
        </div>
        <div className="mt-3 space-y-2">
          {entries.length ? (
            entries.map((entry) => (
              <div key={entry.entry_id} className="rounded-lg border border-slate-200 bg-white px-3 py-2">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-slate-800">{entry.label || entry.layer || "Source entry"}</p>
                    <p className="mt-0.5 truncate text-[11px] uppercase tracking-[0.12em] text-slate-400">
                      {entry.category || "source"} · {entry.source_name || "unknown"}
                    </p>
                  </div>
                  <span
                    className={`shrink-0 rounded-full px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${
                      entry.confidence_band === "higher"
                        ? "bg-emerald-50 text-emerald-700"
                        : entry.confidence_band === "review"
                          ? "bg-amber-50 text-amber-700"
                          : "bg-red-50 text-red-700"
                    }`}
                  >
                    {entry.visible_badge || `${entry.source_type || "unknown"} · ${entry.confidence_band || "low"}`}
                  </span>
                </div>
                {entry.why_low_confidence || entry.next_action ? (
                  <p className="mt-1 line-clamp-2 text-xs text-slate-500">{entry.why_low_confidence || entry.next_action}</p>
                ) : null}
              </div>
            ))
          ) : (
            <p className="text-xs text-slate-500">No source confidence entries are available yet.</p>
          )}
        </div>
      </div>
    </div>
  );
}
