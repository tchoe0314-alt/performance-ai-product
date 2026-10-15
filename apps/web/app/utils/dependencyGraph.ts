import type { BuildingPlacement } from "../types";
import { canonicalControlState } from "./canonicalEditCommands";
import { applyBuildingParkingDependency, parkingDependencyRelationship, type CanonicalDependencyProposal } from "./canonicalDependencyPolicies";
import { readCulDeSac, reconcileCulDeSacUpdate } from "./parametricRoad";
import {geometryIssues,validateObjectGroups} from "./siteObjectDefinition";

export const DEPENDENCY_KINDS = ["road_parking", "building_parking", "building_setback", "road_culdesac", "access_road", "pond_drainage", "utility_building"] as const;
export type DependencyKind = typeof DEPENDENCY_KINDS[number];
export type DependencyPolicy = "follow" | "ask" | "fixed" | "independent";
export type DependencyLink = { id: string; kind: DependencyKind; target_id: string; policy: DependencyPolicy };
export const DEPENDENCY_LABELS: Record<DependencyKind,string> = {road_parking:"Parking",building_parking:"Parking",building_setback:"Setback",road_culdesac:"Cul-de-sac",access_road:"Access",pond_drainage:"Drainage area",utility_building:"Utility"};
export const isBuilding = (item: BuildingPlacement) => item.type === "building" || item.type === "pad" || item.type?.endsWith("_building") === true;
export const isRoad = (item: BuildingPlacement) => ["road","driveway","access_drive","drive_aisle"].includes(item.type ?? "");
export function linkKind(source:BuildingPlacement,target:BuildingPlacement):DependencyKind|null {
  if(isBuilding(source)) {
    if(target.type==="parking")return "building_parking";
    if(target.type==="setback_zone")return "building_setback";
    if(["utility_corridor","hydrant","manhole","inlet","outfall"].includes(target.type??""))return "utility_building";
  }
  if(isRoad(source)) {
    if(target.type==="parking")return "road_parking";
    if(target.type==="road"&&target.meta?.cul_de_sac_v1)return "road_culdesac";
    if(["entrance","driveway","access_drive"].includes(target.type??""))return "access_road";
  }
  if(source.type==="basin"&&(["open_space","landscape"].includes(target.type??"")||target.meta?.semantic_role==="drainage_area"))return "pond_drainage";
  return null;
}
export function dependencyLinks(item:BuildingPlacement,objects:BuildingPlacement[]):DependencyLink[] {
  const links = (item.meta?.dependency_links_v1 ?? []) as DependencyLink[];
  const legacy=parkingDependencyRelationship(item);
  const explicit=(item.meta?.canonical_relationships as {parking?:unknown}|undefined)?.parking!==undefined;
  const parkingIds=explicit?legacy.object_ids:objects.filter(o=>o.type==="parking"&&o.meta?.canonical_parent_id===item.id).map(o=>o.id);
  return [...links,...parkingIds.filter(id=>!links.some(edge=>edge.target_id===id)).map(id=>({id:`parking:${item.id}:${id}`,kind:"building_parking" as const,target_id:id,policy:legacy.policy}))];
}
export function setDependencyLink(source:BuildingPlacement,target:BuildingPlacement,policy:DependencyPolicy|null):Partial<BuildingPlacement> {
  const kind=linkKind(source,target);if(!kind)throw new Error("These object types do not have a supported relationship.");
  const links=((source.meta?.dependency_links_v1??[]) as DependencyLink[]).filter(edge=>edge.target_id!==target.id);
  if(policy)links.push({id:`link:${source.id}:${target.id}`,kind,target_id:target.id,policy});
  const related=Array.isArray(source.meta?.object_relationship_ids_v1)?source.meta.object_relationship_ids_v1.filter(id=>id!==target.id):[];
  if(policy)related.push(target.id);
  return {meta:{...source.meta,dependency_links_v1:links,object_relationship_ids_v1:related}};
}
export function validateDependencyGraph(objects:BuildingPlacement[]) {
  validateObjectGroups(objects);
  const byId=new Map(objects.map(item=>[item.id,item]));
  const adjacency=new Map<string,string[]>();const incoming=new Map<string,string>();const edgeIds=new Set<string>();
  for(const source of objects) {
    const raw=source.meta?.dependency_links_v1;
    if(raw!==undefined&&(!Array.isArray(raw)||raw.length>1000))throw new Error("Invalid dependency links.");
    const relationships=source.meta?.canonical_relationships as {parking?:{policy?:unknown;object_ids?:unknown}}|undefined;
    const legacy=relationships?.parking;
    if(relationships&&Object.prototype.hasOwnProperty.call(relationships,"parking")&&(!legacy||typeof legacy!=="object"||Array.isArray(legacy)))throw new Error("Invalid parking relationship.");
    if(legacy&&((legacy.policy!==undefined&&!["follow","ask","fixed","independent"].includes(String(legacy.policy)))||(legacy.object_ids!==undefined&&(!Array.isArray(legacy.object_ids)||!legacy.object_ids.every(id=>typeof id==="string")))))throw new Error("Invalid parking relationship.");
    const seen=new Set<string>();
    for(const edge of dependencyLinks(source,objects)) {
      const target=byId.get(edge?.target_id);
      if(!edge||typeof edge.id!=="string"||!edge.id||edgeIds.has(edge.id)||!DEPENDENCY_KINDS.includes(edge.kind)||!["follow","ask","fixed","independent"].includes(edge.policy)||!target||target.id===source.id||seen.has(target.id)||linkKind(source,target)!==edge.kind)throw new Error("A dependency has a missing, duplicate or incompatible object.");
      edgeIds.add(edge.id);
      seen.add(target.id);
      // Independent edges document intent but do not drive the geometry graph.
      if(edge.policy!=="independent") {
        const owner=incoming.get(target.id);if(owner&&owner!==source.id)throw new Error("A linked object cannot have two geometry drivers. Make one link Independent.");
        incoming.set(target.id,source.id);adjacency.set(source.id,[...(adjacency.get(source.id)??[]),target.id]);
      }
    }
    const quantity=source.meta?.quantity_relationship_v1;
    if(quantity!==undefined&&!["follow","ask","fixed","independent"].includes(String(quantity)))throw new Error("Invalid quantity relationship.");
    if(quantity){const id=`quantity:${source.id}`;if(edgeIds.has(id))throw new Error("Duplicate quantity relationship identity.");edgeIds.add(id);}
  }
  const degree=new Map([...byId.keys()].map(id=>[id,Number(incoming.has(id))]));
  const ready=[...degree].filter(([,value])=>!value).map(([id])=>id);let count=0;
  while(ready.length){const id=ready.pop()!;count++;for(const child of adjacency.get(id)??[]){degree.set(child,degree.get(child)!-1);if(!degree.get(child))ready.push(child);}}
  if(count!==byId.size)throw new Error("Dependency cycles are not allowed.");
}
export function dependencyRecords(objects:BuildingPlacement[]) {
  validateDependencyGraph(objects);
  return objects.flatMap(source=>[
    ...dependencyLinks(source,objects).map(edge=>({owner:"dependency_graph_v1",source_id:source.id,...edge,review_only:true})),
    ...(source.meta?.quantity_relationship_v1?[{owner:"dependency_graph_v1",id:`quantity:${source.id}`,source_id:source.id,target_id:`quantity:${source.id}`,kind:"quantity_geometry",policy:source.meta.quantity_relationship_v1,review_only:true}]:[]),
  ]);
}
export function geometryKey(item:BuildingPlacement) {
  return JSON.stringify([item.x??0,item.y??0,item.w,item.d,item.rotation??0,item.geometryType??null,item.geometry??null,item.type,item.meta?.cul_de_sac_v1??null]);
}
export function geometryQuantity(item:BuildingPlacement) {
  const points=item.geometry??[];let area:number|null=null,length:number|null=null;
  if(item.geometryType==="polyline")length=points.slice(1).reduce((sum,p,i)=>sum+Math.hypot(p[0]-points[i][0],p[1]-points[i][1]),0);
  else if(item.geometryType==="polygon")area=Math.abs(points.reduce((sum,p,i)=>{const q=points[(i+1)%points.length];return sum+p[0]*q[1]-q[0]*p[1];},0))/2;
  else if(item.geometryType!=="point")area=item.w*item.d;
  const valid=geometryIssues(item).length===0;
  return {area:valid?area:null,length:valid?length:null,geometry_key:geometryKey(item),review_only:true,status:valid?"current":"unavailable"};
}
const protectedObject=(item:BuildingPlacement)=>item.locked||["fixed","existing","reference"].includes(canonicalControlState(item));
function followGeometry(target:BuildingPlacement,before:BuildingPlacement,after:BuildingPlacement,kind:DependencyKind):BuildingPlacement {
  // Preserve target dimensions and offsets; resize is never a fabricated engineering solution.
  const oldCx=(before.x??0)+before.w/2,oldCy=(before.y??0)+before.d/2;
  const newCx=(after.x??0)+after.w/2,newCy=(after.y??0)+after.d/2;
  const angle=((after.rotation??0)-(before.rotation??0))*Math.PI/180;
  const transform=([x,y]:[number,number]):[number,number]=>[newCx+(x-oldCx)*Math.cos(angle)-(y-oldCy)*Math.sin(angle),newCy+(x-oldCx)*Math.sin(angle)+(y-oldCy)*Math.cos(angle)];
  const center=transform([(target.x??0)+target.w/2,(target.y??0)+target.d/2]);
  const updates:Partial<BuildingPlacement>={x:center[0]-target.w/2,y:center[1]-target.d/2,rotation:(target.rotation??0)+(after.rotation??0)-(before.rotation??0),geometry:target.geometry?.map(transform)};
  if(kind==="building_setback"&&!target.geometry?.length&&!before.geometry?.length&&!after.geometry?.length){
    updates.w=target.w+after.w-before.w;updates.d=target.d+after.d-before.d;
    if(updates.w<=0||updates.d<=0)throw new Error("The linked setback cannot preserve its offsets at this size. Review the change manually.");
    updates.x=center[0]-updates.w/2;updates.y=center[1]-updates.d/2;
  }
  const parameters=readCulDeSac(target);
  if(kind==="road_culdesac"&&parameters){
    // Straight rectangular roads use depth as their cross-road width. Arbitrary
    // linework is not assigned a width or endpoint attachment by inference.
    if(!before.geometry?.length&&!after.geometry?.length&&before.d!==after.d){
      const width=after.d/(parameters.coordinateUnits==="m"?.3048:1);
      if(width<20||width>48)throw new Error("Linked cul-de-sac approach width must be 20–48 ft. Review this road change manually.");
      updates.meta={...target.meta,cul_de_sac_v1:{...parameters,roadWidthFt:width}};
    }
    Object.assign(updates,reconcileCulDeSacUpdate(target,updates));
  }
  return {...target,...updates,meta:{...target.meta,...updates.meta,dependency_review_v1:{kind,source_id:before.id,review_only:true,needs_engineering_review:true}}};
}
/** Plan every writer atomically. Explicit child edits are preserved, but Fixed is never bypassed. */
export function planDependencyGraph(source:BuildingPlacement[],requested:BuildingPlacement[],projectId:string|null,label="Linked object change") {
  const fail=(reason:string)=>({status:"blocked" as const,reason,placements:source,proposal:null as CanonicalDependencyProposal|null});
  try {validateDependencyGraph(requested);}catch(error){return fail(error instanceof Error?error.message:String(error));}
  const old=new Map(source.map(item=>[item.id,item]));const next=new Map(requested.map(item=>[item.id,item]));
  let asks=false;const reports:CanonicalDependencyProposal["reflowReports"]=[];
  const changed=new Set(source.filter(item=>next.has(item.id)&&geometryKey(item)!==geometryKey(next.get(item.id)!)).map(item=>item.id));
  // A deletion cannot leave a live link dangling; removing/replacing its link is an explicit override.
  const visited=new Set<string>();
  const propagate=(id:string):string|null=>{
    if(visited.has(id))return null;visited.add(id);
    const before=old.get(id),after=next.get(id);if(!before||!after||geometryKey(before)===geometryKey(after))return null;
    for(const edge of dependencyLinks(after,requested)) {
      const original=old.get(edge.target_id),target=next.get(edge.target_id);if(!original||!target)continue;
      if(edge.policy==="independent")continue;
      if(edge.policy==="fixed") {if(geometryKey(original)!==geometryKey(target))return `${target.label} is Fixed in this relationship. Change its relationship policy before editing it.`;continue;}
      if(protectedObject(original))return `${original.label} is protected and cannot follow this change. Unlock it or make the link Independent.`;
      // Explicitly edited members of a bulk transaction are not moved a second time.
      if(!changed.has(target.id)) {
        let followed:BuildingPlacement;
        if(edge.kind==="building_parking") {
          const synthetic={...before,meta:{...before.meta,canonical_relationships:{parking:{policy:"follow",object_ids:[target.id]}}}};
          const result=applyBuildingParkingDependency([...next.values()],synthetic,after,{kind:"update_object",objectId:id,updates:after,source:"dependency",transactionId:"graph",createdAt:new Date().toISOString()});
          followed=result.after[0]??target;reports.push(...result.reflowReports);
        } else {try{followed=followGeometry(target,before,after,edge.kind);}catch(error){return error instanceof Error?error.message:String(error);}}
        next.set(target.id,followed);
      }
      asks ||= edge.policy==="ask";
      const error=propagate(target.id);if(error)return error;
    }
    const policy=after.meta?.quantity_relationship_v1 as DependencyPolicy|undefined;
    if(policy&&policy!=="independent") {
      if(policy==="fixed")next.set(id,{...next.get(id)!,meta:{...next.get(id)!.meta,geometry_quantity_v1:{...(after.meta?.geometry_quantity_v1 as object??{}),status:"stale",review_only:true}}});
      else {asks ||= policy==="ask";next.set(id,{...next.get(id)!,meta:{...next.get(id)!.meta,geometry_quantity_v1:geometryQuantity(next.get(id)!)}});}
    }
    return null;
  };
  // Sources first: prevents a directly edited child from being visited before its upstream parent.
  const driven=new Set(requested.flatMap(item=>dependencyLinks(item,requested).filter(edge=>edge.policy!=="independent").map(edge=>edge.target_id)));
  for(const id of [...changed].sort((a,b)=>Number(driven.has(a))-Number(driven.has(b)))){const error=propagate(id);if(error)return fail(error);}
  // Fixed targets are protected even when the parent itself did not move.
  for(const item of requested)for(const edge of dependencyLinks(item,requested))if(edge.policy==="fixed"&&old.has(edge.target_id)&&next.has(edge.target_id)&&geometryKey(old.get(edge.target_id)!)!==geometryKey(next.get(edge.target_id)!))return fail(`${next.get(edge.target_id)!.label} is Fixed in this relationship. Change its relationship policy first.`);
  const placements=requested.map(item=>next.get(item.id)!);
  const before=source.filter(item=>next.has(item.id)&&JSON.stringify(item)!==JSON.stringify(next.get(item.id)));
  const after=placements.filter(item=>before.some(previous=>previous.id===item.id));
  const tx=`graph-${crypto.randomUUID()}`;
  const proposal:CanonicalDependencyProposal|null=asks?{id:tx,transactionId:tx,buildingId:before[0]?.id??"",buildingLabel:label,before,after,reflowReports:reports,createdAt:new Date().toISOString(),projectId,sourceSnapshot:JSON.stringify(source),completePlacements:placements}:null;
  return {status:asks?"proposed" as const:"applied" as const,reason:null,placements,proposal};
}
