import type { ChangeEvent, RefObject } from "react";

import type { PlanPdfAnalysis, PlanPdfChangedElements, PlanPdfElement } from "../types";

type PlanPdfSummaryRow = readonly [string, number];
type PlanPdfClassificationRow = {
  label: string;
  value: string;
};
type PlanPdfPage = NonNullable<PlanPdfAnalysis["pages"]>[number];
type PlanPdfChangedElement = NonNullable<PlanPdfChangedElements["elements"]>[number];

type PlanPdfElementPatch = {
  text?: string;
  review_status?: "accepted" | "rejected" | "pending";
  move_target?: {
    x0: number;
    y0: number;
  };
};

export function PlanPdfWorkflowPanel({
  analysis,
  sourceUrl,
  firstPage,
  elements,
  selectedElement,
  changedReport,
  changedElements,
  unreadableItems,
  blockers,
  uploadState,
  uploadMessage,
  draftText,
  moveX,
  moveY,
  extractionSummaryRows,
  classificationPreviewRows,
  inputRef,
  onUploadFile,
  onSelectElement,
  onDraftTextChange,
  onMoveXChange,
  onMoveYChange,
  onUpdateElement,
  onExportJson,
  onExportPdf,
  onEditByChat,
  onWhatChanged,
  onAskUnreadable,
  onInvalidMove,
}: {
  analysis: PlanPdfAnalysis | undefined;
  sourceUrl: string;
  firstPage: PlanPdfPage | null;
  elements: PlanPdfElement[];
  selectedElement: PlanPdfElement | null;
  changedReport: PlanPdfChangedElements | null;
  changedElements: PlanPdfChangedElement[];
  unreadableItems: string[];
  blockers: string[];
  uploadState: "idle" | "uploading" | "uploaded" | "failed";
  uploadMessage: string;
  draftText: string;
  moveX: string;
  moveY: string;
  extractionSummaryRows: PlanPdfSummaryRow[];
  classificationPreviewRows: PlanPdfClassificationRow[];
  inputRef: RefObject<HTMLInputElement | null>;
  onUploadFile: (file: File) => Promise<void>;
  onSelectElement: (elementId: string) => void;
  onDraftTextChange: (value: string) => void;
  onMoveXChange: (value: string) => void;
  onMoveYChange: (value: string) => void;
  onUpdateElement: (elementId: string, patch: PlanPdfElementPatch) => void;
  onExportJson: () => void;
  onExportPdf: () => void;
  onEditByChat: () => void;
  onWhatChanged: () => void;
  onAskUnreadable: () => void;
  onInvalidMove: () => void;
}) {
  const handleInputChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.currentTarget.files?.[0];
    if (file) {
      await onUploadFile(file);
    }
    event.currentTarget.value = "";
  };

  const firstPageWidth = Number((firstPage as { width?: number } | null)?.width ?? 1);
  const firstPageHeight = Number((firstPage as { height?: number } | null)?.height ?? 1);
  const firstPageHasSize = Boolean(firstPageWidth && firstPageHeight);

  return (
    <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-3" data-testid="plan-pdf-workflow">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">PDF Plan Visual Editor</p>
          <p className="mt-1 text-xs font-medium text-slate-500">
            {analysis
              ? `${analysis.source_pdf?.filename ?? "Plan PDF"} · ${analysis.page_count ?? 0} page(s) · ${elements.length} editable/review candidates`
              : "Import a plan PDF to extract review-required sheet objects."}
          </p>
        </div>
        <span className="shrink-0 rounded-full bg-amber-50 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-amber-700">
          {analysis?.source_confidence ?? "review required"}
        </span>
      </div>
      <input ref={inputRef} type="file" accept="application/pdf,.pdf" className="hidden" onChange={handleInputChange} />
      <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-5">
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-slate-700 hover:bg-slate-50"
        >
          {uploadState === "uploading" ? "Importing..." : "Upload PDF"}
        </button>
        <button
          type="button"
          onClick={onEditByChat}
          disabled={!analysis}
          className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Edit by Chat
        </button>
        <button
          type="button"
          onClick={onWhatChanged}
          disabled={!analysis}
          className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
        >
          What Changed
        </button>
        <button
          type="button"
          onClick={onExportJson}
          disabled={!analysis}
          className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Export JSON
        </button>
        <button
          type="button"
          onClick={onExportPdf}
          disabled={!analysis}
          className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Export PDF
        </button>
      </div>
      {uploadMessage ? (
        <p
          data-testid="pdf-upload-status"
          className={`mt-3 rounded-xl border px-3 py-2 text-xs font-semibold ${
            uploadState === "failed" ? "border-red-200 bg-red-50 text-red-700" : "border-slate-200 bg-slate-50 text-slate-600"
          }`}
        >
          {uploadMessage}
        </p>
      ) : null}
      {analysis ? (
        <div className="mt-3 grid gap-3 xl:grid-cols-[1.2fr_0.8fr]">
          <div className="min-w-0">
            <div
              className="relative overflow-hidden rounded-lg border border-slate-200 bg-white"
              style={{
                aspectRatio: firstPageHasSize ? `${firstPageWidth} / ${firstPageHeight}` : "8.5 / 11",
              }}
            >
              {sourceUrl ? (
                <iframe title="Plan PDF source preview" src={sourceUrl} className="absolute inset-0 h-full w-full" />
              ) : (
                <div className="flex h-full items-center justify-center px-4 text-center text-xs font-semibold text-slate-500">
                  Source PDF preview is unavailable.
                </div>
              )}
              {elements
                .filter((element) => element.page_index === 0 && element.bbox && firstPageHasSize)
                .sort((left, right) => {
                  const leftBox = left.bbox;
                  const rightBox = right.bbox;
                  const leftArea = leftBox
                    ? Math.max(1, Number(leftBox.x1 ?? 0) - Number(leftBox.x0 ?? 0)) *
                      Math.max(1, Number(leftBox.y1 ?? 0) - Number(leftBox.y0 ?? 0))
                    : 0;
                  const rightArea = rightBox
                    ? Math.max(1, Number(rightBox.x1 ?? 0) - Number(rightBox.x0 ?? 0)) *
                      Math.max(1, Number(rightBox.y1 ?? 0) - Number(rightBox.y0 ?? 0))
                    : 0;
                  return rightArea - leftArea;
                })
                .slice(0, 40)
                .map((element, index) => {
                  const bbox = element.bbox;
                  if (!bbox) return null;
                  const x0 = Number(bbox.x0 ?? 0);
                  const y0 = Number(bbox.y0 ?? 0);
                  const x1 = Number(bbox.x1 ?? x0 + 20);
                  const y1 = Number(bbox.y1 ?? y0 + 12);
                  return (
                    <button
                      key={element.element_id}
                      type="button"
                      aria-label={`Select extracted PDF element ${element.text ?? element.type ?? "element"}`}
                      onClick={() => onSelectElement(element.element_id)}
                      className={`absolute border bg-amber-300/20 text-left text-[9px] font-semibold text-amber-950 ${
                        selectedElement?.element_id === element.element_id ? "border-slate-900 ring-2 ring-slate-900" : "border-amber-500"
                      }`}
                      style={{
                        left: `${Math.max(0, Math.min(100, (x0 / firstPageWidth) * 100))}%`,
                        top: `${Math.max(0, Math.min(100, 100 - (y1 / firstPageHeight) * 100))}%`,
                        width: `${Math.max(2, Math.min(80, ((x1 - x0) / firstPageWidth) * 100))}%`,
                        height: `${Math.max(2, Math.min(20, ((y1 - y0) / firstPageHeight) * 100))}%`,
                        zIndex: 20 + index,
                      }}
                    >
                      <span className="sr-only">{element.text}</span>
                    </button>
                  );
                })}
            </div>
            <div className="mt-2 grid grid-cols-2 gap-2 text-center text-[11px] font-semibold uppercase tracking-[0.12em] sm:grid-cols-4">
              {extractionSummaryRows.map(([label, value]) => (
                <div key={label} className="rounded-lg border border-slate-200 bg-white px-2 py-2">
                  <p className="text-slate-400">{label}</p>
                  <p className="mt-1 text-sm text-slate-800">{value}</p>
                </div>
              ))}
            </div>
            <div className="mt-2 grid gap-2 text-xs sm:grid-cols-2">
              {classificationPreviewRows.map((row) => (
                <div key={row.label} className="min-w-0 rounded-lg border border-slate-200 bg-white px-3 py-2">
                  <p className="font-semibold uppercase tracking-[0.12em] text-slate-400">{row.label}</p>
                  <p className="mt-1 truncate font-semibold text-slate-700">{row.value || "No extracted text"}</p>
                </div>
              ))}
            </div>
          </div>
          <div className="min-w-0 space-y-3">
            <div className="rounded-lg border border-slate-200 bg-white p-3">
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Sheet/Object Inspector</p>
              {selectedElement ? (
                <div className="mt-2 space-y-2">
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate text-sm font-semibold text-slate-800">
                      {String(selectedElement.type ?? "sheet element").replace(/_/g, " ")}
                    </span>
                    <span className="shrink-0 rounded-full bg-amber-50 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-amber-700">
                      {selectedElement.review_status ?? "pending"}
                    </span>
                  </div>
                  <textarea
                    value={draftText}
                    onChange={(event) => onDraftTextChange(event.target.value)}
                    disabled={selectedElement.editable === false}
                    rows={4}
                    className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700 focus:border-slate-400 focus:outline-none disabled:cursor-not-allowed disabled:opacity-60"
                  />
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-2">
                      <p className="font-semibold uppercase tracking-[0.12em] text-slate-400">Original</p>
                      <p className="mt-1 line-clamp-3 text-slate-700">{selectedElement.original_text || selectedElement.text || "No text"}</p>
                    </div>
                    <div className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-2">
                      <p className="font-semibold uppercase tracking-[0.12em] text-slate-400">Edited</p>
                      <p className="mt-1 line-clamp-3 text-slate-700">{selectedElement.text || "No text"}</p>
                    </div>
                  </div>
                  <div className="grid grid-cols-[1fr_1fr_auto] gap-2">
                    <label className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">
                      X0
                      <input
                        value={moveX}
                        onChange={(event) => onMoveXChange(event.target.value)}
                        disabled={selectedElement.editable === false || !selectedElement.bbox}
                        className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-2 py-2 text-xs text-slate-700 disabled:cursor-not-allowed disabled:opacity-50"
                      />
                    </label>
                    <label className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">
                      Y0
                      <input
                        value={moveY}
                        onChange={(event) => onMoveYChange(event.target.value)}
                        disabled={selectedElement.editable === false || !selectedElement.bbox}
                        className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-2 py-2 text-xs text-slate-700 disabled:cursor-not-allowed disabled:opacity-50"
                      />
                    </label>
                    <button
                      type="button"
                      onClick={() => {
                        const x0 = Number(moveX);
                        const y0 = Number(moveY);
                        if (!Number.isFinite(x0) || !Number.isFinite(y0)) {
                          onInvalidMove();
                          return;
                        }
                        onUpdateElement(selectedElement.element_id, { move_target: { x0, y0 } });
                      }}
                      disabled={selectedElement.editable === false || !selectedElement.bbox}
                      className="mt-5 rounded-lg border border-slate-200 bg-white px-2 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      Move
                    </button>
                  </div>
                  <div className="grid grid-cols-3 gap-2">
                    <button
                      type="button"
                      onClick={() => onUpdateElement(selectedElement.element_id, { text: draftText })}
                      disabled={selectedElement.editable === false}
                      className="rounded-lg border border-slate-200 bg-white px-2 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      Save
                    </button>
                    <button
                      type="button"
                      onClick={() => onUpdateElement(selectedElement.element_id, { review_status: "accepted" })}
                      className="rounded-lg border border-emerald-200 bg-white px-2 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-emerald-700 hover:bg-emerald-50"
                    >
                      Accept
                    </button>
                    <button
                      type="button"
                      onClick={() => onUpdateElement(selectedElement.element_id, { review_status: "rejected" })}
                      className="rounded-lg border border-red-200 bg-white px-2 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-red-600 hover:bg-red-50"
                    >
                      Reject
                    </button>
                  </div>
                  <p className="text-xs text-slate-500">
                    PDF-derived content is editable for review only. It does not modify protected authorization marks or field-use status.
                  </p>
                </div>
              ) : (
                <p className="mt-2 text-xs text-slate-500">No extracted sheet element is selected.</p>
              )}
            </div>
            <div className="rounded-lg border border-slate-200 bg-white p-3">
              <div className="flex items-center justify-between gap-2">
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Extracted Elements</p>
                <span className="text-[11px] font-semibold text-slate-400">{elements.length}</span>
              </div>
              <div className="mt-2 max-h-48 space-y-1 overflow-auto pr-1" data-testid="plan-pdf-extracted-elements">
                {elements.length ? (
                  elements.slice(0, 80).map((element) => (
                    <button
                      key={element.element_id}
                      type="button"
                      aria-label={`Select extracted PDF list element ${element.text || element.type || "PDF element"}`}
                      onClick={() => onSelectElement(element.element_id)}
                      className={`w-full rounded-md border px-2 py-1.5 text-left text-xs ${
                        selectedElement?.element_id === element.element_id
                          ? "border-slate-900 bg-slate-900 text-white"
                          : "border-slate-200 bg-slate-50 text-slate-700 hover:bg-white"
                      }`}
                    >
                      <span className="block truncate font-semibold">{element.text || element.type || "PDF element"}</span>
                      <span className="block truncate text-[10px] opacity-70">
                        {String(element.type ?? "element").replace(/_/g, " ")} / {element.review_status ?? "pending"}
                      </span>
                    </button>
                  ))
                ) : (
                  <p className="text-xs text-slate-500">No embedded text candidates were extracted.</p>
                )}
              </div>
            </div>
            <div className="rounded-lg border border-slate-200 bg-white p-3" data-testid="plan-pdf-changed-elements">
              <div className="flex items-center justify-between gap-2">
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Changed Elements</p>
                <span className="text-[11px] font-semibold text-slate-400">{changedReport?.changed_count ?? changedElements.length}</span>
              </div>
              <div className="mt-2 space-y-1">
                {changedElements.length ? (
                  changedElements.slice(0, 6).map((element) => (
                    <div key={element.element_id} className="rounded-md bg-slate-50 px-2 py-1.5 text-xs text-slate-600">
                      <p className="truncate font-semibold">{element.original_text || "(blank)"} -&gt; {element.text || "(blank)"}</p>
                      <p className="mt-0.5 text-[10px] uppercase tracking-[0.12em] text-slate-400">
                        {element.review_status ?? "pending"}
                        {element.moved ? " / moved" : ""}
                        {element.changed_text ? " / text edited" : ""}
                      </p>
                    </div>
                  ))
                ) : (
                  <p className="text-xs text-slate-500">No PDF-derived sheet edits have been recorded yet.</p>
                )}
              </div>
            </div>
            <div className="rounded-lg border border-slate-200 bg-white p-3">
              <div className="flex items-center justify-between gap-2">
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Unreadable / Needs review</p>
                <button
                  type="button"
                  onClick={onAskUnreadable}
                  className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500 hover:text-slate-900"
                >
                  Ask
                </button>
              </div>
              <div className="mt-2 space-y-1">
                {unreadableItems.length ? (
                  unreadableItems.slice(0, 4).map((blocker) => (
                    <p key={blocker} className="rounded-md bg-slate-50 px-2 py-1 text-xs font-medium text-slate-600">
                      {blocker.replace(/_/g, " ")}
                    </p>
                  ))
                ) : (
                  <p className="text-xs text-slate-500">No unreadable-text blocker has been recorded.</p>
                )}
              </div>
            </div>
            <div className="rounded-lg border border-slate-200 bg-white p-3">
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Blockers</p>
              <div className="mt-2 space-y-1">
                {blockers.length ? (
                  blockers.slice(0, 5).map((blocker) => (
                    <p key={blocker} className="rounded-md bg-slate-50 px-2 py-1 text-xs font-medium text-slate-600">
                      {blocker.replace(/_/g, " ")}
                    </p>
                  ))
                ) : (
                  <p className="text-xs text-slate-500">No extraction blockers recorded.</p>
                )}
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
