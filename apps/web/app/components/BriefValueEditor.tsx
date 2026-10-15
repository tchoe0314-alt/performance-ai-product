import { useState } from "react";
import type { ProjectInput } from "../types";
import type { BriefSummaryRow } from "../utils/activeBriefSummary";
import { briefRawValue, briefProtectionKey, briefInputUnits, EDITABLE_BRIEF_FIELDS, type EditableBriefField, type BriefEditOptions } from "../utils/briefEditing";
import { classificationFor } from "../utils/briefClassification";
import { validateBriefSources } from "../utils/briefSources";

export type EditBriefHandler = (row: BriefSummaryRow, text: string, options: BriefEditOptions) => boolean;
export function BriefValueEditor({ input, row, onEdit }: { input: ProjectInput; row: BriefSummaryRow; onEdit: EditBriefHandler }) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [override, setOverride] = useState(false);
  const [sourceId, setSourceId] = useState("");
  const [valueUnit, setValueUnit] = useState<BriefEditOptions["unit"]>();
  const [protectionKey, setProtectionKey] = useState("");
  const [openedValue, setOpenedValue] = useState<{ text: string; unit: BriefEditOptions["unit"] }>({ text: "", unit: "text" });
  const [valueEdited, setValueEdited] = useState(false);
  if (!(EDITABLE_BRIEF_FIELDS as readonly string[]).includes(row.id)) return null;
  const id = row.id as EditableBriefField;
  const sourced = ["sourced", "externally_verified"].includes(classificationFor(row, input.meta?.site_inputs?.active_brief_classifications_v1).trust);
  const originals = input.meta?.site_inputs?.brief_edit_originals_v1 as { fields?: Record<string, unknown> } | undefined;
  const inputUnits = briefInputUnits(input, id), unit = inputUnits[0];
  const sources = input.meta?.site_inputs?.brief_sources_v1 === undefined ? [] : validateBriefSources(input.meta.site_inputs.brief_sources_v1).records.filter(source => source.accepted && !source.superseded);
  const changeInputUnit = (nextUnit: BriefEditOptions["unit"]) => {
    const numeric = Number(text);
    if (text.trim() && Number.isFinite(numeric) && nextUnit !== valueUnit) {
      const factors: Record<string, number> = ["building-area", "usable-acreage"].includes(id) ? { sf: 1, m2: 1 / 0.3048 ** 2, ac: 43560 } : { ft: 1, m: 1 / 0.3048 };
      const converted = numeric * (factors[valueUnit ?? ""] ?? 1) / (factors[nextUnit ?? ""] ?? 1);
      // Hide floating-point display noise; unit-only changes still submit the
      // exact opened value rather than this presentation string.
      if (Number.isFinite(converted)) setText(String(Number(converted.toPrecision(14))));
    }
    setValueUnit(nextUnit);
  };
  return <div className="mt-2 font-normal">
    {!open ? <button type="button" className="rounded border px-2 py-1" aria-label={`Edit ${row.label}`} onClick={() => { const initialText = String(briefRawValue(input, id) ?? ""); const initialUnit = unit as BriefEditOptions["unit"] || "text"; setText(initialText); setOpenedValue({ text: initialText, unit: initialUnit }); setValueEdited(false); setOverride(false); setSourceId(""); setProtectionKey(briefProtectionKey(input, id)); setValueUnit(initialUnit); setOpen(true); }}>Edit</button> : <form className="space-y-2" onSubmit={event => { event.preventDefault(); if (onEdit(row, valueEdited ? text : openedValue.text, { override, unit: valueEdited ? valueUnit : openedValue.unit, expectedProtectionKey: protectionKey, ...(sourceId ? { sourceId } : {}) })) setOpen(false); }}>
      {sourced && <div><p>Source value protected. Changes become unverified.</p><button type="button" disabled={override} className="rounded border px-2 py-1 disabled:opacity-50" onClick={() => setOverride(true)}>Override</button></div>}
      <label className="block">{row.label}{valueUnit && valueUnit !== "text" ? ` (${valueUnit === "m2" ? "m²" : valueUnit})` : ""}<input aria-label={`${row.label} value`} disabled={sourced && !override} value={text} onChange={event => { setText(event.target.value); setValueEdited(true); }} className="mt-1 block w-full min-w-0 rounded border p-1 text-slate-900" /></label>
      {inputUnits.length > 1 && <label className="block">Input units<select aria-label={`${row.label} units`} disabled={sourced && !override} className="mt-1 block w-full rounded border p-1" value={valueUnit} onChange={event => changeInputUnit(event.target.value as BriefEditOptions["unit"])}>{inputUnits.map(item => <option key={item} value={item}>{item === "m2" ? "m²" : item}</option>)}</select></label>}
      {sources.length > 0 && <label className="block">Source<select aria-label={`${row.label} source`} className="mt-1 block w-full rounded border p-1" value={sourceId} onChange={event => setSourceId(event.target.value)}><option value="">No new source</option>{sources.map(source => <option key={source.id} value={source.id}>{source.name}</option>)}</select></label>}
      <p className="text-[11px] text-slate-600">Drawing units stay unchanged. Blank means unknown; affected results need recalculation.</p>
      <div className="flex flex-wrap gap-2"><button type="submit" disabled={sourced && !override} className="rounded border px-2 py-1 disabled:opacity-50">Apply</button><button type="button" onClick={() => setOpen(false)} className="rounded border px-2 py-1">Cancel</button>{Boolean(originals?.fields?.[id]) && <button type="button" className="rounded border px-2 py-1" onClick={() => { if (onEdit(row, "", { reset: true })) setOpen(false); }}>Reset original</button>}</div>
    </form>}
  </div>;
}
