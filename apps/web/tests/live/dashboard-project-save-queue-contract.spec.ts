import { expect, test } from "@playwright/test";
import { enqueueDashboardProjectSave, type DashboardProjectSaveQueue } from "../../app/utils/dashboardProjectSaveQueue";

function gate() {
  let release!: () => void;
  const promise = new Promise<void>(resolve => { release = resolve; });
  return { promise, release };
}

test("saves cannot finish out of order and queued saves sample current input", async () => {
  const owner = { current: null as DashboardProjectSaveQueue | null };
  const wait = gate();
  const calls: number[] = [];
  let input = 100;
  const first = enqueueDashboardProjectSave(owner, 0, async () => { calls.push(input); await wait.promise; return 100; });
  await Promise.resolve();
  const next = enqueueDashboardProjectSave(owner, 0, async () => { calls.push(input); return input; });
  input = 125;
  await Promise.resolve();
  expect(calls).toEqual([100]);
  wait.release();
  expect(await first).toBe(100);
  expect(await next).toBe(125);
  expect(calls).toEqual([100, 125]);
});

test("a failed save does not poison following saves", async () => {
  const owner = { current: null as DashboardProjectSaveQueue | null };
  const failed = enqueueDashboardProjectSave(owner, 0, async () => { throw new Error("fixture failure"); });
  const next = enqueueDashboardProjectSave(owner, 0, async () => "recovered");
  await expect(failed).rejects.toThrow("fixture failure");
  expect(await next).toBe("recovered");
});

test("new workspaces do not wait for old saves and old queued work can be rejected", async () => {
  const owner = { current: null as DashboardProjectSaveQueue | null };
  const wait = gate();
  let generation = 0;
  const first = enqueueDashboardProjectSave(owner, 0, async () => { await wait.promise; return "old"; });
  const oldQueued = enqueueDashboardProjectSave(owner, 0, async () => generation === 0 ? "old queued" : null);
  generation = 1;
  expect(await enqueueDashboardProjectSave(owner, 1, async () => "new")).toBe("new");
  const newOwner = owner.current;
  wait.release();
  expect(await first).toBe("old");
  expect(await oldQueued).toBeNull();
  expect(owner.current).toBe(newOwner);
});
