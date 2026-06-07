"use client";

import {
  Download,
  FileJson,
  FileText,
  Layers,
  LayoutPanelTop,
  Maximize2,
  MessageSquarePlus,
  Plus,
  Ruler,
  Table2,
  Tag,
  TextCursorInput,
} from "lucide-react";

export type PlanSheetScale = "1:10" | "1:20" | "1:30" | "1:40" | "1:50" | "1:100";

export type PlanSheetTitleBlock = {
  projectName: string;
  sheetTitle: string;
  sheetNumber: string;
  reviewStage: string;
  preparedBy: string;
  checkedBy: string;
  date: string;
};

export type PlanSheetViewport = {
  id: string;
  label: string;
  source: string;
  scale: PlanSheetScale;
  x: number;
  y: number;
  w: number;
  h: number;
};

export type PlanSheetAnnotation = {
  id: string;
  type: "label" | "callout" | "dimension" | "note";
  text: string;
  x: number;
  y: number;
};

export type PlanSheetTable = {
  id: string;
  title: string;
  rows: Array<[string, string]>;
};

export type PlanSheetReference = {
  id: string;
  kind: "profile" | "section" | "detail";
  label: string;
  target: string;
};

export type PlanSheet = {
  id: string;
  name: string;
  size: "ARCH D" | "ARCH E" | "11x17";
  titleBlock: PlanSheetTitleBlock;
  viewports: PlanSheetViewport[];
  annotations: PlanSheetAnnotation[];
  legends: PlanSheetTable[];
  detailBlocks: PlanSheetTable[];
  references: PlanSheetReference[];
};

export type PlanSheetSet = {
  id: string;
  name: string;
  status: "draft" | "review";
  sheets: PlanSheet[];
  activeSheetId: string;
  blockers: string[];
  updatedAt: string;
};

type PlanSheetEditorProps = {
  sheetSet: PlanSheetSet;
  onUpdateTitleBlock: (updates: Partial<PlanSheetTitleBlock>) => void;
  onChangeScale: (viewportId: string, scale: PlanSheetScale) => void;
  onAddNote: (text?: string) => void;
  onAddLabel: () => void;
  onAddCallout: () => void;
  onAddDimension: () => void;
  onAddViewport: () => void;
  onAddTable: () => void;
  onAddDetailBlock: () => void;
  onAddReference: (kind: PlanSheetReference["kind"]) => void;
  onSelectSheet: (sheetId: string) => void;
  onCreateSheet: () => void;
  onExportJson: () => void;
  onExportPdf: () => void;
};

const scaleOptions: PlanSheetScale[] = ["1:10", "1:20", "1:30", "1:40", "1:50", "1:100"];

const annotationTone: Record<PlanSheetAnnotation["type"], string> = {
  label: "border-sky-200 bg-sky-50 text-sky-800",
  callout: "border-amber-200 bg-amber-50 text-amber-800",
  dimension: "border-emerald-200 bg-emerald-50 text-emerald-800",
  note: "border-slate-200 bg-white text-slate-700",
};

export default function PlanSheetEditor({
  sheetSet,
  onUpdateTitleBlock,
  onChangeScale,
  onAddNote,
  onAddLabel,
  onAddCallout,
  onAddDimension,
  onAddViewport,
  onAddTable,
  onAddDetailBlock,
  onAddReference,
  onSelectSheet,
  onCreateSheet,
  onExportJson,
  onExportPdf,
}: PlanSheetEditorProps) {
  const activeSheet =
    sheetSet.sheets.find((sheet) => sheet.id === sheetSet.activeSheetId) ?? sheetSet.sheets[0];
  const title = activeSheet?.titleBlock;

  if (!activeSheet || !title) {
    return (
      <div className="rounded-2xl border border-slate-200 bg-white p-4">
        <p className="text-sm font-semibold text-slate-700">No review sheets yet.</p>
        <button
          type="button"
          onClick={onCreateSheet}
          className="mt-3 inline-flex items-center gap-2 rounded-xl border border-slate-900 bg-slate-950 px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-white"
        >
          <Plus className="h-4 w-4" />
          Make Sheet
        </button>
      </div>
    );
  }

  const blockerCount = sheetSet.blockers.length;

  return (
    <div className="space-y-4" data-testid="plan-sheet-editor">
      <div className="rounded-2xl border border-slate-200 bg-white p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
              Plan Sheet Editor
            </p>
            <p className="mt-1 text-sm font-semibold text-slate-900">{sheetSet.name}</p>
            <p className="mt-1 text-xs font-medium text-slate-500">
              Review package sheets only. Sheet data can be edited, checked, and exported for review.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={onExportJson}
              className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50"
            >
              <FileJson className="h-4 w-4" />
              JSON
            </button>
            <button
              type="button"
              onClick={onExportPdf}
              className="inline-flex items-center gap-2 rounded-xl border border-slate-900 bg-slate-950 px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-white hover:bg-slate-800"
            >
              <Download className="h-4 w-4" />
              Review PDF
            </button>
          </div>
        </div>
        <div className="mt-4 grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
          {[
            ["Sheets", sheetSet.sheets.length.toLocaleString()],
            ["Viewports", activeSheet.viewports.length.toLocaleString()],
            ["Notes", activeSheet.annotations.filter((item) => item.type === "note").length.toLocaleString()],
            ["Blockers", blockerCount.toLocaleString()],
          ].map(([label, value]) => (
            <div key={label} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
              <p className="font-semibold uppercase tracking-[0.14em] text-slate-400">{label}</p>
              <p className="mt-1 font-semibold text-slate-900">{value}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="rounded-2xl border border-slate-200 bg-white p-3">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap gap-2">
              {sheetSet.sheets.map((sheet) => (
                <button
                  key={sheet.id}
                  type="button"
                  onClick={() => onSelectSheet(sheet.id)}
                  className={`rounded-xl border px-3 py-2 text-xs font-semibold uppercase tracking-[0.12em] ${
                    sheet.id === activeSheet.id
                      ? "border-slate-900 bg-slate-950 text-white"
                      : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
                  }`}
                >
                  {sheet.titleBlock.sheetNumber}
                </button>
              ))}
              <button
                type="button"
                onClick={onCreateSheet}
                className="inline-flex items-center gap-1 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-slate-600 hover:bg-slate-50"
              >
                <Plus className="h-3.5 w-3.5" />
                Sheet
              </button>
            </div>
            <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500">
              {activeSheet.size}
            </span>
          </div>

          <div className="relative min-h-[560px] overflow-hidden rounded-xl border border-slate-300 bg-slate-100 p-4">
            <div className="absolute inset-4 rounded-lg border border-slate-400 bg-white shadow-inner">
              <div className="absolute inset-x-5 top-5 flex items-start justify-between border-b border-slate-200 pb-2">
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">
                    Review Sheet
                  </p>
                  <p className="mt-1 text-sm font-semibold text-slate-900">{title.sheetTitle}</p>
                </div>
                <p className="text-right text-xs font-semibold text-slate-500">{title.sheetNumber}</p>
              </div>

              {activeSheet.viewports.map((viewport) => (
                <div
                  key={viewport.id}
                  className="absolute rounded-lg border-2 border-slate-700 bg-slate-50/90 p-3"
                  style={{
                    left: `${viewport.x}%`,
                    top: `${viewport.y}%`,
                    width: `${viewport.w}%`,
                    height: `${viewport.h}%`,
                  }}
                >
                  <div className="flex h-full flex-col">
                    <div className="flex items-center justify-between gap-2 border-b border-slate-200 pb-2">
                      <p className="truncate text-xs font-semibold text-slate-800">{viewport.label}</p>
                      <select
                        value={viewport.scale}
                        onChange={(event) => onChangeScale(viewport.id, event.target.value as PlanSheetScale)}
                        className="rounded-md border border-slate-200 bg-white px-2 py-1 text-[11px] font-semibold text-slate-700"
                      >
                        {scaleOptions.map((scale) => (
                          <option key={scale} value={scale}>
                            {scale}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="relative mt-3 flex flex-1 items-center justify-center overflow-hidden rounded border border-dashed border-slate-300 bg-[linear-gradient(90deg,#e2e8f0_1px,transparent_1px),linear-gradient(#e2e8f0_1px,transparent_1px)] bg-[length:26px_26px]">
                      <div className="h-20 w-32 rounded border-2 border-slate-400 bg-white/70" />
                      <div className="absolute left-6 top-8 h-24 w-24 rounded-full border-2 border-slate-300" />
                      <div className="absolute bottom-10 right-8 h-16 w-28 rounded border-2 border-slate-300" />
                    </div>
                    <p className="mt-2 truncate text-[11px] font-medium text-slate-500">{viewport.source}</p>
                  </div>
                </div>
              ))}

              {activeSheet.annotations.map((annotation) => (
                <div
                  key={annotation.id}
                  className={`absolute max-w-[190px] rounded-lg border px-2 py-1 text-[11px] font-semibold shadow-sm ${annotationTone[annotation.type]}`}
                  style={{ left: `${annotation.x}%`, top: `${annotation.y}%` }}
                >
                  {annotation.type === "dimension" ? <Ruler className="mr-1 inline h-3.5 w-3.5" /> : null}
                  {annotation.type === "callout" ? <Tag className="mr-1 inline h-3.5 w-3.5" /> : null}
                  {annotation.text}
                </div>
              ))}

              <div className="absolute bottom-5 right-5 w-[38%] min-w-[260px] rounded-lg border-2 border-slate-700 bg-white">
                <div className="grid grid-cols-[1fr_90px] border-b border-slate-700">
                  <div className="p-3">
                    <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">
                      Project
                    </p>
                    <p className="mt-1 text-sm font-semibold text-slate-900">{title.projectName}</p>
                  </div>
                  <div className="border-l border-slate-700 p-3">
                    <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">
                      Sheet
                    </p>
                    <p className="mt-1 text-sm font-semibold text-slate-900">{title.sheetNumber}</p>
                  </div>
                </div>
                <div className="grid grid-cols-2 divide-x divide-slate-700 border-b border-slate-700">
                  <div className="p-3">
                    <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">
                      Title
                    </p>
                    <p className="mt-1 text-xs font-semibold text-slate-800">{title.sheetTitle}</p>
                  </div>
                  <div className="p-3">
                    <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">
                      Stage
                    </p>
                    <p className="mt-1 text-xs font-semibold text-slate-800">{title.reviewStage}</p>
                  </div>
                </div>
                <div className="grid grid-cols-3 divide-x divide-slate-700 text-[11px]">
                  <div className="p-2">
                    <span className="font-semibold text-slate-400">By</span>
                    <p className="font-semibold text-slate-800">{title.preparedBy}</p>
                  </div>
                  <div className="p-2">
                    <span className="font-semibold text-slate-400">Check</span>
                    <p className="font-semibold text-slate-800">{title.checkedBy}</p>
                  </div>
                  <div className="p-2">
                    <span className="font-semibold text-slate-400">Date</span>
                    <p className="font-semibold text-slate-800">{title.date}</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="space-y-4">
          <div className="rounded-2xl border border-slate-200 bg-white p-4">
            <div className="flex items-center gap-2">
              <LayoutPanelTop className="h-4 w-4 text-slate-500" />
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                Title Block Fields
              </p>
            </div>
            <div className="mt-3 grid gap-2 text-xs">
              {(
                [
                  ["projectName", "Project"],
                  ["sheetTitle", "Sheet title"],
                  ["sheetNumber", "Sheet number"],
                  ["reviewStage", "Review stage"],
                  ["preparedBy", "Prepared by"],
                  ["checkedBy", "Checked by"],
                  ["date", "Date"],
                ] as Array<[keyof PlanSheetTitleBlock, string]>
              ).map(([key, label]) => (
                <label key={key} className="flex flex-col gap-1 font-semibold text-slate-600">
                  {label}
                  <input
                    value={title[key]}
                    onChange={(event) => onUpdateTitleBlock({ [key]: event.target.value })}
                    className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-900"
                  />
                </label>
              ))}
            </div>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-4">
            <div className="flex items-center gap-2">
              <Maximize2 className="h-4 w-4 text-slate-500" />
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                Viewports
              </p>
            </div>
            <div className="mt-3 space-y-2">
              {activeSheet.viewports.map((viewport) => (
                <div key={viewport.id} className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                  <p className="text-sm font-semibold text-slate-800">{viewport.label}</p>
                  <p className="mt-1 text-xs text-slate-500">{viewport.source}</p>
                  <div className="mt-2 flex items-center gap-2 text-xs font-semibold text-slate-500">
                    Scale
                    <select
                      value={viewport.scale}
                      onChange={(event) => onChangeScale(viewport.id, event.target.value as PlanSheetScale)}
                      className="rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs text-slate-800"
                    >
                      {scaleOptions.map((scale) => (
                        <option key={scale} value={scale}>
                          {scale}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              ))}
              <button
                type="button"
                onClick={onAddViewport}
                className="inline-flex w-full items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50"
              >
                <Plus className="h-4 w-4" />
                Viewport
              </button>
            </div>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-4">
            <div className="flex items-center gap-2">
              <MessageSquarePlus className="h-4 w-4 text-slate-500" />
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                Markups
              </p>
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2">
              <button type="button" onClick={() => onAddNote()} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-slate-700 hover:bg-slate-50">
                <TextCursorInput className="mr-1 inline h-4 w-4" />
                Note
              </button>
              <button type="button" onClick={onAddLabel} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-slate-700 hover:bg-slate-50">
                Label
              </button>
              <button type="button" onClick={onAddCallout} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-slate-700 hover:bg-slate-50">
                Callout
              </button>
              <button type="button" onClick={onAddDimension} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-slate-700 hover:bg-slate-50">
                Dimension
              </button>
            </div>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-4">
            <div className="flex items-center gap-2">
              <Table2 className="h-4 w-4 text-slate-500" />
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                Legends, Tables, Details
              </p>
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2">
              <button type="button" onClick={onAddTable} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-slate-700 hover:bg-slate-50">
                Legend
              </button>
              <button type="button" onClick={onAddDetailBlock} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-slate-700 hover:bg-slate-50">
                Detail
              </button>
              <button type="button" onClick={() => onAddReference("profile")} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-slate-700 hover:bg-slate-50">
                Profile Ref
              </button>
              <button type="button" onClick={() => onAddReference("section")} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-slate-700 hover:bg-slate-50">
                Section Ref
              </button>
            </div>
            <div className="mt-3 space-y-2 text-xs">
              {[...activeSheet.legends, ...activeSheet.detailBlocks].map((table) => (
                <div key={table.id} className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                  <p className="font-semibold text-slate-800">{table.title}</p>
                  {table.rows.map(([label, value]) => (
                    <div key={`${table.id}-${label}`} className="mt-1 flex justify-between gap-3 text-slate-500">
                      <span>{label}</span>
                      <span className="font-semibold text-slate-700">{value}</span>
                    </div>
                  ))}
                </div>
              ))}
              {activeSheet.references.map((reference) => (
                <div key={reference.id} className="rounded-xl border border-slate-200 bg-white px-3 py-2">
                  <Layers className="mr-1 inline h-3.5 w-3.5 text-slate-400" />
                  <span className="font-semibold text-slate-800">{reference.label}</span>
                  <span className="ml-2 text-slate-500">{reference.target}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-4">
            <div className="flex items-center gap-2">
              <FileText className="h-4 w-4 text-slate-500" />
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                Sheet Blockers
              </p>
            </div>
            <div className="mt-3 space-y-2 text-xs text-slate-600">
              {sheetSet.blockers.length ? (
                sheetSet.blockers.map((blocker) => (
                  <p key={blocker} className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 font-semibold text-amber-800">
                    {blocker}
                  </p>
                ))
              ) : (
                <p className="rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 font-semibold text-emerald-800">
                  No sheet blockers recorded.
                </p>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
