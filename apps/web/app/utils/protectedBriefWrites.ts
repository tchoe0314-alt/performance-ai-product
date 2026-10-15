import type { ProjectInput } from "../types";
import { buildActiveBriefSummary } from "./activeBriefSummary";
import { classificationFor } from "./briefClassification";
import { briefRawValue } from "./briefEditing";

export function protectedBriefWriteReason(input: ProjectInput, id: "required-parking" | "setbacks", value: string | number): string | null {
  try {
    const row = buildActiveBriefSummary(input).find(item => item.id === id)!;
    const classification = classificationFor(row, input.meta?.site_inputs?.active_brief_classifications_v1);
    if (!["sourced", "externally_verified"].includes(classification.trust)) return null;
    const existing = briefRawValue(input, id);
    if (existing !== null && String(value).trim() !== "" && Number.isFinite(Number(value)) && Number(value) === Number(existing)) return null;
    return `${row.label} is source-protected. Use Brief > Edit > Override to change it. The requirement was not changed.`;
  } catch { return "Review invalid brief data before changing its requirements."; }
}
