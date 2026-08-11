import { useState } from "react";

import type { BuildingPlacement, SiteObjectType } from "../types";
import { SITE_OBJECT_CATALOG } from "../utils/siteObjectCatalog";

type SelectedObjectCardProps = {
  selectedObject: BuildingPlacement | null;
  displayType: string;
  dimensionsLabel: string;
  objectTypeOptions: Array<{ type: SiteObjectType; label: string }>;
  objectOutlineColor: string;
  onRename: (item: BuildingPlacement, value: string) => void;
  onColor: (item: BuildingPlacement, value: string) => void;
  onType: (item: BuildingPlacement, type: SiteObjectType) => void;
  onHeight: (item: BuildingPlacement, heightFt: number) => void;
  onRoofProfile: (item: BuildingPlacement, profile: "flat" | "gable" | "dome" | "tower") => void;
  onToggleVisibility: (item: BuildingPlacement) => void;
  onMove: (item: BuildingPlacement) => void;
  onFocus: (item: BuildingPlacement) => void;
  onCopy: (item: BuildingPlacement) => void;
  onRotate: (item: BuildingPlacement) => void;
  onFlipHorizontal: (item: BuildingPlacement) => void;
  onDelete: (item: BuildingPlacement) => void;
  onClearSelection: () => void;
};

function BuildingHeightInput({
  label,
  value,
  onCommit,
}: {
  label: string;
  value: number | "";
  onCommit: (heightFt: number) => void;
}) {
  const [draft, setDraft] = useState(String(value));
  const commit = () => {
    const heightFt = Number(draft);
    if (Number.isFinite(heightFt) && heightFt > 0) {
      onCommit(heightFt);
      return;
    }
    setDraft(String(value));
  };

  return (
    <input
      type="number"
      min={1}
      max={500}
      step={1}
      value={draft}
      aria-label={`Height selected object ${label}`}
      data-testid="selected-object-height-input"
      onChange={(event) => setDraft(event.target.value)}
      onBlur={commit}
      onKeyDown={(event) => {
        if (event.key === "Enter") event.currentTarget.blur();
        if (event.key === "Escape") {
          setDraft(String(value));
          event.currentTarget.blur();
        }
      }}
      className="rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-sm font-semibold text-slate-900"
    />
  );
}

export function SelectedObjectCard({
  selectedObject,
  displayType,
  dimensionsLabel,
  objectTypeOptions,
  objectOutlineColor,
  onRename,
  onColor,
  onType,
  onHeight,
  onRoofProfile,
  onToggleVisibility,
  onMove,
  onFocus,
  onCopy,
  onRotate,
  onFlipHorizontal,
  onDelete,
  onClearSelection,
}: SelectedObjectCardProps) {
  const selectedHeight = selectedObject
    ? selectedObject.h ?? SITE_OBJECT_CATALOG[selectedObject.type ?? "custom"]?.defaultH ?? ""
    : "";
  const supportsHeight = Boolean(
    selectedObject &&
      ((SITE_OBJECT_CATALOG[selectedObject.type ?? "custom"]?.defaultH ?? 0) > 0 || (selectedObject.h ?? 0) > 0),
  );
  const supportsRoofProfile = Boolean(
    selectedObject && /building/.test(String(selectedObject.type || "")),
  );
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
        <div className="flex shrink-0 items-center gap-2">
          <span className="rounded-full bg-slate-50 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500">
            {selectedObject?.meta?.ui_hidden ? "Hidden" : selectedObject ? "Visible" : "None"}
          </span>
          {selectedObject ? (
            <button
              type="button"
              onClick={onClearSelection}
              data-testid="preview-object-manager-clear-selection"
              className="rounded-[7px] border border-slate-200 bg-white px-2.5 py-1 text-[10px] font-semibold text-slate-600 transition hover:bg-slate-50 hover:text-slate-950"
            >
              Clear
            </button>
          ) : null}
        </div>
      </div>
      {selectedObject ? (
        <>
          {selectedObject.type !== "site" ? (
            <div className="mt-3 grid grid-cols-[1fr_auto] gap-2 text-[11px]">
              <label className="col-span-2 flex flex-col gap-1 font-medium text-slate-500">
                Name
                <input
                  type="text"
                  value={selectedObject.label}
                  aria-label={`Rename selected object ${selectedObject.label}`}
                  data-testid="preview-object-manager-rename"
                  onChange={(event) => onRename(selectedObject, event.target.value)}
                  className="rounded-lg border border-slate-200 px-2 py-1.5 text-sm font-semibold text-slate-900"
                />
              </label>
              <label className="flex flex-col gap-1 font-medium text-slate-500">
                Classify outline as
                <select
                  value={selectedObject.type ?? "custom"}
                  aria-label={`Layer type selected object ${selectedObject.label}`}
                  data-testid="preview-object-manager-type"
                  onChange={(event) => onType(selectedObject, event.target.value as SiteObjectType)}
                  className="rounded-lg border border-slate-200 px-2 py-1.5 text-sm font-semibold text-slate-900"
                >
                  {objectTypeOptions.map((option) => (
                    <option key={option.type} value={option.type}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex flex-col gap-1 font-medium text-slate-500">
                Color
                <input
                  type="color"
                  value={String(selectedObject.meta?.ui_color || selectedObject.meta?.color || objectOutlineColor || "#64748b")}
                  aria-label={`Color selected object ${selectedObject.label}`}
                  data-testid="preview-object-manager-color"
                  onChange={(event) => onColor(selectedObject, event.target.value)}
                  className="h-9 w-12 rounded-lg border border-slate-200 bg-white"
                />
              </label>
              {supportsHeight ? (
                <div className="col-span-2 grid grid-cols-2 gap-2 rounded-xl border border-slate-200 bg-slate-50 p-2" data-testid="selected-object-3d-properties">
                  <label className={`flex flex-col gap-1 font-medium text-slate-500 ${supportsRoofProfile ? "" : "col-span-2"}`}>
                    Height (ft)
                    <BuildingHeightInput
                      key={`${selectedObject.id}:${selectedHeight}`}
                      label={selectedObject.label}
                      value={selectedHeight}
                      onCommit={(heightFt) => onHeight(selectedObject, heightFt)}
                    />
                  </label>
                  {supportsRoofProfile ? (
                    <label className="flex flex-col gap-1 font-medium text-slate-500">
                      Roof
                      <select
                        value={String(selectedObject.meta?.roof_profile || "flat")}
                        aria-label={`Roof selected object ${selectedObject.label}`}
                        data-testid="selected-object-roof-select"
                        onChange={(event) => onRoofProfile(selectedObject, event.target.value as "flat" | "gable" | "dome" | "tower")}
                        className="rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-sm font-semibold text-slate-900"
                      >
                        <option value="flat">Flat</option>
                        <option value="gable">Gable</option>
                        <option value="dome">Dome</option>
                        <option value="tower">Tower</option>
                      </select>
                    </label>
                  ) : null}
                </div>
              ) : null}
            </div>
          ) : null}
          <div className="mt-3 grid grid-cols-2 gap-2 text-[11px]">
            <button
              type="button"
              onClick={() => onMove(selectedObject)}
              data-testid="selected-object-move-on-canvas"
              className="rounded-lg border border-slate-950 bg-slate-950 px-3 py-2 font-semibold uppercase tracking-[0.12em] text-white hover:bg-slate-800"
            >
              Move
            </button>
            <button
              type="button"
              onClick={() => onFocus(selectedObject)}
              data-testid="preview-object-manager-focus"
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
              onClick={() => onToggleVisibility(selectedObject)}
              data-testid="preview-object-manager-visibility"
              disabled={selectedObject.type === "site"}
              className="rounded-lg border border-slate-200 bg-white px-3 py-2 font-semibold uppercase tracking-[0.12em] text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {selectedObject.meta?.ui_hidden ? "Show" : "Hide"}
            </button>
            <button
              type="button"
              onClick={() => onDelete(selectedObject)}
              disabled={selectedObject.type === "site"}
              className="col-span-2 rounded-lg border border-rose-200 bg-white px-3 py-2 font-semibold uppercase tracking-[0.12em] text-rose-600 hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Delete
            </button>
          </div>
        </>
      ) : null}
    </div>
  );
}
