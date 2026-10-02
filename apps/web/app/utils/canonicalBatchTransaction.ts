import type { BuildingPlacement } from "../types";
import { applyCanonicalUpdateCommand, canonicalControlState, createCanonicalUpdateCommand } from "./canonicalEditCommands";
import { applyBuildingParkingDependency, type CanonicalDependencyProposal } from "./canonicalDependencyPolicies";

export type CanonicalBatchEdit = { objectId: string; updates: Partial<BuildingPlacement> };

/** Pure planning: all edits/dependencies succeed before any caller may commit. */
export function planCanonicalBatchTransaction(
  source: BuildingPlacement[], edits: CanonicalBatchEdit[], projectId: string | null,
  label: string, transactionId: string, createdAt = new Date().toISOString(),
) {
  const fail = (reason: string) => ({ status: "blocked" as const, reason, placements: source, proposal: null, before: [], after: [] });
  if (new Set(source.map(item => item.id)).size !== source.length || new Set(edits.map(edit => edit.objectId)).size !== edits.length) {
    return fail("Duplicate object identities prevent a safe transaction.");
  }
  let working = source;
  let asks = false;
  const reports: CanonicalDependencyProposal["reflowReports"] = [];
  for (const edit of edits) {
    const current = working.find(item => item.id === edit.objectId);
    if (!current) return fail("An object changed or disappeared. Request a fresh revision.");
    if (current.locked || ["fixed", "existing", "reference"].includes(canonicalControlState(current))) {
      return fail(`${current.label} is protected. Explicitly make it flexible before revising the program.`);
    }
    const command = createCanonicalUpdateCommand(current.id, edit.updates, "chat", transactionId, createdAt);
    const result = applyCanonicalUpdateCommand(current, command);
    if (result.blockedReason) return fail(result.blockedReason);
    const next = result.object;
    if (![next.x ?? 0, next.y ?? 0, next.w, next.d].every(Number.isFinite) || next.w <= 0 || next.d <= 0 ||
        next.geometry?.some(point => point.length !== 2 || !point.every(Number.isFinite))) {
      return fail(`${current.label} has invalid geometry. The transaction was not applied.`);
    }
    const dependency = applyBuildingParkingDependency(working, current, next, command);
    for (const linked of dependency.after) {
      const original = working.find(item => item.id === linked.id)!;
      if (JSON.stringify(linked) !== JSON.stringify(original) &&
          (original.locked || ["fixed", "existing", "reference"].includes(canonicalControlState(original)))) {
        return fail(`${original.label} is protected and cannot follow this revision.`);
      }
    }
    asks ||= dependency.proposalObjectIds.length > 0;
    reports.push(...dependency.reflowReports);
    const replacements = new Map(dependency.after.map(item => [item.id, item]));
    replacements.set(current.id, next);
    working = working.map(item => replacements.get(item.id) ?? item);
  }
  const before = source.filter((item, index) => JSON.stringify(item) !== JSON.stringify(working[index]));
  const ids = new Set(before.map(item => item.id));
  const after = working.filter(item => ids.has(item.id));
  const proposal: CanonicalDependencyProposal | null = asks ? {
    id: transactionId, transactionId, buildingId: edits[0]?.objectId ?? "", buildingLabel: label,
    before, after, reflowReports: reports, createdAt, projectId, sourceSnapshot: JSON.stringify(source),
  } : null;
  return { status: asks ? "proposed" as const : "applied" as const, reason: null, placements: working, proposal, before, after };
}
