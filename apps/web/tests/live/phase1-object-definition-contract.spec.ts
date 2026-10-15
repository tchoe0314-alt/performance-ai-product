import { expect,test } from "@playwright/test";
import { objectDefinition,geometryIssues,validateObjectGroups } from "../../app/utils/siteObjectDefinition";
import { connectedLineChain } from "../../app/utils/objectLineChain";
import { withCanonicalCanvasSnapshot,resolveCanonicalCanvasInput } from "../../app/utils/canonicalCanvasProject";
import type {BuildingPlacement} from "../../app/types";
import {execFileSync} from "node:child_process";
import path from "node:path";
import {assessSiteInterference} from "../../app/utils/siteInterference";
import {runObjectManagerBulkMove} from "../../app/utils/dashboardObjectManagerTransformActions";
import type {ObjectManagerBulkActions} from "../../app/utils/dashboardObjectManagerBulkActions";

const outline: BuildingPlacement={id:"a",label:"Building",type:"building",x:0,y:0,w:20,d:20,geometryType:"polygon",geometry:[[0,0],[20,0],[20,20],[0,20]]};
const line=(id:string,a:[number,number],b:[number,number]):BuildingPlacement=>({id,label:id,type:"custom",w:20,d:1,geometryType:"polyline",geometry:[a,b]});

test("standard object records preserve identity and native geometry has authority",()=>{
  const input=withCanonicalCanvasSnapshot({manual_fields:{units:"ft",site_objects:[outline]}});
  const wrapper=(input.canonical_project_v1!.buildings as Array<{object_v1:ReturnType<typeof objectDefinition>}>)[0];
  expect(wrapper.object_v1.validation.engineering_verified).toBe(false);
  wrapper.object_v1.geometry.origin[0]=25;
  expect(resolveCanonicalCanvasInput(input).manual_fields!.site_objects![0].x).toBe(25);
  const record=objectDefinition(outline,"ft");
  expect(objectDefinition(outline,"ft",record).revision.number).toBe(1);
  expect(objectDefinition({...outline,x:3},"ft",record).revision.number).toBe(2);
});

test("open shapes and crossed polygons pause affected systems, custom remains reference",()=>{
  expect(objectDefinition({...outline,geometryType:"polyline"},"ft").validation.paused_systems).toContain("parking");
  expect(geometryIssues({...outline,geometry:[[0,0],[20,20],[0,20],[20,0]]})).toContain("The outline crosses or touches itself.");
  expect(objectDefinition({...outline,type:"custom"},"ft").validation.status).toBe("unverified");
});

test("connected linework orders both ends, keeps open chains and rejects branches gaps duplicates",()=>{
  const a=line("a",[10,0],[10,10]),b=line("b",[0,0],[10,0]),c=line("c",[10,10],[0,10]);
  expect(connectedLineChain([a,b,c])).toEqual({points:[[0,0],[10,0],[10,10],[0,10]],closed:false});
  expect(connectedLineChain([a,b,c,line("d",[0,10],[0,0])]).closed).toBe(true);
  expect(connectedLineChain([a,b,line("branch",[10,0],[30,0])]).error).toContain("branches");
  expect(connectedLineChain([a,line("gap",[0,0],[9.99,0])]).error).toBeTruthy();
  expect(connectedLineChain([a,a]).error).toContain("duplicate");
});

test("group tree rejects cycles missing parents duplicate IDs and non-group parents",()=>{
  const group={...outline,id:"g",type:"group" as const};
  validateObjectGroups([group,{...outline,meta:{group_id:"g"}}]);
  for (const objects of [[outline,outline],[{...outline,meta:{group_id:"missing"}}],[{...group,meta:{group_id:"a"}},{...outline,meta:{group_id:"g"}}]]) expect(()=>validateObjectGroups(objects)).toThrow();
});

test("browser and backend produce the same standardized object contract",()=>{
  const fixtures=[outline,{...outline,type:"custom" as const,meta:{custom_properties_v1:{diameter:12},canonical_relationships:{parking:{object_ids:["parking"]}}}},
    {...outline,type:"group" as const}, {...outline,geometryType:"polyline" as const}];
  const script="import json,sys;from backend.services.site_objects import object_definition;print(json.dumps([object_definition(item,'ft') for item in json.load(sys.stdin)]))";
  const backend=JSON.parse(execFileSync(process.env.CIVORA_PYTHON??"python3",["-c",script],{cwd:path.resolve(process.cwd(),"../.."),input:JSON.stringify(fixtures),encoding:"utf8"}));
  expect(fixtures.map(item=>objectDefinition(item,"ft"))).toEqual(backend);
});

test("project types survive deleting their last instance and malformed libraries fail closed",()=>{
  const custom={version:1,id:"custom-project",name:"Project feature",fields:[]};
  let input=withCanonicalCanvasSnapshot({manual_fields:{units:"ft",site_objects:[{...outline,type:"custom",meta:{custom_type_definition_v1:custom,custom_type_id:custom.id}}]}});
  input=withCanonicalCanvasSnapshot({...input,manual_fields:{...input.manual_fields,site_objects:[]}});
  expect((input.canonical_project_v1!.extensions as {object_type_library_v1:unknown}).object_type_library_v1).toEqual({[custom.id]:custom});
  (input.canonical_project_v1!.extensions as Record<string,unknown>).object_type_library_v1={broken:null};
  expect(()=>resolveCanonicalCanvasInput(input)).toThrow(/custom type/);
});

test("combined physical objects still participate in collision checks, groups and hidden traces do not",()=>{
  const combined={...outline,placed:true,meta:{combined_from_object_ids:["source"],semantic_source_mode:"linework"}};
  const neighbor={...outline,id:"neighbor",placed:true};
  expect(assessSiteInterference([combined,neighbor]).some(result=>result.severity==="conflict")).toBe(true);
  expect(assessSiteInterference([{...combined,meta:{ui_hidden:true}},neighbor]).some(result=>result.severity==="conflict")).toBe(true);
  expect(assessSiteInterference([combined,{...outline,id:"source",placed:true,meta:{ui_hidden:true,combined_into_object_id:combined.id}}])).toEqual([]);
  expect(assessSiteInterference([{...combined,type:"group"},neighbor])).toEqual([]);
});

test("group transforms cannot bypass protection on imported existing members",()=>{
  let changed=false,message="";
  const noop=()=>{};
  const actions:ObjectManagerBulkActions={setBuildingPlacements:()=>{changed=true;},setSelectedObjectIds:noop,setActivePlacementId:noop,setPreviewInteraction:noop,setObjectManagerStatusMessage:noop,setStatusMessage:noop,appendChatMessage:noop,recordRecentChange:noop,recordDraftUndoAction:noop,markSystemsStale:noop,systemsImpactedByPlacement:()=>[],reportObjectActionBlocker:text=>{message=text;},handleUpdateBuilding:noop,clearGeneratedPreview:noop,persistDraftRefresh:noop};
  const group={...outline,id:"g",type:"group" as const};
  const member={...outline,source:"detected_from_gis" as const,meta:{group_id:"g"}};
  runObjectManagerBulkMove({bulkMoveX:"10",bulkMoveY:"0",buildingPlacements:[group,member],selectedObjectIds:["g"],actions});
  expect(changed).toBe(false);expect(message).toContain("protected members");
});

test("unknown and prototype-like classifications remain reference-only, never crash imports",()=>{
  for(const type of ["future_type","__proto__","constructor"]) {
    const input=withCanonicalCanvasSnapshot({manual_fields:{units:"ft",site_objects:[{...outline,type}]}});
    const wrappers=(input.canonical_project_v1!.extensions as {canvas_other_placements_v1:Array<{object_v1:{validation:{status:string};export_mapping:{mode:string}}}>}).canvas_other_placements_v1;
    expect(wrappers[0].object_v1.validation.status).toBe("unverified");
    expect(wrappers[0].object_v1.export_mapping.mode).toBe("reference_only");
    expect(resolveCanonicalCanvasInput(input).manual_fields!.site_objects![0].type).toBe(type);
  }
});
