import { expect, test } from "@playwright/test";
import { createHash } from "node:crypto";
import { createDraftHistory } from "../../app/utils/draftHistory";
import { liveInputFingerprint, isLiveCalculationCurrent } from "../../app/utils/liveCalculationFreshness";
import type { ProjectInput, PlanResponse } from "../../app/types";
import type { DraftUndoAction } from "../../app/utils/dashboardTypes";

const action = (id: string) => ({ action: "add", object: { id, type: "office_building", x: 100, y: 50, w: 40, d: 30 } }) as DraftUndoAction;
const input = (): ProjectInput => ({ manual_fields: { units: "ft", site_objects: [{ id: "a", type: "office_building", x: 1e-7, y: -0, label: "Café 🚧" }] }, meta: { site_inputs: { note: "測量" } } } as ProjectInput);

test("multiple undo and redo steps preserve their order", () => {
  const history = createDraftHistory();
  for (const id of ["one", "two", "three"]) history.record(action(id));
  const undo = () => { const current = history.last!; history.prepareUndo(current); history.consumeUndo(); return current; };
  expect(undo()).toEqual(action("three"));
  expect(undo()).toEqual(action("two"));
  expect(history.last).toEqual(action("one"));
  history.record(history.next!);
  expect(history.last).toEqual(action("two"));
  expect(history.next).toEqual(action("three"));
  history.record(history.next!);
  expect(history.last).toEqual(action("three"));
  expect(history.next).toBeNull();
});

test("new edits invalidate redo; snapshots detach; limits and workspace reset apply", () => {
  const history = createDraftHistory(2);
  const original = action("one");
  history.record(original);
  if (original.action === "add") original.object.x = 999;
  expect(history.last).toEqual(action("one"));
  history.record(action("two"));
  history.record(action("three"));
  history.prepareUndo(history.last!); history.consumeUndo();
  history.record(action("new branch"));
  expect(history.next).toBeNull();
  history.prepareUndo(history.last!); history.consumeUndo();
  history.prepareUndo(history.last!); history.consumeUndo();
  expect(history.last).toBeNull();
  history.reset();
  expect(history.next).toBeNull();
});

test("portable input keys exactly match Python for decimals, negative zero and Unicode", () => {
  expect(createHash("sha256").update(liveInputFingerprint(input())).digest("hex"))
    .toBe("052aebb38581c85b637a7274049c880f2593f2957fdeb25f9e431004ed028281");
});

test("unsaved edits block a result; undo to identical inputs matches; legacy remains unverified", async () => {
  const current = input();
  const sourceKey = createHash("sha256").update(liveInputFingerprint(current)).digest("hex");
  const result: PlanResponse = { metadata: { canvas_result_binding_v1: { version: 1, scope: "canvas_manual_fields_and_site_inputs", input_signature: "legacy", live_input_key_v1: sourceKey } } };
  expect(await isLiveCalculationCurrent(result, () => current)).toBe(true);
  current.manual_fields!.site_objects![0].x = 200;
  expect(await isLiveCalculationCurrent(result, () => current)).toBe(false);
  current.manual_fields!.site_objects![0].x = 1e-7;
  expect(await isLiveCalculationCurrent(result, () => current)).toBe(true);
  expect(await isLiveCalculationCurrent({}, () => current)).toBe(true);
});
