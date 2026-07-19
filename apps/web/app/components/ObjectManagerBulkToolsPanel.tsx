import type { SiteObjectType } from "../types";

type ObjectManagerBulkToolsPanelProps = {
  objectTypeOptions: Array<{ type: SiteObjectType; label: string }>;
  arrayRows: string;
  arrayColumns: string;
  arraySpacingX: string;
  arraySpacingY: string;
  bulkMoveX: string;
  bulkMoveY: string;
  bulkMoveToX: string;
  bulkMoveToY: string;
  bulkScaleFactor: string;
  bulkRotateAngle: string;
  onHideSelected: () => void;
  onShowSelected: () => void;
  onIsolateSelected: () => void;
  onLockSelected: () => void;
  onUnlockSelected: () => void;
  onColorSelected: (color: string) => void;
  onTypeSelected: (type: SiteObjectType) => void;
  onDuplicateSelected: () => void;
  onLayoutSelected: (layout: "align_left" | "align_top" | "distribute_x" | "distribute_y") => void;
  onDeleteSelected: () => void;
  onArrayRowsChange: (value: string) => void;
  onArrayColumnsChange: (value: string) => void;
  onArraySpacingXChange: (value: string) => void;
  onArraySpacingYChange: (value: string) => void;
  onCreateArray: () => void;
  onBulkMoveXChange: (value: string) => void;
  onBulkMoveYChange: (value: string) => void;
  onMoveSelected: () => void;
  onCopyByOffset: () => void;
  onBulkMoveToXChange: (value: string) => void;
  onBulkMoveToYChange: (value: string) => void;
  onMoveToCoordinate: () => void;
  onBulkScaleFactorChange: (value: string) => void;
  onScaleSelected: () => void;
  onBulkRotateAngleChange: (value: string) => void;
  onRotateSelected: () => void;
  onMirrorSelected: (axis: "x" | "y") => void;
};

export function ObjectManagerBulkToolsPanel({
  objectTypeOptions,
  arrayRows,
  arrayColumns,
  arraySpacingX,
  arraySpacingY,
  bulkMoveX,
  bulkMoveY,
  bulkMoveToX,
  bulkMoveToY,
  bulkScaleFactor,
  bulkRotateAngle,
  onHideSelected,
  onShowSelected,
  onIsolateSelected,
  onLockSelected,
  onUnlockSelected,
  onColorSelected,
  onTypeSelected,
  onDuplicateSelected,
  onLayoutSelected,
  onDeleteSelected,
  onArrayRowsChange,
  onArrayColumnsChange,
  onArraySpacingXChange,
  onArraySpacingYChange,
  onCreateArray,
  onBulkMoveXChange,
  onBulkMoveYChange,
  onMoveSelected,
  onCopyByOffset,
  onBulkMoveToXChange,
  onBulkMoveToYChange,
  onMoveToCoordinate,
  onBulkScaleFactorChange,
  onScaleSelected,
  onBulkRotateAngleChange,
  onRotateSelected,
  onMirrorSelected,
}: ObjectManagerBulkToolsPanelProps) {
  return (
    <>
      <div className="mt-2 grid grid-cols-2 gap-2 text-[11px]">
        <button
          type="button"
          onClick={onHideSelected}
          data-testid="object-manager-bulk-hide"
          className="rounded-lg border border-slate-200 bg-white px-2 py-2 font-semibold uppercase tracking-[0.12em] text-slate-600 hover:bg-slate-50"
        >
          Hide selected
        </button>
        <button
          type="button"
          onClick={onShowSelected}
          data-testid="object-manager-bulk-show"
          className="rounded-lg border border-slate-200 bg-white px-2 py-2 font-semibold uppercase tracking-[0.12em] text-slate-600 hover:bg-slate-50"
        >
          Show selected
        </button>
        <button
          type="button"
          onClick={onIsolateSelected}
          data-testid="object-manager-isolate-selected"
          className="col-span-2 rounded-lg border border-slate-200 bg-white px-2 py-2 font-semibold uppercase tracking-[0.12em] text-slate-600 hover:bg-slate-50"
        >
          Isolate selected
        </button>
        <button
          type="button"
          onClick={onLockSelected}
          data-testid="object-manager-bulk-lock"
          className="rounded-lg border border-slate-200 bg-white px-2 py-2 font-semibold uppercase tracking-[0.12em] text-slate-600 hover:bg-slate-50"
        >
          Lock selected
        </button>
        <button
          type="button"
          onClick={onUnlockSelected}
          data-testid="object-manager-bulk-unlock"
          className="rounded-lg border border-slate-200 bg-white px-2 py-2 font-semibold uppercase tracking-[0.12em] text-slate-600 hover:bg-slate-50"
        >
          Unlock selected
        </button>
        <label className="flex items-center justify-between gap-2 rounded-lg border border-slate-200 bg-white px-2 py-2 font-semibold uppercase tracking-[0.12em] text-slate-500">
          Color
          <input
            type="color"
            defaultValue="#0f766e"
            onChange={(event) => onColorSelected(event.target.value)}
            data-testid="object-manager-bulk-color"
            className="h-7 w-9 rounded border border-slate-200 bg-white"
          />
        </label>
        <select
          aria-label="Bulk layer type"
          data-testid="object-manager-bulk-type"
          defaultValue=""
          onChange={(event) => {
            if (!event.target.value) return;
            onTypeSelected(event.target.value as SiteObjectType);
          }}
          className="rounded-lg border border-slate-200 bg-white px-2 py-2 font-semibold text-slate-600"
        >
          <option value="">Layer/type</option>
          {objectTypeOptions.map((option) => (
            <option key={`bulk-${option.type}`} value={option.type}>
              {option.label}
            </option>
          ))}
        </select>
        <button
          type="button"
          onClick={onDuplicateSelected}
          data-testid="object-manager-bulk-duplicate"
          className="col-span-2 rounded-lg border border-slate-200 bg-white px-2 py-2 font-semibold uppercase tracking-[0.12em] text-slate-600 hover:bg-slate-50"
        >
          Duplicate selected
        </button>
        <button
          type="button"
          onClick={() => onLayoutSelected("align_left")}
          data-testid="object-manager-bulk-align-left"
          className="rounded-lg border border-slate-200 bg-white px-2 py-2 font-semibold uppercase tracking-[0.12em] text-slate-600 hover:bg-slate-50"
        >
          Align left
        </button>
        <button
          type="button"
          onClick={() => onLayoutSelected("align_top")}
          data-testid="object-manager-bulk-align-top"
          className="rounded-lg border border-slate-200 bg-white px-2 py-2 font-semibold uppercase tracking-[0.12em] text-slate-600 hover:bg-slate-50"
        >
          Align top
        </button>
        <button
          type="button"
          onClick={() => onLayoutSelected("distribute_x")}
          data-testid="object-manager-bulk-distribute-x"
          className="rounded-lg border border-slate-200 bg-white px-2 py-2 font-semibold uppercase tracking-[0.12em] text-slate-600 hover:bg-slate-50"
        >
          Distribute X
        </button>
        <button
          type="button"
          onClick={() => onLayoutSelected("distribute_y")}
          data-testid="object-manager-bulk-distribute-y"
          className="rounded-lg border border-slate-200 bg-white px-2 py-2 font-semibold uppercase tracking-[0.12em] text-slate-600 hover:bg-slate-50"
        >
          Distribute Y
        </button>
        <button
          type="button"
          onClick={onDeleteSelected}
          data-testid="object-manager-bulk-delete"
          className="col-span-2 rounded-lg border border-rose-200 bg-white px-2 py-2 font-semibold uppercase tracking-[0.12em] text-rose-600 hover:bg-rose-50"
        >
          Delete selected
        </button>
      </div>
      <div className="mt-3 rounded-xl border border-slate-200 bg-white p-3" data-testid="object-manager-array-selected">
        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
          Rectangular array
        </p>
        <div className="mt-2 grid grid-cols-2 gap-2">
          <label className="flex flex-col gap-1 text-[11px] font-semibold text-slate-500">
            Rows
            <input
              type="number"
              min="1"
              max="10"
              value={arrayRows}
              onChange={(event) => onArrayRowsChange(event.target.value)}
              data-testid="object-manager-array-rows"
              className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-2 text-sm font-medium text-slate-900 outline-none focus:border-blue-300 focus:ring-2 focus:ring-blue-100"
            />
          </label>
          <label className="flex flex-col gap-1 text-[11px] font-semibold text-slate-500">
            Columns
            <input
              type="number"
              min="1"
              max="10"
              value={arrayColumns}
              onChange={(event) => onArrayColumnsChange(event.target.value)}
              data-testid="object-manager-array-columns"
              className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-2 text-sm font-medium text-slate-900 outline-none focus:border-blue-300 focus:ring-2 focus:ring-blue-100"
            />
          </label>
          <label className="flex flex-col gap-1 text-[11px] font-semibold text-slate-500">
            X spacing
            <input
              type="number"
              value={arraySpacingX}
              onChange={(event) => onArraySpacingXChange(event.target.value)}
              data-testid="object-manager-array-spacing-x"
              className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-2 text-sm font-medium text-slate-900 outline-none focus:border-blue-300 focus:ring-2 focus:ring-blue-100"
            />
          </label>
          <label className="flex flex-col gap-1 text-[11px] font-semibold text-slate-500">
            Y spacing
            <input
              type="number"
              value={arraySpacingY}
              onChange={(event) => onArraySpacingYChange(event.target.value)}
              data-testid="object-manager-array-spacing-y"
              className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-2 text-sm font-medium text-slate-900 outline-none focus:border-blue-300 focus:ring-2 focus:ring-blue-100"
            />
          </label>
        </div>
        <button
          type="button"
          onClick={onCreateArray}
          data-testid="object-manager-array-action"
          className="mt-2 w-full rounded-lg border border-slate-200 bg-slate-900 px-2 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-white hover:bg-slate-800"
        >
          Create array
        </button>
        <p className="mt-2 text-[11px] font-medium text-slate-500">
          Draft copies stay review-required and trace back to the selected source object.
        </p>
      </div>
      <div className="mt-3 rounded-xl border border-slate-200 bg-white p-3" data-testid="object-manager-transform-selected">
        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
          Transform selected
        </p>
        <div className="mt-2 grid grid-cols-2 gap-2">
          <label className="flex flex-col gap-1 text-[11px] font-semibold text-slate-500">
            Move X
            <input
              type="number"
              value={bulkMoveX}
              onChange={(event) => onBulkMoveXChange(event.target.value)}
              data-testid="object-manager-bulk-move-x"
              className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-2 text-sm font-medium text-slate-900 outline-none focus:border-blue-300 focus:ring-2 focus:ring-blue-100"
            />
          </label>
          <label className="flex flex-col gap-1 text-[11px] font-semibold text-slate-500">
            Move Y
            <input
              type="number"
              value={bulkMoveY}
              onChange={(event) => onBulkMoveYChange(event.target.value)}
              data-testid="object-manager-bulk-move-y"
              className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-2 text-sm font-medium text-slate-900 outline-none focus:border-blue-300 focus:ring-2 focus:ring-blue-100"
            />
          </label>
        </div>
        <button
          type="button"
          onClick={onMoveSelected}
          data-testid="object-manager-bulk-move-action"
          className="mt-2 w-full rounded-lg border border-slate-200 bg-white px-2 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-700 hover:bg-slate-50"
        >
          Move selected
        </button>
        <button
          type="button"
          onClick={onCopyByOffset}
          data-testid="object-manager-bulk-copy-offset-action"
          className="mt-2 w-full rounded-lg border border-slate-200 bg-white px-2 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-700 hover:bg-slate-50"
        >
          Copy by offset
        </button>
        <div className="mt-3 rounded-xl border border-slate-100 bg-slate-50 p-2" data-testid="object-manager-move-to-coordinate">
          <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-400">
            Move selection top-left to coordinate
          </p>
          <div className="mt-2 grid grid-cols-2 gap-2">
            <label className="flex flex-col gap-1 text-[11px] font-semibold text-slate-500">
              Target X
              <input
                type="number"
                value={bulkMoveToX}
                onChange={(event) => onBulkMoveToXChange(event.target.value)}
                data-testid="object-manager-bulk-move-to-x"
                className="rounded-lg border border-slate-200 bg-white px-2 py-2 text-sm font-medium text-slate-900 outline-none focus:border-blue-300 focus:ring-2 focus:ring-blue-100"
              />
            </label>
            <label className="flex flex-col gap-1 text-[11px] font-semibold text-slate-500">
              Target Y
              <input
                type="number"
                value={bulkMoveToY}
                onChange={(event) => onBulkMoveToYChange(event.target.value)}
                data-testid="object-manager-bulk-move-to-y"
                className="rounded-lg border border-slate-200 bg-white px-2 py-2 text-sm font-medium text-slate-900 outline-none focus:border-blue-300 focus:ring-2 focus:ring-blue-100"
              />
            </label>
          </div>
          <button
            type="button"
            onClick={onMoveToCoordinate}
            data-testid="object-manager-bulk-move-to-action"
            className="mt-2 w-full rounded-lg border border-slate-200 bg-white px-2 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-700 hover:bg-white"
          >
            Move to coordinate
          </button>
        </div>
        <div className="mt-2 grid grid-cols-[1fr_auto] gap-2">
          <label className="flex flex-col gap-1 text-[11px] font-semibold text-slate-500">
            Scale factor
            <input
              type="number"
              step="0.05"
              min="0.05"
              max="10"
              value={bulkScaleFactor}
              onChange={(event) => onBulkScaleFactorChange(event.target.value)}
              data-testid="object-manager-bulk-scale-factor"
              className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-2 text-sm font-medium text-slate-900 outline-none focus:border-blue-300 focus:ring-2 focus:ring-blue-100"
            />
          </label>
          <button
            type="button"
            onClick={onScaleSelected}
            data-testid="object-manager-bulk-scale-action"
            className="self-end rounded-lg border border-slate-200 bg-white px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-700 hover:bg-slate-50"
          >
            Scale
          </button>
        </div>
        <div className="mt-2 grid grid-cols-[1fr_auto] gap-2">
          <label className="flex flex-col gap-1 text-[11px] font-semibold text-slate-500">
            Rotate degrees
            <input
              type="number"
              step="1"
              value={bulkRotateAngle}
              onChange={(event) => onBulkRotateAngleChange(event.target.value)}
              data-testid="object-manager-bulk-rotate-angle"
              className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-2 text-sm font-medium text-slate-900 outline-none focus:border-blue-300 focus:ring-2 focus:ring-blue-100"
            />
          </label>
          <button
            type="button"
            onClick={onRotateSelected}
            data-testid="object-manager-bulk-rotate-action"
            className="self-end rounded-lg border border-slate-200 bg-white px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-700 hover:bg-slate-50"
          >
            Rotate
          </button>
        </div>
        <div className="mt-2 grid grid-cols-2 gap-2">
          <button
            type="button"
            onClick={() => onMirrorSelected("x")}
            data-testid="object-manager-bulk-mirror-x"
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-700 hover:bg-slate-50"
          >
            Mirror X
          </button>
          <button
            type="button"
            onClick={() => onMirrorSelected("y")}
            data-testid="object-manager-bulk-mirror-y"
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-700 hover:bg-slate-50"
          >
            Mirror Y
          </button>
        </div>
      </div>
    </>
  );
}
