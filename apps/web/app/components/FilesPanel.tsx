type FilesPanelProps = {
  mapSnapshotReady: boolean;
  surveyFileName: string;
  projectRecordLabel: string;
  surveyUploadMessage: string;
  sourceEffectRows: string[];
  previewReady: boolean;
  reportReady: boolean;
  dxfStatus: string;
  onOpenImportFiles: () => void;
  onSelectMapImage: () => void;
  onSelectSurveyFile: () => void;
  onOpenPlanPdf: () => void;
  onExportDxf: () => void;
  onExportReport: () => void;
  exportBlockReason: string;
};

function StatusRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm">
      <span className="font-semibold text-slate-700">{label}</span>
      <span className="max-w-[150px] truncate text-xs uppercase tracking-[0.12em] text-slate-500">{value}</span>
    </div>
  );
}

export function FilesPanel({
  mapSnapshotReady,
  surveyFileName,
  projectRecordLabel,
  surveyUploadMessage,
  sourceEffectRows,
  previewReady,
  reportReady,
  dxfStatus,
  onOpenImportFiles,
  onSelectMapImage,
  onSelectSurveyFile,
  onOpenPlanPdf,
  onExportDxf,
  onExportReport,
  exportBlockReason,
}: FilesPanelProps) {
  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-slate-200 bg-white p-4">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Input files</p>
        <div className="mt-3 space-y-2">
          <StatusRow label="Map snapshot" value={mapSnapshotReady ? "Ready" : "Not uploaded"} />
          <StatusRow label="Survey/topo" value={surveyFileName || "Not uploaded"} />
          <StatusRow label="Project record" value={projectRecordLabel || "Draft"} />
        </div>
        <button
          type="button"
          onClick={onOpenImportFiles}
          className="mt-3 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50"
        >
          Import files
        </button>
        <div className="mt-2 grid grid-cols-2 gap-2">
          <button type="button" onClick={onSelectMapImage} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50">
            Map image
          </button>
          <button type="button" onClick={onSelectSurveyFile} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50">
            Survey file
          </button>
          <button type="button" onClick={onOpenPlanPdf} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50">
            Plan PDF
          </button>
        </div>
        {surveyUploadMessage ? (
          <p
            data-testid="survey-upload-status"
            className={`mt-3 rounded-xl border px-3 py-2 text-xs font-semibold ${
              surveyUploadMessage.toLowerCase().includes("failed")
                ? "border-red-200 bg-red-50 text-red-700"
                : "border-slate-200 bg-slate-50 text-slate-600"
            }`}
          >
            {surveyUploadMessage}
          </p>
        ) : null}
        {sourceEffectRows.length ? (
          <div data-testid="source-effects-summary" className="mt-3 rounded-xl border border-sky-100 bg-sky-50/80 p-3">
            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-sky-700">Source effects</p>
            <ul className="mt-2 space-y-1 text-xs leading-5 text-slate-700">
              {sourceEffectRows.map((row) => (
                <li key={row}>{row}</li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
      <div className="rounded-2xl border border-slate-200 bg-white p-4">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Generated outputs</p>
        <div className="mt-3 space-y-2">
          <StatusRow label="Preview" value={previewReady ? "Review ready" : "Not generated"} />
          <StatusRow label="Report" value={reportReady ? "Review package" : "Not generated"} />
          <StatusRow label="DXF" value={dxfStatus} />
          <StatusRow label="DWG" value="Unsupported natively" />
        </div>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <button
            type="button"
            onClick={onExportDxf}
            title={exportBlockReason || "Download DXF review export"}
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50"
          >
            DXF
          </button>
          <button
            type="button"
            onClick={onExportReport}
            title={exportBlockReason || "Download engineer-review report"}
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50"
          >
            Report
          </button>
        </div>
      </div>
    </div>
  );
}
