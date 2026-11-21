from __future__ import annotations

import unittest
from copy import deepcopy
from unittest.mock import patch

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
    def test_generated_storm_identity_resolves_protected_authored_pipe_fail_closed(self) -> None:
        payload = _supported_minimal_payload()
        payload["disciplines"] = ["grading", "drainage", "storm"]
        payload["drainage_structures"] = [
            {"id": "IN-1", "name": "IN-1", "x": 40, "y": 80, "structure_type": "inlet", "rim_elev_ft": 98},
            {"id": "OF-1", "name": "OF-1", "x": 180, "y": 20, "structure_type": "outfall", "rim_elev_ft": 94},
        ]

        generated = planner.build_plan(deepcopy(payload))
        generated_segments = generated["meta"]["storm_pipes"]["segments"]
        target = next(item for item in generated_segments if item.get("id") == "P-001")
        control = next(item for item in generated_segments if item.get("id") == "P-002")

        authored = {
            "id": "P-001",
            "canonical_id": "P-001",
            "utility_type": "storm",
            "path": deepcopy(target["path"]),
            "points": deepcopy(target["path"]),
            "endpoint_inverts_protected": True,
            "invert_start_ft": 95.0,
            "invert_end_ft": 94.5,
            "invert_provenance": {"source": "synthetic explicit", "reviewed": True},
        }
        protected_payload = deepcopy(payload)
        unprotected_control = {
            "id": "P-002",
            "canonical_id": "P-002",
            "utility_type": "storm",
            "path": deepcopy(control["path"]),
            "points": deepcopy(control["path"]),
            "endpoint_inverts_protected": False,
        }
        # Authored input order differs from generated order; identity, not list
        # position, must decide which segment receives protected values.
        protected_payload["pipe_network"] = [unprotected_control, authored]
        protected = planner.build_plan(protected_payload)
        protected_segments = protected["meta"]["storm_pipes"]["segments"]
        protected_target = next(item for item in protected_segments if item.get("id") == "P-001")
        protected_control = next(item for item in protected_segments if item.get("id") == "P-002")
        self.assertEqual(protected_target["canonical_id"], "P-001")
        self.assertEqual(protected_target["start_invert"], 95.0)
        self.assertEqual(protected_target["end_invert"], 94.5)
        self.assertTrue(protected_target["endpoint_inverts_protected"])
        self.assertEqual(protected_target["path"], target["path"])
        self.assertEqual(protected_control["path"], control["path"])
        self.assertEqual(protected_control["start_invert"], control["start_invert"])
        self.assertEqual(protected_control["end_invert"], control["end_invert"])

        ambiguous_payload = deepcopy(payload)
        conflicting_authored = deepcopy(authored)
        conflicting_authored["invert_start_ft"] = 91.0
        conflicting_authored["invert_end_ft"] = 90.5
        ambiguous_payload["pipe_network"] = [authored, conflicting_authored]
        ambiguous = planner.build_plan(ambiguous_payload)
        ambiguous_storm = ambiguous["meta"]["storm_pipes"]
        ambiguous_target = next(item for item in ambiguous_storm["segments"] if item.get("id") == "P-001")
        self.assertEqual(ambiguous_target["start_invert"], target["start_invert"])
        self.assertEqual(ambiguous_target["end_invert"], target["end_invert"])
        self.assertTrue(any("ambiguous" in item for item in ambiguous_storm["errors"]))
        self.assertFalse(ambiguous_storm["export_validation"]["ready"])
        self.assertFalse(
            next(row for row in ambiguous["meta"]["stage_results"] if row["stage_name"] == "storm_pipes")["success"]
        )

        missing_payload = deepcopy(payload)
        missing_authored = deepcopy(authored)
        missing_authored["id"] = "MISSING-PIPE"
        missing_authored["canonical_id"] = "MISSING-PIPE"
        missing_payload["pipe_network"] = [missing_authored]
        missing = planner.build_plan(missing_payload)
        missing_storm = missing["meta"]["storm_pipes"]
        missing_target = next(item for item in missing_storm["segments"] if item.get("id") == "P-001")
        self.assertEqual(missing_target["start_invert"], target["start_invert"])
        self.assertEqual(missing_target["end_invert"], target["end_invert"])
        self.assertTrue(any("could not be matched" in item for item in missing_storm["errors"]))
        self.assertFalse(
            next(row for row in missing["meta"]["stage_results"] if row["stage_name"] == "storm_pipes")["success"]
        )

    def test_traceable_building_quantity_and_review_pipe_reach_exports(self) -> None:
        from tempfile import TemporaryDirectory
        from pathlib import Path
        from backend.services.artifact_service import ArtifactService

        payload = _supported_minimal_payload()
        payload["buildings"] = [{"id": "B-1", "name": "Office", "type": "office", "x": 40, "y": 50, "w": 70, "d": 40}]
        payload["utility_network"] = [{
            "id": "P-1", "utility_type": "storm", "points": [[120, 120], [180, 80]],
            "source": "manual_drawn", "review_required": True, "construction_release_allowed": False,
        }]
        payload["pipe_network"] = [{
            "id": "P-1", "canonical_id": "P-1", "path": [[120, 120], [180, 80]],
            "points": [[120, 120], [180, 80]], "utility_type": "storm",
            "length_ft": 72.111, "diameter_in": 18, "slope_ft_ft": 0.01,
            "source": "manual_drawn", "review_required": True, "construction_release_allowed": False,
        }]
        phased_payload = deepcopy(payload)
        phased_payload["meta"] = {"orchestrator_meta": {"runtime_phase_batch_limit": 1}}
        phased = planner.build_plan(phased_payload)
        phased_buildings = [action for action in phased["actions"] if action.get("layer") == "BUILDING"]
        self.assertEqual(len(phased_buildings), 1)
        self.assertEqual(phased_buildings[0]["canonical_source_id"], "B-1")
        plan = planner.build_plan(payload)
        self.assertEqual(plan["meta"]["quantities"]["totals"]["building_area_sf"], 2800.0)
        self.assertTrue(plan["meta"]["quantities"]["explain"]["quantity_audit"]["building_area_sf"]["trace_complete"])
        self.assertEqual(plan["meta"]["review_pipe_network"]["segments"][0]["canonical_id"], "P-1")
        with TemporaryDirectory() as directory:
            artifact = ArtifactService(Path(directory)).export_landxml(user_id="synthetic", final_plan=plan)
            text = artifact.read_text()
        self.assertIn("<LandXML", text)
        self.assertIn("P-1", text)
        self.assertIn('civoraReviewOnly="true"', text)

    def test_site_only_expansion_preserves_canonical_building_and_parking(self) -> None:
        base = [
            {"task": "rectangle", "layer": "BUILDING", "origin": [300, 120], "width": 170, "height": 90},
            {"task": "rectangle", "layer": "PARKING", "origin": [240, 360], "width": 330, "height": 150},
        ]
        expanded = [
            {"task": "rectangle", "layer": "SITE", "origin": [0, 0], "width": 900, "height": 700},
            {"task": "polygon", "layer": "PAD", "points": [[20, 20], [880, 20], [880, 680], [20, 680]]},
        ]
        filtered = planner._filter_base_preview_actions_for_expanded_plan(base, expanded)
        self.assertEqual([item["layer"] for item in filtered], ["BUILDING", "PARKING"])

    def test_final_plan_preserves_truth_labeled_grading_preview_samples(self) -> None:
        plan = planner.build_plan(_supported_minimal_payload())

        surface_model = plan["meta"]["grading"]["surface_model"]
        spot_elevations = surface_model["spot_elevations"]

        self.assertEqual(surface_model["model"], "grid")
        self.assertEqual(surface_model["source_type"], "assumed")
        self.assertFalse(surface_model["control_verified"])
        self.assertIn("not_survey_backed_reason", surface_model["confidence"])
        self.assertGreaterEqual(len(spot_elevations), 3)
        self.assertEqual(min(point["x"] for point in spot_elevations), surface_model["bounds"][0])
        self.assertEqual(max(point["x"] for point in spot_elevations), surface_model["bounds"][2])
        self.assertEqual(min(point["y"] for point in spot_elevations), surface_model["bounds"][1])
        self.assertEqual(max(point["y"] for point in spot_elevations), surface_model["bounds"][3])
        self.assertTrue(
            all(
                isinstance(point.get(axis), (int, float))
                for point in spot_elevations
                for axis in ("x", "y", "z")
            )
        )

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

    def test_runtime_resume_keeps_complete_downstream_checkpoint_state(self) -> None:
        payload = _supported_minimal_payload()
        checkpoint = planner.build_plan(deepcopy(payload))
        statuses = checkpoint["meta"]["stage_completeness"]["statuses"]

        resumed_payload = deepcopy(payload)
        resumed_payload["meta"] = {
            "orchestrator_meta": {
                "runtime_resume": {
                    "final_plan": checkpoint,
                    "stage_statuses": statuses,
                },
                "runtime_phase_batch_limit": 1,
            }
        }

        resumed = planner.build_plan(resumed_payload)
        self.assertEqual(resumed["meta"]["runtime_phase_checkpoint"]["stage_name"], "sheets")

    def test_accepted_partial_sanitary_invalidates_dependent_outputs(self) -> None:
        payload = _supported_minimal_payload()
        checkpoint = planner.build_plan(deepcopy(payload))
        checkpoint_meta = checkpoint["meta"]
        statuses = checkpoint_meta["stage_completeness"]["statuses"]
        statuses["sanitary"] = "partial"

        resumed_payload = deepcopy(payload)
        resumed_payload["meta"] = {
            "orchestrator_meta": {
                "runtime_resume": {
                    "final_plan": checkpoint,
                    "stage_statuses": statuses,
                },
                "runtime_approved_stages": ["sanitary"],
                "runtime_phase_batch_limit": 1,
            }
        }

        resumed = planner.build_plan(resumed_payload)
        runtime_checkpoint = resumed["meta"]["runtime_phase_checkpoint"]
        self.assertEqual(runtime_checkpoint["stage_name"], "utility_network")
        stage_rows = resumed["meta"]["stage_results"]
        self.assertTrue(
            any(
                row.get("stage_name") == "utility_network"
                and not row.get("meta", {}).get("resumed_from_checkpoint")
                for row in stage_rows
            )
        )

    def test_approved_empty_sanitary_checkpoint_advances_once(self) -> None:
        payload = _supported_minimal_payload()
        checkpoint = planner.build_plan(deepcopy(payload))
        checkpoint_meta = checkpoint["meta"]
        statuses = checkpoint_meta["stage_completeness"]["statuses"]
        statuses["sanitary"] = "partial"
        checkpoint_meta.pop("sanitary", None)

        resumed_payload = deepcopy(payload)
        resumed_payload["meta"] = {
            "orchestrator_meta": {
                "runtime_resume": {
                    "final_plan": checkpoint,
                    "stage_statuses": statuses,
                },
                "runtime_approved_stages": ["sanitary"],
                "runtime_phase_batch_limit": 1,
            }
        }

        resumed = planner.build_plan(resumed_payload)
        runtime_checkpoint = resumed["meta"]["runtime_phase_checkpoint"]
        self.assertEqual(runtime_checkpoint["stage_name"], "utility_network")
        sanitary_rows = [
            row for row in resumed["meta"]["stage_results"]
            if row.get("stage_name") == "sanitary"
        ]
        self.assertTrue(sanitary_rows)
        resumed_rows = [
            row for row in sanitary_rows
            if row.get("meta", {}).get("resumed_from_checkpoint")
        ]
        self.assertEqual(len(resumed_rows), 1)
        self.assertTrue(resumed_rows[0].get("meta", {}).get("approved_checkpoint"))
        self.assertFalse(any(row.get("message") == "Sanitary stage accepted user-supplied sanitary geometry." for row in sanitary_rows))

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

    def test_approved_checkpoint_without_status_map_advances_to_next_stage(self) -> None:
        payload = _supported_minimal_payload()
        payload["meta"] = {
            "orchestrator_meta": {
                "runtime_phase_batch_limit": 1,
                "runtime_approved_stages": ["layout"],
                "runtime_resume": {
                    "final_plan": {"meta": {"runtime_phase_checkpoint": {"stage_name": "layout"}}},
                    "stage_statuses": {},
                },
            }
        }
        resumed = planner.build_plan(payload)
        checkpoint = resumed["meta"]["runtime_phase_checkpoint"]
        self.assertNotEqual(checkpoint["stage_name"], "layout")

    def test_runtime_checkpoint_preserves_current_engine_provenance_without_recertifying_unknown_resume(self) -> None:
        from backend.services.canonical_results import ENGINE_REVISION

        fresh_payload = _supported_minimal_payload()
        fresh_payload["meta"] = {"orchestrator_meta": {"runtime_phase_batch_limit": 1}}
        fresh_checkpoint = planner.build_plan(fresh_payload)
        self.assertEqual(fresh_checkpoint["meta"]["calculation_engine_revision"], ENGINE_REVISION)

        unknown_payload = _supported_minimal_payload()
        unknown_payload["meta"] = {
            "orchestrator_meta": {
                "runtime_phase_batch_limit": 1,
                "runtime_approved_stages": ["layout"],
                "runtime_resume": {
                    "final_plan": {
                        "actions": fresh_checkpoint.get("actions", []),
                        "meta": {
                            "stage_completeness": {"statuses": {"layout": "complete"}},
                            "runtime_phase_checkpoint": {"stage_name": "layout", "yielded": True},
                        },
                    },
                    "stage_statuses": {"layout": "complete"},
                },
            }
        }
        unknown_checkpoint = planner.build_plan(unknown_payload)
        self.assertNotIn("calculation_engine_revision", unknown_checkpoint["meta"])

    def test_runtime_approval_checkpoint_skips_terminal_packaging(self) -> None:
        payload = _supported_minimal_payload()
        payload["meta"] = {"orchestrator_meta": {"runtime_phase_batch_limit": 1}}
        with patch.object(planner, "finalize_plan", side_effect=AssertionError("terminal packaging must not run")):
            checkpoint = planner.build_plan(payload)
        self.assertTrue(checkpoint["meta"]["runtime_phase_checkpoint"]["yielded"])
        self.assertNotIn("quantities", checkpoint["meta"])
        performance = checkpoint["meta"]["performance"]
        self.assertIn("approval wait", performance["measurement_scope"])
        stage_samples = [
            item
            for item in performance["runtime_phase_timings"]
            if item.get("phase") == "stage_execution"
        ]
        self.assertEqual(len(stage_samples), 1)
        self.assertEqual(
            stage_samples[0]["stage_name"],
            checkpoint["meta"]["runtime_phase_checkpoint"]["stage_name"],
        )
        self.assertGreaterEqual(stage_samples[0]["duration_ms"], 0)
        self.assertGreaterEqual(stage_samples[0]["checkpoint_serialization_ms"], 0)

    def test_runtime_timing_survives_checkpoint_resume_without_payload_details(self) -> None:
        payload = _supported_minimal_payload()
        payload["meta"] = {"orchestrator_meta": {"runtime_phase_batch_limit": 1}}
        checkpoint = planner.build_plan(payload)
        approved_stage = checkpoint["meta"]["runtime_phase_checkpoint"]["stage_name"]

        resumed_payload = _supported_minimal_payload()
        resumed_payload["meta"] = {
            "orchestrator_meta": {
                "runtime_phase_batch_limit": 1,
                "runtime_approved_stages": [approved_stage],
                "runtime_resume": {
                    "final_plan": checkpoint,
                    "stage_statuses": checkpoint["meta"]["stage_completeness"]["statuses"],
                },
            }
        }
        resumed = planner.build_plan(resumed_payload)
        timings = resumed["meta"]["performance"]["runtime_phase_timings"]

        self.assertTrue(any(item.get("phase") == "checkpoint_reconstruction" for item in timings))
        self.assertGreaterEqual(
            len([item for item in timings if item.get("phase") == "stage_execution"]),
            2,
        )
        self.assertTrue(all("project_name" not in item for item in timings))
        self.assertTrue(all("actions" not in item for item in timings))

    def test_sparse_approved_layout_checkpoint_rehydrates_user_building(self) -> None:
        payload = _supported_minimal_payload()
        payload["buildings"] = [{"id": "B-1", "name": "Office", "x": 40, "y": 50, "w": 70, "d": 40}]
        payload["meta"] = {"orchestrator_meta": {
            "runtime_phase_batch_limit": 1,
            "runtime_approved_stages": ["layout"],
            "runtime_resume": {
                "stage_statuses": {"layout": "complete"},
                "final_plan": {"units": "ft", "actions": [{"task": "rectangle", "layer": "SITE", "origin": [0, 0], "width": 240, "height": 180}], "meta": {}},
            },
        }}
        resumed = planner.build_plan(payload)
        buildings = [action for action in resumed["actions"] if action.get("layer") == "BUILDING"]
        self.assertEqual(len(buildings), 1)
        self.assertEqual(buildings[0]["canonical_source_id"], "B-1")
        self.assertEqual(buildings[0]["width"] * buildings[0]["height"], 2800.0)

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
