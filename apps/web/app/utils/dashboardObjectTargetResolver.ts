import type { BuildingPlacement } from "../types";

export type ObjectTargetResolution =
  | { status: "resolved"; object: BuildingPlacement }
  | { status: "ambiguous"; candidates: BuildingPlacement[] }
  | { status: "not_found" };

const normalize = (value: string) => value.toLowerCase().replaceAll("_", " ").replace(/[^a-z0-9 -]+/g, " ").replace(/\s+/g, " ").trim();
const deictic = new Set(["", "this", "it", "object", "selected", "selected object", "the selected object", "selected building", "the selected building"]);

export function resolveDashboardObjectTarget({
  objects,
  selectedId,
  targetText,
  allowSelectionFallback = true,
}: {
  objects: BuildingPlacement[];
  selectedId?: string | null;
  targetText: string;
  allowSelectionFallback?: boolean;
}): ObjectTargetResolution {
  const target = normalize(targetText.replace(/^(?:the|a|an)\s+/i, ""));
  const selected = selectedId ? objects.find(item => item.id === selectedId) : undefined;
  if (deictic.has(target)) return allowSelectionFallback && selected ? { status: "resolved", object: selected } : { status: "not_found" };

  const exact = objects.filter(item => normalize(item.label) === target || normalize(item.id) === target);
  if (exact.length === 1) return { status: "resolved", object: exact[0] };
  if (exact.length > 1) return { status: "ambiguous", candidates: exact };

  const fuzzy = objects.filter(item => {
    const label = normalize(item.label), type = normalize(item.type ?? "");
    return label.includes(target) || type === target;
  });
  if (fuzzy.length === 1) return { status: "resolved", object: fuzzy[0] };
  if (fuzzy.length > 1) return { status: "ambiguous", candidates: fuzzy };
  return { status: "not_found" };
}

export function objectTargetClarification(resolution: Exclude<ObjectTargetResolution, { status: "resolved" }>, action: string) {
  return resolution.status === "ambiguous"
    ? `Which object should I ${action}? Matches: ${resolution.candidates.slice(0, 6).map(item => item.label).join(", ")}. No geometry was changed.`
    : `I couldn't find that object. Include its exact name or ID, or select one first. No geometry was changed.`;
}
