type DashboardIssueReportPanelProps = {
  message: string;
  diagnosticSummary: string;
  copied: boolean;
  onMessageChange: (message: string) => void;
  onCopyDiagnostic: () => void;
};

export function DashboardIssueReportPanel({
  message,
  diagnosticSummary,
  copied,
  onMessageChange,
  onCopyDiagnostic,
}: DashboardIssueReportPanelProps) {
  return (
    <details className="rounded-2xl border border-slate-200 bg-white p-4">
      <summary className="cursor-pointer text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
        Report issue
      </summary>
      <div className="mt-3 space-y-3">
        <textarea
          value={message}
          onChange={(event) => onMessageChange(event.target.value)}
          placeholder="What happened? Include the expected result and the action that triggered it."
          className="min-h-24 w-full resize-y rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700 outline-none focus:border-slate-400"
        />
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">
            Diagnostic summary
          </p>
          <pre className="mt-2 max-h-44 overflow-auto whitespace-pre-wrap text-xs leading-5 text-slate-600">
            {diagnosticSummary}
          </pre>
        </div>
        <button
          type="button"
          onClick={onCopyDiagnostic}
          className="w-full rounded-xl border border-slate-950 bg-slate-950 px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-white hover:bg-slate-800"
        >
          {copied ? "Copied" : "Copy diagnostic summary"}
        </button>
      </div>
    </details>
  );
}
