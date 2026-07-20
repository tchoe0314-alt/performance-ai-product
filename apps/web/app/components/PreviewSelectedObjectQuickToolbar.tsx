import type { BuildingPlacement } from "../types";

type PreviewSelectedObjectQuickToolbarProps = {
  item: BuildingPlacement;
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
      className="pointer-events-auto absolute left-1/2 top-0 z-[95] flex min-w-max -translate-x-1/2 -translate-y-[calc(100%+10px)] flex-col items-center gap-1 rounded-lg border border-slate-200 bg-white/95 p-1 text-[10px] font-semibold uppercase tracking-[0.1em] text-slate-700 shadow-lg backdrop-blur"
      onMouseDown={(event) => {
        event.preventDefault();
        event.stopPropagation();
      }}
      onClick={(event) => event.stopPropagation()}
    >
      <div className="flex items-center gap-1">
        <button
          type="button"
          data-testid="selected-object-quick-measure"
          className="rounded-md px-2 py-1 hover:bg-slate-100"
          onClick={onMeasure}
        >
          Measure
        </button>
        <button
          type="button"
          data-testid="selected-object-quick-copy"
          className="rounded-md px-2 py-1 hover:bg-slate-100"
          onClick={onCopy}
        >
          Copy
        </button>
        <button
          type="button"
          data-testid="selected-object-quick-rotate"
          className="rounded-md px-2 py-1 hover:bg-slate-100"
          onClick={onRotate}
        >
          Rotate
        </button>
        <button
          type="button"
          data-testid="selected-object-quick-inspect"
          className="rounded-md px-2 py-1 hover:bg-slate-100"
          onClick={onInspect}
        >
          Inspect
        </button>
        <button
          type="button"
          data-testid="selected-object-quick-delete"
          disabled={!canDelete}
          className="rounded-md px-2 py-1 text-rose-600 hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-40"
          onClick={onDelete}
        >
          Delete
        </button>
      </div>
      <p
        data-testid="selected-object-quick-status"
        className="max-w-[22rem] truncate rounded-md bg-slate-50 px-2 py-0.5 normal-case tracking-normal text-slate-500"
      >
        {statusText || `Selected ${item.label || "draft object"}.`}
      </p>
    </div>
  );
}
