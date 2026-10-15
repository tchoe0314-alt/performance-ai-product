export type WorkspaceLayout={version:1;mode:"simple"|"professional";leftWidth:number;rightWidth:number;deltaHeight:number;leftVisible:boolean;rightVisible:boolean;deltaVisible:boolean};
export const DEFAULT_WORKSPACE_LAYOUT:WorkspaceLayout={version:1,mode:"simple",leftWidth:260,rightWidth:320,deltaHeight:64,leftVisible:false,rightVisible:false,deltaVisible:false};
export function parseWorkspaceLayout(raw:unknown):WorkspaceLayout {
  if(!raw||typeof raw!=="object")return {...DEFAULT_WORKSPACE_LAYOUT};
  const value=raw as Record<string,unknown>;
  if(value.version!==1||!["simple","professional"].includes(String(value.mode)))return {...DEFAULT_WORKSPACE_LAYOUT};
  for(const [key,low,high]of [["leftWidth",220,440],["rightWidth",280,480],["deltaHeight",48,160]] as const)if(typeof value[key]!=="number"||!Number.isInteger(value[key])||value[key]<low||value[key]>high)return {...DEFAULT_WORKSPACE_LAYOUT};
  for(const key of ["leftVisible","rightVisible","deltaVisible"] as const)if(typeof value[key]!=="boolean")return {...DEFAULT_WORKSPACE_LAYOUT};
  return Object.fromEntries(Object.keys(DEFAULT_WORKSPACE_LAYOUT).map(key=>[key,value[key]])) as WorkspaceLayout;
}
