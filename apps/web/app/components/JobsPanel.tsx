import type { JobSummary, WorkflowArtifact } from "../types";
import { PanelCard } from "./ui";

export function JobsPanel({
  activeJob,
  selectedJob,
  jobHistory,
  jobStatusCounts,
  artifactHistory,
  activeJobStale,
  selectedJobStale,
  statusMessage,
  formatTimestamp,
  toReadableLabel,
  jobDetailMessage,
  onRefresh,
  onSelectJob,
  onCancelJob,
  onRetryJob,
  onResumeJob,
  onDownloadArtifact,
}: {
  activeJob: JobSummary | null;
  selectedJob: JobSummary | null;
  jobHistory: JobSummary[];
  jobStatusCounts: Record<string, number>;
  artifactHistory: WorkflowArtifact[];
  activeJobStale: boolean;
  selectedJobStale: boolean;
  statusMessage: string;
  formatTimestamp: (value?: number) => string;
  toReadableLabel: (value: string) => string;
  jobDetailMessage: (job: JobSummary) => string;
  onRefresh: () => void;
  onSelectJob: (jobId: string) => void;
  onCancelJob: (jobId: string) => void;
  onRetryJob: (jobId: string) => void;
  onResumeJob: (jobId: string) => void;
  onDownloadArtifact: (downloadPath: string, filename: string) => void;
}) {
  const staleJob = activeJobStale ? activeJob : selectedJob;

  return (
    <div className="space-y-4" data-testid="async-jobs-panel">
      <PanelCard>
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Job workflow</p>
            <p className="mt-1 text-sm font-semibold text-slate-900">
              {activeJob ? `${toReadableLabel(String(activeJob.status || "active"))} active` : "No active job"}
            </p>
          </div>
          <button
            type="button"
            onClick={onRefresh}
            className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-600 hover:bg-white"
          >
            Refresh
          </button>
        </div>
        <div className="mt-3 grid grid-cols-4 gap-2">
          {[
            ["Queued", jobStatusCounts.queued || 0],
            ["Running", jobStatusCounts.running || 0],
            ["Done", jobStatusCounts.completed || 0],
            ["Failed", (jobStatusCounts.failed || 0) + (jobStatusCounts.cancelled || 0)],
          ].map(([label, value]) => (
            <div key={label} className="rounded-xl border border-slate-200 bg-slate-50 px-2 py-2">
              <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-400">{label}</p>
              <p className="mt-1 text-sm font-semibold text-slate-900">{value}</p>
            </div>
          ))}
        </div>
        {activeJobStale || selectedJobStale ? (
          <p data-testid="jobs-stale-warning" className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-800">
            Backend status is stale. Last update: {formatTimestamp(staleJob?.updated_at)}. Refresh jobs, wait for the worker, or cancel/retry from the detail drawer.
          </p>
        ) : null}
        {statusMessage ? (
          <p data-testid="jobs-refresh-status" className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-800">
            {statusMessage}
          </p>
        ) : null}
      </PanelCard>

      <PanelCard>
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">History</p>
        <div className="mt-3 max-h-72 space-y-2 overflow-y-auto pr-1">
          {jobHistory.length ? (
            jobHistory.map((job) => {
              const status = String(job.status || "").toLowerCase();
              const isSelected = selectedJob?.job_id === job.job_id;
              return (
                <button
                  key={job.job_id}
                  type="button"
                  onClick={() => onSelectJob(job.job_id)}
                  className={`w-full rounded-xl border px-3 py-2 text-left transition ${
                    isSelected
                      ? "border-slate-950 bg-slate-950 text-white"
                      : "border-slate-200 bg-slate-50 text-slate-700 hover:bg-white"
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <span className="min-w-0">
                      <span className="block truncate text-sm font-semibold">{job.job_id}</span>
                      <span className={`mt-0.5 block text-[11px] font-semibold uppercase tracking-[0.12em] ${isSelected ? "text-slate-300" : "text-slate-500"}`}>
                        {toReadableLabel(String(job.job_type || "job"))}
                        {job.retry_of_job_id ? ` retry of ${job.retry_of_job_id}` : ""}
                      </span>
                    </span>
                    <span
                      className={`shrink-0 rounded-full px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${
                        status === "completed"
                          ? "bg-emerald-50 text-emerald-700"
                          : status === "failed" || status === "cancelled"
                            ? "bg-red-50 text-red-600"
                            : status === "awaiting_approval"
                              ? "bg-amber-50 text-amber-700"
                              : "bg-blue-50 text-blue-700"
                      }`}
                    >
                      {toReadableLabel(status || "unknown")}
                    </span>
                  </div>
                  <p className={`mt-1 truncate text-xs ${isSelected ? "text-slate-300" : "text-slate-500"}`}>
                    {job.stage_detail || job.error || job.stage || jobDetailMessage(job)}
                  </p>
                </button>
              );
            })
          ) : (
            <p className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3 text-sm text-slate-500">
              No background jobs yet.
            </p>
          )}
        </div>
      </PanelCard>

      {selectedJob ? (
        <PanelCard testId="job-detail-drawer">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Detail drawer</p>
              <p className="mt-1 truncate text-sm font-semibold text-slate-900">{selectedJob.job_id}</p>
              <p className="mt-1 text-xs text-slate-500">
                {toReadableLabel(String(selectedJob.job_type || "job"))} updated {formatTimestamp(selectedJob.updated_at)}
              </p>
            </div>
            <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-600">
              {Math.round(Number(selectedJob.progress || 0))}%
            </span>
          </div>
          <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-100">
            <div
              className="h-full rounded-full bg-slate-950 transition-all"
              style={{ width: `${Math.max(0, Math.min(100, Number(selectedJob.progress || 0)))}%` }}
            />
          </div>
          <p className="mt-3 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs leading-5 text-slate-600">
            {jobDetailMessage(selectedJob)}
          </p>
          <div className="mt-3 grid grid-cols-3 gap-2">
            <button
              type="button"
              disabled={!selectedJob.can_cancel}
              onClick={() => onCancelJob(selectedJob.job_id)}
              className="rounded-xl border border-slate-200 bg-white px-2 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-400"
            >
              Cancel
            </button>
            <button
              type="button"
              disabled={!selectedJob.can_retry}
              onClick={() => onRetryJob(selectedJob.job_id)}
              className="rounded-xl border border-slate-200 bg-white px-2 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-400"
            >
              Retry
            </button>
            <button
              type="button"
              disabled={!selectedJob.can_resume}
              onClick={() => onResumeJob(selectedJob.job_id)}
              className="rounded-xl border border-slate-200 bg-white px-2 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-400"
            >
              Resume
            </button>
          </div>
          {selectedJob.timeline?.length ? (
            <div className="mt-4">
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Progress timeline</p>
              <div className="mt-3 space-y-2">
                {selectedJob.timeline.map((event, index) => (
                  <div key={`${event.id || index}-${event.timestamp || index}`} className="flex gap-3 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
                    <span
                      className={`mt-1 h-2.5 w-2.5 shrink-0 rounded-full ${
                        event.status === "blocked"
                          ? "bg-red-500"
                          : event.status === "current"
                            ? "bg-amber-500"
                            : "bg-emerald-600"
                      }`}
                    />
                    <span className="min-w-0">
                      <span className="block text-sm font-semibold text-slate-800">{event.label || "Job event"}</span>
                      <span className="block text-xs leading-5 text-slate-500">{event.detail || formatTimestamp(event.timestamp)}</span>
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </PanelCard>
      ) : null}

      <PanelCard>
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Artifact history</p>
        <div className="mt-3 space-y-2">
          {artifactHistory.length ? (
            artifactHistory.slice(0, 8).map((artifact, index) => (
              <div key={`${artifact.artifact_id || artifact.filename || index}`} className="flex items-center justify-between gap-3 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
                <span className="min-w-0">
                  <span className="block truncate text-sm font-semibold text-slate-800">
                    {artifact.filename || artifact.artifact_id || "Generated artifact"}
                  </span>
                  <span className="block text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">
                    {toReadableLabel(String(artifact.kind || "artifact"))}
                  </span>
                </span>
                {artifact.download_path ? (
                  <button
                    type="button"
                    onClick={() => onDownloadArtifact(artifact.download_path || "", artifact.filename || "civora-artifact")}
                    className="rounded-lg border border-slate-200 bg-white px-2 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-600 hover:bg-slate-50"
                  >
                    Download
                  </button>
                ) : null}
              </div>
            ))
          ) : (
            <p className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3 text-sm text-slate-500">
              No generated artifacts have been recorded yet.
            </p>
          )}
        </div>
      </PanelCard>
    </div>
  );
}
