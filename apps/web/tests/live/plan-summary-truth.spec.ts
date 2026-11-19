import { expect, test } from "@playwright/test";

import { summarizePlanResponse } from "../../app/utils/formatting";
import type { PlanResponse } from "../../app/types";

test("a skipped engineering stage is never summarized as complete and unblocked", () => {
  const response = {
    success: true,
    message: "Full design workflow completed.",
    final_plan: {
      meta: {
        manager_export: { system_counts: { skipped: 1 } },
        stage_results: [{
          stage_name: "storm_pipes",
          success: true,
          message: "Storm pipe stage skipped because no inlet records were available.",
        }],
      },
    },
  } as PlanResponse;

  const summary = summarizePlanResponse(response, "run");
  expect(summary).toContain("Storm pipe stage skipped because no inlet records were available.");
  expect(summary).not.toContain("I don’t see any active review items");
  expect(summary).not.toContain("Nothing is explicitly blocked");
});
