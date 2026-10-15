import {useRef} from "react";
type Props={label:string;value:number;min:number;max:number;vertical?:boolean;reverse?:boolean;onChange:(value:number)=>void};
export function WorkspaceResizeHandle({label,value,min,max,vertical=false,reverse=false,onChange}:Props){
  const start=useRef<{position:number;value:number}|null>(null);
  const change=(next:number)=>onChange(Math.round(Math.min(max,Math.max(min,next))));
  return <div role="separator" tabIndex={0} aria-label={label} aria-orientation={vertical?"horizontal":"vertical"} aria-valuemin={min} aria-valuemax={max} aria-valuenow={value}
    className={vertical?"civora-layout-horizontal-resizer":"civora-layout-resizer"}
    onPointerDown={event=>{if(event.button!==0)return;event.preventDefault();event.currentTarget.setPointerCapture(event.pointerId);start.current={position:vertical?event.clientY:event.clientX,value};}}
    onPointerMove={event=>{if(start.current)change(start.current.value+((vertical?event.clientY:event.clientX)-start.current.position)*(reverse?-1:1));}}
    onPointerUp={()=>{start.current=null;}} onPointerCancel={()=>{start.current=null;}} onLostPointerCapture={()=>{start.current=null;}}
    onKeyDown={event=>{const direction=vertical?(event.key==="ArrowUp"?1:event.key==="ArrowDown"?-1:0):(event.key==="ArrowRight"?1:event.key==="ArrowLeft"?-1:0);if(direction){event.preventDefault();event.stopPropagation();change(value+direction*10*(reverse&&!vertical?-1:1));}else if(event.key==="Home"||event.key==="End"){event.preventDefault();event.stopPropagation();change(event.key==="Home"?min:max);}}}/>
}
