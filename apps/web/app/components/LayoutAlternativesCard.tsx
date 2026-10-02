import { useState } from "react";
import { createPortal } from "react-dom";
import { useCompactViewport } from "../hooks/useCompactViewport";
import type { LayoutAlternative, LayoutGoal, LayoutGoalKey } from "../utils/layoutAlternatives";

type LayoutAlternativesCardProps = {
  alternatives: LayoutAlternative[];
  selectedId: string;
  onSelect: (id: string) => void;
  onApply: () => void;
  onCancel: () => void;
  goals: LayoutGoal[];
  onGoalsChange: (goals: LayoutGoal[]) => void;
};

const PRIORITIES: Array<{ key: LayoutGoalKey; label: string; goalLabel: string; weight: number }> = [
  { key: "maximize_parking", label: "Parking", goalLabel: "maximize parking", weight: 1.25 },
  { key: "minimize_conflicts", label: "Conflicts", goalLabel: "minimize conflicts", weight: 1.35 },
  { key: "building_near_entrance", label: "Entry distance", goalLabel: "keep buildings near the entrance", weight: 1 },
  { key: "preserve_drainage", label: "Drainage", goalLabel: "preserve drainage features", weight: 1.25 },
  { key: "minimize_roadway", label: "Road length", goalLabel: "minimize roadway length", weight: 1 },
];

export function LayoutAlternativesCard({ alternatives, selectedId, onSelect, onApply, onCancel, goals, onGoalsChange }: LayoutAlternativesCardProps) {
  const compactViewport = useCompactViewport();
  const [minimized, setMinimized] = useState(false);
  const selected = alternatives.find((item) => item.id === selectedId) ?? alternatives[0];
  if (!selected) return null;
  if (compactViewport && minimized) {
    return createPortal(
      <section data-testid="layout-alternatives-card" data-presentation="viewport" aria-label="Minimized layout comparison" className="fixed inset-x-3 bottom-[calc(env(safe-area-inset-bottom)+6.5rem)] z-[850] flex items-center justify-between gap-2 rounded-xl border border-slate-200 bg-white p-3 shadow-xl">
        <span className="text-xs font-semibold text-slate-700">Options · not applied</span>
        <button type="button" data-testid="layout-alternatives-expand" onClick={() => setMinimized(false)} className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold">Show comparison</button>
      </section>, document.body,
    );
  }
  const toggleGoal = (priority: (typeof PRIORITIES)[number]) => {
    const isActive = goals.some((goal) => goal.key === priority.key);
    if (isActive && goals.length === 1) return;
    const next = isActive
      ? goals.filter((goal) => goal.key !== priority.key)
      : [...goals, { key: priority.key, label: priority.goalLabel, weight: priority.weight }];
    onGoalsChange(next);
  };
  const card = (
    <section data-testid="layout-alternatives-card" data-presentation={compactViewport ? "viewport" : "canvas"} className={`fixed inset-x-3 top-16 ${compactViewport ? "z-[850] max-h-[calc(100svh-12rem)]" : "z-[760] max-h-[calc(100svh-5rem)]"} overflow-y-auto rounded-2xl border border-slate-200 bg-white/96 p-3 shadow-2xl backdrop-blur lg:left-[4.5rem] lg:right-[21rem]`}>
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-blue-700">Layout alternatives · preview only</p>
          <p className="mt-1 text-sm font-semibold text-slate-900">Compare options before changing the working plan</p>
          <p className="mt-1 text-[11px] text-slate-500">Ranked for {selected.goalLabels.join(" + ")}</p>
          <p data-testid="layout-search-report" className="mt-1 text-[10px] text-slate-400">
            Searched {selected.searchReport.explored} candidates · {selected.searchReport.accepted} valid distinct · {selected.searchReport.rejected} rejected
            {selected.searchReport.rejectionReasons.length ? ` (${selected.searchReport.rejectionReasons.join(", ")})` : ""}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {compactViewport ? <button type="button" onClick={() => setMinimized(true)} data-testid="layout-alternatives-minimize" className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-600">Minimize</button> : null}
          <button type="button" onClick={onCancel} data-testid="layout-alternatives-cancel" className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-600">Cancel</button>
        </div>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-1.5 border-t border-slate-100 pt-3" aria-label="Layout ranking priorities">
        <span className="mr-1 text-[10px] font-bold uppercase tracking-[0.12em] text-slate-400">Prioritize</span>
        {PRIORITIES.map((priority) => {
          const active = goals.some((goal) => goal.key === priority.key);
          const lastActive = active && goals.length === 1;
          return (
            <button
              key={priority.key}
              type="button"
              aria-pressed={active}
              disabled={lastActive}
              title={lastActive ? "Keep at least one ranking priority" : undefined}
              data-testid={`layout-priority-${priority.key}`}
              onClick={() => toggleGoal(priority)}
              className={`rounded-full border px-2.5 py-1 text-[10px] font-semibold transition disabled:cursor-not-allowed disabled:opacity-70 ${active ? "border-blue-500 bg-blue-50 text-blue-700" : "border-slate-200 bg-white text-slate-500 hover:border-slate-300 hover:text-slate-700"}`}
            >
              {priority.label}
            </button>
          );
        })}
        <span className="ml-auto text-[10px] text-slate-400">Updates instantly</span>
      </div>
      <div className="mt-3 grid gap-2 sm:grid-cols-3 lg:grid-cols-5">
        {alternatives.map((alternative) => {
          const active = alternative.id === selected.id;
          return (
            <button
              key={alternative.id}
              type="button"
              data-testid={`layout-alternative-${alternative.id}`}
              data-changed-object-count={alternative.differences.length}
              data-changed-types={[...new Set(alternative.differences.map((item) => item.after.type ?? "other"))].join(" ")}
              aria-pressed={active}
              onClick={() => onSelect(alternative.id)}
              className={`rounded-xl border p-2 text-left ${active ? "border-blue-500 bg-blue-50 ring-2 ring-blue-100" : "border-slate-200 bg-white hover:bg-slate-50"}`}
            >
              <span className="flex items-center justify-between gap-2 text-xs font-bold text-slate-900"><span>#{alternative.rank} {alternative.label}</span><span data-testid={`layout-alternative-score-${alternative.id}`} className="rounded-full bg-white px-1.5 py-0.5 text-[10px] text-blue-700">{alternative.score}</span></span>
              <span className="mt-1 block text-[9px] font-semibold uppercase tracking-wide text-slate-400">{alternative.profile}</span>
              <span className="mt-1 block text-[10px] leading-4 text-slate-500">Capacity {alternative.metrics.capacity} · Short {alternative.metrics.shortfall}</span>
              <span className={`mt-1 block text-[10px] font-semibold ${alternative.metrics.conflicts ? "text-red-600" : "text-emerald-600"}`}>{alternative.metrics.conflicts} conflict{alternative.metrics.conflicts === 1 ? "" : "s"}</span>
            </button>
          );
        })}
      </div>
      <div className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-xl bg-slate-50 px-3 py-2">
        <div>
          <p className="text-xs font-bold text-slate-900">{selected.label}</p>
          <p className="text-[11px] text-slate-500">{selected.description} Nothing is committed until Apply.</p>
          <p data-testid="layout-alternative-change-summary" className="mt-1 text-[10px] font-semibold text-blue-700">
            {selected.differences.length
              ? `${selected.differences.length} changed object${selected.differences.length === 1 ? "" : "s"} · ${selected.differences.filter((item) => item.moved).length} moved · ${selected.differences.filter((item) => item.resized).length} resized`
              : "Baseline option · no geometry changes"}
          </p>
          {selected.fixedObjectCount ? (
            <p data-testid="layout-alternative-fixed-summary" className="mt-1 text-[10px] font-semibold text-amber-700">
              {selected.fixedObjectCount} fixed/reference object{selected.fixedObjectCount === 1 ? "" : "s"} protected from movement
            </p>
          ) : null}
          <ul data-testid="layout-alternative-reasons" className="mt-1 flex flex-wrap gap-x-3 text-[10px] text-slate-600">
            {selected.scoreReasons.map((reason) => <li key={reason}>• {reason}</li>)}
          </ul>
        </div>
        <button type="button" data-testid="layout-alternatives-apply" onClick={onApply} className="rounded-lg bg-slate-950 px-4 py-2 text-xs font-bold text-white hover:bg-slate-800">Apply this option</button>
      </div>
    </section>
  );
  return compactViewport ? createPortal(card, document.body) : card;
}
