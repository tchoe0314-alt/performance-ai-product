import { useEffect, useRef, useState } from "react";
import { environmentStorageKey, parseEnvironment, type EnvironmentScope, type WorkspaceEnvironment } from "../utils/workspaceEnvironment";

/** View-only memory, scoped to this tab. No project input or save queue writes. */
export function useWorkspaceEnvironmentMemory(scope:EnvironmentScope,snapshot:WorkspaceEnvironment,restore:(value:WorkspaceEnvironment)=>void) {
  const previous=useRef<EnvironmentScope|null>(null);
  const keyRef=useRef("");const skipWrite=useRef(false);
  const live=useRef(snapshot);
  const apply=useRef(restore);
  useEffect(()=>{live.current=snapshot;apply.current=restore;},[snapshot,restore]);
  const [hasStoredChoice,setHasStoredChoice]=useState(false);
  const [hydratedKey,setHydratedKey]=useState("");
  const key=environmentStorageKey(scope);
  const {account,project,generation}=scope;
  useEffect(()=>{
    let raw:string|null=null;try{raw=sessionStorage.getItem(key);}catch{/* Session memory is optional. */}
    const old=previous.current;
    const inherit=!raw&&old?.account===account&&old.project!==project&&Boolean(project)&&old.generation===generation;
    previous.current={account,project,generation};keyRef.current=key;skipWrite.current=true;
    // Session-storage hydration must complete before map auto-enable runs.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setHasStoredChoice(Boolean(raw)||inherit);
    setHydratedKey(key);
    apply.current(inherit?live.current:parseEnvironment(raw));
  },[key,account,project,generation]);
  useEffect(()=>{
    if(keyRef.current!==key)return;
    if(skipWrite.current){skipWrite.current=false;return;}
    try{sessionStorage.setItem(key,JSON.stringify(snapshot));}catch{/* Editing still works if browser storage is denied. */}
  },[key,snapshot,hydratedKey]);
  return {hasStoredChoice,ready:hydratedKey===key};
}
