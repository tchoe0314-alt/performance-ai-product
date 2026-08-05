from __future__ import annotations

import unittest
from copy import deepcopy

import planner


def _supported_minimal_payload() -> dict:
    return {
        "project_name": "Supported minimal engineering site",
        "units": "ft",
        "mode": "site_plan",
        "project_type": "commercial_pad",
        "site_type": "commercial_pad",
        "terrain": "2% slope north to south",
        "lot": {"x": 0, "y": 0, "w": 240, "h": 180},
        "street_edge": "bottom",
        "setback": 12,
        "site_plan": {"building_width": 60, "building_depth": 40, "parking_count": 24},
        "ponds": [{"name": "BASIN-1", "x": 180, "y": 20, "w": 40, "d": 30}],
        "drainage": {"verified_overflow_capacity_cfs": 5, "tailwater_elev_ft": 94},
        "standards": {"jurisdiction": "Test County", "design_manual": "local drainage criteria", "version": "2026"},
        "survey_control": {
            "datum": "NAVD88",
            "benchmark": "BM-1",
            "points": [{"id": "CP-1", "x": 0, "y": 0, "z": 100}, {"id": "CP-2", "x": 240, "y": 180, "z": 96}],
        },
        "coordinate_system": {"crs": "EPSG:2276", "datum": "NAD83 / Texas North Central"},
    }


def _review(plan: dict) -> dict:
    return plan.get("meta", {}).get("engineering_generation_review", {})


def _system(plan: dict, name: str) -> dict:
    return _review(plan).get("systems", {}).get(name, {})


def _blocker_inputs(plan: dict, name: str) -> set[str]:
    return {item.get("input") for item in _system(plan, name).get("blockers", [])}


class EngineeringGenerationWorkflowTests(unittest.TestCase):
    def test_runtime_resume_advances_past_user_approved_partial_stage(self) -> None:
        payload = _supported_minimal_payload()
        checkpoint = planner.build_plan(deepcopy(payload))
        checkpoint_meta = checkpoint.setdefault("meta", {})
        statuses = checkpoint_meta.setdefault("stage_completeness", {}).setdefault("statuses", {})
        statuses.update(
            {
                "layout": "complete",
                "grading": "complete",
                "drainage": "complete",
                "storm_pipes": "partial",
            }
        )
        checkpoint_meta.pop("storm_pipes", None)

        resumed_payload = deepcopy(payload)
        resumed_payload["meta"] = {
            "orchestrator_meta": {
                "runtime_resume": {
                    "final_plan": checkpoint,
                    "stage_statuses": statuses,
                },
                "runtime_approved_stages": ["storm_pipes"],
                "runtime_phase_batch_limit": 1,
            },
            "runtime_phase_batch_limit": 1,
        }

        resumed = planner.build_plan(resumed_payload)
        runtime_checkpoint = resumed["meta"]["runtime_phase_checkpoint"]
        self.assertEqual(runtime_checkpoint["stage_name"], "sanitary")
        self.assertTrue(runtime_checkpoint["yielded"])

    def test_runtime_resume_advances_past_accepted_stage_without_geometry(self) -> None:
        payload = _supported_minimal_payload()
        checkpoint = planner.build_plan(deepcopy(payload))
        checkpoint_meta = checkpoint.setdefault("meta", {})
        statuses = checkpoint_meta.setdefault("stage_completeness", {}).setdefault("statuses", {})
        statuses.update(
            {
                "layout": "complete",
                "grading": "complete",
                "drainage": "complete",
                "storm_pipes": "assumed",
            }
        )
        checkpoint_meta.pop("storm_pipes", None)

        resumed_payload = deepcopy(payload)
        resumed_payload["meta"] = {
            "orchestrator_meta": {
                "runtime_resume": {
                    "final_plan": checkpoint,
                    "stage_statuses": statuses,
                },
                "runtime_phase_batch_limit": 1,
            },
            "runtime_phase_batch_limit": 1,
        }

        resumed = planner.build_plan(resumed_payload)
        runtime_checkpoint = resumed["meta"]["runtime_phase_checkpoint"]
        self.assertEqual(runtime_checkpoint["stage_name"], "sanitary")
        self.assertTrue(runtime_checkpoint["yielded"])

    def test_runtime_checkpoints_preserve_drawn_drainage_for_storm_generation(self) -> None:
        payload = _supported_minimal_payload()
        payload["disciplines"] = ["grading", "drainage", "storm", "sanitary", "water", "utility"]
        payload["drainage_structures"] = [
            {
                "id": "INLET-1",
                "name": "Parking Inlet",
                "x": 80,
                "y": 90,
                "structure_type": "inlet",
                "source": "manual_drawn",
                "review_required": True,
                "construction_release_allowed": False,
            }
        ]
        payload["pipe_network"] = [
            {
                "id": "STORM-1",
                "label": "Storm Trunk",
                "points": [[80, 90], [180, 40]],
                "path": [[80, 90], [180, 40]],
                "utility_type": "storm",
                "source": "manual_drawn",
                "review_required": True,
                "construction_release_allowed": False,
            }
        ]
        payload["utility_network"] = [
            {
                "id": "WATER-1",
                "label": "Public Water Main",
                "points": [[0, 80], [140, 80]],
                "utility_type": "water",
                "source": "manual_drawn",
                "review_required": True,
                "construction_release_allowed": False,
            },
            {
                "id": "SAN-1",
                "label": "Public Sanitary Main",
                "points": [[0, 60], [140, 60]],
                "utility_type": "sanitary",
                "source": "manual_drawn",
                "review_required": True,
                "construction_release_allowed": False,
            },
        ]

        checkpoint = None
        approved_stages: list[str] = []
        stage_messages: dict[str, str] = {}
        for _ in range(4):
            resumed_payload = deepcopy(payload)
            orchestrator_meta = {
                "runtime_phase_batch_limit": 1,
                "runtime_approved_stages": list(approved_stages),
            }
            if checkpoint is not None:
                checkpoint_meta = checkpoint.get("meta", {})
                orchestrator_meta["runtime_resume"] = {
                    "final_plan": checkpoint,
                    "stage_statuses": checkpoint_meta.get("stage_completeness", {}).get("statuses", {}),
                }
            resumed_payload["meta"] = {
                "orchestrator_meta": orchestrator_meta,
                "runtime_phase_batch_limit": 1,
                "runtime_approved_stages": list(approved_stages),
            }
            checkpoint = planner.build_plan(resumed_payload)
            checkpoint_meta = checkpoint["meta"]
            runtime_checkpoint = checkpoint_meta["runtime_phase_checkpoint"]
            stage_name = runtime_checkpoint["stage_name"]
            stage_messages[stage_name] = runtime_checkpoint["message"]
            approved_stages.append(stage_name)

        self.assertEqual(stage_messages["drainage"], "Drainage stage accepted user-supplied geometry.")
        self.assertEqual(stage_messages["storm_pipes"], "Storm pipe stage completed.")
        self.assertGreaterEqual(len(checkpoint["meta"]["drainage"]["structures"]), 1)
        self.assertGreaterEqual(len(checkpoint["meta"]["drainage"]["pipes"]), 1)
        self.assertGreaterEqual(len(checkpoint["meta"]["storm_pipes"]["segments"]), 1)

    def test_supported_minimal_site_outputs_are_canonical_and_review_required(self) -> None:
        plan = planner.build_plan(_supported_minimal_payload())
        review = _review(plan)

        self.assertEqual(review["version"], "engineering_generation_review_v1")
        self.assertEqual(review["status"], "review_required")
        self.assertFalse(review["blocked_systems"])
        for system_name, row in review["systems"].items():
            self.assertEqual(row["status"], "review_required", system_name)
            self.assertTrue(row["canonical_output_present"], system_name)
            self.assertTrue(row["engineer_review_required"], system_name)
            self.assertFalse(row["production_usable"], system_name)

        for key in ("grading", "drainage", "storm_pipes", "sanitary", "utilities", "roadway", "quantities", "qa"):
            self.assertTrue(plan["meta"][key]["engineer_review_required"], key)
            self.assertFalse(plan["meta"][key]["production_usable"], key)

    def test_drawn_semantic_civil_objects_reach_native_engine_stages(self) -> None:
        payload = _supported_minimal_payload()
        payload["disciplines"] = ["grading", "drainage", "storm", "sanitary", "water", "utility"]
        payload["buildings"] = [{"id": "BLDG-1", "name": "Office", "x": 40, "y": 50, "w": 80, "d": 60}]
        payload["ponds"] = [{
            "id": "BASIN-1",
            "name": "Detention Basin",
            "boundary_points": [[170, 20], [220, 20], [215, 55], [175, 60]],
            "geometry": [[170, 20], [220, 20], [215, 55], [175, 60]],
            "centroid_xy": [195, 39],
            "area_sf": 1700,
            "source": "manual_drawn",
            "source_confidence": "user_drawn_review_required",
            "review_required": True,
            "construction_release_allowed": False,
        }]
        payload["drainage"] = {
            **payload["drainage"],
            "preferred_outfall": {
                "id": "OUT-1",
                "target_name": "Basin Outfall",
                "x": 215,
                "y": 35,
                "source": "manual_drawn",
                "review_required": True,
                "construction_release_allowed": False,
            },
        }
        payload["drainage_structures"] = [{
            "id": "INLET-1",
            "name": "Parking Inlet",
            "x": 80,
            "y": 90,
            "structure_type": "inlet",
            "source": "manual_drawn",
            "source_confidence": "user_drawn_review_required",
            "review_required": True,
            "construction_release_allowed": False,
        }]
        payload["pipe_network"] = [{
            "id": "STORM-1",
            "label": "Storm Trunk",
            "points": [[80, 90], [180, 40]],
            "path": [[80, 90], [180, 40]],
            "utility_type": "storm",
            "source": "manual_drawn",
            "source_confidence": "user_drawn_review_required",
            "review_required": True,
            "construction_release_allowed": False,
        }]
        payload["utility_network"] = [
            {
                "id": "WATER-1",
                "label": "Public Water Main",
                "points": [[0, 80], [140, 80]],
                "utility_type": "water",
                "source": "manual_drawn",
                "source_confidence": "user_drawn_review_required",
                "review_required": True,
                "construction_release_allowed": False,
            },
            {
                "id": "SAN-1",
                "label": "Public Sanitary Main",
                "points": [[0, 60], [140, 60]],
                "utility_type": "sanitary",
                "source": "manual_drawn",
                "source_confidence": "user_drawn_review_required",
                "review_required": True,
                "construction_release_allowed": False,
            },
        ]

        plan = planner.build_plan(payload)
        messages = {
            row.get("stage_name"): row.get("message")
            for row in plan["meta"].get("stage_results", [])
        }

        self.assertEqual(messages["drainage"], "Drainage stage accepted user-supplied geometry.")
        self.assertEqual(messages["storm_pipes"], "Storm pipe stage completed.")
        self.assertEqual(messages["sanitary"], "Sanitary stage accepted user-supplied sanitary geometry.")
        self.assertEqual(messages["utility_network"], "Utility stage accepted user-supplied geometry.")
        self.assertGreaterEqual(len(plan["meta"]["drainage"]["structures"]), 1)
        self.assertEqual(len(plan["meta"]["drainage"]["basins"]), 1)
        self.assertGreaterEqual(len(plan["meta"]["storm_pipes"]["segments"]), 1)
        self.assertEqual(len(plan["meta"]["utilities"]["segments"]), 2)
        self.assertEqual(
            plan["meta"]["drainage"]["coordination"]["preferred_outfall"]["target_name"],
            "Basin Outfall",
        )
        for system in ("drainage", "storm", "sanitary", "water", "utilities"):
            row = _system(plan, system)
            self.assertEqual(row["status"], "review_required", system)
            self.assertTrue(row["canonical_output_present"], system)
            self.assertTrue(row["engineer_review_required"], system)
            self.assertFalse(row["production_usable"], system)
        self.assertTrue(
            all(segment["construction_release_allowed"] is False for segment in plan["meta"]["utilities"]["segments"])
        )

    def test_missing_terrain_blocks_grading_and_downstream_without_fake_success(self) -> None:
        payload = _supported_minimal_payload()
        payload.pop("terrain")

        plan = planner.build_plan(payload)
        review = _review(plan)

        self.assertIn("terrain", _blocker_inputs(plan, "grading"))
        self.assertIn("grading", review["blocked_systems"])
        self.assertIn("drainage", review["blocked_systems"])
        self.assertIn("grading", _system(plan, "drainage")["stale_or_reactive_status"]["upstream_blocked_systems"])
        self.assertEqual(plan["meta"]["grading"]["workflow_review"]["status"], "blocked_missing_inputs")
        self.assertFalse(review["success"])
        native = plan["meta"]["grading"]["native_engine_guard"]
        self.assertEqual(native["status"], "blocked_missing_inputs")
        self.assertEqual(native["blockers"][0]["blocker_origin"], "discipline_native_engine")

    def test_missing_basin_or_outfall_blocks_drainage_and_storm_exactly(self) -> None:
        payload = _supported_minimal_payload()
        payload["ponds"] = []
        payload["drainage"].pop("tailwater_elev_ft", None)

        plan = planner.build_plan(payload)

        self.assertIn("basin_outfall", _blocker_inputs(plan, "drainage"))
        self.assertIn("basin_outfall", _blocker_inputs(plan, "storm"))
        self.assertEqual(plan["meta"]["drainage"]["workflow_review"]["status"], "blocked_missing_inputs")
        self.assertEqual(plan["meta"]["storm_pipes"]["workflow_review"]["status"], "blocked_missing_inputs")
        self.assertIn("basin_outfall", {item["input"] for item in plan["meta"]["drainage"]["engine_blockers"]})
        self.assertIn("basin_outfall", {item["input"] for item in plan["meta"]["storm_pipes"]["engine_blockers"]})

    def test_missing_standards_blocks_engineering_review_outputs(self) -> None:
        payload = _supported_minimal_payload()
        payload.pop("standards")

        plan = planner.build_plan(payload)

        for system in ("grading", "drainage", "storm", "sanitary", "water", "utilities", "roadway", "qa_review"):
            self.assertIn("standards", _blocker_inputs(plan, system), system)
        self.assertEqual(plan["meta"]["qa"]["review_status"], "blocked_missing_inputs")

    def test_missing_survey_control_blocks_roadway_quantities_and_review(self) -> None:
        payload = _supported_minimal_payload()
        payload.pop("survey_control")
        payload.pop("coordinate_system")

        plan = planner.build_plan(payload)

        for system in ("roadway", "quantities", "qa_review"):
            self.assertIn("survey_control", _blocker_inputs(plan, system), system)
        self.assertEqual(plan["meta"]["quantities"]["workflow_review"]["status"], "blocked_missing_inputs")
        self.assertIn("survey_control", {item["input"] for item in plan["meta"]["roadway"]["engine_blockers"]})
        self.assertIn("survey_control", {item["input"] for item in plan["meta"]["quantities"]["engine_blockers"]})
        self.assertIn("survey_control", {item["input"] for item in plan["meta"]["qa"]["engine_blockers"]})

    def test_missing_utility_service_blocks_sanitary_water_and_utilities(self) -> None:
        payload = _supported_minimal_payload()
        payload["site_plan"] = {"parking_count": 24}
        payload.pop("buildings", None)

        plan = planner.build_plan(payload)

        for system in ("sanitary", "water", "utilities"):
            self.assertIn("utility_service", _blocker_inputs(plan, system), system)
        self.assertEqual(plan["meta"]["utilities"]["workflow_review"]["status"], "blocked_missing_inputs")
        self.assertIn("utility_service", {item["input"] for item in plan["meta"]["utilities"]["engine_blockers"]})

    def test_native_engine_guard_summary_tracks_discipline_blockers(self) -> None:
        payload = _supported_minimal_payload()
        payload.pop("terrain")
        payload["ponds"] = []
        payload.pop("standards")
        payload.pop("survey_control")
        payload.pop("coordinate_system")

        plan = planner.build_plan(payload)
        native = plan["meta"]["discipline_native_engine_guards"]

        for engine in ("grading", "drainage", "storm", "roadway", "utilities", "quantities", "qa_review"):
            self.assertIn(engine, native["blocked_engines"])
            self.assertEqual(native["guards"][engine]["status"], "blocked_missing_inputs")
        self.assertTrue(
            all(item["blocker_origin"] == "discipline_native_engine" for item in native["blockers"])
        )

    def test_incomplete_bad_input_blocks_with_exact_lot_geometry_fields(self) -> None:
        payload = _supported_minimal_payload()
        payload["lot"] = {"x": "bad", "y": 0, "w": 0, "h": -1}
        payload["ponds"] = [{"name": "BASIN-1"}]

        plan = planner.build_plan(payload)
        review = _review(plan)

        self.assertIn("lot_geometry", _blocker_inputs(plan, "grading"))
        self.assertIn("basin_outfall", _blocker_inputs(plan, "drainage"))
        lot_blocker = next(item for item in _system(plan, "grading")["blockers"] if item["input"] == "lot_geometry")
        self.assertEqual(lot_blocker["missing_fields"], ["lot.w", "lot.h"])
        self.assertFalse(review["success"])

    def test_blocked_upstream_records_downstream_stale_reactive_status(self) -> None:
        payload = _supported_minimal_payload()
        payload.pop("terrain")

        plan = planner.build_plan(payload)
        stale = _review(plan)["stale_or_reactive_status"]["downstream_blocked_by_upstream"]

        self.assertIn("drainage", stale)
        self.assertIn("grading", stale["drainage"])
        self.assertIn("qa_review", stale)
        self.assertIn("grading", stale["qa_review"])


if __name__ == "__main__":
    unittest.main()
