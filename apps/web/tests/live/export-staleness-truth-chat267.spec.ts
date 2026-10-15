import { expect, test } from "@playwright/test";

import { createDashboardExportActions, resolveDashboardExportBlockReason, type DashboardExportActionsConfig } from "../../app/utils/dashboardExportActions";

test.describe("export staleness truth", () => {
  test("unsaved live changes block all new exports before queuing or downloading", async () => {
    const messages: string[] = [];
    let started = false;
    const config = {
      token: "authenticated", backendResultPresent: true, projectId: "pilot",
      currentPlanMeta: {}, systemStatuses: {},
      reviewSheetSet: { sheets: [], blockers: [], plotStyles: {} }, siteName: "Pilot",
      isResultCurrent: async () => false,
      setStatusMessage: (message: string) => messages.push(message),
      setExportActionMessage: (message: string) => messages.push(message),
      setBusy: () => { started = true; },
    } as unknown as DashboardExportActionsConfig;
    const actions = createDashboardExportActions(config);
    await actions.handleExportDxf();
    await actions.handleExportReviewPdf();
    await actions.handleExportReport();
    await actions.handleExportQuantityReviewReport();
    expect(started).toBe(false);
    expect(messages).toHaveLength(7);
    expect(messages.every(message => message.toLowerCase().includes("out of date"))).toBe(true);
  });
  test("blocks stale calculations even for preliminary review exports", () => {
    expect(resolveDashboardExportBlockReason({ token: "authenticated", backendResultPresent: true, projectId: "project-1", systemStatuses: { grading: "stale" }, staleOutputs: ["quantities"], exportScope: "review" })).toBe("rerun affected systems before exporting: grading, quantities");
    expect(resolveDashboardExportBlockReason({ token: null, backendResultPresent: true, projectId: "project-1", systemStatuses: {}, staleOutputs: [], exportScope: "review" })).toContain("authenticate");
  });
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
