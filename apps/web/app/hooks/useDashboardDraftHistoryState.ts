import { useCallback, useRef, useState } from "react";

import type { DraftUndoAction, RecentChange } from "../utils/dashboardTypes";
import type {ProjectInput} from "../types";
import {createEditTransactions,detach,type EditTransaction} from "../utils/editTransactions";

export function useDashboardDraftHistoryState() {
  const history = useRef(createEditTransactions());
  const hint=useRef("Edit workspace");
  const description=useRef<EditTransaction["undo_description"]>(undefined);
  const notices=useRef<RecentChange[]>([]);
  const hydration=useRef(false);
  const replay=useRef(false);
  const transactionObserverRef=useRef<(transaction:EditTransaction)=>void>(()=>{});
  const [lastDraftAction, setLastDraftAction] = useState<DraftUndoAction | null>(null);
  const lastDraftActionRef = useRef<DraftUndoAction | null>(null);
  const [redoDraftAction, setRedoDraftAction] = useState<DraftUndoAction | null>(null);
  const redoDraftActionRef = useRef<DraftUndoAction | null>(null);
  const [recentChanges, setRecentChanges] = useState<RecentChange[]>([]);
  const [recentChangesOpen, setRecentChangesOpen] = useState(false);

  const publish = useCallback(() => {
    const action=(tx:EditTransaction|null):DraftUndoAction|null=>tx?{action:"workspace_transaction",transaction:tx}:null;
    lastDraftActionRef.current = action(history.current.last);
    redoDraftActionRef.current = action(history.current.next);
    setLastDraftAction(lastDraftActionRef.current);
    setRedoDraftAction(redoDraftActionRef.current);
    const active=new Set<string>();let tx=history.current.last;
    const byId=new Map(history.current.entries.map(item=>[item.id,item]));
    while(tx){active.add(tx.id);tx=byId.get(tx.parent_id??"")??null;}
    const edits:RecentChange[]=[...history.current.entries].reverse().map(tx=>({id:tx.id,type:"object_style_changed",label:tx.reason,
      detail:`${tx.undo_description?.detail??tx.reason}${active.has(tx.id)?"":" · Saved history branch"}`,createdAt:tx.timestamp,
      ...(tx.id===history.current.last?.id?{undo:action(tx)!}:{undoBlockedReason:"Use Undo/Redo on the current branch. This saved entry remains in history."})}));
    setRecentChanges([...edits,...notices.current].sort((a,b)=>b.createdAt-a.createdAt));
  }, []);

  const recordDraftUndoAction = useCallback((action: DraftUndoAction) => {
    if(action.action!=="workspace_transaction"){
      hint.current="label" in action?action.label:`${action.action} ${"object" in action?action.object.label??"object":"objects"}`;
      description.current={kind:action.action,label:"label" in action?action.label:hint.current,
        object_label:action.action==="update"?action.before.label??"Object":"object" in action?action.object.label??"Object":"",
        count:"objects" in action?action.objects.length:action.action==="bulk_update"?action.before.length:action.action==="combine"?action.hiddenSources.length:action.action==="explode"?action.afterSources.length:1,
        object_ids:("objects" in action?action.objects:action.action==="bulk_update"?action.before:action.action==="update"?[action.before]:action.action==="combine"?[action.object,...action.hiddenSources]:action.action==="explode"?[action.object,...action.beforeSources,...action.afterSources]:[action.object]).map(item=>item.id).filter((id):id is string=>typeof id==="string")};
    }
  }, []);

  const recordDraftRedoAction = useCallback((action: DraftUndoAction) => {
    void action;
  }, []);

  const clearDraftUndoAction = useCallback(() => {
  }, []);

  const resetDraftHistory = useCallback(() => {
    history.current.reset();
    hydration.current=false;replay.current=false;
    description.current=undefined;hint.current="Edit workspace";
    notices.current=[];
    lastDraftActionRef.current = null;
    redoDraftActionRef.current = null;
    setLastDraftAction(null);
    setRedoDraftAction(null);
    setRecentChanges([]);
    setRecentChangesOpen(false);
  }, []);

  const recordRecentChange = useCallback((change: Omit<RecentChange, "id" | "createdAt">) => {
    const nextChange: RecentChange = {
      ...change,
      id: `change-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      createdAt: Date.now(),
    };
    if(change.undo&&change.undo.action!=="workspace_transaction"){
      hint.current=change.label;if(description.current)description.current.detail=change.detail;
    }else{notices.current=[nextChange,...notices.current].slice(0,100);publish();}
    return nextChange;
  }, [publish]);

  const observeDraftInput=useCallback((input:ProjectInput)=>{
    if(hydration.current){hydration.current=false;publish();return;}
    if(replay.current){replay.current=false;publish();return;}
    const transaction=history.current.observe(input,hint.current,undefined,description.current);
    if(transaction){transactionObserverRef.current(transaction);hint.current="Edit workspace";description.current=undefined;publish();}
  },[publish]);
  const restoreDraftHistory=useCallback((input:ProjectInput)=>{
    if(input.meta?.edit_history_v1)history.current.restore(input.meta.edit_history_v1);else history.current.reset(input);
    notices.current=history.current.export().activity_v1??[];
    hydration.current=true;hint.current="Edit workspace";description.current=undefined;publish();
  },[publish]);
  const exportDraftHistory=useCallback((input:ProjectInput)=>{const transaction=history.current.observe(input,hint.current,undefined,description.current);if(transaction)transactionObserverRef.current(transaction);hint.current="Edit workspace";description.current=undefined;publish();return {...history.current.export(),activity_v1:detach(notices.current)};},[publish]);
  const replayDraftTransaction=useCallback((direction:"undo"|"redo")=>{
    const input=direction==="undo"?history.current.undo():history.current.redo();
    if(input){replay.current=true;publish();}return input;
  },[publish]);

  return {
    clearDraftUndoAction,
    lastDraftAction,
    lastDraftActionRef,
    recentChanges,
    recentChangesOpen,
    recordDraftRedoAction,
    recordDraftUndoAction,
    recordRecentChange,
    resetDraftHistory,
    redoDraftAction,
    redoDraftActionRef,
    setRecentChangesOpen,
    observeDraftInput,restoreDraftHistory,exportDraftHistory,replayDraftTransaction,transactionObserverRef,
  };
}
