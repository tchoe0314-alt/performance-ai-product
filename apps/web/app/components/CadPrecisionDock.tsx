"use client";

import type { Dispatch, SetStateAction } from "react";
import {
  CornerUpLeft,
  CornerUpRight,
  Eye,
  EyeOff,
  GitBranch,
  MapPin,
  Move,
  RefreshCw,
  RotateCw,
  Ruler,
  Scale,
  Scissors,
} from "lucide-react";

import type { BuildingPlacement, SiteObjectType } from "../types";
import type { CadDimensionMode, CadSymbolKind } from "../utils/cadToolTypes";
import type { CadSnapKind } from "../utils/cadGeometryKernel";
import { SITE_OBJECT_CATALOG } from "../utils/siteObjectCatalog";

type CadPoint = { x: number; y: number };
type CadHistoryEntry = {
  id: string;
  label: string;
  objectId: string;
  before: BuildingPlacement;
  after: BuildingPlacement;
};
type CadCommandHistoryEntry = {
  id: string;
  command: string;
  status: "applied" | "blocked" | "info";
  message: string;
};
type CadActiveCommand =
  | {
      kind: "draw";
      command: "LINE" | "PLINE" | "RECTANGLE";
      mode: "polyline" | "rect";
      minPoints: number;
    }
  | {
      kind: "offset";
      command: "OFFSET";
      distance?: number;
    }
  | {
      kind: "modify";
      command: "TRIM" | "EXTEND";
      amount?: number;
    }
  | {
      kind: "transform";
      command: "MOVE" | "ROTATE" | "SCALE" | "COPY";
      value?: string;
    }
  | null;
type CadPropertyDraft = {
  id: string;
  name: string;
  type: SiteObjectType;
  layer: string;
  elevation: string;
  material: string;
  size: string;
  source: string;
  sourceNote: string;
  reviewNote: string;
};
type CadMetrics = {
  segmentCount: number;
  totalLength: number;
  firstLength: number;
  firstAngle: number;
  layer: string;
};
type TopologyIssue = {
  code: string;
  objectIds: string[];
  message: string;
};

type CadPrecisionDockProps = {
  visible: boolean;
  selectedCadObject: BuildingPlacement | null;
  selectedCadIds: string[];
  selectedBuildingId: string | null;
  selectedCadMetrics: CadMetrics | null;
  cadSnapEnabled: boolean;
  cadOrthoEnabled: boolean;
  cadCoordinateDraft: { x: string; y: string };
  cadCommandDraft: string;
  cadCommandStatus: string;
  cadCommandHistory: CadCommandHistoryEntry[];
  cadActiveCommand: CadActiveCommand;
  draftPoints: Array<[number, number]>;
  cadHistory: CadHistoryEntry[];
  cadRedoStack: CadHistoryEntry[];
  lastPolylineEdit: unknown;
  lastRectEdit: unknown;
  activeSnapPoint: (CadPoint & { kind: CadSnapKind }) | null;
  cadTransformValue: string;
  cadDimensionMode: CadDimensionMode;
  cadDimensionLabelDraft: string;
  cadOffsetDistance: string;
  cadFilletRadius: string;
  cadLayerDraft: string;
  cadLayerOptions: string[];
  hiddenCadLayers: string[];
  cadSymbolDraft: CadSymbolKind;
  cadPropertyDraft: CadPropertyDraft;
  topologyIssues: TopologyIssue[];
  setCadSnapEnabled: (value: boolean) => void;
  setCadOrthoEnabled: (value: boolean) => void;
  setCadCoordinateDraft: Dispatch<SetStateAction<{ x: string; y: string }>>;
  setCadCommandDraft: (value: string) => void;
  setCadTransformValue: (value: string) => void;
  setCadDimensionMode: (value: CadDimensionMode) => void;
  setCadDimensionLabelDraft: (value: string) => void;
  setCadOffsetDistance: (value: string) => void;
  setCadFilletRadius: (value: string) => void;
  setCadLayerDraft: (value: string) => void;
  setCadSelectionSet: (ids: string[]) => void;
  setCadSymbolDraft: (value: CadSymbolKind) => void;
  setCadPropertyDraft: Dispatch<SetStateAction<CadPropertyDraft>>;
  undoCadCommand: () => void;
  redoCadCommand: () => void;
  applyCadCoordinate: () => void;
  runCadCommand: (commandOverride?: string) => void;
  transformSelectedCadObjects: (kind: "move" | "rotate" | "scale", valueOverride?: string) => void;
  applySelectedCadDimension: () => void;
  offsetSelectedCadObject: () => void;
  trimExtendSelectedCadObject: (kind: "trim" | "extend", amountOverride?: string) => void;
  filletSelectedCadObject: () => void;
  applySelectedCadLayer: () => void;
  toggleCadLayerVisibility: (layer: string) => void;
  insertCadSymbol: () => void;
  applyCadProperties: () => void;
};

export function CadPrecisionDock({
  visible,
  selectedCadObject,
  selectedCadIds,
  selectedBuildingId,
  selectedCadMetrics,
  cadSnapEnabled,
  cadOrthoEnabled,
  cadCoordinateDraft,
  cadCommandDraft,
  cadCommandStatus,
  cadCommandHistory,
  cadActiveCommand,
  draftPoints,
  cadHistory,
  cadRedoStack,
  lastPolylineEdit,
  lastRectEdit,
  activeSnapPoint,
  cadTransformValue,
  cadDimensionMode,
  cadDimensionLabelDraft,
  cadOffsetDistance,
  cadFilletRadius,
  cadLayerDraft,
  cadLayerOptions,
  hiddenCadLayers,
  cadSymbolDraft,
  cadPropertyDraft,
  topologyIssues,
  setCadSnapEnabled,
  setCadOrthoEnabled,
  setCadCoordinateDraft,
  setCadCommandDraft,
  setCadTransformValue,
  setCadDimensionMode,
  setCadDimensionLabelDraft,
  setCadOffsetDistance,
  setCadFilletRadius,
  setCadLayerDraft,
  setCadSelectionSet,
  setCadSymbolDraft,
  setCadPropertyDraft,
  undoCadCommand,
  redoCadCommand,
  applyCadCoordinate,
  runCadCommand,
  transformSelectedCadObjects,
  applySelectedCadDimension,
  offsetSelectedCadObject,
  trimExtendSelectedCadObject,
  filletSelectedCadObject,
  applySelectedCadLayer,
  toggleCadLayerVisibility,
  insertCadSymbol,
  applyCadProperties,
}: CadPrecisionDockProps) {
  if (!visible) return null;
  const classificationOptions = Object.entries(SITE_OBJECT_CATALOG)
    .filter(([type]) => type !== "site")
    .map(([type, definition]) => ({
      value: type as SiteObjectType,
      label: definition.label,
    }));

  return (
    <details
      className="civora-cad-dock group relative z-20 mb-3 shrink-0 overflow-hidden rounded-xl border border-slate-200 bg-white/95 shadow-sm"
      data-testid="cad-precision-tools"
    >
      <summary className="flex min-h-11 cursor-pointer list-none items-center gap-3 px-3 py-2 text-left marker:hidden">
        <span className="min-w-0 flex-1">
          <span className="block text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">
            Precision &amp; commands
          </span>
          <span className="block truncate text-xs font-semibold text-slate-800">
            {selectedCadObject?.label || "Coordinates, command input, layers, and properties"}
          </span>
        </span>
        <span className="rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500 group-open:hidden">
          Open
        </span>
        <span className="hidden rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500 group-open:inline-flex">
          Close
        </span>
      </summary>
      <div className="max-h-[min(55vh,42rem)] overflow-y-auto border-t border-slate-200 p-3">
        <div className="grid gap-3 xl:grid-cols-2 2xl:grid-cols-[1.05fr_1fr_1fr_1.1fr]">
      <section className="relative z-[30] min-w-0">
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Draft precision</p>
            <p className="mt-1 truncate text-sm font-semibold text-slate-900">
              {selectedCadObject?.label || "No draft object selected"}
            </p>
          </div>
          <div className="flex gap-1">
            <button
              type="button"
              aria-label="Undo draft command"
              title="Undo draft command"
              onClick={undoCadCommand}
              disabled={!cadHistory.length && !lastPolylineEdit && !lastRectEdit}
              className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-600 disabled:opacity-40"
            >
              <CornerUpLeft className="h-4 w-4" />
            </button>
            <button
              type="button"
              aria-label="Redo draft command"
              title="Redo draft command"
              onClick={redoCadCommand}
              disabled={!cadRedoStack.length}
              className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-600 disabled:opacity-40"
            >
              <CornerUpRight className="h-4 w-4" />
            </button>
          </div>
        </div>
        <div className="mt-3 grid grid-cols-2 gap-2 text-xs font-semibold text-slate-700 sm:grid-cols-4">
          <label className="flex min-h-10 items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-2">
            <input
              type="checkbox"
              checked={cadSnapEnabled}
              onChange={(event) => setCadSnapEnabled(event.target.checked)}
              className="h-4 w-4 accent-slate-950"
            />
            Snap
          </label>
          <label className="flex min-h-10 items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-2">
            <input
              type="checkbox"
              checked={cadOrthoEnabled}
              onChange={(event) => setCadOrthoEnabled(event.target.checked)}
              className="h-4 w-4 accent-slate-950"
            />
            Ortho
          </label>
          <span className="flex min-h-10 items-center rounded-lg border border-slate-200 bg-slate-50 px-2 text-[11px] uppercase tracking-[0.12em] text-slate-500">
            {activeSnapPoint ? activeSnapPoint.kind : "No snap"}
          </span>
          <span className="flex min-h-10 items-center rounded-lg border border-slate-200 bg-slate-50 px-2 text-[11px] uppercase tracking-[0.12em] text-slate-500">
            {cadHistory.at(-1)?.label || "No command"}
          </span>
        </div>
        <div className="mt-3 grid grid-cols-[1fr_1fr_auto] gap-2">
          <input
            aria-label="Draft X coordinate"
            inputMode="decimal"
            value={cadCoordinateDraft.x}
            onChange={(event) => setCadCoordinateDraft((prev) => ({ ...prev, x: event.target.value }))}
            placeholder="X ft"
            className="h-9 min-w-0 rounded-md border border-slate-200 bg-white px-2 text-sm text-slate-700"
          />
          <input
            aria-label="Draft Y coordinate"
            inputMode="decimal"
            value={cadCoordinateDraft.y}
            onChange={(event) => setCadCoordinateDraft((prev) => ({ ...prev, y: event.target.value }))}
            placeholder="Y ft"
            className="h-9 min-w-0 rounded-md border border-slate-200 bg-white px-2 text-sm text-slate-700"
          />
          <button
            type="button"
            onClick={applyCadCoordinate}
            className="relative z-[40] inline-flex h-9 items-center gap-1.5 rounded-md border border-slate-900 bg-slate-950 px-3 text-xs font-semibold uppercase tracking-[0.12em] text-white"
          >
            <MapPin className="h-3.5 w-3.5" />
            XY
          </button>
        </div>
        <div className="mt-3">
          <p className="mb-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500">Draft command line</p>
          <div className="grid grid-cols-[1fr_auto] gap-2">
            <input
              aria-label="Draft command input"
              value={cadCommandDraft}
              onChange={(event) => setCadCommandDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  runCadCommand();
                }
              }}
              placeholder={cadActiveCommand ? "Next point, FINISH, or CANCEL" : "LINE, then 0,0, then 100,0"}
              className="h-9 min-w-0 rounded-md border border-slate-200 bg-white px-2 text-sm text-slate-700"
            />
            <button
              type="button"
              onClick={() => runCadCommand()}
              className="h-9 rounded-md border border-slate-900 bg-slate-950 px-3 text-xs font-semibold uppercase tracking-[0.12em] text-white"
            >
              Run
            </button>
          </div>
        </div>
        {cadActiveCommand ? (
          <div
            className="mt-2 rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-[11px] font-semibold text-blue-800"
            data-testid="cad-active-command"
          >
            {cadActiveCommand.kind === "draw"
              ? `Active command: ${cadActiveCommand.command} · ${draftPoints.length}/${cadActiveCommand.minPoints}+ point${draftPoints.length === 1 ? "" : "s"} · type next coordinate or run empty to finish.`
              : cadActiveCommand.kind === "offset"
                ? `Active command: OFFSET · ${typeof cadActiveCommand.distance === "number" ? `${cadActiveCommand.distance} ft` : "distance needed"} · type distance or run empty after selecting an object.`
                : cadActiveCommand.kind === "modify"
                  ? `Active command: ${cadActiveCommand.command} · ${typeof cadActiveCommand.amount === "number" ? `${cadActiveCommand.amount} ft` : "amount needed"} · type amount or run empty after selecting a line.`
                  : `Active command: ${cadActiveCommand.command} · ${cadActiveCommand.value || (cadActiveCommand.command === "MOVE" || cadActiveCommand.command === "COPY" ? "vector needed" : cadActiveCommand.command === "ROTATE" ? "angle needed" : "factor needed")} · type the value, then press Run.`}
          </div>
        ) : null}
        <p className="mt-2 text-[11px] font-medium text-slate-500">{cadCommandStatus}</p>
        <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 p-2" data-testid="cad-power-tools">
          <div className="flex items-center justify-between gap-2">
            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500">
              Power tools
            </p>
            <span className="text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-400">
              Same as typed commands
            </span>
          </div>
          <div className="mt-2 grid grid-cols-4 gap-1.5 text-[10px] font-semibold uppercase tracking-[0.1em]">
            {[
              ["join", "Join", "JOIN"],
              ["split", "Split", "SPLIT"],
              ["copy", "Copy", "COPY selected 10,10"],
              ["rotate", "Rotate", "ROTATE 45"],
              ["mirror", "Mirror", "MIRROR H"],
              ["array", "Array", "ARRAY 2 2 20,20"],
              ["hatch", "Hatch", "HATCH"],
              ["align", "Align", "ALIGN LEFT"],
            ].map(([id, label, command]) => (
              <button
                key={id}
                type="button"
                data-testid={`cad-power-${id}`}
                aria-label={`${label} selected draft objects`}
                onClick={() => runCadCommand(command)}
                className="rounded-md border border-slate-200 bg-white px-2 py-1.5 text-slate-600 transition hover:border-slate-300 hover:bg-white"
              >
                {label}
              </button>
            ))}
          </div>
        </div>
        <div className="mt-2 max-h-28 overflow-y-auto rounded-lg border border-slate-200 bg-slate-50 p-2" data-testid="cad-command-feedback-panel" aria-live="polite">
          {cadCommandHistory.length ? (
            <ol className="space-y-1 text-[11px]">
              {cadCommandHistory.slice().reverse().map((entry) => (
                <li key={entry.id} className="grid grid-cols-[4.5rem_1fr] gap-2">
                  <span className={entry.status === "blocked" ? "font-semibold text-amber-700" : entry.status === "applied" ? "font-semibold text-emerald-700" : "font-semibold text-slate-500"}>
                    {entry.command}
                  </span>
                  <span className="min-w-0 break-words text-slate-600">{entry.message}</span>
                </li>
              ))}
            </ol>
          ) : (
            <p className="text-[11px] font-medium text-slate-500">Command feedback appears here.</p>
          )}
        </div>
      </section>
      <section className="min-w-0">
        <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Readout / transform</p>
        <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
          {[
            ["Length", selectedCadMetrics ? `${selectedCadMetrics.totalLength.toFixed(1)} ft` : "Select object"],
            ["Angle", selectedCadMetrics ? `${selectedCadMetrics.firstAngle.toFixed(1)} deg` : "Select object"],
            ["Segments", selectedCadMetrics ? String(selectedCadMetrics.segmentCount) : "--"],
            ["Layer", selectedCadMetrics?.layer || "C-DRAFT"],
          ].map(([label, value]) => (
            <div key={label} className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-2">
              <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-400">{label}</p>
              <p className="mt-1 truncate font-semibold text-slate-800">{value}</p>
            </div>
          ))}
        </div>
        <div className="mt-3 grid grid-cols-[1fr_repeat(3,auto)] gap-2">
          <input
            aria-label="Draft transform value"
            inputMode="decimal"
            value={cadTransformValue}
            onChange={(event) => setCadTransformValue(event.target.value)}
            className="h-9 min-w-0 rounded-md border border-slate-200 bg-white px-2 text-sm text-slate-700"
          />
          <button type="button" aria-label="Move selected draft objects" onClick={() => transformSelectedCadObjects("move")} disabled={!selectedCadIds.length} className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-700 disabled:opacity-40"><Move className="h-4 w-4" /></button>
          <button type="button" aria-label="Rotate selected draft objects" onClick={() => transformSelectedCadObjects("rotate")} disabled={!selectedCadIds.length} className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-700 disabled:opacity-40"><RotateCw className="h-4 w-4" /></button>
          <button type="button" aria-label="Scale selected draft objects" onClick={() => transformSelectedCadObjects("scale")} disabled={!selectedCadIds.length} className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-700 disabled:opacity-40"><Scale className="h-4 w-4" /></button>
        </div>
        <div className="mt-3 grid grid-cols-[auto_1fr_auto] gap-2">
          <select
            aria-label="Draft dimension mode"
            value={cadDimensionMode}
            onChange={(event) => setCadDimensionMode(event.target.value as CadDimensionMode)}
            className="h-9 rounded-md border border-slate-200 bg-white px-2 text-sm text-slate-700"
          >
            <option value="linear">Linear</option>
            <option value="aligned">Aligned</option>
          </select>
          <input
            aria-label="Draft dimension label"
            value={cadDimensionLabelDraft}
            onChange={(event) => setCadDimensionLabelDraft(event.target.value)}
            placeholder="Editable dimension label"
            className="h-9 min-w-0 rounded-md border border-slate-200 bg-white px-2 text-sm text-slate-700"
          />
          <button type="button" onClick={applySelectedCadDimension} disabled={!selectedCadObject} className="h-9 rounded-md border border-slate-200 bg-white px-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-600 disabled:opacity-40">Dim</button>
        </div>
      </section>
      <section className="min-w-0">
        <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Modify / layers</p>
        <div className="mt-3 grid grid-cols-4 gap-2">
          <button type="button" aria-label="Offset selected draft object" title="Offset selected draft object" onClick={offsetSelectedCadObject} disabled={!selectedCadObject} className="inline-flex h-9 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-700 disabled:opacity-40"><Ruler className="h-4 w-4" /></button>
          <button type="button" aria-label="Trim selected draft object" title="Trim selected draft object" onClick={() => trimExtendSelectedCadObject("trim")} disabled={!selectedCadObject} className="inline-flex h-9 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-700 disabled:opacity-40"><Scissors className="h-4 w-4" /></button>
          <button type="button" aria-label="Extend selected draft object" title="Extend selected draft object" onClick={() => trimExtendSelectedCadObject("extend")} disabled={!selectedCadObject} className="inline-flex h-9 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-700 disabled:opacity-40"><GitBranch className="h-4 w-4" /></button>
          <button type="button" aria-label="Fillet selected draft vertex" title="Fillet selected draft vertex" onClick={filletSelectedCadObject} disabled={!selectedCadObject} className="inline-flex h-9 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-700 disabled:opacity-40"><RefreshCw className="h-4 w-4" /></button>
        </div>
        <div className="mt-3 grid grid-cols-[1fr_1fr_auto] gap-2">
          <input aria-label="Draft offset distance" inputMode="decimal" value={cadOffsetDistance} onChange={(event) => setCadOffsetDistance(event.target.value)} className="h-9 min-w-0 rounded-md border border-slate-200 bg-white px-2 text-sm text-slate-700" />
          <input aria-label="Draft fillet radius" inputMode="decimal" value={cadFilletRadius} onChange={(event) => setCadFilletRadius(event.target.value)} className="h-9 min-w-0 rounded-md border border-slate-200 bg-white px-2 text-sm text-slate-700" />
          <button type="button" onClick={() => setCadSelectionSet(selectedBuildingId ? [selectedBuildingId] : [])} disabled={!selectedBuildingId} className="h-9 rounded-md border border-slate-200 bg-white px-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-600 disabled:opacity-40">Set</button>
        </div>
        <div className="mt-3 grid grid-cols-[1fr_auto] gap-2">
          <select
            aria-label="Draft layer"
            value={cadLayerDraft}
            onChange={(event) => setCadLayerDraft(event.target.value)}
            className="h-9 min-w-0 rounded-md border border-slate-200 bg-white px-2 text-sm text-slate-700"
          >
            {cadLayerOptions.map((layer) => (
              <option key={layer} value={layer}>{layer}</option>
            ))}
          </select>
          <button type="button" onClick={applySelectedCadLayer} disabled={!selectedCadIds.length} className="h-9 rounded-md border border-slate-900 bg-slate-950 px-3 text-xs font-semibold uppercase tracking-[0.12em] text-white disabled:opacity-40">Layer</button>
        </div>
        <div className="mt-3 grid max-h-24 gap-1 overflow-y-auto rounded-lg border border-slate-200 bg-slate-50 p-1">
          {cadLayerOptions.map((layer) => {
            const hidden = hiddenCadLayers.includes(layer);
            return (
              <button
                key={`layer-toggle-${layer}`}
                type="button"
                onClick={() => toggleCadLayerVisibility(layer)}
                className="flex min-h-8 items-center justify-between gap-2 rounded-md bg-white px-2 text-left text-[11px] font-semibold text-slate-600"
              >
                <span className="truncate">{layer}</span>
                {hidden ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
              </button>
            );
          })}
        </div>
      </section>
      <section className="min-w-0">
        <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Symbols / properties</p>
        <div className="mt-3 grid grid-cols-[1fr_auto] gap-2">
          <select
            aria-label="Draft symbol"
            value={cadSymbolDraft}
            onChange={(event) => setCadSymbolDraft(event.target.value as CadSymbolKind)}
            className="h-9 min-w-0 rounded-md border border-slate-200 bg-white px-2 text-sm text-slate-700"
          >
            <option value="hydrant">Hydrant</option>
            <option value="inlet">Inlet</option>
            <option value="manhole">Manhole</option>
            <option value="valve">Valve</option>
            <option value="tree">Tree</option>
            <option value="light">Light</option>
            <option value="sign">Sign</option>
            <option value="utility_marker">Utility marker</option>
            <option value="benchmark">Benchmark</option>
            <option value="note_callout">Note / callout</option>
          </select>
          <button type="button" aria-label="Insert draft symbol" onClick={insertCadSymbol} className="h-9 rounded-md border border-slate-200 bg-white px-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-600">Insert</button>
        </div>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <input aria-label="Draft symbol attribute ID" value={cadPropertyDraft.id} onChange={(event) => setCadPropertyDraft((prev) => ({ ...prev, id: event.target.value }))} placeholder="ID" className="h-9 min-w-0 rounded-md border border-slate-200 bg-white px-2 text-sm text-slate-700" />
          <input aria-label="Draft object name" value={cadPropertyDraft.name} onChange={(event) => setCadPropertyDraft((prev) => ({ ...prev, name: event.target.value }))} placeholder="Name" className="h-9 min-w-0 rounded-md border border-slate-200 bg-white px-2 text-sm text-slate-700" />
          <select
            aria-label="Classify selected outline as"
            value={cadPropertyDraft.type}
            onChange={(event) => setCadPropertyDraft((prev) => ({ ...prev, type: event.target.value as SiteObjectType }))}
            className="h-9 min-w-0 rounded-md border border-slate-200 bg-white px-2 text-sm text-slate-700"
          >
            {classificationOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <input aria-label="Draft object layer property" value={cadPropertyDraft.layer} onChange={(event) => setCadPropertyDraft((prev) => ({ ...prev, layer: event.target.value }))} placeholder="Layer" className="h-9 min-w-0 rounded-md border border-slate-200 bg-white px-2 text-sm text-slate-700" />
          <input aria-label="Draft symbol elevation attribute" value={cadPropertyDraft.elevation} onChange={(event) => setCadPropertyDraft((prev) => ({ ...prev, elevation: event.target.value }))} placeholder="Elevation" className="h-9 min-w-0 rounded-md border border-slate-200 bg-white px-2 text-sm text-slate-700" />
          <input aria-label="Draft symbol material attribute" value={cadPropertyDraft.material} onChange={(event) => setCadPropertyDraft((prev) => ({ ...prev, material: event.target.value }))} placeholder="Material" className="h-9 min-w-0 rounded-md border border-slate-200 bg-white px-2 text-sm text-slate-700" />
          <input aria-label="Draft symbol size attribute" value={cadPropertyDraft.size} onChange={(event) => setCadPropertyDraft((prev) => ({ ...prev, size: event.target.value }))} placeholder="Size" className="h-9 min-w-0 rounded-md border border-slate-200 bg-white px-2 text-sm text-slate-700" />
          <button type="button" aria-label="Apply outline classification and properties" onClick={applyCadProperties} disabled={!selectedCadObject} className="h-9 rounded-md border border-slate-900 bg-slate-950 px-3 text-xs font-semibold uppercase tracking-[0.12em] text-white disabled:opacity-40">Apply classification</button>
        </div>
        <div className="mt-3 grid gap-2">
          <input aria-label="Draft symbol source attribute" value={cadPropertyDraft.source} onChange={(event) => setCadPropertyDraft((prev) => ({ ...prev, source: event.target.value }))} placeholder="Source" className="h-9 min-w-0 rounded-md border border-slate-200 bg-white px-2 text-sm text-slate-700" />
          <input aria-label="Draft source note" value={cadPropertyDraft.sourceNote} onChange={(event) => setCadPropertyDraft((prev) => ({ ...prev, sourceNote: event.target.value }))} placeholder="Source note" className="h-9 min-w-0 rounded-md border border-slate-200 bg-white px-2 text-sm text-slate-700" />
          <input aria-label="Draft review note" value={cadPropertyDraft.reviewNote} onChange={(event) => setCadPropertyDraft((prev) => ({ ...prev, reviewNote: event.target.value }))} placeholder="Review note" className="h-9 min-w-0 rounded-md border border-slate-200 bg-white px-2 text-sm text-slate-700" />
        </div>
        <p className="mt-2 text-[11px] font-medium text-slate-500">Snap priority: endpoint, midpoint, intersection, perpendicular, then ortho.</p>
        <div className="mt-2 rounded-lg border border-slate-200 bg-slate-50 px-2 py-2 text-[11px] font-semibold text-slate-600" data-testid="cad-topology-status">
          {topologyIssues.length ? (
            <>
              <p className="text-amber-700">Topology review needs</p>
              <ul className="mt-1 space-y-1">
                {topologyIssues.slice(0, 3).map((issue) => (
                  <li key={`${issue.code}-${issue.objectIds.join("-")}`} className="break-words">
                    {issue.code.replace(/_/g, " ")}: {issue.message}
                  </li>
                ))}
              </ul>
            </>
          ) : (
            <p>Drawing checks: no visible issues.</p>
          )}
        </div>
        </section>
        </div>
      </div>
    </details>
  );
}
