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
      className="pointer-events-auto absolute right-0 top-0 z-[95] flex min-w-max translate-x-[calc(100%+8px)] flex-col gap-1 rounded-lg border border-slate-200 bg-white/90 p-1 text-[10px] font-semibold uppercase tracking-[0.08em] text-slate-700 shadow-md backdrop-blur"
      onMouseDown={(event) => {
        event.preventDefault();
        event.stopPropagation();
      }}
      onClick={(event) => event.stopPropagation()}
    >
      <div className="grid grid-cols-2 gap-1">
        <button
          type="button"
          data-testid="selected-object-quick-measure"
          title="Measure selected object"
          className="rounded-md px-2 py-1 hover:bg-slate-100"
          onClick={onMeasure}
        >
          Measure
        </button>
        <button
          type="button"
          data-testid="selected-object-quick-copy"
          title="Copy selected object"
          className="rounded-md px-2 py-1 hover:bg-slate-100"
          onClick={onCopy}
        >
          Copy
        </button>
        <button
          type="button"
          data-testid="selected-object-quick-rotate"
          title="Rotate selected object"
          className="rounded-md px-2 py-1 hover:bg-slate-100"
          onClick={onRotate}
        >
          Rotate
        </button>
        <button
          type="button"
          data-testid="selected-object-quick-inspect"
          title="Inspect selected object"
          className="rounded-md px-2 py-1 hover:bg-slate-100"
          onClick={onInspect}
        >
          Inspect
        </button>
        <button
          type="button"
          data-testid="selected-object-quick-delete"
          title="Delete selected object"
          disabled={!canDelete}
          className="col-span-2 rounded-md px-2 py-1 text-rose-600 hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-40"
          onClick={onDelete}
        >
          Delete
        </button>
      </div>
      <p
        data-testid="selected-object-quick-status"
        title={statusText || `Selected ${item.label || "draft object"}.`}
        className="max-w-[9rem] truncate rounded-md bg-slate-50 px-2 py-0.5 normal-case tracking-normal text-slate-500"
      >
        {statusText || `Selected ${item.label || "draft object"}.`}
      </p>
    </div>
  );
}
