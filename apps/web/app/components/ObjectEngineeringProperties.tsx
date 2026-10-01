import { useState } from "react";
import type { BuildingPlacement } from "../types";
import { readCulDeSac } from "../utils/parametricRoad";
import type { VerticalExtent } from "../utils/siteInterference";
import { isLinearUtility } from "../utils/siteInterference";

export function ObjectEngineeringProperties({ item, onCommit }: { item: BuildingPlacement; onCommit: (item: BuildingPlacement, meta: Record<string, unknown>) => void }) {
  const road = readCulDeSac(item), z = item.meta?.vertical_extent_v1 as Partial<VerticalExtent> | undefined;
  const [draft, setDraft] = useState({ min: String(z?.minFt ?? ""), max: String(z?.maxFt ?? ""), datum: z?.datum ?? "", source: z?.source ?? "", clearance: String(z?.requiredClearanceFt ?? ""), reviewed: z?.reviewed ?? false, diameter: String(item.meta?.pipe_diameter_ft ?? "") });
  const [error, setError] = useState("");
  const field = (key: "min" | "max" | "datum" | "source" | "clearance" | "diameter", label: string, numeric = true) => (
    <label className="flex flex-col gap-1 text-xs text-slate-600">{label}<input aria-label={label} type={numeric ? "number" : "text"} step="any" value={draft[key]} onChange={e => setDraft({ ...draft, [key]: e.target.value })} className="min-w-0 rounded-lg border border-slate-200 px-2 py-2 text-sm" /></label>
  );
  const apply = () => {
    const min = Number(draft.min), max = Number(draft.max), clearance = draft.clearance.trim() ? Number(draft.clearance) : null;
    if (!draft.min.trim() || !draft.max.trim() || !Number.isFinite(min) || !Number.isFinite(max) || min > max || !draft.datum.trim() || !draft.source.trim() || (clearance !== null && (!Number.isFinite(clearance) || clearance < 0))) { setError("Enter a valid elevation range, common datum and evidence source. Clearance cannot be negative."); return; }
    setError("");
    onCommit(item, { vertical_extent_v1: { version: 1, minFt: min, maxFt: max, datum: draft.datum.trim(), source: draft.source.trim(), reviewed: draft.reviewed, requiredClearanceFt: clearance } });
  };
  return <div className="rounded-lg border border-slate-200 bg-slate-50 p-3" data-testid="object-engineering-properties">
    {road ? <div className="mb-4 space-y-3" data-testid="project-cul-de-sac-parameters">
      <p className="text-xs font-semibold">Cul-de-sac dimensions (ft)</p>
      <label className="block text-xs">Bulb radius: {road.bulbRadiusFt} ft<input aria-label="Project cul-de-sac bulb radius" type="range" min="35" max="80" step="1" value={road.bulbRadiusFt} disabled={item.locked} onChange={e => onCommit(item, { cul_de_sac_v1: { ...road, bulbRadiusFt: Number(e.target.value) } })} className="mt-2 w-full" /></label>
      <label className="block text-xs">Road width: {road.roadWidthFt} ft<input aria-label="Project cul-de-sac road width" type="range" min="20" max="48" step="1" value={road.roadWidthFt} disabled={item.locked} onChange={e => onCommit(item, { cul_de_sac_v1: { ...road, roadWidthFt: Number(e.target.value) } })} className="mt-2 w-full" /></label>
      <p className="text-[11px] text-slate-500">Island 15 ft · transitions 20 ft. Generic vertex/scale edits convert this template to ordinary draft geometry.</p>
    </div> : null}
    {isLinearUtility(item) ? <div className="mb-4 space-y-2">{field("diameter", "Pipe outside diameter (ft)")}<button type="button" disabled={item.locked} onClick={() => { const diameter = Number(draft.diameter); if (!Number.isFinite(diameter) || diameter <= 0 || diameter > 20) { setError("Pipe diameter must be greater than 0 and at most 20 ft."); return; } setError(""); onCommit(item, { pipe_diameter_ft: diameter }); }} className="rounded-lg border border-slate-300 px-3 py-2 text-xs">Apply pipe diameter</button></div> : null}
    <p className="text-xs font-semibold">Vertical interference envelope</p>
    <p className="mt-1 text-[11px] text-slate-500">Use full occupied extents, including pipe outside diameter and foundations. Enter elevations relative to a shared datum, not a depth below an assumed ground level. Missing data stays review-required.</p>
    <div className="mt-3 grid grid-cols-2 gap-2">{field("min", "Lowest occupied elevation (ft)")}{field("max", "Highest occupied elevation (ft)")}{field("datum", "Elevation datum", false)}{field("source", "Elevation evidence source", false)}{field("clearance", "Required project clearance (ft)")}</div>
    <label className="mt-3 flex gap-2 text-xs"><input type="checkbox" checked={draft.reviewed} onChange={e => setDraft({ ...draft, reviewed: e.target.checked })} />I reviewed the occupied extents and elevation datum.</label>
    <button type="button" disabled={item.locked} onClick={apply} className="mt-3 rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold">Apply elevation envelope</button>
    <button type="button" disabled={item.locked} onClick={() => onCommit(item, { vertical_extent_v1: null })} className="ml-2 text-xs text-slate-600">Clear envelope</button>
    {error ? <p role="alert" className="mt-2 text-xs text-red-700">{error}</p> : null}
  </div>;
}
