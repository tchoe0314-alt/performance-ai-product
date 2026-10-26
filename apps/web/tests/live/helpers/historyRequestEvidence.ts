/** Conservative Q01 test evidence, not an application authorization policy.
 * Unknown/missing observations fail closed; never ignore all ERR_ABORTED reads.
 */
export type HistoryRequestObservation = {
  id: number;
  method: string;
  path: string;
  actorMatches: boolean;
  startedAt: number;
  completedAt?: number;
  failedAt?: number;
  status?: number;
  error?: string;
  startedOrder?: number;
  abortOrder?: number;
  failedOrder?: number;
};

export type CurrentHistoryProof = {
  projectId: string;
  revision: string;
  headerRevision: string;
  headerNameMatches: boolean;
  headerHistoryMatches: boolean;
  historyResponseMatches: boolean;
};

export function provenSupersededHistoryReads(
  observations: readonly HistoryRequestObservation[], proof: CurrentHistoryProof,
): Set<number> {
  const accepted = new Set<number>();
  if (!proof.projectId || !proof.revision || proof.revision !== proof.headerRevision ||
      !proof.headerNameMatches || !proof.headerHistoryMatches || !proof.historyResponseMatches) return accepted;
  const path = `/api/projects/${encodeURIComponent(proof.projectId)}/calculations`;
  const current = observations.filter(item => item.path === path && item.method === "GET" && item.actorMatches);
  const latest = current.reduce<HistoryRequestObservation | undefined>((previous, item) =>
    !previous || item.id > previous.id ? item : previous, undefined);
  if (!latest || latest.status !== 200 || latest.error || latest.failedAt !== undefined ||
      !Number.isFinite(latest.startedAt) || !Number.isFinite(latest.completedAt) ||
      latest.completedAt! < latest.startedAt) return accepted;
  for (const item of current) {
    // Header hook timeout is six seconds. A timeout cannot be reclassified as
    // supersession even if a later unrelated refresh eventually succeeds.
    const elapsed = item.failedAt === undefined ? NaN : item.failedAt - item.startedAt;
    if (item.id >= latest.id || item.error !== "net::ERR_ABORTED" || item.failedAt === undefined ||
        !Number.isFinite(elapsed) || elapsed < 0 || elapsed >= 6000 ||
        latest.completedAt! <= item.failedAt || !Number.isFinite(item.abortOrder) ||
        !Number.isFinite(item.failedOrder) || item.abortOrder! >= item.failedOrder!) continue;
    // Direct client event sequence, not asynchronous driver callback timing:
    // replacement starts after signal abort and before old rejection is observed.
    const replacement = current.some(candidate => candidate.id > item.id &&
      Number.isFinite(candidate.startedOrder) && candidate.startedOrder! > item.abortOrder! &&
      candidate.startedOrder! < item.failedOrder!);
    if (replacement) accepted.add(item.id);
  }
  return accepted;
}
