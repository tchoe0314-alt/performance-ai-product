import type { DrawMode } from "../utils/cadToolTypes";

const DRAW_OBJECT_TOOLS: Array<{ mode: DrawMode; label: string }> = [
  { mode: "polyline", label: "Add Line" },
  { mode: "polygon", label: "Add Area" },
  { mode: "rect", label: "Add Box" },
  { mode: "point", label: "Add Point" },
];
const PAN_TOOL: { mode: DrawMode; label: string } = { mode: "pan", label: "Pan" };

export function PreviewDrawToolButtons({
  drawMode,
  disabled,
  disabledLabel,
  onActivate,
  buttonClassName = "inline-flex h-8 items-center rounded-md border px-2.5 text-xs font-semibold",
  activeClassName = "border-slate-900 bg-slate-950 text-white",
  disabledClassName = "border-amber-200 bg-amber-50 text-amber-800",
  inactiveClassName = "border-slate-200 bg-white text-slate-600",
  itemKeyPrefix = "preview-draw-tool",
  includePan = false,
}: {
  drawMode: DrawMode;
  disabled: boolean;
  disabledLabel: string;
  onActivate: (mode: DrawMode, blockedMessage?: string) => void;
  buttonClassName?: string;
  activeClassName?: string;
  disabledClassName?: string;
  inactiveClassName?: string;
  itemKeyPrefix?: string;
  includePan?: boolean;
}) {
  const tools = includePan ? [PAN_TOOL, ...DRAW_OBJECT_TOOLS] : DRAW_OBJECT_TOOLS;
  return (
    <>
      {tools.map((item) => {
        const active = drawMode === item.mode;
        const itemDisabled = item.mode === "pan" ? false : disabled;
        return (
          <button
            key={`${itemKeyPrefix}-${item.mode}`}
            type="button"
            aria-pressed={active}
            title={itemDisabled ? disabledLabel : item.label}
            data-blocked={itemDisabled ? "true" : undefined}
            onClick={() => onActivate(item.mode, itemDisabled ? disabledLabel : undefined)}
            className={`${buttonClassName} ${
              active ? activeClassName : itemDisabled ? disabledClassName : inactiveClassName
            }`}
          >
            {item.label}
          </button>
        );
      })}
    </>
  );
}
