import { expect, test } from "@playwright/test";
import { guardedTransactionSave } from "../../app/utils/guardedTransactionSave";

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
