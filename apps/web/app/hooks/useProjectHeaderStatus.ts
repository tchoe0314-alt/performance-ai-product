import { useEffect, useState } from "react";
import { getJson } from "../../lib/api";

/** Network availability and API reachability are different signals. */
export function useProjectHeaderStatus(projectId: string, token: string | null, revision?: string, calculation?: unknown) {
  const [connection, setConnection] = useState("Checking connection");
  const [history, setHistory] = useState<{projectId:string; timestamp?:number; failed?:boolean}>({projectId:""});
  useEffect(() => {
    let cancelled = false;
    let controller: AbortController | undefined;
    const check = async () => {
      controller?.abort();
      controller = new AbortController();
      const active = controller;
      if (!navigator.onLine) { setConnection("Offline"); return; }
      const timeout = window.setTimeout(() => active.abort(), 6000);
      try {
        await getJson("/api/health", {signal:active.signal});
        if (!cancelled && active===controller) setConnection("Online");
      } catch {
        if (!cancelled && active===controller) setConnection(navigator.onLine?"API unavailable":"Offline");
      } finally { window.clearTimeout(timeout); }
    };
    void check();
    const timer = window.setInterval(() => { if (!document.hidden) void check(); }, 30000);
    window.addEventListener("online", check); window.addEventListener("offline", check);
    return () => { cancelled=true; controller?.abort(); window.clearInterval(timer); window.removeEventListener("online",check); window.removeEventListener("offline",check); };
  }, []);
  useEffect(() => {
    if (!projectId || !token || projectId.startsWith("demo")) return;
    const controller = new AbortController();
    const timer = window.setTimeout(()=>controller.abort(),6000);
    let cancelled=false;
    void getJson<{last_successful_calculation_at?:number|null;calculations:Array<{created_at:number;successful?:boolean}>}>(`/api/projects/${encodeURIComponent(projectId)}/calculations`,{token,signal:controller.signal})
      .then(data=> {if(!cancelled)setHistory({projectId,timestamp:data.last_successful_calculation_at ?? data.calculations.filter(entry=>entry.successful===true).map(entry=>entry.created_at).filter(Number.isFinite).sort((a,b)=>b-a)[0]});})
      .catch(()=> {if(!cancelled)setHistory({projectId,failed:true});})
      .finally(()=>window.clearTimeout(timer));
    return ()=>{cancelled=true;controller.abort();window.clearTimeout(timer);};
  }, [projectId,token,revision,calculation,connection]);
  return { connection, lastCalculation:history.projectId===projectId?history:undefined };
}
