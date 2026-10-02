import { expect, test } from "@playwright/test";
import type { BuildingPlacement } from "../../app/types";
import { commitPlacementState } from "../../app/utils/placementStateCommit";

test("rapid writers read the latest placement authority before any render", () => {
  const live = { current: [] as BuildingPlacement[] };
  const snapshots: BuildingPlacement[][] = [];
  for (let index = 0; index < 50; index++) {
    commitPlacementState(live, previous => [...previous, { id: String(index), label: "Building", type: "building", w: 120, d: 80, x: index, y: 0 }], next => {
      expect(live.current).toBe(next);
      snapshots.push(next);
    });
  }
  expect(live.current).toHaveLength(50);
  expect(new Set(live.current.map(item => item.id)).size).toBe(50);
  expect(snapshots[0]).toHaveLength(1);
  commitPlacementState(live, previous => previous.filter(item => item.id !== "0"), () => {});
  expect(live.current).toHaveLength(49);
  commitPlacementState(live, [], () => {});
  expect(live.current).toEqual([]);
});
