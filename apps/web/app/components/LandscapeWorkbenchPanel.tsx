import type { BuildingPlacement, SiteObjectType } from "../types";
import { SITE_OBJECT_CATALOG } from "../utils/siteObjectCatalog";

type LandscapeWorkbenchPanelProps = {
  buildingPlacements: BuildingPlacement[];
  hasBackendResult: boolean;
  onAddObject: (type: SiteObjectType) => void;
};

export function LandscapeWorkbenchPanel({
  buildingPlacements,
  hasBackendResult,
  onAddObject,
}: LandscapeWorkbenchPanelProps) {
  const landscapeObjects = buildingPlacements.filter((item) =>
    ["open_space", "amenity", "pool", "sidewalk"].includes(item.type ?? ""),
  );

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-2">
        {[
          ["Status", landscapeObjects.length ? "Draft" : "Not configured"],
          ["Source", hasBackendResult ? "Generated/model" : "User setup"],
          ["Review", "Engineer required"],
        ].map(([label, value]) => (
          <div key={label} className="rounded-xl border border-slate-200 bg-white px-3 py-2">
            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">{label}</p>
            <p className="mt-1 text-sm font-semibold text-slate-800">{value}</p>
          </div>
        ))}
      </div>
      <div className="grid grid-cols-2 gap-2">
        {[
          ["Open space", buildingPlacements.filter((item) => item.type === "open_space").length],
          ["Amenities", buildingPlacements.filter((item) => ["amenity", "pool"].includes(item.type ?? "")).length],
          ["Paths", buildingPlacements.filter((item) => item.type === "sidewalk").length],
          ["Placed", landscapeObjects.filter((item) => item.placed).length],
        ].map(([label, value]) => (
          <div key={label} className="rounded-xl border border-slate-200 bg-white px-3 py-2">
            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">{label}</p>
            <p className="mt-1 text-sm font-semibold text-slate-800">{value}</p>
          </div>
        ))}
      </div>
      <div className="rounded-2xl border border-slate-200 bg-white p-4">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Landscape controls</p>
        <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-slate-600">
          <span className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-2">Open space</span>
          <span className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-2">Amenities</span>
          <span className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-2">Pedestrian paths</span>
          <span className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-2">Buffers</span>
        </div>
      </div>
      <div className="rounded-2xl border border-slate-200 bg-white p-4">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Landscape objects</p>
        <div className="mt-3 grid grid-cols-2 gap-2">
          {(["open_space", "amenity", "pool", "sidewalk"] as const).map((type) => (
            <button key={type} type="button" onClick={() => onAddObject(type)} className="rounded-xl border border-slate-200 bg-white px-3 py-3 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50">
              {SITE_OBJECT_CATALOG[type].label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
