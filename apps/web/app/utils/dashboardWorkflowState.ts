import type {
  JobSummary,
  PlanToolMode,
  ProjectRecord,
  WorkflowArtifact,
  WorkflowReviewDashboard,
  WorkflowRunSummary,
} from "../types";
import {
  artifactFromJob,
  buildThinkingState,
  isLikelyStaleJob,
} from "./dashboardStatus";

type BuildDashboardWorkflowStateOptions = {
  currentProject?: ProjectRecord | null;
  jobs: JobSummary[];
  selectedRunId: string;
  activeJobId: string;
  selectedJobId: string;
  projectId: string;
  jobClockMs: number;
  busy: boolean;
  activePlanTool: PlanToolMode;
  statusMessage: string;
};

export function buildDashboardWorkflowState({
  currentProject,
  jobs,
  selectedRunId,
  activeJobId,
  selectedJobId,
  projectId,
  jobClockMs,
  busy,
  activePlanTool,
  statusMessage,
}: BuildDashboardWorkflowStateOptions) {
  const workflowRuns: WorkflowRunSummary[] = Array.isArray(currentProject?.metadata?.workflow?.runs)
    ? currentProject?.metadata?.workflow?.runs
    : [];
  const selectedRun = workflowRuns.length
    ? workflowRuns.find((run) => run.run_id === selectedRunId) ?? workflowRuns[0]
    : null;
  const workflowReviewDashboard: WorkflowReviewDashboard | null =
    currentProject?.metadata?.workflow?.review_dashboard ?? null;
  const workflowArtifacts: WorkflowArtifact[] = Array.isArray(currentProject?.metadata?.workflow?.artifacts)
    ? currentProject.metadata.workflow.artifacts
    : Array.isArray(workflowReviewDashboard?.recent_artifacts)
      ? workflowReviewDashboard.recent_artifacts.map((item) => item as WorkflowArtifact)
      : [];
  const activeJob = jobs.find((job) => job.job_id === activeJobId) ?? null;
  const jobHistory = [...jobs].sort(
    (a, b) => Number(b.updated_at || b.created_at || 0) - Number(a.updated_at || a.created_at || 0),
  );
  const jobStatusCounts: Record<string, number> = {};
  for (const job of jobs) {
    const key = String(job.status || "unknown").toLowerCase();
    jobStatusCounts[key] = (jobStatusCounts[key] || 0) + 1;
  }
  const fromJobs = jobs.flatMap((job) => job.artifact_history || []);
  const completedExportArtifacts = jobs
    .map((job) => artifactFromJob(job))
    .filter((artifact): artifact is NonNullable<ReturnType<typeof artifactFromJob>> => Boolean(artifact))
    .map((artifact) => ({
      artifact_id: artifact.filename || artifact.download_path || "job-artifact",
      kind: artifact.kind,
      filename: artifact.filename,
      download_path: artifact.download_path,
    }));
  const artifactHistory = [...fromJobs, ...completedExportArtifacts, ...workflowArtifacts].filter((item, index, all) => {
    const key = `${item.artifact_id || ""}:${item.download_path || ""}:${item.filename || ""}`;
    return index === all.findIndex((candidate) => `${candidate.artifact_id || ""}:${candidate.download_path || ""}:${candidate.filename || ""}` === key);
  });
  const currentProjectActiveJob =
    jobs.find(
      (job) =>
        Boolean(projectId) &&
        job.project_id === projectId &&
        ["queued", "running", "awaiting_approval", "cancelling"].includes(String(job.status || "").toLowerCase()),
    ) ?? null;
  const visibleActiveJob = activeJobId ? activeJob : projectId ? currentProjectActiveJob : activeJob;
  const selectedJob = jobs.find((job) => job.job_id === selectedJobId) ?? visibleActiveJob ?? jobs[0] ?? null;
  const visibleActiveJobStale = isLikelyStaleJob(visibleActiveJob, jobClockMs);
  const visibleActiveJobStatus = String(visibleActiveJob?.status || "").toLowerCase();
  const chatBlockingActiveJob = Boolean(
    visibleActiveJob && ["queued", "running", "cancelling"].includes(visibleActiveJobStatus),
  );
  const selectedJobStale = isLikelyStaleJob(selectedJob, jobClockMs);
  const thinkingState = buildThinkingState({
    busy,
    activePlanTool,
    activeJobStatus: visibleActiveJob?.status,
    activeJobStage: visibleActiveJob?.stage,
    activeJobDetail: visibleActiveJob?.stage_detail,
    activeJobProgress: visibleActiveJob?.progress,
    activeJobUpdatedAt: visibleActiveJob?.updated_at,
    activeJobQueuePosition: visibleActiveJob?.queue_position,
    activeJobQueuedCount: visibleActiveJob?.queued_count,
    activeJobRunningCount: visibleActiveJob?.running_count,
    staleJob: visibleActiveJobStale,
    statusMessage,
  });

  return {
    workflowRuns,
    selectedRun,
    workflowReviewDashboard,
    workflowArtifacts,
    activeJob,
    jobHistory,
    jobStatusCounts,
    artifactHistory,
    currentProjectActiveJob,
    visibleActiveJob,
    visibleActiveJobStale,
    visibleActiveJobStatus,
    chatBlockingActiveJob,
    selectedJob,
    selectedJobStale,
    thinkingState,
  };
}
