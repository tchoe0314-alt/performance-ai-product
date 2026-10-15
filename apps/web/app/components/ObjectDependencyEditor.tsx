import type { BuildingPlacement } from "../types";
import { WorkspaceStateBadge } from "./WorkspaceStateBadge";
import { dependencyLinks, DEPENDENCY_LABELS, geometryKey, linkKind, setDependencyLink, type DependencyPolicy } from "../utils/dependencyGraph";

const policies=["ask","follow","fixed","independent"] as const;
export function ObjectDependencyEditor({object,objects,onUpdate}:{object:BuildingPlacement;objects:BuildingPlacement[];onUpdate:(object:BuildingPlacement,updates:Partial<BuildingPlacement>)=>void}) {
  const links=dependencyLinks(object,objects);
  // Keep the established parking control; this compact editor supplies other relationships.
  const candidates=objects.filter(target=>target.id!==object.id&&linkKind(object,target)&&linkKind(object,target)!=="building_parking");
  const quantity=object.meta?.geometry_quantity_v1 as {geometry_key?:string;status?:string;area?:number|null;length?:number|null}|undefined;
  return <details data-testid="object-dependency-editor" className="rounded-xl border border-slate-200 p-3">
    <summary className="cursor-pointer text-xs font-semibold text-slate-700">Relationships{links.length?` · ${links.length}`:""}</summary>
    <p className="mt-2 text-[11px] text-slate-500">Ask previews · Follow moves · Fixed protects</p>
    <div className="mt-2 space-y-2">{candidates.map(target=>{
      const edge=links.find(link=>link.target_id===target.id);
      return <label key={target.id} className="flex flex-wrap items-center gap-2 text-xs">
        <span className="min-w-0 flex-1 truncate" title={target.label}>{DEPENDENCY_LABELS[linkKind(object,target)!]} · {target.label}</span>
        <select aria-label={`Relationship to ${target.label}`} data-testid={`dependency-policy-${target.id}`} value={edge?.policy??"unlinked"} onChange={e=>onUpdate(object,setDependencyLink(object,target,e.target.value==="unlinked"?null:e.target.value as DependencyPolicy))} className="max-w-28 rounded border border-slate-200 bg-white p-1">
          <option value="unlinked">Not linked</option>{policies.map(policy=><option key={policy} value={policy}>{policy[0].toUpperCase()+policy.slice(1)}</option>)}
        </select>
        {edge ? <WorkspaceStateBadge state={edge.policy === "follow" ? "following" : edge.policy} /> : null}
      </label>;
    })}</div>
    <label className="mt-3 flex items-center gap-2 border-t border-slate-100 pt-2 text-xs">
      <span className="flex-1">Geometry quantity</span>
      <select aria-label="Geometry quantity behavior" data-testid="quantity-dependency-policy" value={String(object.meta?.quantity_relationship_v1??"unlinked")} onChange={e=>onUpdate(object,{meta:{...object.meta,quantity_relationship_v1:e.target.value==="unlinked"?undefined:e.target.value}})} className="rounded border border-slate-200 bg-white p-1">
        <option value="unlinked">Not linked</option>{policies.map(policy=><option key={policy} value={policy}>{policy[0].toUpperCase()+policy.slice(1)}</option>)}
      </select>
    </label>
    {quantity?<div className="mt-2 flex flex-wrap items-center gap-1"><WorkspaceStateBadge state={quantity.geometry_key===geometryKey(object)&&quantity.status==="current" ? "unverified" : "stale"} title="Draft quantity only, not an engineering result." /><p data-testid="dependency-quantity-value" className="text-[11px] text-slate-500">{quantity.geometry_key===geometryKey(object)&&quantity.status==="current"?`${quantity.area!=null?quantity.area.toFixed(1)+" square units":quantity.length!=null?quantity.length.toFixed(1)+" linear units":"No measurable geometry"} · draft quantity`:"Previous quantity · stale"}</p></div>:null}
    {!candidates.length?<p className="mt-2 text-[11px] text-slate-500">No compatible objects to link.</p>:null}
  </details>;
}
