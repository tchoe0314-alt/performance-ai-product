import type { SidePanelKey } from "./workspaceShell";

export const WORKSPACE_STAGE_KEYS = ["brief", "explore", "analyze", "review", "deliver"] as const;
export type WorkspaceStage = typeof WORKSPACE_STAGE_KEYS[number];
export const WORKSPACE_STAGES: Record<WorkspaceStage, {label:string; defaultPanel:SidePanelKey; panels:SidePanelKey[]}> = {
  brief:{label:"Brief",defaultPanel:"site_existing",panels:["site_existing","import_survey","data","standards","templates","files"]},
  explore:{label:"Explore",defaultPanel:"objects",panels:["objects","generate","model","layers","details","libraries"]},
  analyze:{label:"Analyze",defaultPanel:"grading",panels:["grading","drainage","sanitary","water","utilities","roadway","landscape","quantities","jobs","catalogs","system_grading","system_storm","system_sanitary","system_water","system_roadway","system_utilities","system_landscape"]},
  review:{label:"Review",defaultPanel:"analysis",panels:["analysis","dashboard"]},
  deliver:{label:"Deliver",defaultPanel:"deliverables",panels:["deliverables","reports"]},
};
export type WorkspaceStageMemory = {version:1; active:WorkspaceStage; panels:Partial<Record<WorkspaceStage,SidePanelKey>>};
export function stageForPanel(panel:SidePanelKey|null):WorkspaceStage|undefined {
  return WORKSPACE_STAGE_KEYS.find(stage=>panel!==null&&WORKSPACE_STAGES[stage].panels.includes(panel));
}
export function emptyStageMemory():WorkspaceStageMemory {return {version:1,active:"brief",panels:{}};}
export function parseStageMemory(raw:string|null):WorkspaceStageMemory {
  if(!raw)return emptyStageMemory();
  try {
    const value=JSON.parse(raw);
    if(value?.version!==1||!WORKSPACE_STAGE_KEYS.includes(value.active))return emptyStageMemory();
    const memory=emptyStageMemory();memory.active=value.active;
    for(const stage of WORKSPACE_STAGE_KEYS){const panel=value.panels?.[stage];if(WORKSPACE_STAGES[stage].panels.includes(panel))memory.panels[stage]=panel;}
    return memory;
  }catch{return emptyStageMemory();}
}
export function rememberStagePanel(memory:WorkspaceStageMemory,panel:SidePanelKey|null):WorkspaceStageMemory {
  const stage=stageForPanel(panel);
  return stage&&panel?{...memory,active:stage,panels:{...memory.panels,[stage]:panel}}:memory;
}
export function rememberedStagePanel(memory:WorkspaceStageMemory,stage:WorkspaceStage):SidePanelKey {
  return memory.panels[stage]??WORKSPACE_STAGES[stage].defaultPanel;
}
export function stageStorageKey(account:string,project:string,generation:number) {
  return `civora-workspace-stages-v1:${JSON.stringify([account,project||`draft-${generation}`])}`;
}
