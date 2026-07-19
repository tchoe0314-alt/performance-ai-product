import type { BuildingPlacement } from "../types";

type SelectedObjectCardProps = {
  selectedObject: BuildingPlacement | null;
  displayType: string;
  dimensionsLabel: string;
  onMove: (item: BuildingPlacement) => void;
  onFocus: (item: BuildingPlacement) => void;
  onCopy: (item: BuildingPlacement) => void;
  onRotate: (item: BuildingPlacement) => void;
  onFlipHorizontal: (item: BuildingPlacement) => void;
  onDelete: (item: BuildingPlacement) => void;
};

export function SelectedObjectCard({
  selectedObject,
  displayType,
  dimensionsLabel,
  onMove,
  onFocus,
  onCopy,
  onRotate,
  onFlipHorizontal,
  onDelete,
}: SelectedObjectCardProps) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4" data-testid="draw-selected-object-card">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
            Selected Object
          </p>
          <p className="mt-1 truncate text-sm font-semibold text-slate-950">
            {selectedObject?.label || "Nothing selected"}
          </p>
          <p className="mt-1 text-xs font-medium text-slate-500">
            {selectedObject
              ? `${displayType} · ${dimensionsLabel}`
              : "Pick an object on the canvas or from the list below."}
          </p>
        </div>
        <span className="shrink-0 rounded-full bg-slate-50 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500">
          {selectedObject?.meta?.ui_hidden ? "Hidden" : selectedObject ? "Visible" : "None"}
        </span>
      </div>
      {selectedObject ? (
        <div className="mt-3 grid grid-cols-2 gap-2 text-[11px]">
          <button
            type="button"
            onClick={() => onMove(selectedObject)}
            className="rounded-lg border border-slate-950 bg-slate-950 px-3 py-2 font-semibold uppercase tracking-[0.12em] text-white hover:bg-slate-800"
          >
            Move
          </button>
          <button
            type="button"
            onClick={() => onFocus(selectedObject)}
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 font-semibold uppercase tracking-[0.12em] text-slate-700 hover:bg-slate-50"
          >
            Focus
          </button>
          <button
            type="button"
            onClick={() => onCopy(selectedObject)}
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 font-semibold uppercase tracking-[0.12em] text-slate-700 hover:bg-slate-50"
          >
            Copy
          </button>
          <button
            type="button"
            onClick={() => onRotate(selectedObject)}
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 font-semibold uppercase tracking-[0.12em] text-slate-700 hover:bg-slate-50"
          >
            Rotate
          </button>
          <button
            type="button"
            onClick={() => onFlipHorizontal(selectedObject)}
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 font-semibold uppercase tracking-[0.12em] text-slate-700 hover:bg-slate-50"
          >
            Flip H
          </button>
          <button
            type="button"
            onClick={() => onDelete(selectedObject)}
            disabled={selectedObject.type === "site"}
            className="rounded-lg border border-rose-200 bg-white px-3 py-2 font-semibold uppercase tracking-[0.12em] text-rose-600 hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-40"
          >
            Delete
          </button>
        </div>
      ) : null}
    </div>
  );
}
