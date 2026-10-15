import type { ProjectInput } from "../types";
import { useState } from "react";
import { buildActiveBriefSummary, type BriefSummaryRow } from "../utils/activeBriefSummary";
import { classificationFor, validateBriefClassifications, type RequirementClass } from "../utils/briefClassification";
import { BriefValueEditor, type EditBriefHandler } from "./BriefValueEditor";
import { briefMissingInformation } from "../utils/briefMissingInformation";
import { validateBriefSources } from "../utils/briefSources";

export function ActiveBriefSummary({ input, savedInput, docked = false, onClassify, onEdit }: { input: ProjectInput; savedInput?: ProjectInput; docked?: boolean; onClassify?: (row: BriefSummaryRow, priority: RequirementClass, confirm?: boolean, override?: boolean) => void; onEdit?: EditBriefHandler }) {
  const [overrides, setOverrides] = useState<Record<string, string>>({});
  const rows = buildActiveBriefSummary(input, savedInput);
  const stored = input.meta?.site_inputs?.active_brief_classifications_v1;
  let sources: ReturnType<typeof validateBriefSources>["records"] = [];
  try { if (stored !== undefined) validateBriefClassifications(stored); }
  catch { return <p role="alert" className="p-3 text-sm text-red-800">Brief classifications need repair. No classification changes were applied.</p>; }
  try { if (input.meta?.site_inputs?.brief_sources_v1 !== undefined) sources = validateBriefSources(input.meta.site_inputs.brief_sources_v1).records; }
  catch { return <p role="alert" className="p-3 text-sm text-red-800">Source records need repair. No source was accepted.</p>; }
  const preview = ["gross-acreage", "building-area", "required-parking", "setbacks"];
  const missing = rows.filter(row => !row.known).length;
  const list = (items: typeof rows, compact = false) => <dl className={compact ? "grid grid-cols-2 gap-x-3 gap-y-2" : "space-y-2"}>
    {items.map(row => {
      const classification = classificationFor(row, stored);
      const missingInfo = briefMissingInformation(row.id);
      const protectedPriority = ["sourced", "externally_verified"].includes(classification.trust) && classification.priority !== "unknown";
      const priorityProtectionKey = JSON.stringify([row.valueKey, classification.priority, classification.trust, classification.source_reference]);
      const priorityOverride = overrides[row.id] === priorityProtectionKey;
      if (compact) return <div key={row.id} data-testid={`brief-value-${row.id}`} className="min-w-0 rounded-md bg-slate-50 px-2 py-1.5 text-xs">
        <dt className="truncate text-[10px] text-slate-500">{row.label}</dt>
        <dd className="truncate font-semibold text-slate-800" title={row.value}>{row.value}</dd>
      </div>;
      return <div key={row.id} data-testid={`brief-value-${row.id}`} className="min-w-0 text-xs">
      <dt className="text-slate-600">{row.label}</dt>
      <dd className="min-w-0 break-words font-medium text-slate-800">
        {row.value}
        {onEdit && <BriefValueEditor key={row.valueKey} input={input} row={row} onEdit={onEdit} />}
        {row.known && <p className="mt-0.5 break-words text-[11px] font-normal text-slate-600">{row.basis.replace(/; unverified$/, "")}</p>}
        <p className="mt-1 text-[11px] font-normal text-slate-600" data-testid="brief-trust">{classification.trust.replaceAll("_", " ")}{["sourced", "externally_verified"].includes(classification.trust) ? " (recorded)" : ""}{classification.source_reference ? ` · ${sources.find(source => source.id === classification.source_reference)?.name ?? classification.source_reference}` : ""}</p>
        {row.known ? <details className="mt-1 font-normal">
          <summary className="cursor-pointer text-slate-700">Requirement · {classification.priority}{classification.needsReview ? " · review change" : ""}</summary>
          {onClassify ? <div className="mt-2 space-y-2">
            {protectedPriority && <button type="button" disabled={priorityOverride} className="rounded border px-2 py-1 disabled:opacity-50" onClick={() => setOverrides(previous => ({ ...previous, [row.id]: priorityProtectionKey }))}>Override requirement</button>}
            <label className="block">Priority
              <select aria-label={`${row.label} requirement`} disabled={protectedPriority && !priorityOverride} className="mt-1 block w-full rounded border border-slate-300 bg-white p-1 text-slate-800 disabled:opacity-60" value={classification.priority} onChange={event => onClassify(row, event.target.value as RequirementClass, false, priorityOverride)}>
                <option value="unknown">Choose…</option><option value="required">Required</option><option value="preferred">Preferred</option><option value="assumed">Assumed</option>
              </select>
            </label>
            <button type="button" disabled={classification.priority === "unknown" || classification.trust === "user_confirmed"} className="rounded border border-slate-300 px-2 py-1 text-slate-700 disabled:opacity-60" onClick={() => onClassify(row, classification.priority, true)}>Confirm this value</button>
          </div> : <p className="mt-1 text-slate-600">Save an editable project to classify.</p>}
        </details> : <details className="mt-1 text-[11px] font-normal text-slate-600" data-testid={`brief-missing-${row.id}`}><summary className="cursor-pointer">Why needed</summary><div className="mt-1 space-y-1"><p>{missingInfo.why}</p><p>Blocked: {missingInfo.blocks}</p><p>{missingInfo.provisional}</p><p>{missingInfo.assumption}</p><p>Verify: {missingInfo.verification}</p></div></details>}
      </dd>
    </div>; })}
  </dl>;
  return <section aria-label="Active Brief Summary" data-testid={docked ? "active-brief-summary-docked" : "active-brief-summary"} className="min-w-0 rounded-lg border border-slate-200 bg-white p-3">
    <div className="mb-2 flex items-center justify-between gap-2"><h2 className="text-sm font-semibold text-slate-900">Brief</h2>{docked&&<span className="text-[10px] text-slate-500">{missing ? `${missing} missing` : "Complete"}</span>}</div>
    {list(rows.filter(row => preview.includes(row.id)), docked)}
    <details className="mt-3">
      <summary className="cursor-pointer text-xs font-medium text-slate-700">All requirements · {missing} not set</summary>
      <div className="mt-3">{list(rows.filter(row => !preview.includes(row.id)))}</div>
    </details>
  </section>;
}
