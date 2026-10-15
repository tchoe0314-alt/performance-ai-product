import {useState,type ReactNode,type CSSProperties} from "react";
import {PanelsTopLeft} from "lucide-react";
import {useWorkspaceLayout} from "../hooks/useWorkspaceLayout";
import {WorkspaceResizeHandle} from "./WorkspaceResizeHandle";

type Props = {
  userId?:string;
  token?:string|null;
  briefChat?:ReactNode;
  inspectorHealth?:ReactNode;
  delta?:ReactNode;
  onCollapseTools?:()=>void;
  toolPanelContext?:string|null;
  onCancelActiveTool: () => void;
  statusSummary: string;
  toasts: ReactNode;
  header: ReactNode;
  leftRail: ReactNode;
  rightPanel: ReactNode;
  canvas: ReactNode;
  shortcuts: ReactNode;
  commandBar: ReactNode;
};

/** Presentation-only frame: responsive regions and Escape, never project/geometry state. */
export function DashboardWorkspaceFrame(props: Props) {
  const {layout,update,reset,notice}=useWorkspaceLayout(props.userId??"demo",props.token);
  const [focus,setFocus]=useState(false);
  const [mobilePanel,setMobilePanel]=useState("brief");
  const left=layout.leftVisible&&!focus,right=layout.rightVisible&&!focus,delta=layout.deltaVisible&&!focus;
  const rightPanel=left&&props.toolPanelContext==="chat"?null:props.rightPanel;
  const style={"--civora-layout-left-width":`min(${layout.leftWidth}px,26vw)`,"--civora-shell-drawer-width":`min(${layout.rightWidth}px,32vw)`,"--civora-layout-delta-height":`${layout.deltaHeight}px`} as CSSProperties;
  return (
    <div style={style} data-testid="workspace-layout-root" data-layout-mobile-panel={mobilePanel} data-layout-left={left} data-layout-right={right} data-layout-delta={delta} data-layout-focus={focus} data-layout-mode={layout.mode} className="civora-app-bg min-h-screen text-[var(--civora-text)]" onKeyDownCapture={event => {
      if (event.key !== "Escape") return;
      if((event.target as HTMLElement).closest('dialog,[data-layout-controls]'))return;
      event.preventDefault();
      props.onCancelActiveTool();
    }}>
      {props.toasts}
      <div className="flex min-h-screen flex-col">
        {props.header}
        <details data-layout-controls className="civora-layout-controls" data-testid="workspace-layout-controls" onKeyDown={event=>{if(event.key==="Escape"){event.preventDefault();event.stopPropagation();event.currentTarget.open=false;event.currentTarget.querySelector<HTMLElement>("summary")?.focus();}}}>
          <summary aria-label="Workspace layout" title="Workspace layout" className="flex h-8 w-8 cursor-pointer list-none items-center justify-center rounded-lg border border-slate-200 bg-white shadow-sm"><PanelsTopLeft size={16}/></summary>
          <div className="mt-1 w-56 space-y-2 rounded-lg border border-slate-200 bg-white p-3 text-xs shadow-lg">
            <label className="flex items-center justify-between">Mode<select aria-label="Workspace mode" value={layout.mode} onChange={event=>{const professional=event.target.value==="professional";update({mode:professional?"professional":"simple",leftVisible:professional,rightVisible:professional,deltaVisible:professional});}}><option value="simple">Simple</option><option value="professional">Professional</option></select></label>
            {([["Brief","leftVisible"],["Inspect","rightVisible"],["Live changes","deltaVisible"]]as const).map(([label,key])=><label key={key} className="flex items-center justify-between">{label}<input type="checkbox" checked={layout[key]} onChange={event=>{if(key==="rightVisible"&&!event.target.checked)props.onCollapseTools?.();update({[key]:event.target.checked});}}/></label>)}
            {([["Brief width","leftWidth",220,440],["Inspector width","rightWidth",280,480],["Delta height","deltaHeight",48,160]]as const).map(([label,key,min,max])=><label key={key} className="block">{label}<input aria-label={label} type="range" min={min} max={max} value={layout[key]} onChange={event=>update({[key]:Number(event.target.value)})} className="block w-full"/></label>)}
            <label className="block lg:hidden">Mobile panel<select aria-label="Mobile supporting panel" value={mobilePanel} onChange={event=>setMobilePanel(event.target.value)}><option value="brief">Brief</option><option value="inspector">Inspect</option><option value="delta">Live changes</option></select></label>
            <button type="button" aria-pressed={focus} onClick={()=>setFocus(value=>!value)} className="block w-full rounded border p-2">{focus?"Exit focus":"Full canvas"}</button>
            <button type="button" onClick={()=>{reset();setFocus(false);props.onCollapseTools?.();}} className="block w-full rounded border p-2">Reset layout</button>
            {notice&&<p role="status">{notice}</p>}
          </div>
        </details>
        <div data-testid="project-status-summary" className="sr-only" aria-live="polite">{props.statusSummary}</div>
        <div className="relative h-[calc(100svh-52px)] min-h-0 w-full max-w-full overflow-hidden lg:h-[calc(100vh-52px)]">
          {props.leftRail}
          {rightPanel}
          {left&&<aside aria-label="Brief and chat" data-testid="workspace-brief-chat" className="civora-layout-left-panel"><div className="flex items-center justify-between border-b px-3 py-2 text-xs font-medium"><span>Brief</span><button type="button" aria-label="Hide brief and chat" onClick={()=>update({leftVisible:false})}>Hide</button></div><div className="min-h-0 flex-1 overflow-y-auto p-3">{props.briefChat}</div><WorkspaceResizeHandle label="Resize brief and chat" value={layout.leftWidth} min={220} max={440} onChange={leftWidth=>update({leftWidth})}/></aside>}
          {right&&!rightPanel&&<aside aria-label="Inspector and health" data-testid="workspace-inspector-health" className="civora-layout-right-panel"><div className="flex items-center justify-between border-b px-3 py-2 text-xs font-medium"><span>Inspect</span><button type="button" aria-label="Hide inspector and health" onClick={()=>update({rightVisible:false})}>Hide</button></div><div className="min-h-0 flex-1 overflow-y-auto p-3">{props.inspectorHealth}</div><WorkspaceResizeHandle label="Resize inspector and health" value={layout.rightWidth} min={280} max={480} reverse onChange={rightWidth=>update({rightWidth})}/></aside>}
          {!focus&&rightPanel&&<div className="civora-existing-panel-resizer"><WorkspaceResizeHandle label="Resize tools panel" value={layout.rightWidth} min={280} max={480} reverse onChange={rightWidth=>update({rightWidth})}/></div>}
          {props.canvas}
          {props.shortcuts}
          {props.commandBar}
          {delta&&<section aria-label="Live Delta" data-testid="workspace-live-delta" className="civora-layout-delta"><WorkspaceResizeHandle label="Resize Live Delta" value={layout.deltaHeight} min={48} max={160} vertical reverse onChange={deltaHeight=>update({deltaHeight})}/><div className="flex items-center justify-between gap-2"><strong className="text-xs">Live changes</strong><button type="button" aria-label="Hide Live Delta" onClick={()=>update({deltaVisible:false})} className="text-xs">Hide</button></div>{props.delta}</section>}
        </div>
      </div>
    </div>
  );
}
