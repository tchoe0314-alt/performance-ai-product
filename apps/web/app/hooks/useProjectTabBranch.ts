import { useCallback, useEffect, useRef, useState } from "react";
import { hasOtherProjectTab, projectTabLeaseKey } from "../utils/projectTabLease";
import { liveInputFingerprint } from "../utils/liveCalculationFreshness";
import type { ProjectInput } from "../types";

export type TabBranchChoice = "copy" | "replace" | "cancel";
export function projectEditKey(input: ProjectInput) {
  // UI builders have optional undefined fields; the backend sees JSON instead.
  input = JSON.parse(JSON.stringify(input)) as ProjectInput;
  const identity = input.meta?.project_identity_v1;
  return JSON.stringify([liveInputFingerprint(input), input.prompt_text, input.manual_fields?.project_name,
    input.manual_fields?.file_name, input.meta?.edit_controls_v1, [identity?.client??"",identity?.siteId??"",identity?.address??"",identity?.parcel??"",identity?.stage??""], input.meta?.chat_thread?.filter(message => message.role === "user").map(message => message.content)]);
}

export function useProjectTabBranch(projectId: string, getInput: () => ProjectInput, generation: number) {
  const tabId = useRef<string>("");
  const baseline = useRef({ projectId: "", generation: -1, key: "" });
  const permitted = useRef("");
  const paused = useRef("");
  const pending = useRef<{ projectId: string; resolve: (choice: TabBranchChoice) => void } | null>(null);
  const [questionProject, setQuestionProject] = useState("");
  useEffect(() => {
    if (!projectId) return;
    if(!tabId.current){
      const navigation=performance.getEntriesByType("navigation")[0] as PerformanceNavigationTiming|undefined;
      let previous:string|null=null;
      try{previous=sessionStorage.getItem("civora-project-page-id-v1");}catch{}
      tabId.current=navigation?.type==="reload"&&previous?previous:crypto.randomUUID();
      try{sessionStorage.setItem("civora-project-page-id-v1",tabId.current);}catch{}
    }
    baseline.current = { projectId, generation, key: projectEditKey(getInput()) };
    permitted.current = "";
    paused.current = "";
    const storageKey = projectTabLeaseKey(projectId, tabId.current);
    let closing=false;
    const announce = () => { if(closing)return;try { localStorage.setItem(storageKey, String(Date.now())); } catch { /* API revisions still protect writes. */ } };
    announce();
    const interval = window.setInterval(announce, 10_000);
    const remove = () => { try { localStorage.removeItem(storageKey); } catch { /* Storage unavailable. */ } };
    const leave=()=>{closing=true;remove();};
    const resume=()=>{closing=false;announce();};
    const protectPendingEdits = (event: BeforeUnloadEvent) => {
      if (pending.current || paused.current === projectId) {
        event.preventDefault();
        event.returnValue = "";
      }
    };
    window.addEventListener("pagehide", leave);
    window.addEventListener("pageshow", resume);
    window.addEventListener("beforeunload", protectPendingEdits);
    document.addEventListener("visibilitychange", announce);
    return () => {
      window.clearInterval(interval); remove();
      window.removeEventListener("pagehide", leave);
      window.removeEventListener("pageshow", resume);
      window.removeEventListener("beforeunload", protectPendingEdits);
      document.removeEventListener("visibilitychange", announce);
      pending.current?.resolve("cancel"); pending.current = null;
    };
  // The input getter is live; opening/changing a workspace establishes its baseline once.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, generation]);
  const choose = useCallback((id: string) => new Promise<TabBranchChoice>(resolve => {
    pending.current?.resolve("cancel");
    pending.current = { projectId: id, resolve }; setQuestionProject(id);
  }), []);
  const answer = (choice: TabBranchChoice) => {
    if (choice === "replace") permitted.current = pending.current?.projectId ?? "";
    paused.current = choice === "cancel" ? pending.current?.projectId ?? "" : "";
    pending.current?.resolve(choice); pending.current = null; setQuestionProject("");
  };
  const hasEdits = useCallback((id: string, input?:ProjectInput) => baseline.current.projectId !== id || projectEditKey(input ?? getInput()) !== baseline.current.key, [getInput]);
  const markSaved = useCallback((id:string,input:ProjectInput,savedGeneration:number) => {
    // Advance to the exact saved request, never to a newer unsaved live edit.
    // Otherwise Undo followed by Redo back to the load-time geometry can be skipped.
    if(baseline.current.projectId===id&&baseline.current.generation===savedGeneration)baseline.current.key=projectEditKey(input);
  }, []);
  const beforeSave = useCallback(async (id: string, silent: boolean, proposedInput?: ProjectInput): Promise<TabBranchChoice | null> => {
    if (paused.current === id) return silent ? "cancel" : await choose(id);
    if (permitted.current === id || baseline.current.projectId !== id) return null;
    if (projectEditKey(proposedInput ?? getInput()) === baseline.current.key) return null;
    try {
      if (hasOtherProjectTab(localStorage, id, tabId.current)) return await choose(id);
    } catch { /* Backend optimistic revision check is the independent safety net. */ }
    return null;
  }, [choose, getInput]);
  return { questionProject, answer, choose, beforeSave, hasEdits, markSaved };
}
