import { useEffect, useRef, useState } from "react";
import type { SidePanelKey } from "../utils/workspaceShell";
import { emptyStageMemory, parseStageMemory, rememberStagePanel, rememberedStagePanel, stageForPanel, stageStorageKey, type WorkspaceStage, type WorkspaceStageMemory } from "../utils/workspaceStages";

/** Per-tab view preferences only. Never writes project input or calculation state. */
export function useWorkspaceStages({account,project,generation,panel,onOpenPanel}: {
  account:string; project:string; generation:number; panel:SidePanelKey|null; onOpenPanel:(panel:SidePanelKey)=>void;
}) {
  const [memory,setMemory]=useState<WorkspaceStageMemory>(emptyStageMemory);
  const state=useRef(memory);
  const scope=useRef<{account:string;project:string;generation:number;key:string}|null>(null);
  const observed=useRef<SidePanelKey|null>(null);
  const open=useRef(onOpenPanel);open.current=onOpenPanel;
  const publish=(next:WorkspaceStageMemory)=>{
    state.current=next;setMemory(next);
    if(!scope.current)return;
    try{sessionStorage.setItem(scope.current.key,JSON.stringify(next));}catch{/* Storage denied: this tab still remembers in memory. */}
  };
  useEffect(()=>{
    if(!account)return;
    const key=stageStorageKey(account,project,generation);
    const previous=scope.current;
    let raw:string|null=null;
    try{raw=sessionStorage.getItem(key);}catch{/* View preferences must not block editing. */}
    // First-save and first-edit copies keep the view. Opening another project
    // changes the workspace generation and must hydrate its own preferences.
    const inherit=!raw&&previous?.account===account&&previous.project!==project&&Boolean(project)&&previous.generation===generation;
    const next=inherit?state.current:parseStageMemory(raw);
    scope.current={account,project,generation,key};observed.current=panel;
    state.current=next;setMemory(next);
    // Keep global utilities (especially Projects and its restore/copy feedback)
    // open during project changes. A fresh page may restore its saved stage.
    if((raw||(previous&&!inherit&&panel))&&(!previous||!panel||stageForPanel(panel)))open.current(rememberedStagePanel(next,next.active));
    else if(!inherit)publish(rememberStagePanel(next,panel));
    else publish(next);
    // Only a workspace/account transition hydrates preferences, not every panel change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  },[account,project,generation]);
  useEffect(()=>{
    if(!scope.current||scope.current.account!==account||scope.current.project!==project||scope.current.generation!==generation||observed.current===panel)return;
    observed.current=panel;
    const next=rememberStagePanel(state.current,panel);
    if(next!==state.current)publish(next);
    // publish updates the live ref; its identity must not make navigation an effect loop.
  },[panel,account,project,generation]);
  const selectStage=(stage:WorkspaceStage)=>{
    const target=rememberedStagePanel(state.current,stage);
    publish({...state.current,active:stage});
    open.current(target);
  };
  return {activeStage:memory.active,selectStage};
}
