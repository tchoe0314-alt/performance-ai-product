import { useEffect, useState } from "react";
import type { BuildingPlacement, SiteObjectType } from "../types";
import { SITE_OBJECT_CATALOG } from "../utils/siteObjectCatalog";
import { geometryIssues, type CustomTypeDefinition } from "../utils/siteObjectDefinition";
import { getStoredToken } from "../utils/auth";
import { apiErrorMessage, getJson, postJson } from "../../lib/api";

export function ObjectClassificationFields({ object, objects, library = {}, disabled, onUpdate }: {
  object: BuildingPlacement; objects: BuildingPlacement[]; disabled: boolean;
  library?: Record<string, CustomTypeDefinition>;
  onUpdate: (object: BuildingPlacement, updates: Partial<BuildingPlacement>) => void;
}) {
  const [accountTypes, setAccountTypes] = useState<CustomTypeDefinition[]>([]);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [fields, setFields] = useState<CustomTypeDefinition["fields"]>([]);
  const [scope, setScope] = useState("project");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    const token = getStoredToken();
    if (token) getJson<{types: CustomTypeDefinition[]}>("/api/object-types", {token, signal: controller.signal})
      .then(response => setAccountTypes(response.types)).catch(() => {});
    return () => controller.abort();
  }, []);
  useEffect(() => { setCreating(false); setError(""); }, [object.id]);
  const projectTypes = objects.flatMap(item => item.meta?.custom_type_definition_v1 ? [item.meta.custom_type_definition_v1 as CustomTypeDefinition] : []);
  const types = [...new Map([...accountTypes,...Object.values(library),...projectTypes].map(type => [type.id,type])).values()];
  const current = object.meta?.custom_type_definition_v1 as CustomTypeDefinition | undefined;
  const issues = geometryIssues(object);
  const apply = (value: string) => {
    if (value === "new") { setCreating(true); return; }
    const custom = types.find(type => type.id === value);
    const type = custom ? "custom" : value as SiteObjectType;
    onUpdate(object, {type, use: SITE_OBJECT_CATALOG[type]?.use,
      meta: {...object.meta, custom_type_id: custom?.id ?? null, custom_type_definition_v1: custom ?? null,
        custom_properties_v1: custom?.id === current?.id ? object.meta?.custom_properties_v1 ?? {} : {}, canonical_object_type: type}});
  };
  const create = async () => {
    setError("");
    const cleanFields = fields.map(field => ({...field,name:field.name.trim()}));
    if (!name.trim() || name.trim().length > 100 || cleanFields.some(field => !field.name || ["__proto__","prototype","constructor"].includes(field.name)) || new Set(cleanFields.map(field=>field.name.toLowerCase())).size !== cleanFields.length) {
      setError("Enter a type name and unique field names."); return;
    }
    const definition: CustomTypeDefinition = {version:1,id:`custom-${crypto.randomUUID()}`,name:name.trim(),fields:cleanFields};
    setBusy(true);
    try {
      if (scope === "account") {
        const token = getStoredToken();
        if (!token) throw new Error("Sign in to save reusable types.");
        await postJson("/api/object-types", definition, {token});
        setAccountTypes(previous => [...previous, definition]);
      }
      onUpdate(object, {type:"custom", meta:{...object.meta, custom_type_id:definition.id, custom_type_definition_v1:definition, custom_properties_v1:{}, canonical_object_type:"custom"}});
      setCreating(false); setName(""); setFields([]);
    } catch (err) { setError(apiErrorMessage(err,"Could not save this type.")); }
    finally { setBusy(false); }
  };
  const inputClass="w-full min-w-0 rounded-md border border-slate-200 bg-white px-2 py-1 text-xs text-slate-900";
  return <div className="space-y-2 rounded-xl border border-slate-200 bg-slate-50 p-3" data-testid="object-classification">
    <label className="block text-xs font-semibold text-slate-600">Type
      <select aria-label="Selected object type" className={`${inputClass} mt-1`} disabled={disabled || object.type === "site" || object.type === "group"} value={current?.id ?? object.type ?? "custom"} onChange={event=>apply(event.target.value)}>
        {Object.entries(SITE_OBJECT_CATALOG).filter(([type])=>type!=="group" || object.type==="group").map(([type,definition])=><option key={type} value={type}>{definition.label}</option>)}
        {types.map(type=><option key={type.id} value={type.id}>{type.name}</option>)}
        <option value="new">New custom type…</option>
      </select>
    </label>
    {creating && <div className="space-y-2" data-testid="custom-type-editor">
      <input aria-label="Custom type name" placeholder="Type name" maxLength={100} className={inputClass} value={name} onChange={event=>setName(event.target.value)} />
      {fields.map((field,index)=><div key={index} className="grid grid-cols-[1fr_80px_28px] gap-1">
        <input aria-label={`Field ${index+1} name`} maxLength={80} className={inputClass} placeholder="Field name" value={field.name} onChange={event=>setFields(previous=>previous.map((f,i)=>i===index?{...f,name:event.target.value}:f))}/>
        <select aria-label={`Field ${index+1} kind`} className={inputClass} value={field.type} onChange={event=>setFields(previous=>previous.map((f,i)=>i===index?{...f,type:event.target.value as typeof f.type}:f))}><option value="text">Text</option><option value="number">Number</option><option value="boolean">Checkbox</option></select>
        <button aria-label={`Remove field ${index+1}`} onClick={()=>setFields(previous=>previous.filter((_,i)=>i!==index))}>×</button>
      </div>)}
      <button type="button" disabled={fields.length>=30} className="text-xs font-semibold text-blue-700" onClick={()=>setFields(previous=>[...previous,{name:"",type:"text"}])}>Add field</button>
      <label className="block text-xs text-slate-600">Reuse in
        <select aria-label="Custom type reuse scope" className={`${inputClass} mt-1`} value={scope} onChange={event=>setScope(event.target.value)}><option value="project">This project</option><option value="account">All my projects</option></select>
      </label>
      <div className="flex gap-2"><button type="button" disabled={busy || disabled} onClick={()=>void create()} className="rounded-md bg-slate-900 px-3 py-1 text-xs text-white">{busy?"Saving…":"Save type"}</button><button type="button" onClick={()=>setCreating(false)} className="text-xs">Cancel</button></div>
    </div>}
    {current?.fields.map(field=><label key={field.name} className="block text-xs text-slate-600">{field.name}{field.unit?` (${field.unit})`:""}
      <input aria-label={`Object property ${field.name}`} disabled={disabled} className={`${inputClass} mt-1`} type={field.type==="boolean"?"checkbox":field.type==="number"?"number":"text"}
        checked={field.type==="boolean" ? (object.meta?.custom_properties_v1 as Record<string,unknown>)?.[field.name]===true : undefined}
        value={field.type==="boolean" ? undefined : String((object.meta?.custom_properties_v1 as Record<string,unknown>)?.[field.name]??"")}
        onChange={event=>{ const value=field.type==="boolean"?event.target.checked:field.type==="number" && event.target.value!==""?Number(event.target.value):event.target.value;
          if (typeof value === "number" && !Number.isFinite(value)) return;
          onUpdate(object,{meta:{...object.meta,custom_properties_v1:{...(object.meta?.custom_properties_v1 as Record<string,unknown>??{}),[field.name]:value}}}); }}/>
    </label>)}
    {object.type === "custom" && <p className="text-xs text-slate-500">Reference only. No engineering rules assigned.</p>}
    {issues.length>0 && <div className="text-xs text-amber-800" role="status"><p>{issues[0]} Affected calculations paused.</p>
      {object.geometryType==="polyline" && (object.geometry?.length??0)>=3 && <button disabled={disabled} type="button" className="mt-1 font-semibold underline" onClick={()=>onUpdate(object,{geometryType:"polygon",meta:{...object.meta,outline_incomplete:false}})}>Close outline</button>}
    </div>}
    {error && <p role="alert" className="text-xs text-red-700">{error}</p>}
  </div>;
}
