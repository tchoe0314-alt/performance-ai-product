import { PanelCard } from "./ui";

export type UtilityCatalogSourceView = {
  source_name?: string;
  source_reference?: string;
  jurisdiction?: string;
  company?: string;
};

export type UtilityPipeCatalogItemView = {
  item_id?: string;
  network?: string;
  material?: string;
  sizes_in?: number[];
  source?: UtilityCatalogSourceView;
  review_status?: string;
  accepted_for_workspace?: boolean;
};

export type UtilityPartCatalogItemView = {
  item_id?: string;
  network?: string;
  part_type?: string;
  name?: string;
  compatible_materials?: string[];
  compatible_sizes_in?: number[];
  source?: UtilityCatalogSourceView;
  review_status?: string;
  accepted_for_workspace?: boolean;
};

export type UtilityCatalogView = {
  pipes?: UtilityPipeCatalogItemView[];
  parts?: UtilityPartCatalogItemView[];
  summary?: {
    pipe_catalog_count?: number;
    part_catalog_count?: number;
    accepted_pipe_catalog_count?: number;
    accepted_part_catalog_count?: number;
    review_required_count?: number;
  };
};

export function UtilityCatalogPanel({
  catalog,
  status,
  networkFilter,
  onNetworkFilterChange,
}: {
  catalog: UtilityCatalogView | null;
  status: string;
  networkFilter: string;
  onNetworkFilterChange: (network: string) => void;
}) {
  const pipes = catalog?.pipes ?? [];
  const parts = catalog?.parts ?? [];
  const filteredPipes = networkFilter === "all" ? pipes : pipes.filter((item) => item.network === networkFilter);
  const filteredParts = networkFilter === "all" ? parts : parts.filter((item) => item.network === networkFilter);
  const reviewCount = Number(catalog?.summary?.review_required_count ?? 0);
  const stateLabel = reviewCount > 0 ? "Review required" : catalog ? "Loaded" : "Pending";
  const stateClass =
    reviewCount > 0 ? "bg-amber-50 text-amber-700" : catalog ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-500";

  return (
    <div className="space-y-4">
      <PanelCard>
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Utility catalog manager</p>
            <p className="mt-1 text-sm font-semibold text-slate-900">{status}</p>
          </div>
          <span className={`shrink-0 rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] ${stateClass}`}>
            {stateLabel}
          </span>
        </div>
        <div className="mt-3 grid grid-cols-2 gap-2 text-xs md:grid-cols-5">
          {[
            ["Pipe catalogs", catalog?.summary?.pipe_catalog_count ?? 0],
            ["Part catalogs", catalog?.summary?.part_catalog_count ?? 0],
            ["Accepted pipes", catalog?.summary?.accepted_pipe_catalog_count ?? 0],
            ["Accepted parts", catalog?.summary?.accepted_part_catalog_count ?? 0],
            ["Needs review", reviewCount],
          ].map(([label, value]) => (
            <div key={label} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
              <p className="font-semibold uppercase tracking-[0.14em] text-slate-400">{label}</p>
              <p className="mt-1 text-base font-semibold text-slate-900">{value}</p>
            </div>
          ))}
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          {["all", "storm", "sanitary", "water"].map((network) => (
            <button
              key={network}
              type="button"
              onClick={() => onNetworkFilterChange(network)}
              className={`rounded-lg border px-3 py-2 text-xs font-semibold uppercase tracking-[0.12em] ${
                networkFilter === network
                  ? "border-slate-950 bg-slate-950 text-white"
                  : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
              }`}
            >
              {network}
            </button>
          ))}
        </div>
        <p className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-800">
          Catalog entries require explicit source and workspace review metadata. Listed sizes do not claim standards compliance.
        </p>
      </PanelCard>
      <PanelCard>
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Pipe material / size catalogs</p>
        <div className="mt-3 overflow-x-auto rounded-xl border border-slate-200">
          <table className="w-full min-w-[720px] border-collapse text-left text-xs">
            <thead className="bg-slate-50 text-[10px] uppercase tracking-[0.12em] text-slate-500">
              <tr>
                <th className="px-3 py-2 font-semibold">Network</th>
                <th className="px-3 py-2 font-semibold">Material</th>
                <th className="px-3 py-2 font-semibold">Sizes</th>
                <th className="px-3 py-2 font-semibold">Source</th>
                <th className="px-3 py-2 font-semibold">Review status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {filteredPipes.map((item) => (
                <tr key={item.item_id} className="align-top">
                  <td className="px-3 py-3 font-semibold text-slate-800">{item.network}</td>
                  <td className="px-3 py-3 font-semibold text-slate-800">{item.material}</td>
                  <td className="px-3 py-3 text-slate-600">{(item.sizes_in ?? []).map((size) => `${size}"`).join(", ") || "No sizes"}</td>
                  <td className="px-3 py-3">
                    <p className="font-semibold text-slate-800">{item.source?.source_name || "Missing source"}</p>
                    <p className="mt-1 text-slate-500">{item.source?.jurisdiction || item.source?.company || "Jurisdiction/company missing"}</p>
                    <p className="mt-1 break-all text-[11px] text-slate-400">{item.source?.source_reference || "Reference missing"}</p>
                  </td>
                  <td className="px-3 py-3">
                    <span
                      className={`inline-flex rounded-full px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${
                        item.accepted_for_workspace ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"
                      }`}
                    >
                      {item.review_status || "needs_review"}
                    </span>
                    <p className="mt-2 text-[11px] text-slate-500">
                      {item.accepted_for_workspace
                        ? "Accepted for workspace validation."
                        : "Needs source/review acceptance before validation use."}
                    </p>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!filteredPipes.length ? (
            <p className="p-4 text-sm font-semibold text-slate-500">No pipe catalogs match this filter.</p>
          ) : null}
        </div>
      </PanelCard>
      <PanelCard>
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Structures / valves / fittings</p>
        <div className="mt-3 grid gap-2">
          {filteredParts.map((item) => (
            <div key={item.item_id} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-slate-900">{item.name}</p>
                  <p className="mt-1 text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">
                    {item.network} / {item.part_type} / {(item.compatible_materials ?? []).join(", ") || "material pending"}
                  </p>
                  <p className="mt-1 text-xs text-slate-500">
                    Sizes: {(item.compatible_sizes_in ?? []).map((size) => `${size}"`).join(", ") || "not listed"}
                  </p>
                  <p className="mt-1 text-xs text-slate-500">
                    Source: {item.source?.source_name || "missing"} / {item.source?.jurisdiction || item.source?.company || "jurisdiction/company missing"}
                  </p>
                </div>
                <span
                  className={`shrink-0 rounded-full px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${
                    item.accepted_for_workspace ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"
                  }`}
                >
                  {item.review_status || "needs_review"}
                </span>
              </div>
            </div>
          ))}
          {!filteredParts.length ? (
            <p className="text-sm font-semibold text-slate-500">No part catalogs match this filter.</p>
          ) : null}
        </div>
      </PanelCard>
    </div>
  );
}
