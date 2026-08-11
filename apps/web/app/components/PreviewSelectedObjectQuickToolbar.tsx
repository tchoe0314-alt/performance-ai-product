import type { BuildingPlacement } from "../types";
import { Copy, PanelRightOpen, RotateCw, Ruler, Trash2 } from "lucide-react";

type PreviewSelectedObjectQuickToolbarProps = {
  item: BuildingPlacement;
  placement?: "left" | "right";
  canDelete: boolean;
  statusText: string;
  onMeasure: () => void;
  onCopy: () => void;
  onRotate: () => void;
  onInspect: () => void;
  onDelete: () => void;
};

export function PreviewSelectedObjectQuickToolbar({
  item,
  placement = "right",
  canDelete,
  statusText,
  onMeasure,
  onCopy,
  onRotate,
  onInspect,
  onDelete,
}: PreviewSelectedObjectQuickToolbarProps) {
  return (
    <div
      data-testid="selected-object-quick-toolbar"
      className={`pointer-events-auto absolute top-0 z-[95] flex min-w-max items-center gap-0.5 rounded-[7px] border border-slate-200 bg-white/96 p-1 text-slate-700 shadow-[0_12px_32px_-22px_rgba(15,23,42,0.5)] backdrop-blur ${
        placement === "left"
          ? "left-0 -translate-x-[calc(100%+8px)]"
          : "right-0 translate-x-[calc(100%+8px)]"
      }`}
      onMouseDown={(event) => {
        event.preventDefault();
        event.stopPropagation();
      }}
      onClick={(event) => event.stopPropagation()}
    >
      <button type="button" data-testid="selected-object-quick-measure" title="Measure selected object" aria-label="Measure selected object" className="flex h-7 w-7 items-center justify-center rounded-[5px] hover:bg-slate-100" onClick={onMeasure}>
        <Ruler className="h-3.5 w-3.5" />
      </button>
      <button type="button" data-testid="selected-object-quick-copy" title="Copy selected object" aria-label="Copy selected object" className="flex h-7 w-7 items-center justify-center rounded-[5px] hover:bg-slate-100" onClick={onCopy}>
        <Copy className="h-3.5 w-3.5" />
      </button>
      <button type="button" data-testid="selected-object-quick-rotate" title="Rotate selected object" aria-label="Rotate selected object" className="flex h-7 w-7 items-center justify-center rounded-[5px] hover:bg-slate-100" onClick={onRotate}>
        <RotateCw className="h-3.5 w-3.5" />
      </button>
      <button type="button" data-testid="selected-object-quick-inspect" title="Open object inspector" aria-label="Open object inspector" className="flex h-7 w-7 items-center justify-center rounded-[5px] hover:bg-slate-100" onClick={onInspect}>
        <PanelRightOpen className="h-3.5 w-3.5" />
      </button>
      <span className="mx-0.5 h-4 w-px bg-slate-200" aria-hidden="true" />
      <button type="button" data-testid="selected-object-quick-delete" title="Delete selected object" aria-label="Delete selected object" disabled={!canDelete} className="flex h-7 w-7 items-center justify-center rounded-[5px] text-rose-600 hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-40" onClick={onDelete}>
        <Trash2 className="h-3.5 w-3.5" />
      </button>
      <p
        data-testid="selected-object-quick-status"
        title={statusText || `Selected ${item.label || "draft object"}.`}
        className="sr-only"
      >
        {statusText || `Selected ${item.label || "draft object"}.`}
      </p>
    </div>
  );
}
