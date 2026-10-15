import type { ReactNode } from "react";
import { ENVIRONMENT_LAYERS, displayLength, type EnvironmentLayer, type WorkspaceEnvironment } from "../utils/workspaceEnvironment";

export function PreviewEnvironmentControls({section,value,counts,mapAvailable,coordinateLabel,onChange}:{
  section:"layers"|"view";value:WorkspaceEnvironment;counts:Record<EnvironmentLayer,number>;
  mapAvailable:boolean;coordinateLabel:string;onChange:(patch:Partial<WorkspaceEnvironment>)=>void;
}) {
  const toggle=(label:string,checked:boolean,onClick:()=>void,disabled=false,detail?:ReactNode)=><button type="button" aria-pressed={checked} disabled={disabled} onClick={onClick}
    className="flex min-h-8 w-full items-center justify-between gap-2 rounded-md px-2 text-left text-xs text-slate-700 hover:bg-slate-50 disabled:opacity-60">
    <span>{label}</span><span className="text-[10px] text-slate-600">{detail??(checked?"On":"Off")}</span></button>;
  if(section==="layers")return <div data-testid="environment-context-layers" className="border-b border-slate-100 py-2">
    {toggle("Satellite",value.mapEnabled&&value.satellite,()=>onChange({mapEnabled:true,satellite:!(value.mapEnabled&&value.satellite)}),!mapAvailable,mapAvailable?undefined:"Needs map")}
    {ENVIRONMENT_LAYERS.map(layer=><div key={layer} data-testid={`environment-layer-${layer}`}>
      {toggle(({topographic:"Topographic",zoning:"Zoning",parcels:"Parcel boundaries",survey:"Survey",utilities:"Utilities"})[layer],value.layers[layer],()=>onChange({layers:{...value.layers,[layer]:!value.layers[layer]}}),counts[layer]===0,counts[layer]===0?"No data":undefined)}
    </div>)}
  </div>;
  return <div data-testid="environment-view-controls" className="space-y-2 border-b border-slate-100 pb-2 text-xs text-slate-700">
    <p data-testid="environment-coordinate-system" className="rounded-md bg-slate-50 px-2 py-1.5">{coordinateLabel}</p>
    <label className="flex items-center justify-between gap-2">Display units<select aria-label="Display units" value={value.units} onChange={e=>onChange({units:e.target.value as "ft"|"m"})} className="rounded-md border border-slate-200 px-2 py-1"><option value="ft">Imperial</option><option value="m">Metric</option></select></label>
    <div className="flex items-center gap-3">
      <label className="flex items-center gap-1.5"><input type="checkbox" aria-label="Show drafting grid" checked={value.grid} onChange={e=>onChange({grid:e.target.checked})}/>Grid</label>
      <label className="flex items-center gap-1.5"><input type="checkbox" aria-label="Enable snapping" checked={value.snap} onChange={e=>onChange({snap:e.target.checked})}/>Snap</label>
      <label className="flex items-center gap-1.5"><input type="checkbox" aria-label="Enable orthogonal drawing" checked={value.ortho} onChange={e=>onChange({ortho:e.target.checked})}/>Ortho</label>
    </div>
    <label className="flex items-center justify-between gap-2">Grid / snap step<select aria-label="Grid and snap spacing" value={value.gridFt} onChange={e=>onChange({gridFt:Number(e.target.value)})} className="rounded-md border border-slate-200 px-2 py-1">
      {Array.from(new Set([1,5,10,25,50,value.gridFt])).sort((a,b)=>a-b).map(ft=><option key={ft} value={ft}>{displayLength(ft,value.units,3)}</option>)}
    </select></label>
    {value.units==="m"?<p className="text-[10px] text-slate-600">Display only; drafting inputs remain ft.</p>:null}
  </div>;
}
