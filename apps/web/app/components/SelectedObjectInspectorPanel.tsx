import type { BuildingPlacement } from "../types";
import {
  parkingDependencyRelationship,
  setParkingDependencyPolicy,
  setParkingDependencyObjectLinked,
  type CanonicalDependencyPolicy,
} from "../utils/canonicalDependencyPolicies";
import { SITE_OBJECT_CATALOG } from "../utils/siteObjectCatalog";

type ObjectConfidenceSummary = {
  confidence_band?: string;
  visible_badge?: string;
  source_type?: string;
  needs_survey_control?: boolean;
  why_low_confidence?: string;
  next_action?: string;
} | null;

type SelectedObjectInspectorPanelProps = {
  selectedBuilding: BuildingPlacement | null;
  availableObjects?: BuildingPlacement[];
  confidenceEntry?: ObjectConfidenceSummary;
  objectManagerStatusMessage?: string;
  objectClipboardCount: number;
  displayType: string;
  reviewLabel: string;
  sourceLabel: string;
  layerLabel: string;
  dimensionsLabel: string;
  editableGeometry?: Array<[number, number]>;
  editBlocked: boolean;
  onRename: (item: BuildingPlacement, value: string) => void;
  onToggleLock: (item: BuildingPlacement) => void;
  onToggleHidden: (item: BuildingPlacement) => void;
  onUpdateObject: (item: BuildingPlacement, updates: Partial<BuildingPlacement>) => void;
  onUpdateVertex: (item: BuildingPlacement, index: number, axis: "x" | "y", value: string) => void;
  onInsertVertex: (item: BuildingPlacement, index: number) => void;
  onDeleteVertex: (item: BuildingPlacement, index: number) => void;
  onSnapVertex: (item: BuildingPlacement, index: number) => void;
  onAlignVertex: (item: BuildingPlacement, index: number, axis: "x" | "y") => void;
  onMove: (item: BuildingPlacement) => void;
  onFocus: (item: BuildingPlacement) => void;
  onCopy: (item: BuildingPlacement) => void;
  onPaste: () => void;
  onTransform: (item: BuildingPlacement, transform: "rotate" | "flip_horizontal" | "flip_vertical") => void;
  onDelete: (item: BuildingPlacement) => void;
};

const parsePositiveNumber = (value: string) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
};

export function SelectedObjectInspectorPanel({
  selectedBuilding,
  availableObjects = [],
  confidenceEntry,
  objectManagerStatusMessage,
  objectClipboardCount,
  displayType,
  reviewLabel,
  sourceLabel,
  layerLabel,
  dimensionsLabel,
  editableGeometry,
  editBlocked,
  onRename,
  onToggleLock,
  onToggleHidden,
  onUpdateObject,
  onUpdateVertex,
  onInsertVertex,
  onDeleteVertex,
  onSnapVertex,
  onAlignVertex,
  onMove,
  onFocus,
  onCopy,
  onPaste,
  onTransform,
  onDelete,
}: SelectedObjectInspectorPanelProps) {
  const supportsHeight = Boolean(
    selectedBuilding &&
      ((SITE_OBJECT_CATALOG[selectedBuilding.type ?? "custom"]?.defaultH ?? 0) > 0 || (selectedBuilding.h ?? 0) > 0),
  );
  const supportsParkingRelationship = Boolean(
    selectedBuilding && ["building", "office_building", "retail_building", "multifamily_building", "industrial_building", "pad"].includes(selectedBuilding.type ?? ""),
  );
  const availableParking = availableObjects.filter((item) => item.type === "parking" && item.id !== selectedBuilding?.id);
  const linkedParkingIds = selectedBuilding ? new Set(parkingDependencyRelationship(selectedBuilding).object_ids) : new Set<string>();
  const parkingReflow = selectedBuilding?.type === "parking"
    ? selectedBuilding.meta?.parking_reflow_v1 as {
        status?: "clear" | "review";
        strategy?: string;
        inside_site?: boolean;
        collision_object_ids?: string[];
        stall_count_preserved?: boolean;
      } | undefined
    : undefined;
  const parkingParams = selectedBuilding?.type === "parking"
    ? (selectedBuilding.meta?.parkingParams as Record<string, unknown> | undefined) ?? {}
    : {};
  const parkingLayout = selectedBuilding?.type === "parking"
    ? selectedBuilding.meta?.parking_layout_v1 as {
        status?: "fits" | "shortfall" | "invalid";
        requested_stalls?: number;
        generated_stalls?: number;
        capacity?: number;
        shortfall?: number;
        excess_capacity?: number;
        required_width_ft?: number;
        required_depth_ft?: number;
      } | undefined
    : undefined;
  const updateParkingParams = (updates: Record<string, unknown>) => {
    if (!selectedBuilding) return;
    onUpdateObject(selectedBuilding, {
      meta: {
        ...(selectedBuilding.meta ?? {}),
        parkingParams: { ...parkingParams, ...updates },
      },
    });
  };
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4" data-testid="selected-object-inspector">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Selected Object Inspector</p>
          <p className="mt-1 text-sm text-slate-600">Review-only object controls tied to the canvas selection.</p>
        </div>
        {selectedBuilding ? (
          <span className="shrink-0 rounded-full bg-slate-50 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500">
            {selectedBuilding.meta?.ui_hidden ? "Hidden" : "Visible"}
          </span>
        ) : null}
      </div>
      {selectedBuilding ? (
        <div className="mt-3 space-y-2 text-sm text-slate-700">
          {confidenceEntry ? (
            <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2" data-testid="selected-object-confidence-badge">
              <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">Source confidence</p>
              <div className="mt-1 flex flex-wrap items-center gap-2">
                <span className={`rounded-full px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${
                  confidenceEntry.confidence_band === "higher"
                    ? "bg-emerald-50 text-emerald-700"
                    : confidenceEntry.confidence_band === "review"
                      ? "bg-amber-50 text-amber-700"
                      : "bg-red-50 text-red-700"
                }`}>
                  {confidenceEntry.visible_badge || confidenceEntry.source_type || "low confidence"}
                </span>
                <span className="text-xs font-medium text-slate-500">
                  {confidenceEntry.needs_survey_control ? "needs survey control" : "verification visible"}
                </span>
              </div>
              <p className="mt-1 text-xs text-slate-500">
                {confidenceEntry.why_low_confidence || confidenceEntry.next_action}
              </p>
            </div>
          ) : null}
          <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
            <label className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">
              Name
              <input
                type="text"
                value={selectedBuilding.label}
                onChange={(event) => onRename(selectedBuilding, event.target.value)}
                aria-label="Selected object name"
                data-testid="selected-object-name-input"
                className="mt-1 w-full rounded-md border border-slate-200 bg-white px-2 py-1 text-sm font-semibold normal-case tracking-normal text-slate-900"
              />
              <span className="mt-1 block text-xs font-semibold normal-case tracking-normal text-slate-700" data-testid="selected-object-name-value">
                {selectedBuilding.label || "Unnamed object"}
              </span>
            </label>
          </div>
          <div className="grid grid-cols-2 gap-2" data-testid="selected-object-inspector-facts">
            {[
              ["Type", displayType],
              ["Status", reviewLabel],
              ["Source", sourceLabel],
              ["Layer", layerLabel],
            ].map(([label, value]) => (
              <div key={label} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
                <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">{label}</p>
                <p className="mt-1 font-semibold text-slate-900">{value}</p>
              </div>
            ))}
            <div className="col-span-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
              <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">Dimensions / metrics</p>
              <p className="mt-1 font-semibold text-slate-900">{dimensionsLabel}</p>
            </div>
          </div>
          <p className={`rounded-xl border px-3 py-2 text-xs font-semibold ${
            selectedBuilding.type === "site"
              ? "border-slate-200 bg-slate-50 text-slate-600"
              : selectedBuilding.locked
                ? "border-amber-200 bg-amber-50 text-amber-800"
                : selectedBuilding.placed
                  ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                  : "border-amber-200 bg-amber-50 text-amber-800"
          }`}>
            {selectedBuilding.type === "site"
              ? "Move/edit is controlled from Setup for the site boundary."
              : selectedBuilding.locked
                ? "Move/edit needs the object unlocked first."
                : selectedBuilding.placed
                  ? "Move/edit controls available for this draft object."
                  : "Move/edit needs the object placed first."}
          </p>
          <p className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-800">
            Review-only: this object is draft/site evidence for qualified review, not final professional output.
          </p>
          {objectManagerStatusMessage ? (
            <p className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-700" data-testid="selected-object-status">
              {objectManagerStatusMessage}
            </p>
          ) : null}
          {parkingReflow ? (
            <div
              data-testid="parking-reflow-status"
              className={`rounded-xl border px-3 py-2 text-xs ${parkingReflow.status === "clear" ? "border-emerald-200 bg-emerald-50 text-emerald-800" : "border-amber-200 bg-amber-50 text-amber-800"}`}
            >
              <p className="font-bold uppercase tracking-[0.12em]">Parking reflow · {parkingReflow.status === "clear" ? "checks clear" : "review needed"}</p>
              <p className="mt-1 font-medium">
                {parkingReflow.stall_count_preserved ? "Stall count preserved. " : "Stall count needs review. "}
                Strategy: {(parkingReflow.strategy ?? "best available").replaceAll("_", " ")}.
                {parkingReflow.collision_object_ids?.length ? ` Possible contact with ${parkingReflow.collision_object_ids.length} object(s).` : " No basic footprint collision found."}
              </p>
            </div>
          ) : null}
          {selectedBuilding.type === "parking" ? (
            <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3" data-testid="parking-layout-editor">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-slate-500">Parking capacity</p>
                  <p className="mt-1 text-sm font-bold text-slate-900">
                    {parkingLayout?.generated_stalls ?? selectedBuilding.stallCount ?? 0} generated / {parkingLayout?.capacity ?? (Number.isFinite(Number(selectedBuilding.meta?.parkingCapacity)) ? Number(selectedBuilding.meta?.parkingCapacity) : "—")} capacity
                  </p>
                </div>
                <span data-testid="parking-layout-status" className={`rounded-full px-2 py-1 text-[10px] font-bold uppercase ${parkingLayout?.status === "shortfall" || parkingLayout?.status === "invalid" ? "bg-red-100 text-red-700" : "bg-emerald-100 text-emerald-700"}`}>
                  {parkingLayout?.status === "shortfall" ? `${parkingLayout.shortfall} short` : parkingLayout?.status === "invalid" ? "Needs input" : "Fits"}
                </span>
              </div>
              {parkingLayout?.status === "shortfall" ? (
                <p className="mt-2 rounded-lg bg-red-50 px-2 py-1.5 text-[11px] font-semibold text-red-700">
                  Increase the field toward {Math.ceil(parkingLayout.required_width_ft ?? selectedBuilding.w)} ft × {Math.ceil(parkingLayout.required_depth_ft ?? selectedBuilding.d)} ft, reduce stalls, or change the parking angle.
                </p>
              ) : null}
              <div className="mt-3 grid grid-cols-2 gap-2 text-[11px]">
                <label className="font-semibold text-slate-600">Requested stalls<input data-testid="parking-requested-stalls" type="number" min="0" value={selectedBuilding.stallCount ?? 0} onChange={(event) => onUpdateObject(selectedBuilding, { stallCount: Math.max(0, Number(event.target.value) || 0) })} className="mt-1 w-full rounded-md border border-slate-200 bg-white px-2 py-1.5" /></label>
                <label className="font-semibold text-slate-600">ADA stalls<input data-testid="parking-ada-count" type="number" min="0" value={Number(parkingParams.adaCount ?? selectedBuilding.meta?.adaCount ?? 0)} onChange={(event) => updateParkingParams({ adaCount: Math.max(0, Number(event.target.value) || 0) })} className="mt-1 w-full rounded-md border border-slate-200 bg-white px-2 py-1.5" /></label>
                <label className="font-semibold text-slate-600">Stall width<input type="number" min="6" step="0.5" value={Number(parkingParams.stallWidth ?? 9)} onChange={(event) => updateParkingParams({ stallWidth: Number(event.target.value) || 9 })} className="mt-1 w-full rounded-md border border-slate-200 bg-white px-2 py-1.5" /></label>
                <label className="font-semibold text-slate-600">Stall depth<input type="number" min="12" step="0.5" value={Number(parkingParams.stallDepth ?? 18)} onChange={(event) => updateParkingParams({ stallDepth: Number(event.target.value) || 18 })} className="mt-1 w-full rounded-md border border-slate-200 bg-white px-2 py-1.5" /></label>
                <label className="font-semibold text-slate-600">Drive aisle<input type="number" min="10" step="1" value={Number(parkingParams.aisleWidth ?? 24)} onChange={(event) => updateParkingParams({ aisleWidth: Number(event.target.value) || 24 })} className="mt-1 w-full rounded-md border border-slate-200 bg-white px-2 py-1.5" /></label>
                <label className="font-semibold text-slate-600">Compact stalls<input type="number" min="0" value={Number(parkingParams.compactCount ?? 0)} onChange={(event) => updateParkingParams({ compactCount: Math.max(0, Number(event.target.value) || 0) })} className="mt-1 w-full rounded-md border border-slate-200 bg-white px-2 py-1.5" /></label>
                <label className="font-semibold text-slate-600">Angle<select data-testid="parking-angle" value={String(parkingParams.angleDeg ?? 90)} onChange={(event) => updateParkingParams({ angleDeg: Number(event.target.value) })} className="mt-1 w-full rounded-md border border-slate-200 bg-white px-2 py-1.5"><option value="90">90°</option><option value="60">60°</option><option value="45">45°</option></select></label>
                <label className="font-semibold text-slate-600">Loading<select value={String(parkingParams.loading ?? "double")} onChange={(event) => updateParkingParams({ loading: event.target.value })} className="mt-1 w-full rounded-md border border-slate-200 bg-white px-2 py-1.5"><option value="double">Double</option><option value="single">Single</option></select></label>
              </div>
            </div>
          ) : null}
          <div className="grid grid-cols-2 gap-2">
            <button type="button" onClick={() => onToggleLock(selectedBuilding)} disabled={selectedBuilding.type === "site"} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50">
              {selectedBuilding.locked ? "Unlock object" : "Lock object"}
            </button>
            <button
              type="button"
              onClick={() => onToggleHidden(selectedBuilding)}
              disabled={selectedBuilding.type === "site"}
              data-testid="selected-object-hide-toggle"
              className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {selectedBuilding.meta?.ui_hidden ? "Show object" : "Hide object"}
            </button>
          </div>
          {supportsParkingRelationship ? (
            <div className="rounded-xl border border-blue-100 bg-blue-50/60 px-3 py-3" data-testid="parking-dependency-policy-control">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-blue-600">When this building changes</p>
                  <p className="mt-1 text-xs font-medium text-slate-600">Choose whether linked parking responds automatically.</p>
                </div>
                <select
                  aria-label="Linked parking behavior"
                  data-testid="parking-dependency-policy"
                  value={parkingDependencyRelationship(selectedBuilding).policy}
                  onChange={(event) => onUpdateObject(
                    selectedBuilding,
                    setParkingDependencyPolicy(selectedBuilding, event.target.value as CanonicalDependencyPolicy),
                  )}
                  className="h-9 rounded-lg border border-blue-200 bg-white px-2 text-xs font-bold text-slate-800"
                >
                  <option value="follow">Follow</option>
                  <option value="ask">Ask</option>
                  <option value="fixed">Fixed</option>
                </select>
              </div>
              <div className="mt-3 border-t border-blue-100 pt-3" data-testid="parking-relationship-editor">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-blue-600">Linked parking</p>
                  <span className="rounded-full bg-white px-2 py-0.5 text-[10px] font-bold text-slate-600">{linkedParkingIds.size} linked</span>
                </div>
                {availableParking.length ? (
                  <div className="mt-2 space-y-1.5">
                    {availableParking.map((parking) => {
                      const linked = linkedParkingIds.has(parking.id);
                      return (
                        <label key={parking.id} className="flex cursor-pointer items-center justify-between gap-3 rounded-lg border border-blue-100 bg-white px-2.5 py-2 text-xs font-semibold text-slate-700">
                          <span className="min-w-0 truncate">{parking.label}</span>
                          <input
                            type="checkbox"
                            checked={linked}
                            data-testid={`parking-relationship-${parking.id}`}
                            aria-label={`${linked ? "Unlink" : "Link"} ${parking.label}`}
                            onChange={(event) => onUpdateObject(
                              selectedBuilding,
                              setParkingDependencyObjectLinked(selectedBuilding, parking.id, event.target.checked),
                            )}
                            className="h-4 w-4 rounded border-blue-300 text-blue-600"
                          />
                        </label>
                      );
                    })}
                  </div>
                ) : (
                  <p className="mt-2 text-xs text-slate-500">Add a parking field to create a relationship.</p>
                )}
                <p className="mt-2 text-[11px] leading-4 text-slate-500">Only checked parking fields respond to Follow or Ask.</p>
              </div>
            </div>
          ) : null}
          <div className="grid grid-cols-2 gap-2 text-[11px]" data-testid="selected-object-exact-geometry">
            <label className="flex flex-col gap-1 font-semibold uppercase tracking-[0.12em] text-slate-500">
              X
              <input
                type="number"
                value={Math.round(selectedBuilding.x ?? 0)}
                aria-label="Selected object X position"
                data-testid="selected-object-x-input"
                onChange={(event) => onUpdateObject(selectedBuilding, { x: Number(event.target.value) || 0 })}
                className="rounded-md border border-slate-200 px-2 py-1 normal-case tracking-normal text-slate-700"
              />
            </label>
            <label className="flex flex-col gap-1 font-semibold uppercase tracking-[0.12em] text-slate-500">
              Y
              <input
                type="number"
                value={Math.round(selectedBuilding.y ?? 0)}
                aria-label="Selected object Y position"
                data-testid="selected-object-y-input"
                onChange={(event) => onUpdateObject(selectedBuilding, { y: Number(event.target.value) || 0 })}
                className="rounded-md border border-slate-200 px-2 py-1 normal-case tracking-normal text-slate-700"
              />
            </label>
            <label className="flex flex-col gap-1 font-semibold uppercase tracking-[0.12em] text-slate-500">
              W
              <input
                type="number"
                value={Math.round(selectedBuilding.w ?? 0)}
                aria-label="Selected object width"
                data-testid="selected-object-width-input"
                onChange={(event) => onUpdateObject(selectedBuilding, { w: parsePositiveNumber(event.target.value) ?? selectedBuilding.w })}
                className="rounded-md border border-slate-200 px-2 py-1 normal-case tracking-normal text-slate-700"
              />
            </label>
            <label className="flex flex-col gap-1 font-semibold uppercase tracking-[0.12em] text-slate-500">
              D
              <input
                type="number"
                value={Math.round(selectedBuilding.d ?? 0)}
                aria-label="Selected object depth"
                data-testid="selected-object-depth-input"
                onChange={(event) => onUpdateObject(selectedBuilding, { d: parsePositiveNumber(event.target.value) ?? selectedBuilding.d })}
                className="rounded-md border border-slate-200 px-2 py-1 normal-case tracking-normal text-slate-700"
              />
            </label>
            <label className="flex flex-col gap-1 font-semibold uppercase tracking-[0.12em] text-slate-500">
              Rotation
              <input
                type="number"
                value={Math.round(selectedBuilding.rotation ?? 0)}
                aria-label="Selected object rotation"
                data-testid="selected-object-rotation-input"
                onChange={(event) => onUpdateObject(selectedBuilding, { rotation: Number(event.target.value) || 0 })}
                className="rounded-md border border-slate-200 px-2 py-1 normal-case tracking-normal text-slate-700"
              />
            </label>
            {supportsHeight ? (
              <label className="flex flex-col gap-1 font-semibold uppercase tracking-[0.12em] text-slate-500">
                Height (ft)
                <input
                  type="number"
                  min={1}
                  max={500}
                  value={Math.round(selectedBuilding.h ?? SITE_OBJECT_CATALOG[selectedBuilding.type ?? "custom"]?.defaultH ?? 1)}
                  aria-label="Selected object height"
                  data-testid="selected-object-height-input-details"
                  onChange={(event) => onUpdateObject(selectedBuilding, {
                    h: Math.max(1, Math.min(parsePositiveNumber(event.target.value) ?? selectedBuilding.h ?? 1, 500)),
                  })}
                  className="rounded-md border border-slate-200 px-2 py-1 normal-case tracking-normal text-slate-700"
                />
              </label>
            ) : null}
            <label className="flex flex-col gap-1 font-semibold uppercase tracking-[0.12em] text-slate-500">
              Source
              <input
                value={sourceLabel}
                readOnly
                className="rounded-md border border-slate-200 bg-slate-50 px-2 py-1 normal-case tracking-normal text-slate-700"
              />
            </label>
          </div>
          {editableGeometry?.length ? (
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-3" data-testid="selected-object-vertex-editor">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">Vertex editor</p>
                  <p className="mt-1 text-xs font-medium text-slate-500">
                    Exact draft coordinates. Editing vertices does not create engineering approval.
                  </p>
                </div>
                <span className="rounded-full bg-white px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500">
                  {editableGeometry.length} point{editableGeometry.length === 1 ? "" : "s"}
                </span>
              </div>
              <div className="mt-3 max-h-48 space-y-2 overflow-y-auto pr-1">
                {editableGeometry.map(([x, y], index) => (
                  <div key={`${selectedBuilding.id}-vertex-${index}`} className="grid grid-cols-[auto_1fr_1fr_auto] items-end gap-2 rounded-lg border border-slate-100 bg-white px-2 py-2" data-testid="selected-object-vertex-row">
                    <span className="pb-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-400">V{index + 1}</span>
                    <label className="flex flex-col gap-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500">
                      X
                      <input
                        type="number"
                        value={Math.round(x * 10) / 10}
                        disabled={editBlocked}
                        aria-label={`Vertex ${index + 1} X`}
                        data-testid="selected-object-vertex-x"
                        onInput={(event) => onUpdateVertex(selectedBuilding, index, "x", event.currentTarget.value)}
                        onChange={(event) => onUpdateVertex(selectedBuilding, index, "x", event.target.value)}
                        className="rounded-md border border-slate-200 px-2 py-1 text-xs font-semibold normal-case tracking-normal text-slate-700 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-400"
                      />
                    </label>
                    <label className="flex flex-col gap-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500">
                      Y
                      <input
                        type="number"
                        value={Math.round(y * 10) / 10}
                        disabled={editBlocked}
                        aria-label={`Vertex ${index + 1} Y`}
                        data-testid="selected-object-vertex-y"
                        onInput={(event) => onUpdateVertex(selectedBuilding, index, "y", event.currentTarget.value)}
                        onChange={(event) => onUpdateVertex(selectedBuilding, index, "y", event.target.value)}
                        className="rounded-md border border-slate-200 px-2 py-1 text-xs font-semibold normal-case tracking-normal text-slate-700 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-400"
                      />
                    </label>
                    <div className="flex flex-col gap-1">
                      <button type="button" disabled={editBlocked || selectedBuilding.geometryType === "point"} onClick={() => onInsertVertex(selectedBuilding, index)} data-testid="selected-object-vertex-insert" className="rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-600 hover:bg-white disabled:cursor-not-allowed disabled:opacity-40">
                        Add
                      </button>
                      <button type="button" disabled={editBlocked} onClick={() => onDeleteVertex(selectedBuilding, index)} data-testid="selected-object-vertex-delete" className="rounded-md border border-rose-100 bg-white px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-rose-600 hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-40">
                        Del
                      </button>
                      <button type="button" disabled={editBlocked} onClick={() => onSnapVertex(selectedBuilding, index)} data-testid="selected-object-vertex-snap" className="rounded-md border border-blue-100 bg-white px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-blue-700 hover:bg-blue-50 disabled:cursor-not-allowed disabled:opacity-40">
                        Snap
                      </button>
                      <button type="button" disabled={editBlocked} onClick={() => onAlignVertex(selectedBuilding, index, "x")} data-testid="selected-object-vertex-align-x" className="rounded-md border border-emerald-100 bg-white px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-emerald-700 hover:bg-emerald-50 disabled:cursor-not-allowed disabled:opacity-40">
                        Align X
                      </button>
                      <button type="button" disabled={editBlocked} onClick={() => onAlignVertex(selectedBuilding, index, "y")} data-testid="selected-object-vertex-align-y" className="rounded-md border border-emerald-100 bg-white px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-emerald-700 hover:bg-emerald-50 disabled:cursor-not-allowed disabled:opacity-40">
                        Align Y
                      </button>
                    </div>
                  </div>
                ))}
              </div>
              {editBlocked ? (
                <p className="mt-2 rounded-lg border border-amber-200 bg-amber-50 px-2 py-2 text-[11px] font-semibold text-amber-800">
                  Unlock this draft object before editing vertices.
                </p>
              ) : null}
            </div>
          ) : null}
          <div className="grid grid-cols-2 gap-2" data-testid="selected-object-actions">
            <button type="button" onClick={() => onMove(selectedBuilding)} className="rounded-xl border border-slate-950 bg-slate-950 px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-white hover:bg-slate-800">
              Move
            </button>
            <button type="button" onClick={() => onFocus(selectedBuilding)} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50">
              Focus
            </button>
            <button type="button" onClick={() => onCopy(selectedBuilding)} data-testid="selected-object-copy" className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50">
              Copy
            </button>
            <button type="button" onClick={onPaste} disabled={!objectClipboardCount} data-testid="selected-object-paste" className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50">
              Paste
            </button>
            <button type="button" onClick={() => onTransform(selectedBuilding, "rotate")} data-testid="selected-object-rotate" className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50">
              Rotate 90
            </button>
            <button type="button" onClick={() => onTransform(selectedBuilding, "flip_horizontal")} data-testid="selected-object-flip-horizontal" className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50">
              Flip H
            </button>
            <button type="button" onClick={() => onTransform(selectedBuilding, "flip_vertical")} data-testid="selected-object-flip-vertical" className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50">
              Flip V
            </button>
            <button type="button" onClick={() => onDelete(selectedBuilding)} disabled={selectedBuilding.type === "site"} data-testid="selected-object-delete" className="rounded-xl border border-rose-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-rose-600 hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-50">
              Delete
            </button>
          </div>
        </div>
      ) : (
        <p className="mt-3 rounded-xl border border-slate-200 bg-slate-50 px-3 py-3 text-sm text-slate-500" data-testid="selected-object-empty-state">
          No object selected. Select an object in Object Manager or on the canvas to inspect it.
        </p>
      )}
    </div>
  );
}
