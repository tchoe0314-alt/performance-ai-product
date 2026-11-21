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
  Minus,
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
  arc: Spline,
};

export function DrawCadToolsPanel({ groups, onSelectTool }: DrawCadToolsPanelProps) {
  return (
    <section className="rounded-[8px] border border-slate-200/90 bg-white p-2.5" data-testid="draw-cad-tools-section">
      <div className="flex items-center gap-2.5 text-left">
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-semibold text-slate-900">Tools</span>
          <span className="sr-only">
            Choose a tool, then use the canvas
          </span>
        </span>
      </div>
      <div className="mt-2 space-y-1.5">
        {groups.map((group, groupIndex) => {
          const toolGrid = (
            <div className="civora-tool-grid">
              {group.tools.map((item) => {
                const Icon = item.tool === "line" ? Minus : TOOL_ICONS[item.tool] ?? BoxSelect;
                return (
                  <button
                    key={`${group.title}-${item.tool}`}
                    type="button"
                    onClick={() => onSelectTool(item.tool, item.label)}
                    data-testid={`cad-tool-${item.tool}`}
                    title={`${item.label} · ${item.hint}`}
                    aria-label={item.label}
                    data-tool-label="true"
                    className="flex min-h-11 flex-col items-center justify-center gap-0.5 rounded-[6px] border border-transparent px-1 py-1 text-center text-slate-600 transition hover:border-slate-200 hover:bg-slate-50 hover:text-slate-950 focus-visible:border-blue-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-100"
                  >
                    <Icon aria-hidden="true" className="h-3.5 w-3.5 shrink-0" />
                    <span className="max-w-full truncate text-[9px] font-semibold leading-none">{item.label}</span>
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
            <details key={group.title} className="border-t border-slate-100 pt-1.5">
              <summary className="flex min-h-9 cursor-pointer items-center gap-2 px-1 py-1 text-xs font-semibold text-slate-600">
                <span className="min-w-0 flex-1">{group.title}</span>
                <span className="text-[10px] text-slate-400">{group.tools.length}</span>
              </summary>
              <div className="mt-1.5">{toolGrid}</div>
            </details>
          );
        })}
      </div>
    </section>
  );
}
