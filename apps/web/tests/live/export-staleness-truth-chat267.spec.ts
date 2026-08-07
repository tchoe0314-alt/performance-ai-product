import { expect, test } from "@playwright/test";

import { resolveDashboardExportBlockReason } from "../../app/utils/dashboardExportActions";

test.describe("export staleness truth", () => {
  test("blocks stale systems before an export job is queued", () => {
    const reason = resolveDashboardExportBlockReason({
      token: "authenticated",
      backendResultPresent: true,
      projectId: "project-1",
      systemStatuses: {
        roads: "fresh",
        parking: "fresh",
        grading: "stale",
        drainage: "stale",
        utilities: "fresh",
      },
      staleOutputs: ["quantities", "drainage"],
    });

    expect(reason).toBe("rerun affected systems before exporting: grading, drainage, quantities");
  });

  test("keeps authentication and missing-run needs ahead of staleness", () => {
    expect(resolveDashboardExportBlockReason({
      token: null,
      backendResultPresent: true,
      projectId: "project-1",
      systemStatuses: { grading: "stale" },
      staleOutputs: [],
    })).toContain("authenticate");

    expect(resolveDashboardExportBlockReason({
      token: "authenticated",
      backendResultPresent: false,
      projectId: "project-1",
      systemStatuses: { grading: "stale" },
      staleOutputs: [],
    })).toContain("run systems");
  });
});
