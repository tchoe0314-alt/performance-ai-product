import { expect, test } from "@playwright/test";
import { canonicalDeletionBlocker } from "../../app/utils/canonicalEditCommands";

test("canonical deletion protects the whole group before any mutation", () => {
  const flexible: BuildingPlacement = { id: "a", label: "Draft", type: "building", x: 0, y: 0, w: 20, d: 20 };
  expect(canonicalDeletionBlocker([flexible])).toBeNull();
  const protectedObjects: BuildingPlacement[] = [
    { ...flexible, locked: true },
    { ...flexible, meta: { canonical_control_state: "fixed" } },
    { ...flexible, source: "detected_from_gis" },
    { ...flexible, meta: { canonical_control_state: "reference" } },
    { ...flexible, capabilities: { deletable: false } },
    { ...flexible, type: "site" },
  ];
  for (const protectedObject of protectedObjects) {
    expect(canonicalDeletionBlocker([flexible, protectedObject])).not.toBeNull();
  }
  expect(canonicalDeletionBlocker([{ ...flexible, locked: false, meta: { canonical_control_state: "flexible" } }])).toBeNull();
});
import type { BuildingPlacement } from "../../app/types";
import { generateLayoutAlternatives, parseLayoutGoals, searchLayoutAlternatives, rerankLayoutSearch } from "../../app/utils/layoutAlternatives";
import { resolveDependencyProposal, type CanonicalDependencyProposal } from "../../app/utils/canonicalDependencyPolicies";

const fixture = (): BuildingPlacement[] => [
  { id: "site", label: "Site", type: "site", x: 0, y: 0, w: 900, d: 700, placed: true },
  { id: "building", label: "Building", type: "building", x: 300, y: 120, w: 160, d: 90, placed: true },
  { id: "parking", label: "Parking", type: "parking", x: 240, y: 360, w: 330, d: 150, stallCount: 60, placed: true },
  { id: "entry", label: "Entry", type: "entrance", x: 60, y: 650, w: 20, d: 20, placed: true },
];

test("dependency approval applies all objects atomically and rejects stale or cross-project previews", () => {
  const source = fixture();
  const before = JSON.stringify(source);
  const proposal: CanonicalDependencyProposal = {
    id: "proposal", transactionId: "transaction", buildingId: "building", buildingLabel: "Building",
    before: [source[1], source[2]], after: [{ ...source[1], x: 325 }, { ...source[2], x: 265 }],
    createdAt: "2026-10-02T00:00:00Z", reflowReports: [], projectId: "project-a", sourceSnapshot: before,
  };
  const accepted = resolveDependencyProposal(JSON.parse(JSON.stringify(proposal)), source, "project-a");
  expect(accepted.accepted).toBe(true);
  expect(accepted.placements[1].x).toBe(325);
  expect(accepted.placements[2].x).toBe(265);
  expect(JSON.stringify(source)).toBe(before);
  expect(resolveDependencyProposal(proposal, source, "project-b").accepted).toBe(false);
  const changed = source.map(item => item.id === "entry" ? { ...item, x: 70 } : item);
  const rejected = resolveDependencyProposal(proposal, changed, "project-a");
  expect(rejected.accepted).toBe(false);
  expect(rejected.placements).toBe(changed);
});

test("generated successful alternatives never contain modeled hard conflicts", () => {
  const source = fixture();
  source[1] = { ...source[1], locked: true };
  source.push({ ...source[1], id: "overlapping-fixed-building" });
  const before = JSON.stringify(source);
  expect(generateLayoutAlternatives(source, 5)).toEqual([]);
  expect(JSON.stringify(source)).toBe(before);
});

test("requested ten valid alternatives are not silently capped at five", () => {
  const options = generateLayoutAlternatives(fixture(), 10);
  expect(options).toHaveLength(10);
  expect(options.every(option => option.metrics.conflicts === 0 && option.metrics.shortfall === 0)).toBe(true);
});

test("priority changes can select candidates outside the original top five", () => {
  const source = fixture();
  const initial = searchLayoutAlternatives(source, 5, parseLayoutGoals("maximize parking"));
  const goals = parseLayoutGoals("building near entrance").goals!;
  const fresh = generateLayoutAlternatives(source, 5, { goals });
  expect(initial.candidatePool.length).toBeGreaterThan(initial.alternatives.length);
  const reranked = rerankLayoutSearch(JSON.parse(JSON.stringify(initial)), goals);
  expect(reranked.alternatives.map(option => option.id)).toEqual(fresh.map(option => option.id));
});

test("missing boundaries and corrupt geometry produce explicit search failures", () => {
  const source = fixture();
  expect(searchLayoutAlternatives(source.slice(1), 5).searchReport.rejectionReasons).toContain("missing site boundary");
  source[1].w = Number.NaN;
  expect(searchLayoutAlternatives(source, 5).searchReport.rejectionReasons).toContain("invalid dimensions: building");
  source[1].w = 160;
  source[1].geometryType = "polygon";
  source[1].geometry = [[0, 0], [10, 0], [Number.NaN, 20]];
  expect(searchLayoutAlternatives(source, 5).alternatives).toEqual([]);
  expect(searchLayoutAlternatives(source, 5).searchReport.rejectionReasons).toContain("invalid geometry: building");
});

test("required parking shortages are not returned as successful options", () => {
  const source = fixture();
  source[2].stallCount = 10000;
  const search = searchLayoutAlternatives(source, 5);
  expect(search.alternatives).toEqual([]);
  expect(search.searchReport.rejectionReasons.some(reason => /required parking shortfall \(\d+ stalls\)/.test(reason))).toBe(true);
  expect(search.searchReport.explored).toBe(32);
});
