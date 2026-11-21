import { expect, test } from "@playwright/test";
import { buildImportedSurveyProvenance, buildPersistedSurveyProvenanceRows } from "../../app/utils/dashboardExistingConditionsUpload";

test("survey import preserves known units and datum without promoting missing control", () => {
  const provenance = buildImportedSurveyProvenance({
    success: true,
    canonical_existing_conditions: {
      coordinate_system: { epsg: "EPSG:2276", units: "ft", source: "survey note" },
      survey_control_package: { vertical_datum: "NAVD88", production_usable: false },
      grading_input_eligibility: {
        review_context_usable: true,
        accepted_grading_input: false,
        coordinate_units: "ft",
        horizontal_datum: "NAD83",
        vertical_datum: "NAVD88",
        control_verified: false,
        blockers: [{ field: "survey_control_verified" }],
      },
    },
  });

  expect(provenance.survey_coordinate_system).toMatchObject({ epsg: "EPSG:2276", units: "ft" });
  expect(provenance.survey_grading_eligibility).toMatchObject({
    review_context_usable: true,
    accepted_grading_input: false,
    coordinate_units: "ft",
    horizontal_datum: "NAD83",
    vertical_datum: "NAVD88",
    control_verified: false,
  });
  expect(buildPersistedSurveyProvenanceRows(provenance)).toEqual(expect.arrayContaining([
    "Coordinate system: EPSG:2276; units: ft.",
    "Datum: horizontal NAD83; vertical NAVD88.",
    "Grading eligibility: review context only; accepted survey/control is still required.",
    "Control blockers: survey_control_verified",
  ]));
});

test("missing datum remains explicit and cannot become accepted grading input", () => {
  const provenance = buildImportedSurveyProvenance({
    success: true,
    canonical_existing_conditions: {
      grading_input_eligibility: { review_context_usable: true, accepted_grading_input: false },
    },
  });

  expect(provenance.survey_grading_eligibility).toMatchObject({
    review_context_usable: true,
    accepted_grading_input: false,
    coordinate_units: null,
    horizontal_datum: null,
    vertical_datum: null,
    control_verified: false,
  });
  expect(buildPersistedSurveyProvenanceRows(provenance)).toContain("Datum: horizontal not recorded; vertical not recorded.");
});

test("explicitly verified survey eligibility remains accepted", () => {
  const provenance = buildImportedSurveyProvenance({
    success: true,
    canonical_existing_conditions: {
      grading_input_eligibility: {
        review_context_usable: true,
        accepted_grading_input: true,
        coordinate_units: "ft",
        horizontal_datum: "NAD83",
        vertical_datum: "NAVD88",
        control_verified: true,
      },
    },
  });
  expect(provenance.survey_grading_eligibility.accepted_grading_input).toBe(true);
  expect(provenance.survey_grading_eligibility.control_verified).toBe(true);
});
