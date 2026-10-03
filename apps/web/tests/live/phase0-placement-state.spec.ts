import { expect, test } from "@playwright/test";
import type { BuildingPlacement } from "../../app/types";
import { commitPlacementState } from "../../app/utils/placementStateCommit";
import { runDashboardCreateCustomGeometry, type DashboardCustomGeometryActions } from "../../app/utils/dashboardCustomGeometryActions";

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

test("custom geometry publishes through the shared writer without assigning its read adapter", () => {
  const live = { current: [] as BuildingPlacement[] };
  const readAdapter = {
    get current() { return live.current; },
    set current(_value: BuildingPlacement[]) { throw new Error("Direct placement write bypassed shared owner"); },
  };
  const noOp = () => {};
  let saves = 0;
  const actions: DashboardCustomGeometryActions = {
    clearGeneratedPreview: noOp, ensureSiteBoundary: () => true, markSystemsStale: noOp,
    persistDraftRefresh: () => { saves++; expect(live.current.length).toBe(saves); },
    resolveLotBounds: () => ({ x: 0, y: 0, w: 500, h: 500 }),
    setActivePlacementId: noOp,
    setBuildingPlacements: update => commitPlacementState(live, update, noOp),
    setPlacementModeEnabled: noOp, setPreviewInteraction: noOp, setPreviewMode: noOp,
    setSelectedObjectIds: noOp, setStatusMessage: noOp,
  };
  for (let index = 0; index < 2; index++) {
    expect(runDashboardCreateCustomGeometry({
      payload: { mode: "rect", points: [[10 + index, 10], [50 + index, 50]] },
      buildingPlacementsRef: readAdapter, siteScaleLocked: true, units: "ft", actions,
    })).toBe(true);
  }
  expect(live.current.map(item => item.label)).toEqual(["Custom Rectangle 1", "Custom Rectangle 2"]);
  expect(saves).toBe(2);
});
