"use client";

import { useEffect, useRef, useState } from "react";
import { MoreHorizontal } from "lucide-react";
import { getJson } from "../../lib/api";

type History = {creator_name:string;entries:Array<{id:string;reason:string;timestamp:number;actor_name:string;is_current:boolean}>};
type Props = {projectId?:string;token?:string|null;onShare:()=>void;onReport:()=>void;onDxf:()=>void;onLandxml:()=>void;onSettings:()=>void;onWorkspaceSettings?:()=>void};

/** Project actions reuse existing workflows; opening a menu never saves or runs. */
export function WorkspaceProjectActions({projectId,token,onShare,onReport,onDxf,onLandxml,onSettings,onWorkspaceSettings}:Props){
  const [historyOpen,setHistoryOpen]=useState(false);
  const [history,setHistory]=useState<History|null>(null);
  const [error,setError]=useState("");
  const dialog=useRef<HTMLDialogElement>(null);
  useEffect(()=>{if(historyOpen&&!dialog.current?.open)dialog.current?.showModal();},[historyOpen]);
  useEffect(()=>{
    if(!historyOpen||!projectId||!token)return;
    let cancelled=false;
    getJson<History>(`/api/projects/${encodeURIComponent(projectId)}/edit-history`,{token}).then(value=>{if(!cancelled)setHistory(value);}).catch(reason=>{if(!cancelled)setError(reason instanceof Error?reason.message:"History could not load.");});
    return ()=>{cancelled=true;};
  },[historyOpen,projectId,token]);
  const select=(event:React.MouseEvent<HTMLButtonElement>,action:()=>void)=>{event.currentTarget.closest("details")?.removeAttribute("open");action();};
  return <>
    <details className="relative" data-testid="workspace-project-actions">
      <summary className="civora-header-icon-button cursor-pointer list-none" aria-label="Project actions" title="Project actions"><MoreHorizontal className="h-4 w-4" /></summary>
      <div className="fixed right-2 top-[60px] w-48 max-h-[60dvh] overflow-y-auto rounded-lg border border-slate-200 bg-white p-1 shadow-lg">
        {([["Share",onShare],["Generate report",onReport],["Export DXF",onDxf],["Edit history",()=>{setHistory(null);setError("");setHistoryOpen(true);}],["Project settings",onSettings]] as const).map(([label,action])=><button key={label} type="button" disabled={label==="Share"&&(!projectId||!token)} onClick={event=>select(event,action)} className="block w-full rounded px-3 py-2 text-left text-xs hover:bg-slate-100 disabled:opacity-40">{label}</button>)}
        <button type="button" title="Supported pipe-network review data only." onClick={event=>select(event,onLandxml)} className="block w-full rounded px-3 py-2 text-left text-xs hover:bg-slate-100">Export LandXML</button>
        {onWorkspaceSettings&&<button type="button" onClick={event=>select(event,onWorkspaceSettings)} className="block w-full rounded px-3 py-2 text-left text-xs hover:bg-slate-100">Workspace settings</button>}
      </div>
    </details>
    {historyOpen&&<dialog ref={dialog} onCancel={()=>setHistoryOpen(false)} onKeyDownCapture={event=>{if(event.key==="Escape"){event.preventDefault();event.stopPropagation();setHistoryOpen(false);}}} aria-label="Edit history" className="fixed inset-0 m-auto max-h-[80dvh] w-[calc(100%-1.5rem)] max-w-lg overflow-y-auto rounded-xl bg-white p-4 shadow-xl backdrop:bg-slate-950/30" data-testid="project-edit-history">
        <div className="flex items-center justify-between"><h2 className="text-sm font-semibold">Edit history</h2><button autoFocus type="button" onClick={()=>setHistoryOpen(false)} className="rounded px-2 py-1 text-xs">Close</button></div>
        {!projectId||!token?<p className="mt-3 text-xs">Save and sign in to view saved history.</p>:error?<p role="alert" className="mt-3 text-xs">{error}</p>:!history?<p className="mt-3 text-xs">Loading…</p>:<>
          <p className="mt-2 text-xs text-slate-500">Creator: {history.creator_name}</p>
          <p className="mt-1 text-xs text-slate-500">Saved edits. Unsaved changes appear after saving.</p>
          <ol className="mt-3 space-y-2">{history.entries.map(entry=><li key={entry.id} className="rounded border border-slate-200 p-2 text-xs"><p>{entry.reason}{entry.is_current?" · Current":""}</p><p className="mt-1 text-slate-500">{entry.actor_name} · {new Date(entry.timestamp).toLocaleString()}</p></li>)}</ol>
          {!history.entries.length&&<p className="mt-3 text-xs">No saved edits yet.</p>}
        </>}
    </dialog>}
  </>;
}
