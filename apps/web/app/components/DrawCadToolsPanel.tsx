import type { CadToolName } from "../utils/cadToolTypes";

export type DrawCadToolGroup = {
  title: string;
  tools: Array<{ label: string; tool: CadToolName; hint: string }>;
};

type DrawCadToolsPanelProps = {
  groups: DrawCadToolGroup[];
  onSelectTool: (tool: CadToolName, label: string) => void;
};

export function DrawCadToolsPanel({ groups, onSelectTool }: DrawCadToolsPanelProps) {
  return (
    <details className="rounded-xl border border-slate-200/90 bg-white p-3.5" open data-testid="draw-cad-tools-section">
      <summary className="flex cursor-pointer items-center gap-2.5 text-left">
        <span className="min-w-0 flex-1">
          <span className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Tools</span>
          <span className="mt-1 block text-sm font-semibold leading-5 text-slate-900">
            Choose a tool, then draw on the canvas
          </span>
        </span>
        <span className="rounded-full bg-slate-50 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500">
          Basic first
        </span>
      </summary>
      <div className="mt-4 space-y-3">
        {groups.map((group, groupIndex) => {
          const toolGrid = (
            <div className="grid grid-cols-3 gap-1.5">
              {group.tools.map((item) => (
                <button
                  key={`${group.title}-${item.tool}`}
                  type="button"
                  onClick={() => onSelectTool(item.tool, item.label)}
                  data-testid={`cad-tool-${item.tool}`}
                  className="min-h-[54px] rounded-xl border border-slate-200 bg-white px-2 py-2 text-center transition hover:border-slate-950 hover:bg-white"
                >
                  <span className="block text-[11px] font-semibold uppercase tracking-[0.1em] text-slate-900">
                    {item.label}
                  </span>
                  <span className="mt-1 block text-[10px] font-medium leading-3 text-slate-400">
                    {item.hint}
                  </span>
                </button>
              ))}
            </div>
          );
          if (groupIndex === 0) {
            return (
              <div key={group.title} className="rounded-lg border border-slate-200/90 bg-slate-50/80 p-2">
                {toolGrid}
              </div>
            );
          }
          return (
            <details key={group.title} className="rounded-lg border border-slate-200/90 bg-white p-2">
              <summary className="flex cursor-pointer items-center gap-2 px-1 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                <span className="min-w-0 flex-1">{group.title}</span>
                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] text-slate-500">{group.tools.length}</span>
              </summary>
              <div className="mt-2">{toolGrid}</div>
            </details>
          );
        })}
      </div>
    </details>
  );
}
