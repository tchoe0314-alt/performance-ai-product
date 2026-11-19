import { expect, test } from "@playwright/test";
import { preserveExplicitBriefProgram } from "../../app/utils/briefProgramPreservation";
import { withCanonicalCanvasSnapshot } from "../../app/utils/canonicalCanvasProject";

test("canvas control rebuilding preserves terrain that has no dimension control", () => {
  const terrain = "Surveyed 2% slope west to east";
  const saved = withCanonicalCanvasSnapshot({ manual_fields: { units: "ft", terrain } });
  const controls = { units: "ft" };
  expect(preserveExplicitBriefProgram(controls, saved).terrain).toEqual(terrain);
  expect(controls).toEqual({ units: "ft" });
  expect(saved.manual_fields?.terrain).toEqual(terrain);
});

test("explicit terrain edits and clears outrank stored terrain and removed sources stay removed", () => {
  const saved = withCanonicalCanvasSnapshot({ manual_fields: { terrain: "Old source" } });
  expect(preserveExplicitBriefProgram({ terrain: "New source" }, saved).terrain).toBe("New source");
  expect(preserveExplicitBriefProgram({ terrain: "" }, saved).terrain).toBe("");
  expect(preserveExplicitBriefProgram({}, withCanonicalCanvasSnapshot({ manual_fields: {} }))).not.toHaveProperty("terrain");
});

test("generated drainage concepts do not discard an explicit reviewed pipe run", () => {
  const explicitPipe = {
    id: "P-1",
    canonical_id: "P-1",
    points: [[0, 0], [100, 10]] as Array<[number, number]>,
    path: [[0, 0], [100, 10]] as Array<[number, number]>,
    utility_type: "storm",
    diameter_in: 18,
    slope_ft_ft: 0.01,
    source: "manual_drawn",
    review_required: true,
    construction_release_allowed: false as const,
  };
  const generated = {
    id: "generate-drainage-path-1",
    points: [[20, 20], [80, 20]] as Array<[number, number]>,
    utility_type: "storm",
    source: "generated",
    review_required: true,
    construction_release_allowed: false as const,
  };
  const saved = withCanonicalCanvasSnapshot({ manual_fields: { pipe_network: [explicitPipe] } });

  expect(preserveExplicitBriefProgram({ pipe_network: [generated] }, saved).pipe_network).toEqual([explicitPipe, generated]);
  expect(preserveExplicitBriefProgram({ pipe_network: [{ ...explicitPipe, diameter_in: 24 }] }, saved).pipe_network).toEqual([
    { ...explicitPipe, diameter_in: 24 },
  ]);
});
