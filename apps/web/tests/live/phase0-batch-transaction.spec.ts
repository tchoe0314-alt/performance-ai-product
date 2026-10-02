import { expect, test } from "@playwright/test";
import type { BuildingPlacement } from "../../app/types";
import { planCanonicalBatchTransaction } from "../../app/utils/canonicalBatchTransaction";
import { resolveDependencyProposal } from "../../app/utils/canonicalDependencyPolicies";

const fixture = (): BuildingPlacement[] => [
  { id: "site", label: "Site", type: "site", x: 0, y: 0, w: 900, d: 700, placed: true },
  { id: "building", label: "Building", type: "building", x: 200, y: 100, w: 100, d: 80, placed: true,
    meta: { canonical_relationships: { parking: { policy: "ask", object_ids: ["parking"] } } } },
  { id: "parking", label: "Parking", type: "parking", x: 180, y: 300, w: 200, d: 100, placed: true, stallCount: 40 },
];

test("batch planning defers every edit when one dependency asks", () => {
  const source = fixture();
  const before = JSON.stringify(source);
  const result = planCanonicalBatchTransaction(source, [
    { objectId: "building", updates: { w: 140 } },
    { objectId: "parking", updates: { stallCount: 60 } },
  ], "project", "Program revision", "batch");
  expect(result.status).toBe("proposed");
  expect(JSON.stringify(source)).toBe(before);
  expect(result.before.map(item => item.id)).toEqual(["building", "parking"]);
  const accepted = resolveDependencyProposal(result.proposal!, source, "project");
  expect(accepted.accepted).toBe(true);
  expect(accepted.placements.find(item => item.id === "parking")?.stallCount).toBe(60);
  expect(resolveDependencyProposal(result.proposal!, [{ ...source[0], w: 901 }, ...source.slice(1)], "project").accepted).toBe(false);
});

test("a protected later target blocks the whole batch without changing the source", () => {
  const source = fixture();
  source[2].locked = true;
  const before = JSON.stringify(source);
  const result = planCanonicalBatchTransaction(source, [
    { objectId: "building", updates: { w: 140 } },
    { objectId: "parking", updates: { stallCount: 60 } },
  ], "project", "Program revision", "batch");
  expect(result.status).toBe("blocked");
  expect(result.placements).toBe(source);
  expect(JSON.stringify(source)).toBe(before);
});

for (const policy of ["follow", "fixed"] as const) {
  test(`batch planning respects ${policy} parking relationships`, () => {
    const source = fixture();
    source[1].meta = { canonical_relationships: { parking: { policy, object_ids: ["parking"] } } };
    const result = planCanonicalBatchTransaction(source, [
      { objectId: "building", updates: { x: 220 } },
    ], "project", "Program revision", "batch");
    expect(result.status).toBe("applied");
    expect(result.placements.find(item => item.id === "building")?.x).toBe(220);
    expect(result.placements.find(item => item.id === "parking")?.x).toBe(policy === "follow" ? 200 : 180);
    expect(source[1].x).toBe(200);
    expect(source[2].x).toBe(180);
  });
}

test("invalid geometry blocks every edit in a batch", () => {
  const source = fixture();
  const before = JSON.stringify(source);
  const result = planCanonicalBatchTransaction(source, [
    { objectId: "parking", updates: { stallCount: 60 } },
    { objectId: "building", updates: { w: Number.NaN } },
  ], "project", "Program revision", "batch");
  expect(result.status).toBe("blocked");
  expect(JSON.stringify(source)).toBe(before);
});

test("parking reflow avoids the resized parent building and translates its polygon", () => {
  const source = fixture();
  source[1].meta = { canonical_relationships: { parking: { policy: "follow", object_ids: ["parking"] } } };
  source[2] = { ...source[2], x: 200, y: 200, geometry: [[200, 200], [400, 200], [400, 300], [200, 300]] };
  const result = planCanonicalBatchTransaction(source, [
    { objectId: "building", updates: { d: 300 } },
  ], "project", "Program revision", "batch");
  expect(result.status).toBe("applied");
  const building = result.placements.find(item => item.id === "building")!;
  const parking = result.placements.find(item => item.id === "parking")!;
  const overlaps = (parking.x! < building.x! + building.w && parking.x! + parking.w > building.x! &&
    parking.y! < building.y! + building.d && parking.y! + parking.d > building.y!);
  expect(overlaps).toBe(false);
  expect(parking.geometry?.[0]).toEqual([parking.x, parking.y]);
  expect(parking.stallCount).toBe(40);
  expect(source[2].geometry?.[0]).toEqual([200, 200]);
});
