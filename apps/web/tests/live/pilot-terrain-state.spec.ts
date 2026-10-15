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
