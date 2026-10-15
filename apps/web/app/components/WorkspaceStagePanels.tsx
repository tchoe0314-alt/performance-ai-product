import { sidePanelCopy, type SidePanelKey } from "../utils/workspaceShell";
import { WORKSPACE_STAGES, stageForPanel, type WorkspaceStage } from "../utils/workspaceStages";

export function WorkspaceStagePanels({stage,panel,onOpenPanel}: {stage:WorkspaceStage;panel:SidePanelKey|null;onOpenPanel:(panel:SidePanelKey)=>void}) {
  if(stageForPanel(panel)!==stage)return null; // Chat, Projects, Help and Settings do not replace a stage's remembered panel.
  return <div className="shrink-0 border-b border-slate-100 px-3 py-2">
    <label className="sr-only" htmlFor="workspace-stage-panel">{WORKSPACE_STAGES[stage].label} tools</label>
    <select id="workspace-stage-panel" data-testid="workspace-stage-panel" value={panel??""} onChange={event=>onOpenPanel(event.target.value as SidePanelKey)}
      className="w-full min-w-0 rounded-md border border-slate-200 bg-white px-2 py-1.5 text-xs text-slate-700">
      {WORKSPACE_STAGES[stage].panels.map(key=><option key={key} value={key}>{key==="objects"?"Draw":sidePanelCopy[key].title}</option>)}
    </select>
  </div>;
}
