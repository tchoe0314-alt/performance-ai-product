import {expect,test} from "@playwright/test";
import type {BuildingPlacement} from "../../app/types";
import {dependencyLinks,dependencyRecords,geometryQuantity,planDependencyGraph,setDependencyLink,validateDependencyGraph} from "../../app/utils/dependencyGraph";
import {resolveDependencyProposal} from "../../app/utils/canonicalDependencyPolicies";
import {withCanonicalCanvasSnapshot,resolveCanonicalCanvasInput} from "../../app/utils/canonicalCanvasProject";
const object=(id:string,type:BuildingPlacement["type"],meta:BuildingPlacement["meta"]={}):BuildingPlacement=>({id,label:id,type,x:id==="a"?100:300,y:100,w:50,d:50,placed:true,source:"manual_drawn",meta});
const fixtures:Array<[BuildingPlacement,BuildingPlacement]>=[
  [object("a","road"),object("b","parking")],
  [object("a","building"),object("b","parking")],
  [object("a","building"),object("b","setback_zone")],
  [object("a","road"),object("b","road",{cul_de_sac_v1:{version:1,bulbRadiusFt:50,roadWidthFt:30,islandRadiusFt:15,transitionRadiusFt:20,coordinateUnits:"ft"}})],
  [object("a","road"),object("b","entrance")],
  [object("a","basin"),object("b","open_space")],
  [object("a","building"),object("b","utility_corridor")],
];
for(const [source,target] of fixtures)for(const policy of ["ask","follow","fixed","independent"] as const)test(`${source.type} to ${target.type} supports ${policy}`,()=>{
  const a={...source,...setDependencyLink(source,target,policy)},objects=[a,target];
  const result=planDependencyGraph(objects,[{...a,x:150},target],"project");
  expect(result.status).toBe(policy==="ask"?"proposed":"applied");
  if(policy==="ask") {
    expect(result.proposal?.sourceSnapshot).toBe(JSON.stringify(objects));
    expect(resolveDependencyProposal(result.proposal!,objects,"project").accepted).toBe(true);
    expect(resolveDependencyProposal(result.proposal!,objects,"other").accepted).toBe(false);
  }
  if(policy==="fixed"||policy==="independent")expect(result.placements[1]).toEqual(target);
  else expect(result.placements[1].x).not.toBe(target.x);
  expect(objects[0].x).toBe(100);
});
test("default parking remains Ask; Independent survives save/reopen and canonical edges",()=>{
  const a=object("a","building",{canonical_relationships:{parking:{object_ids:["b"],policy:"independent"}}}),b=object("b","parking");
  expect(dependencyLinks({...a,meta:{canonical_relationships:{parking:{object_ids:["b"]}}}},[a,b])[0].policy).toBe("ask");
  const input=withCanonicalCanvasSnapshot({manual_fields:{units:"ft",site_objects:[a,b]}});
  expect(input.canonical_project_v1?.dependencies).toEqual(expect.arrayContaining([expect.objectContaining({policy:"independent",target_id:"b"})]));
  expect(resolveCanonicalCanvasInput(input).manual_fields?.site_objects?.[0].meta?.canonical_relationships).toEqual(a.meta?.canonical_relationships);
});
test("rejects missing targets, cycles, incompatible links and competing drivers atomically",()=>{
  const a=object("a","road"),b=object("b","driveway"),c=object("c","parking");
  const linkedA={...a,...setDependencyLink(a,b,"follow")};
  expect(()=>validateDependencyGraph([linkedA])).toThrow(/missing/);
  const cycle={...b,...setDependencyLink(b,object("a","driveway"),"ask")};
  expect(()=>validateDependencyGraph([{...linkedA,type:"driveway"},cycle])).toThrow(/cycles/);
  expect(()=>validateDependencyGraph([{...a,...setDependencyLink(a,c,"follow")},{...b,...setDependencyLink(b,c,"ask")},c])).toThrow(/two geometry/);
  expect(planDependencyGraph([a,b],[{...linkedA,meta:{dependency_links_v1:[{id:"x",kind:"utility_building",target_id:"b",policy:"follow"}]}},b],null).status).toBe("blocked");
});
test("Fixed protects direct child edits; linked protected objects block Follow and Ask",()=>{
  const a=object("a","road"),b=object("b","parking");
  const fixed={...a,...setDependencyLink(a,b,"fixed")};
  expect(planDependencyGraph([fixed,b],[fixed,{...b,x:400}],null).status).toBe("blocked");
  for(const policy of ["follow","ask"] as const){const source={...a,...setDependencyLink(a,b,policy)},locked={...b,locked:true};expect(planDependencyGraph([source,locked],[{...source,x:150},locked],null).status).toBe("blocked");}
});
test("chain propagation visits downstream members once and preserves explicitly edited bulk members",()=>{
  const a=object("a","road"),b=object("b","driveway"),c=object("c","parking");
  const linkedA={...a,...setDependencyLink(a,b,"follow")},linkedB={...b,...setDependencyLink(b,c,"follow")};
  const result=planDependencyGraph([linkedA,linkedB,c],[{...linkedA,x:150},linkedB,c],null);
  expect(result.placements.map(item=>item.x)).toEqual([150,350,350]);
  const bulk=planDependencyGraph([linkedA,linkedB,c],[{...linkedA,x:150},{...linkedB,x:400},c],null);
  expect(bulk.placements.map(item=>item.x)).toEqual([150,400,400]);
});
test("quantity policies compute draft geometry only and never reactivate stale engineering results",()=>{
  const a=object("a","building");expect(geometryQuantity(a).area).toBe(2500);
  for(const policy of ["follow","ask","fixed","independent"] as const){
    const source={...a,meta:{quantity_relationship_v1:policy}},result=planDependencyGraph([source],[{...source,w:100}],null);
    expect(result.status).toBe(policy==="ask"?"proposed":"applied");
    const value=result.placements[0].meta?.geometry_quantity_v1 as {area?:number;status?:string;review_only?:boolean}|undefined;
    if(policy==="follow"||policy==="ask"){expect(value?.area).toBe(5000);expect(value?.review_only).toBe(true);}else if(policy==="fixed")expect(value?.status).toBe("stale");else expect(value).toBeUndefined();
    expect(dependencyRecords([source])[0].kind).toBe("quantity_geometry");
  }
});
test("linked road width rebuilds cul-de-sac transitions and rectangular setbacks preserve offsets",()=>{
  const road={...object("a","road"),d:30},bulb=fixtures[3][1],source={...road,...setDependencyLink(road,bulb,"follow")};
  const result=planDependencyGraph([source,bulb],[{...source,d:40},bulb],null);
  expect(result.status).toBe("applied");expect((result.placements[1].meta?.cul_de_sac_v1 as {roadWidthFt:number}).roadWidthFt).toBe(40);expect(result.placements[1].geometry!.length).toBeGreaterThan(100);
  expect(planDependencyGraph([source,bulb],[{...source,d:80},bulb],null).status).toBe("blocked");
  const building=object("a","building"),setback={...object("b","setback_zone"),x:90,y:90,w:70,d:70},linked={...building,...setDependencyLink(building,setback,"follow")};
  const expanded=planDependencyGraph([linked,setback],[{...linked,w:100},setback],null);
  expect(expanded.placements[1].w).toBe(120);expect(expanded.placements[1].x).toBe(90);
});
