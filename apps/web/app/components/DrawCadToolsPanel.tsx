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

const ICON_ONLY_TOOLS = new Set<CadToolName>(["select", "pan", "line", "area", "box", "point", "circle", "text", "dimension", "move", "copy", "rotate", "scale", "trim", "delete"]);

export function DrawCadToolsPanel({ groups, onSelectTool }: DrawCadToolsPanelProps) {
  return (
    <section className="rounded-[8px] border border-slate-200/90 bg-white p-3" data-testid="draw-cad-tools-section">
      <div className="flex items-center gap-2.5 text-left">
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-semibold text-slate-900">Tools</span>
          <span className="sr-only">
            Choose a tool, then use the canvas
          </span>
        </span>
      </div>
      <div className="mt-3 space-y-2">
        {groups.map((group, groupIndex) => {
          const toolGrid = (
            <div className="civora-tool-grid">
              {group.tools.map((item) => {
                const Icon = item.tool === "line" ? Minus : TOOL_ICONS[item.tool] ?? BoxSelect;
                const iconOnly = ICON_ONLY_TOOLS.has(item.tool);
                return (
                  <button
                    key={`${group.title}-${item.tool}`}
                    type="button"
                    onClick={() => onSelectTool(item.tool, item.label)}
                    data-testid={`cad-tool-${item.tool}`}
                    title={`${item.label} · ${item.hint}`}
                    aria-label={item.label}
                    data-tool-label={iconOnly ? undefined : "true"}
                    className="flex items-center justify-center rounded-[6px] border border-transparent text-center text-slate-600 transition hover:border-slate-200 hover:bg-slate-50 hover:text-slate-950"
                  >
                    <Icon aria-hidden="true" className="h-4 w-4 shrink-0" />
                    <span className={iconOnly ? "sr-only" : "text-[11px] font-semibold"}>{item.label}</span>
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
