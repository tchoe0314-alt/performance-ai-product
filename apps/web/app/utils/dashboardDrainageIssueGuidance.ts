import type { Issue } from "../types";

type DrainageIssueGuidance = {
  explanation: string | null;
  bestNextFix: string | null;
  suggested: string[] | null;
};

export function getDashboardDrainageIssueApplyLabel(issue: Issue) {
  const code = (issue.code ?? "").toUpperCase();
  if (code === "NO_PONDS_DEFINED" || code === "NO_VALID_OUTFALL" || code === "DRAINAGE_NO_BASIN") {
    return "Add basin";
  }
  if (code === "BASIN_UNREACHABLE") return "Add basin";
  if (code === "POOR_SLOPE") return "Adjust slope";
  if (code === "ORPHAN_INLETS") return "Connect inlet";
  if (code === "UNDER_COLLECTION") return "Add inlet";
  if (code === "UNDER_COLLECTION_REDUCED") return "Add inlet";
  return null;
}

export function getDashboardDrainageIssueGuidance(issue: Issue): DrainageIssueGuidance {
  const code = (issue.code ?? "").toUpperCase();
  const rawContext = issue.context;
  const context =
    rawContext && typeof rawContext === "object"
      ? (rawContext as Record<string, unknown>)
      : null;
  const explanation =
    context && typeof context.explanation === "string"
      ? String(context.explanation)
      : null;
  const bestNextFix =
    context && typeof context.best_next_fix === "string"
      ? String(context.best_next_fix)
      : null;
  const suggested =
    context && Array.isArray(context.suggested_actions)
      ? context.suggested_actions
          .filter((item) => typeof item === "string")
          .map((item) => String(item))
      : null;
  if (explanation || bestNextFix || (suggested && suggested.length)) {
    return { explanation, bestNextFix, suggested };
  }
  const fallback: Record<string, { explanation: string; suggested: string[]; bestNextFix: string }> = {
    BASIN_UNREACHABLE: {
      explanation: "Flow cannot reach the basin from current low points.",
      suggested: [
        "Move the basin to a lower point.",
        "Add an inlet near the low point.",
        "Adjust grading to direct flow toward the basin.",
      ],
      bestNextFix: "Move the basin to a lower point.",
    },
    DRAINAGE_NO_BASIN: {
      explanation: "No valid basin or outfall was provided for drainage.",
      suggested: [
        "Add a basin at a low point.",
        "Define an outfall location.",
        "Connect to an existing downstream system.",
      ],
      bestNextFix: "Add a basin at a low point.",
    },
    NO_VALID_OUTFALL: {
      explanation: "No valid outlet was found for drainage discharge.",
      suggested: [
        "Add a basin at a low point.",
        "Define an outfall location.",
        "Connect to an existing downstream system.",
      ],
      bestNextFix: "Add a basin at a low point.",
    },
    NO_PONDS_DEFINED: {
      explanation: "No basin/pond target is defined for drainage.",
      suggested: [
        "Add a basin at a low point.",
        "Define an outfall location.",
        "Connect to an existing downstream system.",
      ],
      bestNextFix: "Add a basin at a low point.",
    },
    POOR_SLOPE: {
      explanation: "Terrain is too flat for the minimum pipe slope.",
      suggested: [
        "Modify grading to introduce slope.",
        "Relocate inlets or basin to a steeper area.",
        "Increase slope in this region.",
      ],
      bestNextFix: "Modify grading to introduce slope.",
    },
    SLOPE_ADJUSTMENT_FAILED: {
      explanation: "Slope adjustment is not feasible with the current geometry.",
      suggested: [
        "Modify grading to introduce slope.",
        "Relocate inlets or basin to a steeper area.",
        "Increase slope in this region.",
      ],
      bestNextFix: "Modify grading to introduce slope.",
    },
    ORPHAN_INLETS: {
      explanation: "One or more inlets are not connected to a drainage run.",
      suggested: [
        "Connect the inlet to the nearest run.",
        "Reroute the pipe network to include the inlet.",
      ],
      bestNextFix: "Connect the inlet to the nearest run.",
    },
    UNDER_COLLECTION: {
      explanation: "There are not enough inlets to collect runoff.",
      suggested: ["Add inlets along pavement edges."],
      bestNextFix: "Add inlets along pavement edges.",
    },
    UNDER_COLLECTION_REDUCED: {
      explanation: "Inlet coverage improved, but runoff is still under-collected.",
      suggested: ["Add inlets along pavement edges."],
      bestNextFix: "Add inlets along pavement edges.",
    },
  };
  const fallbackGuidance = fallback[code];
  return fallbackGuidance
    ? fallbackGuidance
    : { explanation: null, bestNextFix: null, suggested: null };
}

export function canApplyDashboardDrainageIssue(issue: Issue) {
  const code = (issue.code ?? "").toUpperCase();
  return (
    code === "UNDER_COLLECTION" ||
    code === "UNDER_COLLECTION_REDUCED" ||
    code === "BASIN_UNREACHABLE" ||
    code === "DRAINAGE_NO_BASIN" ||
    code === "NO_VALID_OUTFALL" ||
    code === "NO_PONDS_DEFINED" ||
    code === "ORPHAN_INLETS" ||
    code === "POOR_SLOPE"
  );
}
