import type { JobSummary } from "../types";

function hasOlderTimestamp(incoming: JobSummary, existing: JobSummary): boolean {
  const incomingUpdatedAt = Number(incoming.updated_at);
  const existingUpdatedAt = Number(existing.updated_at);
  return Number.isFinite(incomingUpdatedAt) && incomingUpdatedAt > 0 &&
    Number.isFinite(existingUpdatedAt) && existingUpdatedAt > incomingUpdatedAt;
}

export function isJobSnapshotOlderThan(
  incoming: JobSummary,
  knownUpdatedAt: number | undefined,
): boolean {
  const incomingUpdatedAt = Number(incoming.updated_at);
  return Number.isFinite(incomingUpdatedAt) && incomingUpdatedAt > 0 &&
    Number.isFinite(knownUpdatedAt) && Number(knownUpdatedAt) > incomingUpdatedAt;
}

/** A late detail response must not replace a newer list or approval response. */
export function upsertJobSnapshot(current: JobSummary[], incoming: JobSummary): JobSummary[] {
  const index = current.findIndex(item => item.job_id === incoming.job_id);
  if (index < 0) return [incoming, ...current];
  const existing = current[index];
  if (hasOlderTimestamp(incoming, existing)) return current;
  const next = [...current];
  next[index] = { ...existing, ...incoming } as JobSummary;
  return next;
}

/** Lightweight polling must not erase an already fetched terminal artifact. */
export function mergeJobSummaries(current: JobSummary[], incoming: JobSummary[]): JobSummary[] {
  return incoming.map(summary => {
    const detail = current.find(item => item.job_id === summary.job_id);
    if (!detail) return summary;
    if (hasOlderTimestamp(summary, detail)) return detail;
    const sameSnapshot = detail.updated_at === summary.updated_at && detail.status === summary.status;
    return { ...(sameSnapshot ? detail : {}), ...summary,
      artifact_history: summary.artifact_history ?? detail.artifact_history,
    } as JobSummary;
  });
}
