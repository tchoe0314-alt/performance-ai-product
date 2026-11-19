import type { SystemGenerationTarget } from "./workflowConstants";

/** Resolve an explicit Generate command without letting the first discipline word
 * discard the rest of a combined site-program request. */
export function resolveDashboardGenerationTarget(message: string): SystemGenerationTarget | null {
  const normalized = message.toLowerCase();
  if (!/(?:generate|run)\b/.test(normalized)) return null;
  if (/\b(?:full|all|everything)\b/.test(normalized)) return "full";

  const mentionsBuilding = /\b(?:building|office|commercial|industrial|residential|mixed[- ]use|site)\b/.test(normalized);
  const targets: SystemGenerationTarget[] = [];
  if (/\b(?:roads?|circulation)\b/.test(normalized)) targets.push("roads");
  if (/\bparking\b/.test(normalized)) targets.push("parking");
  if (/\b(?:grading|contours?)\b/.test(normalized)) targets.push("grading");
  if (/\b(?:drainage|storm(?:water)?)\b/.test(normalized)) targets.push("drainage");
  if (/\b(?:utilities|utility)\b/.test(normalized)) targets.push("utilities");

  // Buildings are part of the coordinated full-site concept, not a standalone
  // engineering-system target. Multiple requested disciplines likewise require
  // the coordinated path so none of the explicit program is silently omitted.
  if (mentionsBuilding || new Set(targets).size > 1) return "full";
  return targets[0] ?? null;
}
