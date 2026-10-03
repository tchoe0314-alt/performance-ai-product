import { expect, test } from "@playwright/test";
import { buildDashboardGeometryCommandUpdates, parseDashboardGeometryCommand } from "../../app/utils/dashboardGeometryCommands";
import type { BuildingPlacement } from "../../app/types";

test("strict and conversational adapters retain separate command grammars", () => {
  expect(parseDashboardGeometryCommand(" Move Office 12.5 feet NORTH ", "strict")).toEqual({ kind: "move", targetText: "office", distance: 12.5, direction: "north" });
  expect(parseDashboardGeometryCommand("please move this 12.5 feet north thanks", "strict")).toBeNull();
  expect(parseDashboardGeometryCommand("please move this 12.5 feet north thanks", "conversational")).toEqual({ kind: "move", targetText: "", distance: 12.5, direction: "north" });
  for (const grammar of ["strict", "conversational"] as const) {
    expect(parseDashboardGeometryCommand("resize office to 30.5 ft × 40 feet", grammar)).toMatchObject({ kind: "resize", width: 30.5, depth: 40 });
    expect(parseDashboardGeometryCommand("show quantities", grammar)).toBeNull();
  }
});

test("all move aliases share patches without mutating source objects", () => {
  const target: BuildingPlacement = { id: "office", label: "Office", type: "building", x: 100, y: 200, w: 30, d: 40, meta: { retained: true } };
  const before = JSON.stringify(target);
  for (const [direction, x, y] of [["east", 110, 200], ["right", 110, 200], ["west", 90, 200], ["left", 90, 200], ["north", 100, 190], ["up", 100, 190], ["south", 100, 210], ["down", 100, 210]] as const) {
    expect(buildDashboardGeometryCommandUpdates(target, { kind: "move", targetText: "", distance: 10, direction })).toEqual({ x, y, placed: true, meta: { retained: true, canonical_edit_source: "chat" } });
  }
  expect(buildDashboardGeometryCommandUpdates(target, { kind: "resize", targetText: "", width: 50, depth: 60 })).toEqual({ w: 50, d: 60, meta: { retained: true, canonical_edit_source: "chat" } });
  expect(JSON.stringify(target)).toBe(before);
});
