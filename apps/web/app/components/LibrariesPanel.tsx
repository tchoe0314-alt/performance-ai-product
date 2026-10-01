import { PanelCard } from "./ui";
import type { AddObjectOptions } from "../utils/dashboardObjectPlacementBuilder";
import { defaultCulDeSacParameters } from "../utils/parametricRoad";
import { useRef, useState } from "react";
import { parseLayout } from "../utils/culDeSacConcept";

export type LibraryPanelItem = {
  type: string;
  label: string;
};

export type LibraryPanelSection = {
  key: string;
  title: string;
  items: LibraryPanelItem[];
};

export function LibrariesPanel({
  sections,
  onAddObject,
  units = "ft",
}: {
  sections: LibraryPanelSection[];
  onAddObject: (type: string, options?: AddObjectOptions) => void;
  units?: string;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [notice, setNotice] = useState("");
  return (
    <div className="space-y-4">
      <PanelCard>
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Concept studies</p>
        <button type="button" onClick={() => onAddObject("road", { label: "Cul-de-sac", placed: true, meta: { cul_de_sac_v1: defaultCulDeSacParameters() } })} className="mt-3 w-full rounded-xl border border-blue-200 bg-blue-50 px-3 py-3 text-sm font-semibold text-blue-800" data-testid="add-project-cul-de-sac">Add cul-de-sac to project</button>
        <button type="button" onClick={() => onAddObject("utility_corridor", { label: "Pipe", placed: true, geometryType: "polyline", meta: { asset_kind: "pipe", network: "water", pipe_diameter_ft: 1, draft_review_required: true } })} className="mt-2 w-full rounded-xl border border-slate-200 px-3 py-3 text-sm font-semibold text-slate-700" data-testid="add-project-pipe">Add pipe (draft diameter 1 ft)</button>
        <button type="button" onClick={() => input.current?.click()} className="mt-2 w-full rounded-xl border border-slate-200 px-3 py-3 text-sm font-semibold text-slate-700">Import study JSON into project</button>
        <input ref={input} type="file" accept=".json,application/json" className="hidden" aria-label="Import cul-de-sac study into project" onChange={async e => {
          const element = e.currentTarget, file = element.files?.[0]; if (!file) return;
          try {
            if (file.size > 8192) throw new Error("Oversized file");
            const layout = parseLayout(JSON.parse(await file.text())), scale = units === "m" ? .3048 : 1;
            const shift = layout.bulbRadius + 24;
            onAddObject("road", { label: "Imported cul-de-sac", placed: true, x: (24 + layout.position.x) * scale, y: (24 + layout.position.y) * scale,
              meta: { cul_de_sac_v1: { ...defaultCulDeSacParameters(units), bulbRadiusFt: layout.bulbRadius, roadWidthFt: layout.roadWidth } } });
            onAddObject("building", { label: "Imported study building", placed: true, x: (layout.building.x + shift) * scale, y: (layout.building.y + shift) * scale, width: layout.building.w * scale, depth: layout.building.d * scale });
            setNotice("Imported road and building as draft project objects, with relative positions preserved. Review the site boundary and save the project.");
          } catch { setNotice("Import rejected: unsupported schema or dimensions. No objects were added."); }
          finally { element.value = ""; }
        }} />
        {notice ? <p role="status" className="mt-2 text-xs text-slate-600">{notice}</p> : null}
        <a href="/concepts/cul-de-sac.html" target="_blank" rel="noopener noreferrer" className="mt-3 block rounded-xl border border-slate-200 bg-white px-3 py-3 text-sm font-semibold text-blue-700 hover:bg-slate-50">
          Cul-de-sac · adjustable 2D plan
        </a>
        <p className="mt-2 text-xs text-slate-500">Explore bulb and road dimensions in a separate concept study.</p>
      </PanelCard>
      {sections.map((group) => (
        <PanelCard key={group.key}>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">{group.title}</p>
          <div className="mt-3 grid grid-cols-2 gap-2">
            {group.items.map((item) => (
              <button
                key={item.type}
                type="button"
                onClick={() => onAddObject(item.type)}
                className="rounded-xl border border-slate-200 bg-white px-3 py-3 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50"
              >
                {item.label}
              </button>
            ))}
          </div>
        </PanelCard>
      ))}
    </div>
  );
}
