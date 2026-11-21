const fs = require("node:fs");
const path = require("node:path");

const source = path.resolve(__dirname, "../docs/acceptance/core-pass-2026-11-21.json");
const card = JSON.parse(fs.readFileSync(source, "utf8"));
const fail = (message) => { throw new Error(message); };

if (card.kind !== "acceptance_preparation_not_a_run") fail("Run card must not claim execution.");
if (card.suite_sources.major_case_count !== 26 || card.suite_sources.case_ids.length !== 26) fail("Acceptance v2 must retain 26 major cases.");
if (new Set(card.suite_sources.case_ids).size !== 26) fail("Acceptance case IDs must be unique.");
if (card.suite_sources.historical_family_count !== 131) fail("Historical workflow-family cross-check must remain 131.");

const building = card.fixture.building;
if (building.initial_width_ft * building.depth_ft !== building.initial_area_sq_ft) fail("Initial building area oracle mismatch.");
if (building.revised_width_ft * building.depth_ft !== building.revised_area_sq_ft) fail("Revised building area oracle mismatch.");
if (building.revised_area_sq_ft - building.initial_area_sq_ft !== building.expected_delta_sq_ft) fail("Building delta oracle mismatch.");

const pipe = card.fixture.storm_pipe;
const expectedEnd = pipe.invert_start_ft - pipe.length_ft * pipe.slope_ft_ft;
if (Math.abs(expectedEnd - pipe.invert_end_ft) > 1e-9) fail("Storm invert/slope oracle mismatch.");
if (pipe.from_node === pipe.to_node) fail("Storm endpoint identities must be distinct.");
if (!pipe.review_required || pipe.construction_release_allowed) fail("Storm fixture must remain review-only.");
if (card.acceptance.terminal_job_budget_ms !== 120000) fail("Existing performance gate changed.");
if (card.acceptance.native_civil_3d_claim_allowed !== false) fail("Native Civil 3D cannot be pre-accepted.");

console.log("core acceptance fixture: valid");
