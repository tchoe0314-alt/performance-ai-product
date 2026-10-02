import { expect, test } from "@playwright/test";
import { guardedTransactionSave } from "../../app/utils/guardedTransactionSave";
import { captureWorkspaceSaveGuard } from "../../app/utils/workspaceSaveGuard";
import type { BuildingPlacement } from "../../app/types";

test("switching workspace during draft creation prevents a follow-up save", async () => {
  let current = true;
  let saves = 0;
  const result = await guardedTransactionSave({
    isCurrent: () => current,
    ensureDraft: async () => { current = false; },
    save: async () => { saves++; return {}; },
    onFailure: () => { throw new Error("Unexpected failure notice"); },
  });
  expect(result).toBe("superseded");
  expect(saves).toBe(0);
});

test("late save completion cannot refresh a newer workspace", async () => {
  let current = true;
  let refreshes = 0;
  const result = await guardedTransactionSave({
    isCurrent: () => current, ensureDraft: async () => {},
    save: async () => { current = false; return {}; },
    refresh: () => { refreshes++; }, onFailure: () => {},
  });
  expect(result).toBe("superseded");
  expect(refreshes).toBe(0);
});

test("successful saves refresh once and failures are handled", async () => {
  let refreshes = 0;
  let failures = 0;
  const options = { isCurrent: () => true, ensureDraft: async () => {},
    save: async (): Promise<unknown> => ({}), refresh: () => { refreshes++; }, onFailure: () => { failures++; } };
  expect(await guardedTransactionSave(options)).toBe("saved");
  expect(refreshes).toBe(1);
  expect(await guardedTransactionSave({ ...options, save: async () => { throw new Error("offline"); } })).toBe("failed");
  expect(failures).toBe(1);
  expect(await guardedTransactionSave({ ...options, save: async () => null })).toBe("unavailable");
  expect(refreshes).toBe(1);
});

test("action-time guard rejects a new workspace even when its geometry is identical", () => {
  const generation = { current: 1 };
  const placements = { current: [] as BuildingPlacement[] };
  const current = captureWorkspaceSaveGuard(generation, placements);
  expect(current()).toBe(true);
  generation.current++;
  expect(current()).toBe(false);
});

test("delayed delete, restore, and boundary saves cannot follow a newer placement edit", async () => {
  const generation = { current: 1 };
  const placements = { current: [{ id: "one", label: "One", w: 50, d: 40 }] as BuildingPlacement[] };
  let saves = 0;
  const result = await guardedTransactionSave({
    isCurrent: captureWorkspaceSaveGuard(generation, placements),
    ensureDraft: async () => { placements.current = [{ ...placements.current[0], x: 100 }]; },
    save: async () => { saves++; return {}; },
    onFailure: () => { throw new Error("Unexpected stale failure notice"); },
  });
  expect(result).toBe("superseded");
  expect(saves).toBe(0);
});

test("detected-object request ordering rejects an older payload without a geometry change", async () => {
  const generation = { current: 1 };
  const placements = { current: [] as BuildingPlacement[] };
  let sequence = 1;
  let saves = 0;
  const older = captureWorkspaceSaveGuard(generation, placements, () => sequence === 1);
  sequence = 2;
  expect(await guardedTransactionSave({ isCurrent: older, ensureDraft: async () => {},
    save: async () => { saves++; return {}; }, onFailure: () => {} })).toBe("superseded");
  const latest = captureWorkspaceSaveGuard(generation, placements, () => sequence === 2);
  expect(await guardedTransactionSave({ isCurrent: latest, ensureDraft: async () => {},
    save: async () => { saves++; return {}; }, onFailure: () => {} })).toBe("saved");
  expect(saves).toBe(1);
});
