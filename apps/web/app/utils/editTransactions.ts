import type {BuildingPlacement, ProjectInput} from "../types";
import {typeDefinition, validateObjectGroups,geometryIssues} from "./siteObjectDefinition";
import {validateDependencyGraph} from "./dependencyGraph";

export type EditTransaction = {
  id: string; parent_id: string | null; before: ProjectInput; after: ProjectInput;
  affected_object_ids: string[]; reason: string; actor: {kind: "user" | "system"; user_id: string | null};
  calculation_invalidations: string[]; warnings: string[]; timestamp: number;
  undo: "restore_before";
  undo_description?: {kind:string;label:string;object_label:string;count:number;object_ids:string[];detail?:string};
};
export type EditLedger = {version: 1; baseline: ProjectInput; transactions: EditTransaction[]; head: string | null; redo: string[];activity_v1?:import("./dashboardTypes").RecentChange[]};
export const detach = <T>(value:T):T => JSON.parse(JSON.stringify(value));
export function stableJson(value:unknown):string {
  return JSON.stringify(value, (_key,item)=>item && typeof item==="object" && !Array.isArray(item)
    ? Object.fromEntries(Object.keys(item).sort().map(key=>[key,item[key]])) : item);
}
/** Editable inputs only: result status, chat and project identity are not undoable geometry. */
export function editableInput(input:ProjectInput):ProjectInput {
  const meta=input.meta??{};
  return detach({manual_fields:input.manual_fields??{},
    image_path:input.image_path??null, input_mode:input.input_mode??"user",
    meta:{site_inputs:meta.site_inputs??{}, requested_site_program_v1:meta.requested_site_program_v1,
      reactive_edit_policy_preference:meta.reactive_edit_policy_preference,edit_controls_v1:meta.edit_controls_v1}});
}
/** Restore-time defaults are presentation equivalences, not user edits. */
export function semanticEditKey(input:ProjectInput):string {
  const value=editableInput(input);
  for(const key of ["site_objects","buildings"] as const){
    const list=value.manual_fields?.[key];
    if(Array.isArray(list))for(const object of list){if(!object.id)continue;
      object.locked=object.locked===true;object.generated=object.generated===true;
      object.systemDependencies??=["roads","parking","grading","drainage","utilities"];
    }
  }
  return stableJson(value);
}
function validateSnapshot(value:ProjectInput) {
  if (!value || typeof value!=="object" || Array.isArray(value) || !value.manual_fields || typeof value.manual_fields!=="object"||Array.isArray(value.manual_fields)||(value.meta!==undefined&&(!value.meta||typeof value.meta!=="object"||Array.isArray(value.meta)))) throw new Error("Invalid edit snapshot.");
  if (value.canonical_project_v1 || value.meta?.edit_history_v1) throw new Error("Recursive edit history is not allowed.");
  const objects=value.manual_fields.site_objects;
  if (objects!==undefined) {if (!Array.isArray(objects)) throw new Error("Invalid edit objects."); validateObjectGroups(objects as BuildingPlacement[]);validateDependencyGraph(objects as BuildingPlacement[]);}
  JSON.stringify(value,(_key,item)=>{if(typeof item==="number"&&!Number.isFinite(item)) throw new Error("Invalid edit number.");return item;});
}
export function validateLedger(value:unknown):EditLedger {
  const ledger=value as EditLedger;
  if(!ledger||ledger.version!==1||!Array.isArray(ledger.transactions)||!Array.isArray(ledger.redo)||ledger.transactions.length>10000) throw new Error("Invalid saved edit history.");
  validateSnapshot(ledger.baseline);
  if(ledger.activity_v1!==undefined&&(!Array.isArray(ledger.activity_v1)||ledger.activity_v1.length>100||ledger.activity_v1.some(item=>!item||typeof item.id!=="string"||typeof item.label!=="string"||typeof item.detail!=="string"||!Number.isFinite(item.createdAt)||item.undo!==undefined)))throw new Error("Invalid saved activity feed.");
  const known=new Map<string,EditTransaction>();
  for(const tx of ledger.transactions) {
    if(!tx||typeof tx.id!=="string"||!tx.id||known.has(tx.id)||typeof tx.reason!=="string"||!Number.isFinite(tx.timestamp)||tx.undo!=="restore_before"||!tx.actor||!["user","system"].includes(tx.actor.kind)||!(tx.actor.user_id===null||typeof tx.actor.user_id==="string")||![tx.affected_object_ids,tx.calculation_invalidations,tx.warnings].every(list=>Array.isArray(list)&&list.every(v=>typeof v==="string"))) throw new Error("Invalid edit transaction.");
    validateSnapshot(tx.before);validateSnapshot(tx.after);
    const description=tx.undo_description;
    if(description&&(!["add","add_many","delete","delete_many","update","combine","explode","bulk_update"].includes(description.kind)||typeof description.label!=="string"||typeof description.object_label!=="string"||!Number.isInteger(description.count)||description.count<0||!Array.isArray(description.object_ids)||!description.object_ids.every(id=>typeof id==="string")))throw new Error("Invalid undo description.");
    const previous=tx.parent_id===null?ledger.baseline:known.get(tx.parent_id)?.after;
    if(!previous||stableJson(previous)!==stableJson(tx.before)) throw new Error("Broken edit history chain.");
    known.set(tx.id,tx);
  }
  if(ledger.head!==null&&!known.has(ledger.head)) throw new Error("Invalid edit history head.");
  let head=ledger.head;
  for(const id of [...ledger.redo].reverse()) {const tx=known.get(id);if(!tx||tx.parent_id!==head)throw new Error("Invalid redo branch.");head=id;}
  return detach(ledger);
}
export function createEditTransactions() {
  let ledger:EditLedger={version:1,baseline:editableInput({}),transactions:[],head:null,redo:[]};
  let initialized=false;
  const head=()=>ledger.transactions.find(tx=>tx.id===ledger.head)??null;
  const current=()=>head()?.after??ledger.baseline;
  return {
    get last(){return head();}, get next(){return ledger.transactions.find(tx=>tx.id===ledger.redo.at(-1))??null;},
    get entries(){return ledger.transactions;},
    get current(){return detach(current());},
    export(){return detach(ledger);},
    reset(input?:ProjectInput){ledger={version:1,baseline:editableInput(input??{}),transactions:[],head:null,redo:[]};initialized=!!input;},
    restore(value:unknown){ledger=validateLedger(value);initialized=true;},
    observe(input:ProjectInput,reason="Edit workspace",actor:EditTransaction["actor"]={kind:"user",user_id:null},description?:EditTransaction["undo_description"]) {
      const after=editableInput(input); validateSnapshot(after);
      if(!initialized){ledger.baseline=after;initialized=true;return null;}
      const before=current();if(semanticEditKey(before)===semanticEditKey(after))return null;
      const oldObjects=before.manual_fields?.site_objects??[],newObjects=after.manual_fields?.site_objects??[];
      const old=new Map(oldObjects.map(item=>[item.id,item])),next=new Map(newObjects.map(item=>[item.id,item]));
      const ids=[...new Set([...old.keys(),...next.keys()])].filter((id):id is string=>typeof id==="string"&&stableJson(old.get(id))!==stableJson(next.get(id)));
      const systems=new Set(ids.flatMap(id=>[...typeDefinition(old.get(id)?.type).systems,...typeDefinition(next.get(id)?.type).systems]));
      const controls=(snapshot:ProjectInput)=>({...snapshot,manual_fields:{...snapshot.manual_fields,site_objects:undefined,buildings:undefined,site:undefined,site_plan:undefined,project_name:undefined,file_name:undefined}});
      if(stableJson(controls(before))!==stableJson(controls(after))) ["roads","parking","grading","drainage","utilities"].forEach(system=>systems.add(system));
      const tx:EditTransaction={id:`edit-${crypto.randomUUID()}`,parent_id:ledger.head,before:detach(before),after,
        affected_object_ids:ids,reason,actor,timestamp:Date.now(),undo:"restore_before",warnings:ids.flatMap(id=>next.has(id)?geometryIssues(next.get(id) as BuildingPlacement).map(issue=>`${id}: ${issue}`):[]),calculation_invalidations:[...systems]};
      if(description)tx.undo_description=detach(description);
      ledger.transactions.push(tx);ledger.head=tx.id;ledger.redo=[];return tx;
    },
    undo(){const tx=head();if(!tx)return null;ledger.head=tx.parent_id;ledger.redo.push(tx.id);return detach(tx.before);},
    redo(){const id=ledger.redo.pop();if(!id)return null;const tx=ledger.transactions.find(item=>item.id===id)!;ledger.head=id;return detach(tx.after);},
  };
}

/** Preserve existing recovery wording; geometry is always replayed by the shared ledger. */
export function transactionReplayMessage(tx:EditTransaction,direction:"undo"|"redo"):string {
  const d=tx.undo_description;if(!d)return `${direction==="undo"?"Undo":"Redo"}: ${tx.reason}`;
  const name=d.object_label;
  if(direction==="undo"){
    if(d.kind==="add")return `Undo: removed ${name}.`;
    if(d.kind==="delete")return `Undo: restored ${name}.`;
    if(d.kind==="update")return `Undo: restored previous state for ${name}.`;
    if(d.kind==="combine")return `Undo: restored ${d.count} source objects from ${d.label}.`;
    if(d.kind==="explode")return `Undo: restored ${name} after ${d.label}.`;
    return `Undo: ${d.kind==="add_many"?"removed":"restored"} ${d.count} draft objects from ${d.label}.`;
  }
  if(d.kind==="add")return `Redo: restored ${name}.`;
  if(d.kind==="delete")return `Redo: deleted ${name}.`;
  if(d.kind==="update")return `Redo: restored edited state for ${name}.`;
  if(d.kind==="combine")return `Redo: recombined ${d.count} source objects into ${name}.`;
  if(d.kind==="explode")return `Redo: exploded ${name} into ${d.count} source pieces.`;
  return `Redo: ${d.kind==="bulk_update"?"reapplied":d.kind==="delete_many"?"deleted":"restored"} ${d.count} draft objects from ${d.label}.`;
}
