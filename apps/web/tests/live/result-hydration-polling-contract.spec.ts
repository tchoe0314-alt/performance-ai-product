import { expect, test } from "@playwright/test";

import { ACTIVE_JOB_POLL_INTERVAL_MS, runActiveJobPoll, shouldLoadActiveJobDetail, shouldPollActiveJob } from "../../app/hooks/useJobPolling";
import { shouldDiscardSavedResultResponse, shouldRetrySavedResultHydration } from "../../app/utils/savedResultHydration";

test("saved result hydration retries only for a settled project without a result", () => {
  const base = { token: "synthetic", workspaceRestoreState: "restored", projectId: "project-a", hasBackendResult: false };
  expect(shouldRetrySavedResultHydration(base)).toBe(true);
  expect(shouldRetrySavedResultHydration({ ...base, workspaceRestoreState: "loading" })).toBe(false);
  expect(shouldRetrySavedResultHydration({ ...base, projectId: "" })).toBe(false);
  expect(shouldRetrySavedResultHydration({ ...base, hasBackendResult: true })).toBe(false);
  expect(shouldRetrySavedResultHydration({ ...base, token: null })).toBe(false);
  // A project switch changes the effect dependency and cancels the old timer;
  // the new project remains independently eligible for its own hydration.
  expect(shouldRetrySavedResultHydration({ ...base, projectId: "project-b" })).toBe(true);
});

test("saved result hydration accepts same-project restore advances and rejects switches", () => {
  const base = {
    requestId: 4,
    latestRequestId: 4,
    workspaceGeneration: 7,
    latestWorkspaceGeneration: 8,
    requestedProjectId: "project-a",
    activeProjectId: "project-a",
  };
  expect(shouldDiscardSavedResultResponse(base)).toBe(false);
  expect(shouldDiscardSavedResultResponse({ ...base, activeProjectId: "project-b" })).toBe(true);
  expect(shouldDiscardSavedResultResponse({ ...base, latestRequestId: 5 })).toBe(true);
  expect(shouldDiscardSavedResultResponse({ ...base, latestWorkspaceGeneration: 7, activeProjectId: "project-b" })).toBe(false);
});

test("job polling is bounded to visible active jobs", () => {
  expect(ACTIVE_JOB_POLL_INTERVAL_MS).toBe(2_000);
  for (const status of [undefined, "queued", "running", "cancelling"]) {
    expect(shouldPollActiveJob(status, false)).toBe(true);
  }
  for (const status of ["awaiting_approval", "completed", "failed", "cancelled"]) {
    expect(shouldPollActiveJob(status, false)).toBe(false);
  }
  expect(shouldPollActiveJob("running", true)).toBe(false);
  for (const status of ["awaiting_approval", "completed", "failed", "cancelled"]) {
    expect(shouldLoadActiveJobDetail(status)).toBe(true);
  }
  for (const status of [undefined, "queued", "running", "cancelling"]) {
    expect(shouldLoadActiveJobDetail(status)).toBe(false);
  }
});

test("job polling never overlaps and releases its guard after settlement", async () => {
  const inFlight = { current: false };
  let release!: () => void;
  const pending = new Promise<void>(resolve => { release = resolve; });
  let refreshes = 0;
  const first = runActiveJobPoll({
    status: "running",
    documentHidden: false,
    inFlight,
    refresh: () => { refreshes += 1; return pending; },
  });
  expect(inFlight.current).toBe(true);
  expect(await runActiveJobPoll({
    status: "running",
    documentHidden: false,
    inFlight,
    refresh: () => { refreshes += 1; },
  })).toBe(false);
  expect(refreshes).toBe(1);
  release();
  expect(await first).toBe(true);
  expect(inFlight.current).toBe(false);
});
