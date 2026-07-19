import type { DragEvent, ReactNode } from "react";
import type { BuildingPlacement, SiteObjectType, SourceConfidenceEntry } from "../types";

type ObjectTypeOption = {
  type: SiteObjectType;
  label: string;
};

type ObjectManagerRowProps = {
  item: BuildingPlacement;
  isSelected: boolean;
  isMultiSelected: boolean;
  confidenceEntry?: SourceConfidenceEntry;
  displayType: string;
  dimensionsLabel: string;
  sourceLabel: string;
  reviewLabel: string;
  layerLabel: string;
  objectTypeOptions: ObjectTypeOption[];
  objectOutlineColor: string;
  hasDefaultHeight: boolean;
  customGeometryDetails?: ReactNode;
  onDragStart: (event: DragEvent<HTMLDivElement>) => void;
  onToggleMultiSelect: (checked: boolean) => void;
  onDelete: () => void;
  onRename: (value: string) => void;
  onColor: (value: string) => void;
  onType: (type: SiteObjectType) => void;
  onLength: (value: string) => void;
  onWidth: (value: string) => void;
  onHeight: (value: string) => void;
  onToggleLock: () => void;
  onMove: () => void;
  onSelect: () => void;
  onFocus: () => void;
  onToggleVisibility: () => void;
  onInspect: () => void;
  onCopy: () => void;
  onRotate: () => void;
  onFlipHorizontal: () => void;
  onFlipVertical: () => void;
  onExplodeCombined: () => void;
};

export function ObjectManagerRow({
  item,
  isSelected,
  isMultiSelected,
  confidenceEntry,
  displayType,
  dimensionsLabel,
  sourceLabel,
  reviewLabel,
  layerLabel,
  objectTypeOptions,
  objectOutlineColor,
  hasDefaultHeight,
  customGeometryDetails,
  onDragStart,
  onToggleMultiSelect,
  onDelete,
  onRename,
  onColor,
  onType,
  onLength,
  onWidth,
  onHeight,
  onToggleLock,
  onMove,
  onSelect,
  onFocus,
  onToggleVisibility,
  onInspect,
  onCopy,
  onRotate,
  onFlipHorizontal,
  onFlipVertical,
  onExplodeCombined,
}: ObjectManagerRowProps) {
  const isCombined = Array.isArray(item.meta?.combined_from_object_ids) && item.meta.combined_from_object_ids.length > 0;

  return (
    <div
      data-testid="object-manager-row"
      data-object-id={item.id}
      draggable={!item.locked}
      onDragStart={onDragStart}
      className={`rounded-2xl border bg-white p-3 text-xs text-slate-600 ${
        isSelected ? "border-slate-900 ring-2 ring-slate-200" : "border-slate-200"
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="flex items-start gap-2">
            <input
              type="checkbox"
              checked={isMultiSelected}
              onChange={(event) => onToggleMultiSelect(event.target.checked)}
              aria-label={`Select ${item.label} for bulk actions`}
              data-testid="object-manager-bulk-select"
              className="mt-1 h-4 w-4 shrink-0 accent-slate-950"
            />
            <div className="min-w-0">
              <p className="truncate font-semibold text-slate-900">{item.label}</p>
              <p className="mt-1 uppercase tracking-[0.12em] text-slate-400">
                {displayType} · {item.placed ? "Placed" : "Unplaced"} · {item.meta?.ui_hidden ? "Hidden" : "Visible"}
              </p>
            </div>
          </div>
          <p className="mt-2 text-[11px] font-medium text-slate-500" data-testid="object-manager-row-metrics">
            {dimensionsLabel}
          </p>
          <p className="mt-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-400" data-testid="object-manager-row-status">
            {sourceLabel} · {reviewLabel} · {layerLabel}
          </p>
          {confidenceEntry ? (
            <span className={`mt-2 inline-flex rounded-full px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${
              confidenceEntry.confidence_band === "higher"
                ? "bg-emerald-50 text-emerald-700"
                : confidenceEntry.confidence_band === "review"
                  ? "bg-amber-50 text-amber-700"
                  : "bg-red-50 text-red-700"
            }`}>
              {confidenceEntry.visible_badge || confidenceEntry.source_type || "low confidence"}
            </span>
          ) : null}
          {customGeometryDetails}
        </div>
        <button
          type="button"
          onClick={onDelete}
          data-testid="object-manager-delete"
          className="text-[11px] font-semibold uppercase tracking-[0.12em] text-rose-500"
        >
          Delete
        </button>
      </div>
      {item.type !== "site" ? (
        <div className="mt-3 grid grid-cols-2 gap-2 text-[11px]">
          <label className="col-span-2 flex flex-col gap-1">
            Name
            <input
              type="text"
              value={item.label}
              aria-label={`Rename ${item.label}`}
              data-testid="object-manager-rename"
              onChange={(event) => onRename(event.target.value)}
              className="rounded-md border border-slate-200 px-2 py-1 text-sm"
            />
          </label>
          <label className="col-span-2 flex items-center justify-between gap-3 rounded-md border border-slate-200 px-2 py-2">
            <span className="font-semibold uppercase tracking-[0.12em] text-slate-400">Color</span>
            <input
              type="color"
              value={String(item.meta?.ui_color || item.meta?.color || objectOutlineColor || "#64748b")}
              aria-label={`Color ${item.label}`}
              data-testid="object-manager-color"
              onChange={(event) => onColor(event.target.value)}
              className="h-8 w-10 rounded border border-slate-200 bg-white"
            />
          </label>
          <label className="col-span-2 flex flex-col gap-1">
            Layer / type
            <select
              value={item.type ?? "custom"}
              aria-label={`Layer type ${item.label}`}
              data-testid="object-manager-type"
              onChange={(event) => onType(event.target.value as SiteObjectType)}
              className="rounded-md border border-slate-200 px-2 py-1 text-sm"
            >
              {objectTypeOptions.map((option) => (
                <option key={option.type} value={option.type}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            Length
            <input
              type="number"
              value={item.w}
              aria-label={`Length ${item.label}`}
              data-testid="object-manager-length"
              onChange={(event) => onLength(event.target.value)}
              className="rounded-md border border-slate-200 px-2 py-1"
            />
          </label>
          <label className="flex flex-col gap-1">
            Width
            <input
              type="number"
              value={item.d}
              aria-label={`Width ${item.label}`}
              data-testid="object-manager-width"
              onChange={(event) => onWidth(event.target.value)}
              className="rounded-md border border-slate-200 px-2 py-1"
            />
          </label>
          {hasDefaultHeight ? (
            <label className="col-span-2 flex flex-col gap-1">
              Height
              <input
                type="number"
                value={item.h ?? ""}
                aria-label={`Height ${item.label}`}
                data-testid="object-manager-height"
                onChange={(event) => onHeight(event.target.value)}
                className="rounded-md border border-slate-200 px-2 py-1"
              />
            </label>
          ) : null}
          <button
            type="button"
            onClick={onToggleLock}
            data-testid="object-manager-lock"
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50"
          >
            {item.locked ? "Unlock" : "Lock"}
          </button>
          <button
            type="button"
            onClick={onMove}
            data-testid="object-manager-move"
            className="rounded-xl border border-slate-900 bg-slate-950 px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-white"
          >
            {item.placed ? "Move on Canvas" : "Place on Canvas"}
          </button>
          <button
            type="button"
            onClick={onSelect}
            data-testid="object-manager-select"
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50"
          >
            Select
          </button>
          <button
            type="button"
            onClick={onFocus}
            data-testid="object-manager-focus"
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50"
          >
            Focus
          </button>
          <button
            type="button"
            onClick={onToggleVisibility}
            data-testid="object-manager-visibility"
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50"
          >
            {item.meta?.ui_hidden ? "Show" : "Hide"}
          </button>
          <button
            type="button"
            onClick={onInspect}
            data-testid="object-manager-inspect"
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50"
          >
            Inspect
          </button>
          <button
            type="button"
            onClick={onCopy}
            data-testid="object-manager-copy"
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50"
          >
            Copy
          </button>
          <button
            type="button"
            onClick={onRotate}
            data-testid="object-manager-rotate"
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50"
          >
            Rotate 90
          </button>
          <button
            type="button"
            onClick={onFlipHorizontal}
            data-testid="object-manager-flip-horizontal"
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50"
          >
            Flip H
          </button>
          <button
            type="button"
            onClick={onFlipVertical}
            data-testid="object-manager-flip-vertical"
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50"
          >
            Flip V
          </button>
          {isCombined ? (
            <button
              type="button"
              onClick={onExplodeCombined}
              data-testid="object-manager-explode-combined"
              className="col-span-2 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-amber-800 hover:bg-amber-100"
            >
              Explode combined
            </button>
          ) : null}
        </div>
      ) : (
        <div className="mt-3 grid grid-cols-2 gap-2 text-[11px]">
          <button
            type="button"
            onClick={onSelect}
            data-testid="object-manager-select"
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50"
          >
            Select
          </button>
          <button
            type="button"
            onClick={onInspect}
            data-testid="object-manager-inspect"
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50"
          >
            Inspect
          </button>
        </div>
      )}
    </div>
  );
}
