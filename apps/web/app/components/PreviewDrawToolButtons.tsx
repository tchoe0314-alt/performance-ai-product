import type { DrawMode } from "../utils/cadToolTypes";

const DRAW_OBJECT_TOOLS: Array<{ mode: DrawMode; label: string }> = [
  { mode: "polyline", label: "Add Line" },
  { mode: "polygon", label: "Add Area" },
  { mode: "rect", label: "Add Box" },
  { mode: "point", label: "Add Point" },
];

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
}) {
  return (
    <>
      {DRAW_OBJECT_TOOLS.map((item) => {
        const active = drawMode === item.mode;
        return (
          <button
            key={`${itemKeyPrefix}-${item.mode}`}
            type="button"
            aria-pressed={active}
            title={disabled ? disabledLabel : item.label}
            data-blocked={disabled ? "true" : undefined}
            onClick={() => onActivate(item.mode, disabled ? disabledLabel : undefined)}
            className={`${buttonClassName} ${
              active ? activeClassName : disabled ? disabledClassName : inactiveClassName
            }`}
          >
            {item.label}
          </button>
        );
      })}
    </>
  );
}
