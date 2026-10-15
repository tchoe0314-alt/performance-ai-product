import {useEffect,useRef,useState} from "react";
import {getJson,toApiUrl} from "../../lib/api";
import {DEFAULT_WORKSPACE_LAYOUT,parseWorkspaceLayout,type WorkspaceLayout} from "../utils/workspaceLayout";

export function useWorkspaceLayout(userId:string,token?:string|null){
  const [state,setState]=useState({userId:"",layout:{...DEFAULT_WORKSPACE_LAYOUT}});
  const [notice,setNotice]=useState("");
  const edited=useRef(false);
  useEffect(()=>{
    let cancelled=false;edited.current=false;
    const key=`civora-layout-v1:${userId}`;
    let cached:WorkspaceLayout={...DEFAULT_WORKSPACE_LAYOUT};try{cached=parseWorkspaceLayout(JSON.parse(localStorage.getItem(key)??"null"));}catch{}
    // Hydrate view preferences only; never feeds project save/Undo state.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setState({userId,layout:cached});setNotice("");
    if(token)getJson<{layout:WorkspaceLayout}>("/api/account/workspace-layout",{token}).then(value=>{if(!cancelled&&!edited.current)setState({userId,layout:parseWorkspaceLayout(value.layout)});}).catch(()=>{if(!cancelled)setNotice("Using this device’s layout; account sync unavailable.");});
    return ()=>{cancelled=true;};
  },[userId,token]);
  useEffect(()=>{
    if(state.userId!==userId)return;
    try{localStorage.setItem(`civora-layout-v1:${userId}`,JSON.stringify(state.layout));}catch{}
    if(!token||!edited.current)return;
    const controller=new AbortController();
    const timer=setTimeout(()=>{fetch(toApiUrl("/api/account/workspace-layout"),{method:"PUT",headers:{"Content-Type":"application/json",Authorization:`Bearer ${token}`},body:JSON.stringify(state.layout),signal:controller.signal}).then(response=>{if(!response.ok)throw new Error();setNotice("");}).catch(()=>{if(!controller.signal.aborted)setNotice("Layout kept on this device; account sync unavailable.");});},400);
    return ()=>{clearTimeout(timer);controller.abort();};
  },[state,userId,token]);
  const layout=state.userId===userId?state.layout:DEFAULT_WORKSPACE_LAYOUT;
  const update=(changes:Partial<WorkspaceLayout>)=>{edited.current=true;setState(previous=>({userId,layout:parseWorkspaceLayout({...((previous.userId===userId)?previous.layout:DEFAULT_WORKSPACE_LAYOUT),...changes})}));};
  return {layout,update,notice,reset:()=>update({...DEFAULT_WORKSPACE_LAYOUT})};
}
