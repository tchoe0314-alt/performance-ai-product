import { expect, test } from "@playwright/test";
import { ensureDashboardProjectDraft } from "../../app/utils/dashboardProjectDraft";
import type { ProjectRecord } from "../../app/types";

function deferred() {
  let resolve!: (value: ProjectRecord | null) => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<ProjectRecord | null>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

test("draft creation shares one request and preserves explicit names", async () => {
  const request = deferred();
  const pending = { current: null as Promise<ProjectRecord | null> | null };
  const calls: unknown[] = [];
  const options = { token: "fixture", demo: false, resolvedProjectId: "", projectId: "", pending,
    siteName: " Office ", fileName: " plan ", saveProject: (settings: unknown) => { calls.push(settings); return request.promise; } };
  const first = ensureDashboardProjectDraft(options);
  const second = ensureDashboardProjectDraft(options);
  expect(calls).toEqual([{ silent: true, projectIdOverride: null, nameOverride: "Office", fileNameOverride: "plan", autoNamedOverride: false, autoFileNamedOverride: false }]);
  request.resolve({ project_id: "saved", name: "Office" });
  expect(await first).toBe("saved");
  expect(await second).toBe("saved");
  expect(pending.current).toBeNull();
});

test("old request completion cannot clear a newer project's pending save", async () => {
  const old = deferred();
  const newer = deferred();
  const pending = { current: null as Promise<ProjectRecord | null> | null };
  const options = { token: "fixture", demo: false, resolvedProjectId: "", projectId: "", pending, siteName: "", fileName: "", saveProject: () => old.promise };
  const oldResult = ensureDashboardProjectDraft(options);
  pending.current = newer.promise;
  old.resolve({ project_id: "old", name: "Old" });
  expect(await oldResult).toBe("old");
  expect(pending.current).toBe(newer.promise);
  newer.resolve(null);
});

test("failed drafts release their own request; demo/auth and existing IDs do not save", async () => {
  const pending = { current: null as Promise<ProjectRecord | null> | null };
  let calls = 0;
  const options = { token: "fixture" as string | null, demo: false, resolvedProjectId: "", projectId: "", pending, siteName: "", fileName: "", saveProject: async () => { calls++; throw new Error("fixture failure"); } };
  expect(await ensureDashboardProjectDraft({ ...options, token: null })).toBeNull();
  expect(await ensureDashboardProjectDraft({ ...options, demo: true })).toBeNull();
  expect(await ensureDashboardProjectDraft({ ...options, resolvedProjectId: "resolved", projectId: "other" })).toBe("resolved");
  expect(await ensureDashboardProjectDraft({ ...options, currentProjectId: "current" })).toBe("current");
  expect(calls).toBe(0);
  await expect(ensureDashboardProjectDraft(options)).rejects.toThrow("fixture failure");
  expect(pending.current).toBeNull();
});
