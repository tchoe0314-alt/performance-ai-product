import { useState } from "react";
import type { BuildingPlacement, SiteObjectType } from "../types";
import { SITE_OBJECT_RULEBOOK, objectRule, type CoordinationEnvelope } from "../utils/siteObjectRulebook";
import { SITE_OBJECT_CATALOG } from "../utils/siteObjectCatalog";

export function ObjectCoordinationProperties({ item, objects, onCommit }: { item: BuildingPlacement; objects: BuildingPlacement[]; onCommit: (item: BuildingPlacement, meta: Record<string, unknown>) => void }) {
  const envelope = item.meta?.coordination_envelope_v1 as Partial<CoordinationEnvelope> | undefined;
  const setback = item.meta?.setback_rule_v1 as { mode?: string; appliesTo?: string[]; source?: string; reviewed?: boolean } | undefined;
  const connection = item.meta?.intentional_connections_v1 as { objectIds?: string[]; source?: string; reviewed?: boolean } | undefined;
  const [buffer, setBuffer] = useState(String(envelope?.bufferFt ?? ""));
  const [purpose, setPurpose] = useState<CoordinationEnvelope["purpose"]>(envelope?.purpose ?? "maintenance");
  const [source, setSource] = useState(envelope?.source ?? ""), [reviewed, setReviewed] = useState(envelope?.reviewed ?? false);
  const [mode, setMode] = useState(setback?.mode ?? ""), [types, setTypes] = useState(setback?.appliesTo ?? Object.keys(SITE_OBJECT_RULEBOOK).filter(t => SITE_OBJECT_RULEBOOK[t as SiteObjectType].category === "structure"));
  const [zoneSource, setZoneSource] = useState(setback?.source ?? ""), [zoneReviewed, setZoneReviewed] = useState(setback?.reviewed ?? false);
  const [target, setTarget] = useState(connection?.objectIds?.[0] ?? ""), [connectionSource, setConnectionSource] = useState(connection?.source ?? ""), [connectionReviewed, setConnectionReviewed] = useState(connection?.reviewed ?? false);
  const [error, setError] = useState("");
  const commit = (meta: Record<string, unknown>) => { setError(""); onCommit(item, meta); };
  const textInput = "mt-1 w-full rounded border border-slate-200 bg-white p-2";
  const button = "mt-2 rounded border border-slate-300 bg-white px-3 py-2 text-xs";
  const eligibleConnections = ["surface", "utility", "fixture"].includes(objectRule(item).category);
  return <details className="rounded-lg border border-slate-200 bg-slate-50 p-3" data-testid="object-coordination-properties">
    <summary className="cursor-pointer text-xs font-semibold">Object compatibility requirements</summary>
    <p className="mt-2 text-xs text-slate-600">{objectRule(item).guidance}</p>
    <p className="mt-1 text-[11px] text-slate-500">Entered project requirements only; no regulatory distances are assumed. Buffers remain review constraints even with vertical separation.</p>
    <fieldset disabled={item.locked} className="mt-3 space-y-2 text-xs">
      <legend>Horizontal protection / access buffer</legend>
      <label className="block">Additional protection distance (ft)<input aria-label="Additional protection distance (ft)" type="number" min="0" step="any" className={textInput} value={buffer} onChange={e => setBuffer(e.target.value)} /></label>
      <label className="block">Buffer purpose<select aria-label="Buffer purpose" className={textInput} value={purpose} onChange={e => setPurpose(e.target.value as CoordinationEnvelope["purpose"])}><option value="maintenance">Maintenance / access</option><option value="roots">Root protection</option><option value="foundation">Foundation projection</option><option value="separation">Utility / object separation</option></select></label>
      <label className="block">Buffer evidence source<input className={textInput} value={source} onChange={e => setSource(e.target.value)} /></label>
      <label className="flex gap-2"><input type="checkbox" checked={reviewed} onChange={e => setReviewed(e.target.checked)} />I reviewed this horizontal buffer.</label>
      <button type="button" className={button} onClick={() => { const value = Number(buffer); if (!buffer.trim() || !Number.isFinite(value) || value < 0 || !source.trim()) { setError("Enter a nonnegative buffer and evidence source."); return; } commit({ coordination_envelope_v1: { version: 1, bufferFt: value, purpose, source: source.trim(), reviewed } }); }}>Apply horizontal buffer</button>
      <button type="button" className="ml-2" onClick={() => commit({ coordination_envelope_v1: null })}>Clear buffer</button>
      {item.type === "setback_zone" ? <div className="space-y-2 border-t pt-3">
        <label className="block">Setback area meaning<select aria-label="Setback area meaning" className={textInput} value={mode} onChange={e => setMode(e.target.value)}><option value="">Not specified</option><option value="excluded_area">Objects must stay outside this area</option><option value="buildable_area">Objects must stay inside this area</option></select></label>
        <fieldset className="grid grid-cols-2 gap-2"><legend>Setback applies to</legend>{Object.keys(SITE_OBJECT_CATALOG).filter(t => !["container", "restriction"].includes(SITE_OBJECT_RULEBOOK[t as SiteObjectType].category)).map(t => <label key={t} className="flex gap-1"><input type="checkbox" checked={types.includes(t)} onChange={e => setTypes(e.target.checked ? [...types, t] : types.filter(value => value !== t))} />{SITE_OBJECT_CATALOG[t as SiteObjectType].label}</label>)}</fieldset>
        <label className="block">Setback evidence source<input className={textInput} value={zoneSource} onChange={e => setZoneSource(e.target.value)} /></label>
        <label className="flex gap-2"><input type="checkbox" checked={zoneReviewed} onChange={e => setZoneReviewed(e.target.checked)} />I reviewed this setback rule.</label>
        <button type="button" className={button} onClick={() => { if (!["excluded_area", "buildable_area"].includes(mode) || !types.length || !zoneSource.trim()) { setError("Specify setback meaning, applicable types and evidence source."); return; } commit({ setback_rule_v1: { version: 1, mode, appliesTo: types, source: zoneSource.trim(), reviewed: zoneReviewed } }); }}>Apply setback rule</button>
        <button type="button" className="ml-2" onClick={() => commit({ setback_rule_v1: null })}>Clear setback rule</button>
      </div> : null}
      {eligibleConnections ? <div className="space-y-2 border-t pt-3">
        <label className="block">Intentional connection to<select aria-label="Intentional connection to" className={textInput} value={target} onChange={e => setTarget(e.target.value)}><option value="">Choose an object</option>{objects.filter(o => o.id !== item.id && o.placed && (objectRule(item).category === "surface" ? objectRule(o).category === "surface" : ["utility", "fixture"].includes(objectRule(o).category))).map(o => <option key={o.id} value={o.id}>{o.label}</option>)}</select></label>
        <label className="block">Connection evidence source<input className={textInput} value={connectionSource} onChange={e => setConnectionSource(e.target.value)} /></label>
        <label className="flex gap-2"><input type="checkbox" checked={connectionReviewed} onChange={e => setConnectionReviewed(e.target.checked)} />I reviewed this intentional connection.</label>
        <button type="button" className={button} onClick={() => { if (!target || !connectionSource.trim()) { setError("Choose a connection object and evidence source."); return; } commit({ intentional_connections_v1: { version: 1, objectIds: [...new Set([...(connection?.objectIds ?? []), target])], source: connectionSource.trim(), reviewed: connectionReviewed } }); }}>Apply intentional connection</button>
        <button type="button" className="ml-2" onClick={() => commit({ intentional_connections_v1: null })}>Clear connections</button>
        <p className="text-[11px] text-slate-500">Connections do not waive island, protection buffer or maintenance checks. Network fittings still require review.</p>
      </div> : null}
    </fieldset>
    {error ? <p role="alert" className="mt-2 text-xs text-red-700">{error}</p> : null}
  </details>;
}
