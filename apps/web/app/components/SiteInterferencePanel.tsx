import { useMemo } from "react";
import type { BuildingPlacement } from "../types";
import { assessSiteInterference } from "../utils/siteInterference";

export function SiteInterferencePanel({ objects }: { objects: BuildingPlacement[] }) {
  const results = useMemo(() => assessSiteInterference(objects), [objects]);
  const conflicts = results.filter(r => r.severity === "conflict"), review = results.filter(r => r.severity === "review"), clear = results.filter(r => r.severity === "clear");
  return <section className="rounded-lg border border-slate-200 bg-white p-3" data-testid="site-interference-panel" aria-label="Object interference review">
    <p className="text-xs font-semibold">Object interference · {conflicts.length} conflicts · {review.length} review · {clear.length} separated crossings</p>
    <p className="mt-1 text-[11px] text-slate-500">Type-aware draft checks. Hidden objects still count; unplaced objects do not. A pipe crossing a footprint is not automatically a clash—or automatically safe.</p>
    {results.length ? <ul className="mt-2 space-y-2 text-xs">{[...conflicts, ...review, ...clear].slice(0, 20).map((r, i) => <li key={`${r.code}:${r.objectIds.join(":")}:${i}`} data-interference-severity={r.severity} className={r.severity === "conflict" ? "text-red-700" : r.severity === "review" ? "text-amber-800" : "text-slate-600"}>{r.message}</li>)}</ul> : <p className="mt-2 text-xs text-slate-600">No modeled contact found among checked placed objects. This is not engineering approval.</p>}
    {results.length > 20 ? <p className="mt-2 text-xs">Showing the first 20 of {results.length} crossing results.</p> : null}
  </section>;
}
