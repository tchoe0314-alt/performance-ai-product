"use client";

import { useEffect, useRef, useState } from "react";
import { ChevronDown, X } from "lucide-react";
import type { ProjectIdentity } from "../types";

export type ProjectHeaderDetailsProps = {
  projectKey:string; name:string; identity?:ProjectIdentity; saveStatus:string; connection:string;
  revision?:string; savedAt?:number; calculatedAt?:number; calculationUnavailable?:boolean;
  health:string; healthDetail:string; editable:boolean;
  onSave:(name:string,identity:ProjectIdentity)=>Promise<boolean>;
};
export function headerTimestamp(value?:number) {
  const date=new Date(typeof value==="number"?value*1000:NaN);
  return typeof value==="number"&&value>0&&Number.isFinite(date.getTime())?date.toLocaleString():"Not recorded";
}
const empty:ProjectIdentity={client:"",siteId:"",address:"",parcel:"",stage:""};
const fields:Array<[keyof ProjectIdentity,string,number]>=[["client","Client / ID",160],["siteId","Site ID",160],["address","Address",400],["parcel","APN / parcel",160],["stage","Project stage",80]];

export default function ProjectHeaderDetails(props:ProjectHeaderDetailsProps) {
  const [open,setOpen]=useState(false);
  const [name,setName]=useState(props.name);
  const [identity,setIdentity]=useState({...empty,...props.identity});
  const [pending,setPending]=useState(false);
  const [error,setError]=useState("");
  const root=useRef<HTMLDivElement>(null);
  const button=useRef<HTMLButtonElement>(null);
  const nameInput=useRef<HTMLInputElement>(null);
  const closeButton=useRef<HTMLButtonElement>(null);
  const generation=useRef(0);
  const dirty=name!==props.name||JSON.stringify(identity)!==JSON.stringify({...empty,...props.identity});
  useEffect(()=>{generation.current++;setOpen(false);setPending(false);setError("");},[props.projectKey]);
  useEffect(()=>{
    if(!open)return;
    if(props.editable)nameInput.current?.focus();else closeButton.current?.focus();
    const close=(event:PointerEvent)=>{if(!pending&&!root.current?.contains(event.target as Node))setOpen(false);};
    document.addEventListener("pointerdown",close);
    return ()=>document.removeEventListener("pointerdown",close);
  },[open,pending,props.editable]);
  const close=()=>{if(!pending){setOpen(false);button.current?.focus();}};
  return <div ref={root} className="relative shrink-0" onKeyDown={event=>{if(event.key==="Escape"){event.preventDefault();event.stopPropagation();close();}}}>
    <button ref={button} type="button" className="civora-header-icon-button" aria-label="Project details" title="Project details"
      aria-expanded={open} aria-controls="project-header-details" onClick={()=>{
        if(open){close();return;}setName(props.name);setIdentity({...empty,...props.identity});setError("");setOpen(true);
      }}><ChevronDown className="h-4 w-4" /></button>
    {open&&<section id="project-header-details" aria-label="Project details" role="region" data-testid="project-header-details"
      className="fixed left-2 right-2 top-[58px] z-[1050] mx-auto max-h-[calc(100dvh-70px)] max-w-[420px] overflow-y-auto rounded-xl border border-slate-200 bg-white p-3 shadow-xl sm:left-auto sm:right-4 sm:w-[380px]">
      <div className="mb-3 flex items-center justify-between"><h2 className="text-sm font-semibold">Project details</h2><button ref={closeButton} type="button" className="civora-header-icon-button" aria-label="Close project details" onClick={close} disabled={pending}><X className="h-4 w-4" /></button></div>
      <form onSubmit={async event=>{
        event.preventDefault();if(pending||!props.editable)return;
        const attempt=generation.current;setPending(true);setError("");
        try {const ok=await props.onSave(name.trim(),Object.fromEntries(Object.entries(identity).map(([key,value])=>[key,value.trim()])) as ProjectIdentity);
          if(attempt!==generation.current)return;
          if(ok){setOpen(false);button.current?.focus();}else setError("Not saved. Your details are still here. Retry when ready.");
        }catch{if(attempt===generation.current)setError("Could not save. Your details are still here.");}
        finally{if(attempt===generation.current)setPending(false);}
      }}>
        <fieldset disabled={!props.editable||pending} className="grid grid-cols-2 gap-2">
          <label className="col-span-2 text-xs text-slate-600">Project name<input ref={nameInput} required maxLength={160} value={name} onChange={event=>setName(event.target.value)} className="mt-1 w-full rounded-md border border-slate-300 px-2 py-2 text-sm text-slate-900" /></label>
          {fields.map(([key,label,maxLength])=><label key={key} className={`${key==="address"?"col-span-2":""} text-xs text-slate-600`}>{label}<input maxLength={maxLength} value={identity[key]} onChange={event=>setIdentity(previous=>({...previous,[key]:event.target.value}))} className="mt-1 w-full rounded-md border border-slate-300 px-2 py-2 text-sm text-slate-900" /></label>)}
        </fieldset>
        <p className="my-2 text-xs text-slate-500">Details don’t change map context.</p>
        <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-2 border-t border-slate-100 pt-3 text-xs">
          {[["Status",pending?"Saving":dirty?"Unsaved details":props.saveStatus],["Connection",props.connection],["Active revision",props.revision||"Not saved"],["Last save",headerTimestamp(props.savedAt)],["Last calculation",props.calculationUnavailable?"Unavailable":headerTimestamp(props.calculatedAt)],["Project health",props.health]].map(([label,value])=><div key={label} className="contents"><dt className="text-slate-500">{label}</dt><dd className="break-words text-slate-800" title={label==="Project health"?props.healthDetail:undefined}>{value}</dd></div>)}
        </dl>
        {error&&<p role="alert" className="mt-2 text-xs text-red-700">{error}</p>}
        {!props.editable&&<p className="mt-2 text-xs text-slate-500">Sign in to save project details.</p>}
        <div className="mt-3 flex justify-end gap-2"><button type="button" disabled={pending} onClick={close} className="rounded-md border px-3 py-2 text-xs">Cancel</button><button disabled={!props.editable||pending||!name.trim()} className="rounded-md bg-slate-900 px-3 py-2 text-xs text-white">{pending?"Saving…":"Save details"}</button></div>
      </form>
    </section>}
  </div>;
}
