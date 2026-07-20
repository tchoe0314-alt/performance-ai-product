import type { DesignAlternative, DesignAlternativesV1, ReviewIssueTrackerV1 } from "../types";

export type ReviewIssueItem = NonNullable<ReviewIssueTrackerV1["issues"]>[number];

export type DesignAlternativeSummary = {
  items: DesignAlternative[];
  top: DesignAlternative | null;
  selectedId: string;
  quantityAvailable: boolean;
};

export type ReviewIssueCollections = {
  items: ReviewIssueItem[];
  openItems: ReviewIssueItem[];
  drainageItems: ReviewIssueItem[];
};

export function buildDesignAlternativeSummary(designAlternatives: DesignAlternativesV1): DesignAlternativeSummary {
  const items = designAlternatives.alternatives ?? [];
  const top =
    items
      .slice()
      .sort((a, b) => Number(b.scoring?.review_score ?? 0) - Number(a.scoring?.review_score ?? 0))[0] ?? null;
  return {
    items,
    top,
    selectedId: designAlternatives.selected_alternative_id || designAlternatives.selected_alternative?.alternative_id || "",
    quantityAvailable: Boolean(designAlternatives.quantity_basis?.available),
  };
}

export function buildReviewIssueCollections(reviewIssueTracker: ReviewIssueTrackerV1): ReviewIssueCollections {
  const items = reviewIssueTracker.issues ?? [];
  const openItems = reviewIssueTracker.open_issues ?? items.filter((item) =>
    ["open", "in_review", "reopened"].includes(String(item.status ?? "open")),
  );
  const drainageItems = openItems.filter((item) =>
    String(item.discipline ?? "").toLowerCase() === "drainage" ||
    String(item.title ?? item.description ?? "").toLowerCase().includes("drainage") ||
    String(item.title ?? item.description ?? "").toLowerCase().includes("storm"),
  );
  return { items, openItems, drainageItems };
}
