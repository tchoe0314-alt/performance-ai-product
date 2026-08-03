import { toReadableLabel } from "./formatting";

const WORD_REPLACEMENTS: Array<[RegExp, string]> = [
  [/\bwut\b/g, "what"],
  [/\bwat\b/g, "what"],
  [/\bwhats\b/g, "what is"],
  [/\bwhast\b/g, "what"],
  [/\bblockd\b/g, "blocked"],
  [/\bblok(?:ed|d)\b/g, "blocked"],
  [/\bchnged\b/g, "changed"],
  [/\bshud\b/g, "should"],
  [/\bnex\b/g, "next"],
  [/\brn\b/g, "right now"],
  [/\bexpot\b/g, "export"],
];

const INTERNAL_RELEASE_BOUNDARY = /^(?:construction(?:_|\s)|release(?:_|\s)|final_plan_release|latest_(?:run|artifact)_release|professional_release|engineer_of_record)/i;

export function normalizeDashboardChatIntent(message: string) {
  let normalized = message
    .toLowerCase()
    .replace(/[’']/g, "")
    .replace(/[^a-z0-9.%+\-\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  for (const [pattern, replacement] of WORD_REPLACEMENTS) {
    normalized = normalized.replace(pattern, replacement);
  }
  return normalized.replace(/\s+/g, " ").trim();
}

export function userFacingWorkflowNeeds(values: Array<string | null | undefined>) {
  const seen = new Set<string>();
  const needs: string[] = [];
  for (const rawValue of values) {
    const value = String(rawValue || "").trim();
    if (!value || INTERNAL_RELEASE_BOUNDARY.test(value)) continue;
    const readable = toReadableLabel(value)
      .replace(/\breview required\b/gi, "needs review")
      .replace(/\bblocked\b/gi, "needs input")
      .replace(/\s+/g, " ")
      .trim();
    const key = readable.toLowerCase();
    if (!readable || seen.has(key)) continue;
    seen.add(key);
    needs.push(readable);
  }
  return needs;
}
