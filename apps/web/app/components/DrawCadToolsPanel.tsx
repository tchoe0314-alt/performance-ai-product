import type { CadToolName } from "../utils/cadToolTypes";
import type { LucideIcon } from "lucide-react";
import {
  BoxSelect,
  Circle,
  Copy,
  Hand,
  MapPin,
  MousePointer2,
  Move,
  MoveDiagonal2,
  RotateCw,
  Ruler,
  Scissors,
  Shapes,
  Square,
  Spline,
  Trash2,
  Type,
} from "lucide-react";

export type DrawCadToolGroup = {
  title: string;
  tools: Array<{ label: string; tool: CadToolName; hint: string }>;
};

type DrawCadToolsPanelProps = {
  groups: DrawCadToolGroup[];
  onSelectTool: (tool: CadToolName, label: string) => void;
};

const TOOL_ICONS: Partial<Record<CadToolName, LucideIcon>> = {
  select: MousePointer2,
  pan: Hand,
  line: Spline,
  polyline: Spline,
  area: Shapes,
  box: Square,
  point: MapPin,
  circle: Circle,
  text: Type,
  dimension: Ruler,
  move: Move,
  copy: Copy,
  rotate: RotateCw,
  scale: MoveDiagonal2,
  trim: Scissors,
  extend: MoveDiagonal2,
  delete: Trash2,
};

export function DrawCadToolsPanel({ groups, onSelectTool }: DrawCadToolsPanelProps) {
  return (
    <section className="rounded-[8px] border border-slate-200/90 bg-white p-3" data-testid="draw-cad-tools-section">
      <div className="flex items-center gap-2.5 text-left">
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-semibold text-slate-900">Tools</span>
          <span className="mt-0.5 block text-xs leading-4 text-slate-500">
            Choose a tool, then use the canvas
          </span>
        </span>
      </div>
      <div className="mt-3 space-y-2">
        {groups.map((group, groupIndex) => {
          const toolGrid = (
            <div className="grid grid-cols-3 gap-1">
              {group.tools.map((item) => {
                const Icon = TOOL_ICONS[item.tool] ?? BoxSelect;
                return (
                  <button
                    key={`${group.title}-${item.tool}`}
                    type="button"
                    onClick={() => onSelectTool(item.tool, item.label)}
                    data-testid={`cad-tool-${item.tool}`}
                    title={item.hint}
                    className="flex min-h-[58px] flex-col items-center justify-center gap-1.5 rounded-[7px] border border-transparent px-1.5 py-2 text-center text-slate-600 transition hover:border-slate-200 hover:bg-slate-50 hover:text-slate-950"
                  >
                    <Icon className="h-4 w-4" />
                    <span className="block text-[11px] font-semibold leading-none text-slate-700">{item.label}</span>
                  </button>
                );
              })}
            </div>
          );
          if (groupIndex === 0) {
            return (
              <div key={group.title}>
                {toolGrid}
              </div>
            );
          }
          return (
            <details key={group.title} className="border-t border-slate-100 pt-2">
              <summary className="flex cursor-pointer items-center gap-2 px-1 py-1 text-xs font-semibold text-slate-600">
                <span className="min-w-0 flex-1">{group.title}</span>
                <span className="text-[10px] text-slate-400">{group.tools.length}</span>
              </summary>
              <div className="mt-2">{toolGrid}</div>
            </details>
          );
        })}
      </div>
    </section>
  );
}
