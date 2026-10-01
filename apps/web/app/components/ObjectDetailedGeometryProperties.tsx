import { useState } from "react";
import type { BuildingPlacement } from "../types";
import { detailedGeometryBinding, validateComponentModel, validatePipeProfile, type ComponentModel, type PipeProfile, type OccupiedComponent } from "../utils/detailedObjectGeometry";
import { isLinearUtility } from "../utils/siteInterference";

type PartDraft = { id: string; label: string; kind: OccupiedComponent["kind"]; xFt: string; yFt: string; wFt: string; dFt: string; minFt: string; maxFt: string };
export function ObjectDetailedGeometryProperties({ item, onCommit }: { item: BuildingPlacement; onCommit: (item: BuildingPlacement, meta: Record<string, unknown>) => void }) {
  const isPipe = isLinearUtility(item) && item.geometryType === "polyline";
  const saved = (isPipe ? item.meta?.pipe_profile_v1 : item.meta?.occupied_components_v1) as PipeProfile & ComponentModel | undefined;
  const [datum, setDatum] = useState(saved?.datum ?? ""), [source, setSource] = useState(saved?.source ?? ""), [clearance, setClearance] = useState(saved?.requiredClearanceFt == null ? "" : String(saved.requiredClearanceFt));
  const [reviewed, setReviewed] = useState(Boolean(saved?.reviewed && saved.geometryBinding === detailedGeometryBinding(item))), [complete, setComplete] = useState(saved?.complete ?? false), [error, setError] = useState("");
  const [elevations, setElevations] = useState((item.geometry ?? []).map((_, i) => saved?.centerElevationsFt?.[i] == null ? "" : String(saved.centerElevationsFt[i])));
  const [parts, setParts] = useState<PartDraft[]>((saved?.components ?? []).map(c => ({ ...c, xFt: String(c.xFt), yFt: String(c.yFt), wFt: String(c.wFt), dFt: String(c.dFt), minFt: String(c.minFt), maxFt: String(c.maxFt) })));
  const apply = () => {
    const evidence = { version: 1 as const, datum: datum.trim(), source: source.trim(), reviewed, requiredClearanceFt: clearance.trim() ? Number(clearance) : null, geometryBinding: detailedGeometryBinding(item) };
    if (isPipe) {
      if (elevations.some(z => !z.trim())) { setError("Enter the center elevation at every route vertex."); return; }
      const value: PipeProfile = { ...evidence, centerElevationsFt: elevations.map(Number) }, invalid = validatePipeProfile(value, { ...item, meta: { ...item.meta, occupied_components_v1: null } });
      if (invalid) { setError(invalid); return; } setError(""); onCommit(item, { pipe_profile_v1: value, occupied_components_v1: null });
    } else {
      if (parts.some(c => [c.xFt, c.yFt, c.wFt, c.dFt, c.minFt, c.maxFt].some(v => !v.trim()))) { setError("Enter every part's footprint and elevation limits."); return; }
      const value: ComponentModel = { ...evidence, complete, components: parts.map(c => ({ ...c, xFt: Number(c.xFt), yFt: Number(c.yFt), wFt: Number(c.wFt), dFt: Number(c.dFt), minFt: Number(c.minFt), maxFt: Number(c.maxFt) })) }, invalid = validateComponentModel(value, { ...item, meta: { ...item.meta, pipe_profile_v1: null } });
      if (invalid) { setError(invalid); return; } setError(""); onCommit(item, { occupied_components_v1: value, pipe_profile_v1: null });
    }
  };
  const input = "mt-1 w-full min-w-0 rounded border border-slate-200 bg-white p-2";
  return <details data-testid="object-detailed-geometry" className="rounded-lg border border-slate-200 bg-slate-50 p-3">
    <summary className="cursor-pointer text-xs font-semibold">{isPipe ? "Pipe depth along route" : "Occupied parts and foundations"}</summary>
    <p className="mt-2 text-[11px] text-amber-800">Detailed geometry drives coordination checks only; the main 3D preview does not yet render these parts or pipe elevations.</p>
    <p className="mt-2 text-[11px] text-slate-600">{isPipe ? "Enter center elevations, not inverts or burial depths. Elevation varies linearly between route vertices; outside diameter must be known." : "Parts are occupied rectangular prisms. Local footprint offsets are in feet from the object's unrotated upper-left corner. Include the body and all foundations; bridges need deck, supports and foundations."} This is model evidence, not professional approval. Movement, resizing, route edits or diameter changes require fresh review.</p>
    <fieldset disabled={item.locked} className="mt-3 space-y-2 text-xs">
      <label className="block">Detailed elevation datum<input className={input} value={datum} onChange={e => setDatum(e.target.value)} /></label>
      <label className="block">Detailed geometry evidence source<input className={input} value={source} onChange={e => setSource(e.target.value)} /></label>
      <label className="block">Detailed required clearance (ft)<input type="number" min="0" step="any" className={input} value={clearance} onChange={e => setClearance(e.target.value)} /></label>
      {isPipe ? elevations.map((z, i) => <label key={i} className="block">Pipe center elevation at vertex {i + 1} (ft)<input type="number" step="any" className={input} value={z} onChange={e => setElevations(values => values.map((value, j) => j === i ? e.target.value : value))} /></label>) : <>
        {parts.map((part, i) => <div key={part.id} className="space-y-2 rounded border border-slate-200 p-2">
          <label className="block">Part {i + 1} label<input className={input} value={part.label} onChange={e => setParts(values => values.map((p, j) => j === i ? { ...p, label: e.target.value } : p))} /></label>
          <label className="block">Part {i + 1} kind<select aria-label={`Part ${i + 1} kind`} className={input} value={part.kind} onChange={e => setParts(values => values.map((p, j) => j === i ? { ...p, kind: e.target.value as PartDraft["kind"] } : p))}><option value="body">Occupied body</option><option value="foundation">Foundation</option><option value="deck">Bridge deck</option><option value="support">Support / pier</option></select></label>
          <div className="grid grid-cols-2 gap-2">{(["xFt", "yFt", "wFt", "dFt", "minFt", "maxFt"] as const).map(key => {
            const labels = { xFt: "X offset", yFt: "Y offset", wFt: "Width", dFt: "Depth", minFt: "Lowest elevation", maxFt: "Highest elevation" };
            return <label key={key}>Part {i + 1} {labels[key]} (ft)<input type="number" step="any" className={input} value={part[key]} onChange={e => setParts(values => values.map((p, j) => j === i ? { ...p, [key]: e.target.value } : p))} /></label>;
          })}</div>
          <button type="button" onClick={() => setParts(values => values.filter((_, j) => j !== i))}>Remove part {i + 1}</button>
        </div>)}
        <button type="button" disabled={parts.length >= 64} className="rounded border px-3 py-2" onClick={() => { const unit = item.meta?.coordinate_units === "m" ? .3048 : 1; setParts(values => [...values, { id: `part-${Date.now()}-${values.length}`, kind: "body", label: `Part ${values.length + 1}`, xFt: "0", yFt: "0", wFt: String(item.w / unit), dFt: String(item.d / unit), minFt: "", maxFt: "" }]); }}>Add occupied part</button>
        <label className="flex gap-2"><input type="checkbox" checked={complete} onChange={e => setComplete(e.target.checked)} />This includes all occupied parts, foundations and supports.</label>
      </>}
      <label className="flex gap-2"><input type="checkbox" checked={reviewed} onChange={e => setReviewed(e.target.checked)} />I reviewed this detailed geometry against its source.</label>
      <button type="button" onClick={apply} className="rounded border border-slate-300 bg-white px-3 py-2">{isPipe ? "Apply pipe depth profile" : "Apply occupied parts"}</button>
      <button type="button" onClick={() => onCommit(item, { [isPipe ? "pipe_profile_v1" : "occupied_components_v1"]: null })} className="ml-2">Clear detailed model</button>
    </fieldset>
    {error ? <p role="alert" className="mt-2 text-xs text-red-700">{error}</p> : null}
  </details>;
}
