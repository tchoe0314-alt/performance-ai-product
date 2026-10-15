import type { DragEvent, ReactNode } from "react";
import type { BuildingPlacement, SiteObjectType, SourceConfidenceEntry } from "../types";
import { Copy, Eye, EyeOff, Focus, Lock, Unlock, Move, MousePointer2, PanelRightOpen, RotateCw, Trash2 } from "lucide-react";
import { WorkspaceStateBadge } from "./WorkspaceStateBadge";

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
      data-selected={isSelected ? "true" : "false"}
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
              aria-label={`Include ${item.label} in bulk actions`}
              data-testid="object-manager-bulk-select"
              className="mt-1 h-4 w-4 shrink-0 accent-slate-950"
            />
            <div className="min-w-0">
              <p className="truncate font-semibold text-slate-900">{item.label}</p>
              <p className="mt-1 text-slate-500">
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
          <div className="mt-1 flex flex-wrap gap-1" data-testid="object-state-badges">
            {isSelected ? <WorkspaceStateBadge state="selected" /> : null}
            {item.locked ? <WorkspaceStateBadge state="locked" /> : null}
            {item.meta?.ui_hidden ? <WorkspaceStateBadge state="hidden" /> : null}
            {item.source === "inferred" ? <WorkspaceStateBadge state="assumed" /> : <WorkspaceStateBadge state="unverified" title="Draft geometry is not engineering verification." />}
          </div>
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
          aria-label="Delete"
          title="Delete object"
          className="civora-icon-control text-rose-600 hover:bg-rose-50"
        >
          <Trash2 aria-hidden="true" />
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
            Classify as
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
          <div className="civora-panel-actions col-span-2">
          <button
            type="button"
            onClick={onToggleLock}
            data-testid="object-manager-lock"
            aria-label={item.locked ? "Unlock" : "Lock"}
            title={item.locked ? "Unlock object" : "Lock object"}
            className="civora-icon-control border border-slate-200 hover:bg-slate-50"
          >
            {item.locked ? <Unlock aria-hidden="true" /> : <Lock aria-hidden="true" />}
          </button>
          <button
            type="button"
            onClick={onMove}
            aria-label={`${item.placed ? "Move" : "Place"} on canvas: ${item.label}`}
            data-testid="object-manager-move"
            title={item.placed ? "Move on canvas" : "Place on canvas"}
            className="civora-icon-control border border-slate-900 bg-slate-950 text-white"
          >
            <Move aria-hidden="true" />
          </button>
          <button
            type="button"
            onClick={onSelect}
            data-testid="object-manager-select"
            aria-label="Select" title="Select object"
            className="civora-icon-control border border-slate-200 hover:bg-slate-50"
          >
            <MousePointer2 aria-hidden="true" />
          </button>
          <button
            type="button"
            onClick={onFocus}
            data-testid="object-manager-focus"
            aria-label="Focus" title="Focus object"
            className="civora-icon-control border border-slate-200 hover:bg-slate-50"
          >
            <Focus aria-hidden="true" />
          </button>
          <button
            type="button"
            onClick={onToggleVisibility}
            data-testid="object-manager-visibility"
            aria-label={item.meta?.ui_hidden ? "Show" : "Hide"}
            title={item.meta?.ui_hidden ? "Show object" : "Hide object"}
            className="civora-icon-control border border-slate-200 hover:bg-slate-50"
          >
            {item.meta?.ui_hidden ? <Eye aria-hidden="true" /> : <EyeOff aria-hidden="true" />}
          </button>
          <button
            type="button"
            onClick={onInspect}
            data-testid="object-manager-inspect"
            aria-label="Inspect" title="Inspect object"
            className="civora-icon-control border border-slate-200 hover:bg-slate-50"
          >
            <PanelRightOpen aria-hidden="true" />
          </button>
          <button
            type="button"
            onClick={onCopy}
            data-testid="object-manager-copy"
            aria-label="Copy" title="Copy object"
            className="civora-icon-control border border-slate-200 hover:bg-slate-50"
          >
            <Copy aria-hidden="true" />
          </button>
          <button
            type="button"
            onClick={onRotate}
            data-testid="object-manager-rotate"
            aria-label="Rotate 90" title="Rotate 90°"
            className="civora-icon-control border border-slate-200 hover:bg-slate-50"
          >
            <RotateCw aria-hidden="true" />
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
          </div>
          {isCombined || item.type === "group" ? (
            <button
              type="button"
              onClick={onExplodeCombined}
              data-testid="object-manager-explode-combined"
              className="col-span-2 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-amber-800 hover:bg-amber-100"
            >
              {item.type === "group" ? "Ungroup" : "Uncombine"}
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
