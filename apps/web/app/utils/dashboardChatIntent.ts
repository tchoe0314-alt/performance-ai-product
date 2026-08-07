import { toReadableLabel } from "./formatting";

const WORD_REPLACEMENTS: Array<[RegExp, string]> = [
  [/\bwut\b/g, "what"],
  [/\bwat\b/g, "what"],
  [/\bwhats\b/g, "what is"],
  [/\bwhast\b/g, "what"],
  [/\bblockd\b/g, "blocked"],
  [/\bblok(?:ed|d)\b/g, "blocked"],
  [/\b(?:bloced|blcoked|bocked)\b/g, "blocked"],
  [/\bchnged\b/g, "changed"],
  [/\bchang+e+d\b/g, "changed"],
  [/\bchaged\b/g, "changed"],
  [/\bbuldings\b/g, "buildings"],
  [/\bbulding\b/g, "building"],
  [/\badress\b/g, "address"],
  [/\bboundry\b/g, "boundary"],
  [/\bdrveway\b/g, "driveway"],
  [/\bdrivewy\b/g, "driveway"],
  [/\bdriveay\b/g, "driveway"],
  [/\bsanatary\b/g, "sanitary"],
  [/\bsanitry\b/g, "sanitary"],
  [/\bsewar\b/g, "sewer"],
  [/\bwatter\b/g, "water"],
  [/\bparkin\b/g, "parking"],
  [/\bparkng\b/g, "parking"],
  [/\bprking\b/g, "parking"],
  [/\b(?:spces|spacs|sapces)\b/g, "spaces"],
  [/\bofice\b/g, "office"],
  [/\bbilding\b/g, "building"],
  [/\bbason\b/g, "basin"],
  [/\bstrom\b/g, "storm"],
  [/\b(?:side\s+walks?|sidewaks?|sidewlk?s?)\b/g, "sidewalk"],
  [/\bdraniage\b/g, "drainage"],
  [/\bdrainange\b/g, "drainage"],
  [/\bdeten(?:ion|tion)\b/g, "detention"],
  [/\b(?:detenshun|detenshion|detenton)\b/g, "detention"],
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
    .replace(/[^a-z0-9.,%+\-\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  for (const [pattern, replacement] of WORD_REPLACEMENTS) {
    normalized = normalized.replace(pattern, replacement);
  }
  return normalized
    .replace(/\bwhat is changed\b/g, "what changed")
    .replace(/\bwhat is next\b/g, "what next")
    .replace(/\s+/g, " ")
    .trim();
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
