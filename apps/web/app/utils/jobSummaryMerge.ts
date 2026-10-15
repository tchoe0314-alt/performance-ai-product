import type { JobSummary } from "../types";

/** Lightweight polling must not erase an already fetched terminal artifact. */
export function mergeJobSummaries(current: JobSummary[], incoming: JobSummary[]): JobSummary[] {
  return incoming.map(summary => {
    const detail = current.find(item => item.job_id === summary.job_id);
    if (!detail) return summary;
    if (Number(detail.updated_at ?? 0) > Number(summary.updated_at ?? 0)) return detail;
    const sameSnapshot = detail.updated_at === summary.updated_at && detail.status === summary.status;
    return { ...(sameSnapshot ? detail : {}), ...summary,
      artifact_history: summary.artifact_history ?? detail.artifact_history,
    } as JobSummary;
  });
}
