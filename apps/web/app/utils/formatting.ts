import type {
  MetricValue,
  BackendAssumption,
  PlanResponse,
  PlanToolMode,
} from "../types";

export const defaultAssumptions = [
  {
    field: "project_type",
    value: "commercial_pad",
    reason:
      "AI filled this because the prompt described a general commercial site concept.",
  },
  {
    field: "lot",
    value: "estimated from sketch extents",
    reason: "No exact lot dimensions were provided in the form.",
  },
];

export function formatChatTimestamp(value: number) {
  if (!value) return "";
  try {
    return new Date(value).toLocaleTimeString([], {
      hour: "numeric",
      minute: "2-digit",
    });
  } catch {
    return "";
  }
}

export function toReadableLabel(value: string): string {
  const normalized = value
    .replace(/design_defaults/gi, "design defaults")
    .replace(/^qa$/i, "validation")
    .replace(/^general$/i, "design")
    .replace(/_/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  return normalized
    .replace(/_/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

export function joinNatural(items: string[], limit = 3): string {
  const filtered = items
    .map((item) => item.trim())
    .filter(Boolean)
    .slice(0, limit);
  if (!filtered.length) {
    return "";
  }
  if (filtered.length === 1) {
    return filtered[0];
  }
  if (filtered.length === 2) {
    return `${filtered[0]} and ${filtered[1]}`;
  }
  return `${filtered.slice(0, -1).join(", ")}, and ${filtered[filtered.length - 1]}`;
}

export function toArray<T>(value: unknown): T[] {
  return Array.isArray(value) ? (value as T[]) : [];
}

export function parsePositiveNumber(
  value: string | number | null | undefined,
): number | null {
  const numeric = Number(value ?? 0);
  return Number.isFinite(numeric) && numeric > 0 ? numeric : null;
}

export function readMetricValue(value: MetricValue | undefined): number | null {
  if (value == null) return null;
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "object" && typeof value.value === "number" && Number.isFinite(value.value)) {
    return value.value;
  }
  return null;
}

export function formatMetric(value: number | null, unit: string): string {
  if (value == null || !Number.isFinite(value)) return "Pending";
  return `${value.toFixed(1)} ${unit}`;
}

export function formatCount(value: number | null, unit?: string): string {
  if (value == null || !Number.isFinite(value)) return "Pending";
  const rounded = Math.round(value);
  return unit ? `${rounded.toLocaleString()} ${unit}` : rounded.toLocaleString();
}

export function summarizePlanResponse(
  data: PlanResponse,
  mode: PlanToolMode,
): string {
  const missingRequirements =
    data?.missing_requirements ?? data?.metadata?.missing_requirements ?? null;
  if (missingRequirements && data?.success === false) {
    const missingFields = Array.isArray(missingRequirements.missing_fields)
      ? missingRequirements.missing_fields
          .map((item) => String(item || "").trim())
          .filter(Boolean)
      : [];
    const suggestedActions = Array.isArray(missingRequirements.suggested_next_actions)
      ? missingRequirements.suggested_next_actions
          .map((item) => String(item || "").trim())
          .filter(Boolean)
      : [];
    const headline =
      typeof data?.message === "string" && data.message.trim()
        ? data.message.trim()
        : missingFields.length
          ? `Civora needs ${joinNatural(missingFields.slice(0, 3))} before it can complete this step.`
          : "Civora needs more information before it can complete this step.";
    const nextAction = suggestedActions.length
      ? `Next: ${suggestedActions.slice(0, 2).join(" ")}`
      : missingRequirements.can_assist_if_enabled
        ? "Next: add the missing details, or turn on Assisted to let Civora infer clearly labeled assumptions."
        : null;
    return [headline, nextAction].filter(Boolean).join(" ");
  }

  const plan = data?.final_plan ?? {};
  const meta = plan?.meta ?? {};
  const explanation = meta?.explanation;
  const convergence = meta?.convergence_summary ?? {};
  const assumptionSummary = convergence?.assumption_summary ?? {};
  const producedDeliverables = Array.isArray(meta?.deliverables?.produced)
    ? meta.deliverables.produced
    : Array.isArray(meta?.produced_deliverables)
      ? meta.produced_deliverables
      : [];
  const failedDeliverables = Array.isArray(meta?.deliverables?.failed)
    ? meta.deliverables.failed
    : Array.isArray(meta?.failed_deliverables)
      ? meta.failed_deliverables
      : [];
  const assumptions = Array.isArray(data?.assumptions)
    ? data.assumptions
    : Array.isArray(assumptionSummary?.examples)
      ? assumptionSummary.examples.map((example) => ({
          field_name: "assumption",
          reason: String(example || ""),
        }))
      : [];
  const issues = Array.isArray(data?.issues) ? data.issues : [];
  const assumptionExamples = (() => {
    const seen = new Set<string>();
    const isInternalAssumption = (value: string) => {
      const lowered = value.toLowerCase();
      return (
        lowered === "plan" ||
        lowered === "assumption" ||
        lowered.includes("planner execution assumption") ||
        lowered.includes("projectmanager as active lifecycle state") ||
        lowered.includes("action geometry is treated as output packaging") ||
        lowered.includes("quantities prefer canonical projectmanager metrics") ||
        lowered.includes("planner executed model-first workflow") ||
        lowered.includes("prompt was parsed with deterministic fast-path rules") ||
        lowered.includes("autofix site layout") ||
        lowered.includes("autofix_site_layout")
      );
    };
    const formatted = assumptions
      .map((assumption) => {
        const fallbackField =
          "field_name" in assumption
            ? assumption.field_name
            : (assumption as BackendAssumption | null)?.field;
        const field = String(fallbackField || "an input")
          .replace(/_/g, " ")
          .trim();
        const reason = String(assumption?.reason || "").trim();
        const loweredField = field.toLowerCase();
        if (
          loweredField === "plan" ||
          loweredField === "assumption" ||
          isInternalAssumption(reason)
        ) {
          return null;
        }
        const normalized = `${field}::${reason}`.toLowerCase();
        if (seen.has(normalized)) {
          return null;
        }
        seen.add(normalized);
        return reason ? `${field} (${reason})` : field;
      })
      .filter(Boolean);
    if (formatted.length) {
      return formatted.slice(0, 3);
    }
    const fallbackExamples = Array.isArray(assumptionSummary?.examples)
      ? assumptionSummary.examples
          .map((example) => String(example || "").trim())
          .filter((example: string) => Boolean(example) && !isInternalAssumption(example))
      : [];
    return fallbackExamples.slice(0, 3);
  })();
  const fixSummary = convergence?.fix_summary ?? {};
  const blockedReasons = Array.isArray(convergence?.blocked_reasons)
    ? convergence.blocked_reasons
    : [];
  const blockedExports = Array.isArray(convergence?.blocked_exports)
    ? convergence.blocked_exports
    : [];
  const reviewCategories = Array.isArray(convergence?.unresolved_issue_categories)
    ? convergence.unresolved_issue_categories
    : [];
  const autofixActions = Array.isArray(fixSummary?.autofix_actions)
    ? fixSummary.autofix_actions
    : [];
  const dominantFixTargets = Array.isArray(convergence?.dominant_issue_categories)
    ? convergence.dominant_issue_categories
    : [];
  const unresolved = Number(convergence?.unresolved_conflict_count ?? 0);
  const headline =
    (typeof explanation?.summary === "string"
      ? explanation.summary
      : typeof explanation?.overview === "string"
        ? explanation.overview
        : typeof data?.message === "string"
          ? data.message
          : mode === "fix"
            ? "I ran a focused fix pass and updated the active design."
            : mode === "improve"
              ? "I ran an improvement pass and updated the active design."
              : "I updated the active design workspace.");
  const why =
    typeof explanation?.why === "string"
      ? explanation.why
      : typeof explanation?.reasoning === "string"
        ? explanation.reasoning
        : null;

  const readableAutofixActions = autofixActions
    .map((item) => toReadableLabel(String(item || "")))
    .filter(Boolean);
  const readableFixTargets = dominantFixTargets
    .map((item) => toReadableLabel(String(item || "")))
    .filter(Boolean);
  const readableReviewCategories = reviewCategories
    .map((item) => toReadableLabel(String(item || "")))
    .filter(
      (item: string) =>
        Boolean(item) &&
        item.toLowerCase() !== "uncategorized" &&
        item.toLowerCase() !== "general",
    );
  const readableBlockedReasons = blockedReasons
    .map((item) => toReadableLabel(String(item || "")))
    .filter(Boolean);
  const readableBlockedExports = blockedExports
    .map((item) => toReadableLabel(String(item || "")))
    .filter(Boolean);
  const readableProduced = producedDeliverables
    .map((item) => toReadableLabel(String(item || "")))
    .filter(Boolean);
  const readableFailed = failedDeliverables
    .map((item) => toReadableLabel(String(item || "")))
    .filter(Boolean);
  const issueMessages = issues
    .slice(0, 2)
    .map((issue) => String(issue?.message || "").trim())
    .filter(Boolean);

  const assumptionList = assumptionExamples.filter(
    (item): item is string => Boolean(item),
  );

  const notes = [
    assumptionList.length
      ? `I used assisted assumptions for ${joinNatural(assumptionList)}.`
      : "I did not need to record any explicit assisted assumptions on this run.",
    readableAutofixActions.length || readableFixTargets.length
      ? `I applied fixes around ${joinNatural(
          readableAutofixActions.length ? readableAutofixActions : readableFixTargets,
        )}.`
      : "I did not need to record any corrective fix actions on this run.",
    readableReviewCategories.length || issueMessages.length || unresolved > 0
      ? `You should still review ${joinNatural(
          readableReviewCategories.length
            ? readableReviewCategories
            : issueMessages.length
              ? issueMessages
              : [`${unresolved} unresolved conflicts`],
        )}.`
      : "I don’t see any active review items recorded right now.",
    readableBlockedReasons.length || readableBlockedExports.length || readableFailed.length
      ? `What is still blocked: ${joinNatural(
          readableBlockedReasons.length
            ? readableBlockedReasons
            : readableBlockedExports.length
              ? readableBlockedExports
              : readableFailed,
        )}.`
      : "Nothing is explicitly blocked right now.",
    producedDeliverables.length
      ? `I produced ${joinNatural(readableProduced, 4)}.`
      : null,
    why,
  ].filter(Boolean);

  return [headline, ...notes].join(" ");
}
