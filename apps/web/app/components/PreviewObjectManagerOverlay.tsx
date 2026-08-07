"use client";

import { Eye, EyeOff, Maximize2, Trash2, X } from "lucide-react";

import type { BuildingPlacement, SiteObjectType } from "../types";
import { SITE_OBJECT_CATALOG } from "../utils/siteObjectCatalog";

type ObjectManagerCounts = {
  total: number;
  visible: number;
  draft: number;
  generated: number;
};

type PreviewObjectManagerOverlayProps = {
  visible: boolean;
  selectedObject: BuildingPlacement | null;
  selectedBuildingId: string | null;
  objectManagerRows: BuildingPlacement[];
  objectManagerCounts: ObjectManagerCounts;
  selectedCadIds: string[];
  onSetManagedObjectId: (id: string | null) => void;
  onSelectBuilding: (id: string | null) => void;
  onSelectObjects?: (ids: string[]) => void;
  onSetCadSelectionSet: (ids: string[]) => void;
  onClearSelectedVertex: () => void;
  onSetCadCommandStatus: (message: string) => void;
  onUpdatePreviewManagedObject: (item: BuildingPlacement, updates: Partial<BuildingPlacement>) => boolean;
  onFocusPreviewManagedObject: (item: BuildingPlacement | null) => void;
  onRemoveBuilding: (id: string) => void;
  onSetLastRectEdit: (value: { id: string; snapshot: BuildingPlacement; action: "update" | "delete" | "add"; ts: number }) => void;
  getPreviewObjectActionBlocker: (
    item: BuildingPlacement | null,
    action: "rename" | "style" | "type" | "hide" | "delete" | "focus",
  ) => string | null;
  getPreviewObjectDimensionsLabel: (item: BuildingPlacement) => string;
  getPreviewObjectSourceLabel: (item: BuildingPlacement) => string;
  getPreviewObjectStatusLabel: (item: BuildingPlacement) => string;
  getCadLayer: (item: BuildingPlacement) => string;
};

const PREVIEW_OBJECT_TYPES = Object.entries(SITE_OBJECT_CATALOG)
  .filter(([type]) => type !== "site")
  .map(([type, catalog]) => ({ type: type as SiteObjectType, label: catalog.label }));

export function PreviewObjectManagerOverlay({
  visible,
  selectedObject,
  selectedBuildingId,
  objectManagerRows,
  objectManagerCounts,
  selectedCadIds,
  onSetManagedObjectId,
  onSelectBuilding,
  onSelectObjects,
  onSetCadSelectionSet,
  onClearSelectedVertex,
  onSetCadCommandStatus,
  onUpdatePreviewManagedObject,
  onFocusPreviewManagedObject,
  onRemoveBuilding,
  onSetLastRectEdit,
  getPreviewObjectActionBlocker,
  getPreviewObjectDimensionsLabel,
  getPreviewObjectSourceLabel,
  getPreviewObjectStatusLabel,
  getCadLayer,
}: PreviewObjectManagerOverlayProps) {
  return (
    <section
      className={`${visible ? "pointer-events-auto relative z-[230] flex" : "hidden"} min-w-[280px] max-w-full flex-wrap items-center gap-1.5 rounded-lg border border-slate-200 bg-white/94 p-1 shadow-[0_18px_45px_-34px_rgba(15,23,42,0.65)] backdrop-blur`}
      data-testid="preview-object-manager"
    >
      <span className="px-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">Objects</span>
      {selectedObject?.label ? (
        <span className="max-w-[180px] truncate rounded-md border border-slate-200 bg-white px-2 py-1.5 text-xs font-semibold text-slate-700">
          {selectedObject.label}
        </span>
      ) : null}
      <select
        aria-label="Object Manager object list"
        data-testid="preview-object-manager-list"
        value={selectedObject?.id ?? selectedBuildingId ?? ""}
        onChange={(event) => {
          const id = event.target.value || null;
          onSetManagedObjectId(id);
          onSelectBuilding(id);
          onSelectObjects?.(id ? [id] : []);
          onSetCadSelectionSet(id ? [id] : []);
          onClearSelectedVertex();
        }}
        className="h-9 min-w-[168px] max-w-[240px] rounded-md border border-slate-200 bg-white px-2 text-xs font-semibold text-slate-700"
      >
        <option value="">
          {objectManagerCounts.total
            ? `${objectManagerCounts.total} objects: ${objectManagerCounts.visible} visible`
            : "No objects"}
        </option>
        {objectManagerRows.map((item) => (
          <option key={`manager-option-${item.id}`} value={item.id}>
            {item.label || item.id}
          </option>
        ))}
      </select>
      <span
        className="hidden h-9 items-center rounded-md border border-slate-200 bg-white px-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500 lg:inline-flex"
        data-testid="preview-object-manager-counts"
      >
        {objectManagerCounts.draft} draft / {objectManagerCounts.generated} generated
      </span>
      {selectedCadIds.length ? (
        <span
          data-testid="preview-object-manager-selection-count"
          className="h-9 items-center rounded-md border border-sky-200 bg-sky-50 px-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-sky-700"
        >
          {selectedCadIds.length} object{selectedCadIds.length === 1 ? "" : "s"} selected
        </span>
      ) : null}
      {selectedObject ? (
        <>
          <button
            type="button"
            aria-label="Deselect canvas object"
            title="Deselect canvas object"
            data-testid="preview-object-manager-clear-selection"
            onClick={() => {
              onSetManagedObjectId(null);
              onSelectBuilding(null);
              onSelectObjects?.([]);
              onSetCadSelectionSet([]);
              onClearSelectedVertex();
              onSetCadCommandStatus("Selection cleared.");
            }}
            className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
          >
            <X className="h-4 w-4" />
          </button>
          <input
            aria-label="Rename selected object"
            data-testid="preview-object-manager-rename"
            value={selectedObject.label || ""}
            onChange={(event) => {
              const blocker = getPreviewObjectActionBlocker(selectedObject, "rename");
              if (blocker) {
                onSetCadCommandStatus(blocker);
                return;
              }
              onUpdatePreviewManagedObject(selectedObject, { label: event.target.value });
            }}
            className="h-9 min-w-[128px] max-w-[190px] rounded-md border border-slate-200 bg-white px-2 text-xs font-semibold text-slate-800"
          />
          <span
            className="hidden h-9 max-w-[190px] items-center truncate rounded-md border border-slate-200 bg-white px-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500 xl:inline-flex"
            data-testid="preview-object-manager-selected-status"
          >
            {getPreviewObjectDimensionsLabel(selectedObject)}
          </span>
          <details className="hidden h-9 max-w-[210px] items-center rounded-md border border-slate-200 bg-white px-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500 xl:inline-flex">
            <summary className="cursor-pointer list-none whitespace-nowrap">Details</summary>
            <div className="absolute right-4 top-24 z-[140] w-72 rounded-xl border border-slate-200 bg-white p-3 text-left normal-case tracking-normal text-slate-600 shadow-xl">
              <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">Selected object</p>
              <p className="mt-2 text-xs font-semibold text-slate-800">{getPreviewObjectSourceLabel(selectedObject)}</p>
              <p className="mt-1 text-xs text-slate-500">{getPreviewObjectStatusLabel(selectedObject)}</p>
              <p className="mt-1 text-xs text-slate-500">{getPreviewObjectDimensionsLabel(selectedObject)}</p>
            </div>
          </details>
          <input
            type="color"
            aria-label="Change selected object color"
            data-testid="preview-object-manager-color"
            value={String(selectedObject.meta?.ui_color || selectedObject.meta?.color || "#64748b")}
            onChange={(event) => {
              const blocker = getPreviewObjectActionBlocker(selectedObject, "style");
              if (blocker) {
                onSetCadCommandStatus(blocker);
                return;
              }
              onUpdatePreviewManagedObject(selectedObject, {
                meta: { ...(selectedObject.meta ?? {}), ui_color: event.target.value },
              });
            }}
            className="h-9 w-10 rounded-md border border-slate-200 bg-white p-1"
          />
          <select
            aria-label="Change selected object layer or type"
            data-testid="preview-object-manager-type"
            value={selectedObject.type ?? "custom"}
            onChange={(event) => {
              const blocker = getPreviewObjectActionBlocker(selectedObject, "type");
              if (blocker) {
                onSetCadCommandStatus(blocker);
                return;
              }
              const type = event.target.value as BuildingPlacement["type"];
              onUpdatePreviewManagedObject(selectedObject, {
                type,
                meta: {
                  ...(selectedObject.meta ?? {}),
                  cad_layer: getCadLayer({ ...selectedObject, type }),
                },
              });
            }}
            className="h-9 max-w-[132px] rounded-md border border-slate-200 bg-white px-2 text-xs font-semibold capitalize text-slate-700"
          >
            {PREVIEW_OBJECT_TYPES.map((option) => (
              <option key={`preview-object-type-${option.type}`} value={option.type}>
                {option.label}
              </option>
            ))}
          </select>
          <button
            type="button"
            aria-label="Focus selected object"
            data-testid="preview-object-manager-focus"
            onClick={() => onFocusPreviewManagedObject(selectedObject)}
            className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
          >
            <Maximize2 className="h-4 w-4" />
          </button>
          <button
            type="button"
            aria-label={selectedObject.meta?.ui_hidden ? "Show selected object" : "Hide selected object"}
            data-testid="preview-object-manager-visibility"
            onClick={() => {
              const blocker = getPreviewObjectActionBlocker(selectedObject, "hide");
              if (blocker) {
                onSetCadCommandStatus(blocker);
                return;
              }
              onUpdatePreviewManagedObject(selectedObject, {
                meta: {
                  ...(selectedObject.meta ?? {}),
                  ui_hidden: !Boolean(selectedObject.meta?.ui_hidden),
                },
              });
            }}
            className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
          >
            {selectedObject.meta?.ui_hidden ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
          </button>
          <button
            type="button"
            aria-label="Delete selected object"
            data-testid="preview-object-manager-delete"
            onClick={() => {
              const blocker = getPreviewObjectActionBlocker(selectedObject, "delete");
              if (blocker) {
                onSetCadCommandStatus(blocker);
                return;
              }
              onSetLastRectEdit({
                id: selectedObject.id,
                snapshot: { ...selectedObject },
                action: "delete",
                ts: Date.now(),
              });
              onRemoveBuilding(selectedObject.id);
            }}
            className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-rose-200 bg-white text-rose-600 hover:bg-rose-50"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </>
      ) : null}
    </section>
  );
}
