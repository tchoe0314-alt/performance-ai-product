import type { SourceConfidenceEntry } from "../types";

export type SourceConfidenceSummaryView = {
  entry_count?: number;
  low_confidence_count?: number;
  user_drawn_count?: number;
  needs_survey_control_count?: number;
};

export function SourceConfidencePanel({
  summary,
  entries,
  totalEntryCount,
}: {
  summary: SourceConfidenceSummaryView;
  entries: SourceConfidenceEntry[];
  totalEntryCount: number;
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4">
      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Source confidence</p>
      <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
        {[
          ["Entries", summary.entry_count ?? totalEntryCount],
          ["Low confidence", summary.low_confidence_count ?? 0],
          ["User drawn", summary.user_drawn_count ?? 0],
          ["Need control", summary.needs_survey_control_count ?? 0],
        ].map(([label, value]) => (
          <div key={label} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
            <p className="font-semibold uppercase tracking-[0.14em] text-slate-400">{label}</p>
            <p className="mt-1 font-semibold text-slate-800">{value}</p>
          </div>
        ))}
      </div>
      <div className="mt-3 space-y-2">
        {entries.slice(0, 5).map((entry) => (
          <div key={entry.entry_id} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
            <div className="flex items-start justify-between gap-3">
              <span className="text-sm font-semibold text-slate-700">{entry.label || "Source entry"}</span>
              <span
                className={`text-right text-[11px] font-semibold uppercase tracking-[0.12em] ${
                  entry.confidence_band === "higher"
                    ? "text-emerald-700"
                    : entry.confidence_band === "review"
                      ? "text-amber-600"
                      : "text-red-600"
                }`}
              >
                {entry.visible_badge || entry.source_type}
              </span>
            </div>
            <p className="mt-1 line-clamp-2 text-xs text-slate-500">
              {entry.why_low_confidence || entry.next_action || "Verification status visible."}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
