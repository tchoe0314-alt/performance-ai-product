type DashboardProjectSummaryProps = {
  siteName: string;
  fileName: string;
  lotWidth?: number;
  lotHeight?: number;
  hasHardSystemBlock: boolean;
  hasBackendResult: boolean;
  onSiteNameChange: (value: string) => void;
  onFileNameChange: (value: string) => void;
  onSaveName: () => void;
};

export function DashboardProjectSummary({
  siteName,
  fileName,
  lotWidth,
  lotHeight,
  hasHardSystemBlock,
  hasBackendResult,
  onSiteNameChange,
  onFileNameChange,
  onSaveName,
}: DashboardProjectSummaryProps) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Dashboard</p>
          <p className="mt-1 text-lg font-semibold text-slate-950">{siteName || "Untitled Project"}</p>
          <p className="mt-1 text-xs text-slate-500">
            {fileName || "No file name"} · {lotWidth && lotHeight ? `${lotWidth.toFixed(0)} ft x ${lotHeight.toFixed(0)} ft` : "No site boundary yet"}
          </p>
        </div>
        <span className={`rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] ${
          hasHardSystemBlock
            ? "bg-amber-50 text-amber-700"
            : hasBackendResult
              ? "bg-slate-100 text-slate-700"
              : "bg-amber-50 text-amber-600"
        }`}>
          {hasHardSystemBlock ? "Needs input" : hasBackendResult ? "Review output" : "Setup"}
        </span>
      </div>
      <details className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-3">
        <summary className="cursor-pointer text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
          Rename project
        </summary>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <input
            value={siteName}
            onChange={(event) => onSiteNameChange(event.target.value)}
            placeholder="Project name"
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 focus:border-slate-400 focus:outline-none"
          />
          <input
            value={fileName}
            onChange={(event) => onFileNameChange(event.target.value)}
            placeholder="File name"
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 focus:border-slate-400 focus:outline-none"
          />
        </div>
        <button
          type="button"
          onClick={onSaveName}
          className="mt-3 w-full rounded-xl border border-slate-950 bg-slate-950 px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-white hover:bg-slate-800"
        >
          Save name
        </button>
      </details>
    </div>
  );
}
