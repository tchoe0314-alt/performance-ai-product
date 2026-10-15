import type { PlanResponse, ProjectInput } from "../types";
import { withCanonicalCanvasSnapshot, resolveCanonicalCanvasInput } from "./canonicalCanvasProject";

export function liveInputFingerprint(input: ProjectInput): string {
  const resolved = resolveCanonicalCanvasInput(withCanonicalCanvasSnapshot(input));
  const fields = { ...resolved.manual_fields };
  delete fields.project_name;
  delete fields.file_name;
  const encode = (value: unknown): unknown => {
    if (value === null) return ["null"];
    if (typeof value === "boolean") return ["bool", value];
    if (typeof value === "string") return ["string", value];
    if (typeof value === "number") {
      if (!Number.isFinite(value)) throw new Error("Invalid calculation input.");
      const buffer = new ArrayBuffer(8);
      new DataView(buffer).setFloat64(0, value === 0 ? 0 : value);
      return ["number", Array.from(new Uint8Array(buffer), byte => byte.toString(16).padStart(2, "0")).join("")];
    }
    if (Array.isArray(value)) return ["array", value.map(encode)];
    if (value && typeof value === "object") return ["object", Object.keys(value).sort().map(key => [key, encode((value as Record<string, unknown>)[key])])];
    throw new Error("Unsupported calculation input.");
  };
  return JSON.stringify(encode({ manual_fields: fields, site_inputs: resolved.meta?.site_inputs || {} }))
    .replace(/[\u0080-\uffff]/g, char => `\\u${char.charCodeAt(0).toString(16).padStart(4, "0")}`);
}

export async function isLiveCalculationCurrent(result: PlanResponse, getInput: () => ProjectInput): Promise<boolean> {
  const binding = result.metadata?.canvas_result_binding_v1;
  if (!binding?.live_input_key_v1) return true; // Legacy results remain explicitly unverified.
  try {
    const before = liveInputFingerprint(getInput());
    const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(before));
    const key = Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, "0")).join("");
    return binding.live_input_key_v1 === key && before === liveInputFingerprint(getInput());
  } catch {
    return false;
  }
}
