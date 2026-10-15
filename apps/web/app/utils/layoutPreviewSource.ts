import type { ProjectInput } from "../types";
import { liveInputFingerprint } from "./liveCalculationFreshness";
import { parseNonNegativeInteger, parseNonNegativeNumber } from "./formatting";
import type { LayoutAlternativeRequest } from "./layoutAlternatives";

export type LayoutPreviewSource = { projectId: string | null; placements: string; inputKey?: string };

export function layoutRequirementContext(input: ProjectInput): Pick<LayoutAlternativeRequest, "units" | "requiredParking" | "setback"> {
  const controls = input.meta?.edit_controls_v1 as Record<string, unknown> | undefined;
  const raw = controls && Object.hasOwn(controls, "parkingCount") ? controls.parkingCount : input.manual_fields?.site_plan?.parking_count;
  const absent = raw === undefined || raw === null || typeof raw === "string" && !raw.trim();
  const parsed = typeof raw === "string" || typeof raw === "number" ? parseNonNegativeInteger(raw) : null;
  const rawSetback = controls && Object.hasOwn(controls, "setback") ? controls.setback : input.manual_fields?.setback;
  const unsetSetback = rawSetback == null || typeof rawSetback === "string" && !rawSetback.trim();
  const setback = typeof rawSetback === "number" || typeof rawSetback === "string" ? parseNonNegativeNumber(rawSetback) : null;
  return { units: input.manual_fields?.units ?? "", requiredParking: absent ? null : parsed ?? NaN, setback: unsetSetback ? null : setback ?? NaN };
}

export function layoutInputsMatch(source: LayoutPreviewSource, input: ProjectInput): boolean {
  try { return source.inputKey === liveInputFingerprint(input); } catch { return false; }
}
