import {expect,test} from "@playwright/test";
import {createEditTransactions,editableInput,validateLedger} from "../../app/utils/editTransactions";
import {commitPlacementState} from "../../app/utils/placementStateCommit";
import type {ProjectInput,BuildingPlacement} from "../../app/types";
const input=(x=100):ProjectInput=>({manual_fields:{units:"ft",site_objects:[{id:"a",type:"building",x,y:100,w:20,d:20}]}});
test("saved transactions restore multi-step undo and redo after sessions",()=>{
  const h=createEditTransactions();h.reset(input());h.observe(input(120),"Move");h.observe(input(140),"Move again");
  const restored=createEditTransactions();restored.restore(JSON.parse(JSON.stringify(h.export())));
  expect(restored.undo()).toEqual(editableInput(input(120)));expect(restored.undo()).toEqual(editableInput(input()));
  const next=createEditTransactions();next.restore(restored.export());expect(next.redo()).toEqual(editableInput(input(120)));expect(next.redo()).toEqual(editableInput(input(140)));
});
test("new edits retain abandoned redo branch without replaying it over the new plan",()=>{
  const h=createEditTransactions();h.reset(input());const old=h.observe(input(120),"Old branch")!;h.undo();h.observe(input(150),"New branch");
  expect(h.next).toBeNull();expect(h.entries.map(tx=>tx.id)).toContain(old.id);expect(h.export().transactions).toHaveLength(2);
  h.undo();expect(h.redo()).toEqual(editableInput(input(150)));
});
test("AI and imports add remove and update objects in one reversible snapshot",()=>{
  const h=createEditTransactions();h.reset(input());const after=input(200);after.manual_fields!.site_objects!.push({id:"b",type:"road",x:0,y:0,w:30,d:100});
  const tx=h.observe(after,"AI revision")!;expect(tx.affected_object_ids).toEqual(["a","b"]);expect(tx.calculation_invalidations).toContain("roads");
  after.manual_fields!.site_objects![0].x=999;expect(h.undo()).toEqual(editableInput(input()));expect(h.redo()?.manual_fields?.site_objects?.[0].x).toBe(200);
  const empty=input();empty.manual_fields!.site_objects=[];h.observe(empty,"Delete all");expect(h.undo()?.manual_fields?.site_objects).toHaveLength(2);
});
test("chat typing and result status do not create plan edits; engineering controls do",()=>{
  const h=createEditTransactions();h.reset(input());expect(h.observe({...input(),prompt_text:"move building",meta:{chat_thread:[],system_dirty_state:{roads:"stale"}}})).toBeNull();
  const controls=input();controls.manual_fields!.units="m";expect(h.observe(controls)?.calculation_invalidations).toContain("utilities");
});
test("invalid chains heads redo cycles groups and recursive snapshots fail closed",()=>{
  const h=createEditTransactions();h.reset(input());h.observe(input(120));
  for(const mutate of [(v:ReturnType<typeof h.export>)=>v.head="missing",(v:ReturnType<typeof h.export>)=>v.redo=[v.head!],(v:ReturnType<typeof h.export>)=>v.transactions[0].parent_id=v.head,(v:ReturnType<typeof h.export>)=>v.transactions[0].before.manual_fields!.units="m"]){const value=h.export();mutate(value);expect(()=>validateLedger(value)).toThrow();}
});
test("invalid or throwing batch updater cannot partially mutate live objects",()=>{
  const live={current:input().manual_fields!.site_objects as BuildingPlacement[]};let publishes=0;
  expect(()=>commitPlacementState(live,prev=>{prev[0].x=999;throw new Error("Rejected");},()=>publishes++)).toThrow();expect(live.current[0].x).toBe(100);
  expect(()=>commitPlacementState(live,prev=>[...prev,prev[0]],()=>publishes++)).toThrow();expect(publishes).toBe(0);
});
test("restoring presentation defaults cannot add an edit or erase redo",()=>{
  const h=createEditTransactions();const first=input();h.reset(first);h.observe(input(120));h.undo();
  const normalized=input();Object.assign(normalized.manual_fields!.site_objects![0],{locked:false,generated:false,systemDependencies:["roads","parking","grading","drainage","utilities"]});
  expect(h.observe(normalized)).toBeNull();expect(h.next).not.toBeNull();
});
