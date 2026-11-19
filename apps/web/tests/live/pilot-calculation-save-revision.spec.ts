import { expect, test } from "@playwright/test";

import type { ProjectRecord } from "../../app/types";
import { canRebaseCalculationRevision } from "../../app/utils/projectSaveRebase";

function fixture(): ProjectRecord {
  return {
    project_id: "p",
    name: "Design",
    description: "",
    tags: [],
    metadata: { design_save_generation_v1: 237 },
    project_input: {
      input_mode: "assisted",
      manual_fields: { units: "ft", site_objects: [] },
      meta: { site_inputs: { source: "synthetic" } },
    },
  } as ProjectRecord;
}

test("calculation-only revision 237 to 240 can retry without replacing a concurrent design", () => {
  const before = fixture();
  const after = structuredClone(before);
  after.metadata = { design_save_generation_v1: 240 };
  after.revision_token = "revision-240";
  Object.assign(after.project_input!, {
    request_payload: { calculation_only: true },
    persist_trace_metadata: true,
  });
  Object.assign(after.project_input!.meta!, {
    requested_system: "full",
    calculation_omit_fields_v1: [],
    generate_notes: [],
  });
  expect(canRebaseCalculationRevision(before, after)).toBe(true);

  const concurrentEdit = structuredClone(after);
  concurrentEdit.project_input!.manual_fields!.units = "m";
  expect(canRebaseCalculationRevision(before, concurrentEdit)).toBe(false);

  const concurrentGeometry = structuredClone(after);
  concurrentGeometry.project_input!.manual_fields!.site_objects = [
    { id: "road-1", type: "road", x: 10, y: 10, w: 100, d: 24, placed: true },
  ];
  expect(canRebaseCalculationRevision(before, concurrentGeometry)).toBe(false);
});
