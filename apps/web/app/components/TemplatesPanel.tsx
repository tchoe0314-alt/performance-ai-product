import { PanelCard } from "./ui";

export type TemplateSummary = {
  template_id?: string;
  name?: string;
  firm_name?: string;
  review_status?: string;
  present_sections?: string[];
  missing_sections?: string[];
  layer_count?: number;
  label_style_count?: number;
  symbol_count?: number;
  report_template_count?: number;
  cost_book_link_count?: number;
  pipe_hook_ready?: boolean;
  roadway_hook_ready?: boolean;
};

export type TemplateRegistryView = {
  active_template_id?: string;
  summaries?: TemplateSummary[];
  behavior?: {
    active_template?: TemplateSummary | null;
    blockers?: string[];
  };
  policy?: {
    truth_label?: string;
  };
};

export function TemplatesPanel({
  registry,
  status,
  summaries,
  activeTemplate,
  blockerCount,
  onUseCompanyTemplate,
  onExportJson,
  onActivateTemplate,
  toReadableLabel,
}: {
  registry: TemplateRegistryView | null;
  status: string;
  summaries: TemplateSummary[];
  activeTemplate: TemplateSummary | null;
  blockerCount: number;
  onUseCompanyTemplate: () => void;
  onExportJson: () => void;
  onActivateTemplate: (template: TemplateSummary) => void;
  toReadableLabel: (value: string) => string;
}) {
  const registryStateLabel = blockerCount > 0 ? "Review" : registry ? "Loaded" : "Pending";
  const registryStateClass =
    blockerCount > 0 ? "bg-amber-50 text-amber-700" : registry ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-500";

  return (
    <div className="space-y-4">
      <PanelCard>
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Firm template registry</p>
            <p className="mt-1 text-sm font-semibold text-slate-900">{status}</p>
          </div>
          <span className={`shrink-0 rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] ${registryStateClass}`}>
            {registryStateLabel}
          </span>
        </div>
        <div className="mt-3 grid grid-cols-2 gap-2 text-xs md:grid-cols-4">
          {[
            ["Templates", summaries.length],
            ["Layer sets", activeTemplate?.layer_count ?? 0],
            ["Label styles", activeTemplate?.label_style_count ?? 0],
            ["Symbols", activeTemplate?.symbol_count ?? 0],
            ["Reports", activeTemplate?.report_template_count ?? 0],
            ["Cost links", activeTemplate?.cost_book_link_count ?? 0],
            ["Pipe hooks", activeTemplate?.pipe_hook_ready ? "Ready" : "Missing"],
            ["Road hooks", activeTemplate?.roadway_hook_ready ? "Ready" : "Missing"],
          ].map(([label, value]) => (
            <div key={label} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
              <p className="font-semibold uppercase tracking-[0.14em] text-slate-400">{label}</p>
              <p className="mt-1 text-base font-semibold text-slate-900">{value}</p>
            </div>
          ))}
        </div>
        <p className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-800">
          {registry?.policy?.truth_label || "Templates are user/company standards only and do not create legal compliance evidence."}
        </p>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <button
            type="button"
            onClick={onUseCompanyTemplate}
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50"
          >
            Use Company Template
          </button>
          <button
            type="button"
            onClick={onExportJson}
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50"
          >
            Export JSON
          </button>
        </div>
      </PanelCard>
      <PanelCard>
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Registered templates</p>
        <div className="mt-3 space-y-2">
          {summaries.map((item) => (
            <div key={item.template_id || item.name} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-slate-900">{item.name || "Company template"}</p>
                  <p className="mt-1 text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">
                    {item.firm_name || "Firm"} / {item.review_status || "needs_review"}
                  </p>
                  <p className="mt-2 text-xs text-slate-500">
                    Present: {(item.present_sections ?? []).map((value) => toReadableLabel(value)).join(", ") || "No sections"}
                  </p>
                  <p className="mt-1 text-xs text-slate-500">
                    Missing: {(item.missing_sections ?? []).map((value) => toReadableLabel(value)).join(", ") || "None"}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => onActivateTemplate(item)}
                  className={`shrink-0 rounded-lg border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${
                    item.template_id === registry?.active_template_id
                      ? "border-slate-950 bg-slate-950 text-white"
                      : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
                  }`}
                >
                  {item.template_id === registry?.active_template_id ? "Active" : "Use"}
                </button>
              </div>
            </div>
          ))}
          {!summaries.length ? (
            <p className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3 text-sm font-semibold text-slate-500">
              No firm templates are registered yet.
            </p>
          ) : null}
        </div>
      </PanelCard>
    </div>
  );
}
