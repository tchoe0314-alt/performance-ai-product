import unittest
from copy import deepcopy
from unittest.mock import patch

from planner import build_plan
from planner_orchestrator import PlannerOrchestratorRequest, orchestrate_manual, orchestrate_plan


def _manual_payload(**overrides):
    payload = {
        "project_name": "Manual Validation Test",
        "units": "ft",
        "mode": "site_plan",
        "project_type": "commercial_pad",
        "site_type": "commercial_pad",
        "lot": {"x": 0.0, "y": 0.0, "w": 140.0, "h": 110.0},
        "setback": 10.0,
        "street_edge": "bottom",
        "layout_strategy": "front_parking",
        "site_plan": {"building_width": 48.0, "building_depth": 34.0, "parking_count": 24},
        "meta": {"input_mode": "manual", "source_input_mode": "manual", "manual_mode": True},
    }
    for key, value in overrides.items():
        payload[key] = value
    return payload


def _failure_codes(plan):
    return [item.get("code") for item in (((plan.get("meta") or {}).get("manual_validation") or {}).get("failures") or [])]


class ManualModeValidationTest(unittest.TestCase):
    def test_manual_mode_can_complete_when_core_engineering_outputs_exist(self) -> None:
        plan = build_plan(
            {
                "project_name": "Manual Validation Success",
                "units": "ft",
                "mode": "site_plan",
                "project_type": "commercial_pad",
                "site_type": "commercial_pad",
                "lot": {"x": 0.0, "y": 0.0, "w": 140.0, "h": 110.0},
                "setback": 10.0,
                "street_edge": "bottom",
                "layout_strategy": "front_parking",
                "site_plan": {"parking_count": 24},
                "meta": {"input_mode": "manual", "source_input_mode": "manual", "manual_mode": True},
            }
        )
        meta = plan.get("meta") or {}
        self.assertEqual(_failure_codes(plan), [])
        self.assertTrue((meta.get("engineering_status") or {}).get("success"))
        self.assertEqual(((meta.get("parking_program") or {}).get("requested_target")), 24)
        produced = (meta.get("deliverables") or {}).get("produced") or []
        self.assertNotIn("drainage_plan", produced)
        self.assertNotIn("storm_pipe_plan", produced)
        self.assertIn("utility_plan", produced)
        self.assertIn("primary_detention_overflow_assumed", (((meta.get("drainage") or {}).get("export_validation") or {}).get("reasons") or []))
        qa_issues = ((meta.get("qa") or {}).get("issues") or [])
        self.assertFalse([issue for issue in qa_issues if issue.get("severity") == "error"])
        self.assertTrue((meta.get("truth_audit") or {}).get("success"))
        self.assertTrue(((meta.get("stage_completeness") or {}).get("all_required_complete")))
        self.assertGreaterEqual(((meta.get("engineering_status") or {}).get("engineering_trust_score") or 0.0), 70.0)

    def test_stage_results_include_canonical_diff_snapshots(self) -> None:
        plan = build_plan(_manual_payload())
        stage_rows = {item["stage_name"]: item for item in ((plan.get("meta") or {}).get("stage_results") or [])}
        self.assertIn("layout", stage_rows)
        layout_meta = stage_rows["layout"]["meta"]
        self.assertIn("canonical_snapshot_before", layout_meta)
        self.assertIn("canonical_snapshot_after", layout_meta)
        self.assertIn("canonical_diff", layout_meta)
        self.assertIn("changed_keys", layout_meta["canonical_diff"])

    def test_identical_inputs_are_deterministic_for_actions_and_truth_audit(self) -> None:
        first = build_plan(_manual_payload())
        second = build_plan(_manual_payload())
        self.assertEqual(first.get("actions"), second.get("actions"))
        self.assertEqual((first.get("meta") or {}).get("truth_audit"), (second.get("meta") or {}).get("truth_audit"))
        self.assertEqual((first.get("meta") or {}).get("deliverables"), (second.get("meta") or {}).get("deliverables"))
        self.assertEqual(
            ((first.get("meta") or {}).get("stage_completeness") or {}).get("required_stage_status"),
            ((second.get("meta") or {}).get("stage_completeness") or {}).get("required_stage_status"),
        )

    def test_manual_mode_fails_on_untraceable_parking_target(self) -> None:
        plan = build_plan(
            _manual_payload(
                project_type="custom_site",
                site_type="custom_site",
                site_plan={"building_width": 48.0, "building_depth": 34.0},
            )
        )
        self.assertIn("MANUAL_PARKING_TARGET_UNTRACEABLE", _failure_codes(plan))

    def test_manual_mode_failure_reasoning_exposes_system_rule_location_and_cause(self) -> None:
        import planner as planner_module

        original = planner_module._run_conflict_resolution_stage

        def wrapped(ctx, hydrology):
            original(ctx, hydrology)
            summary = deepcopy(ctx.manager.latest_outputs.get("coordination", {}))
            summary["success"] = False
            summary["unresolved_conflicts"] = [
                {
                    "conflict_type": "storm_water_clearance",
                    "systems": ["storm", "water"],
                    "location": [52.0, 18.0],
                    "resolution_reason": "No safe vertical separation candidate remained after evaluating crossing rules.",
                }
            ]
            ctx.manager.latest_outputs["coordination"] = summary
            ctx.manager.project.meta["coordination_summary"] = deepcopy(summary)

        with patch("planner._run_conflict_resolution_stage", side_effect=wrapped):
            plan = build_plan(_manual_payload())

        reasoning = (((plan.get("meta") or {}).get("manual_validation") or {}).get("failure_reasoning") or [])
        self.assertTrue(reasoning)
        first = reasoning[0]
        self.assertEqual(first["system"], "coordination")
        self.assertEqual(first["rule"], "unresolved_conflicts")
        self.assertEqual(first["location"], [52.0, 18.0])
        self.assertIn("No safe vertical separation candidate", first["why_unresolved"])

    def test_manual_mode_generates_requested_profile_deliverable(self) -> None:
        plan = build_plan(_manual_payload(deliverables=["road_profile"]))
        deliverables = ((plan.get("meta") or {}).get("deliverables") or {})
        self.assertIn("road_profile", deliverables.get("produced") or [])
        self.assertEqual(_failure_codes(plan), [])
        qa_messages = [item.get("message") for item in (((plan.get("meta") or {}).get("qa") or {}).get("issues") or [])]
        self.assertNotIn("Deliverables suggest profile support, but no profile-like signal was found.", qa_messages)
        self.assertTrue((plan.get("meta") or {}).get("profiles"))

    def test_manual_mode_generates_requested_cross_sections(self) -> None:
        plan = build_plan(_manual_payload(deliverables=["cross_sections"]))
        self.assertEqual(_failure_codes(plan), [])
        deliverables = ((plan.get("meta") or {}).get("deliverables") or {})
        self.assertIn("cross_sections", deliverables.get("produced") or [])
        qa_messages = [item.get("message") for item in (((plan.get("meta") or {}).get("qa") or {}).get("issues") or [])]
        self.assertNotIn("Deliverables suggest cross-section support, but no cross-section-like signal was found.", qa_messages)
        self.assertTrue((plan.get("meta") or {}).get("cross_sections"))

    def test_manual_mode_exposes_ready_storm_export_after_verified_overflow(self) -> None:
        plan = build_plan(
            _manual_payload(
                deliverables=["storm_pipe_plan"],
                drainage={
                    "verified_overflow_capacity_cfs": 12.0,
                    "overflow_verification_source": "manual_test_fixture",
                    "verified_tailwater_elev_ft": 96.0,
                    "tailwater_verification_source": "manual_test_fixture",
                },
            )
        )
        meta = plan.get("meta") or {}
        self.assertEqual(_failure_codes(plan), [])
        self.assertIn("storm_pipe_plan", ((meta.get("deliverables") or {}).get("produced") or []))
        self.assertTrue((((meta.get("storm_pipes") or {}).get("export_validation") or {}).get("ready")))
        self.assertEqual((meta.get("storm_pipes") or {}).get("hydraulic_depth_source"), "storm_hydraulic_engine")

    def test_conflict_heavy_manual_path_keeps_sanitary_truth_valid_and_can_now_resolve(self) -> None:
        plan = build_plan(
            _manual_payload(
                deliverables=["road_profile", "cross_sections", "storm_pipe_plan", "sanitary_plan", "utility_plan"],
                site_plan={"building_width": 52.0, "building_depth": 36.0, "parking_count": 26},
            )
        )
        meta = plan.get("meta") or {}
        sanitary = meta.get("sanitary") or {}
        self.assertTrue((sanitary.get("graph_validation") or {}).get("valid"))
        self.assertTrue((sanitary.get("network_validation") or {}).get("valid"))
        self.assertEqual((sanitary.get("network_validation") or {}).get("invalid_cover_segments") or [], [])
        self.assertNotIn("MANUAL_SANITARY_OUTPUT_MISSING", _failure_codes(plan))
        self.assertNotIn("MANUAL_SANITARY_GRAPH_INVALID", _failure_codes(plan))
        self.assertNotIn("MANUAL_SANITARY_NETWORK_INVALID", _failure_codes(plan))
        self.assertIn("MANUAL_DELIVERABLES_MISSING", _failure_codes(plan))
        self.assertIn("MANUAL_STORM_DELIVERABLE_MATCH", _failure_codes(plan))
        self.assertEqual(len((meta.get("coordination") or {}).get("unresolved_conflicts") or []), 0)
        self.assertFalse((meta.get("truth_audit") or {}).get("success"))
        self.assertIn(
            "STORM_DELIVERABLE_MATCH",
            [item.get("code") for item in ((meta.get("truth_audit") or {}).get("failing_checks") or [])],
        )

    def test_manual_mode_fails_when_grading_falls_back(self) -> None:
        with patch("planner.GradingEngine.build", return_value=None):
            plan = build_plan(_manual_payload())
        self.assertIn("MANUAL_GRADING_FALLBACK_USED", _failure_codes(plan))

    def test_manual_mode_fails_when_utility_routing_uses_fallback(self) -> None:
        with patch("planner.UtilityEngine.generate", side_effect=TypeError("forced fallback")):
            plan = build_plan(_manual_payload())
        self.assertIn("MANUAL_UTILITY_FALLBACK_USED", _failure_codes(plan))

    def test_manual_mode_fails_when_storm_pipe_summary_is_missing(self) -> None:
        import planner as planner_module

        original = planner_module._run_storm_pipe_stage

        def wrapped(ctx, hydrology):
            original(ctx, hydrology)
            ctx.manager.latest_outputs["storm_pipe_summary"] = {"segments": [{"name": "P-1"}]}
            ctx.manager.project.meta["storm_pipe_summary"] = {"segments": [{"name": "P-1"}]}

        with patch("planner._run_storm_pipe_stage", side_effect=wrapped):
            plan = build_plan(_manual_payload())
        failure_codes = _failure_codes(plan)
        self.assertTrue(
            {"MANUAL_STORM_SEGMENT_DATA_MISSING", "MANUAL_STORM_HYDRAULIC_INVALID"} & set(failure_codes),
            failure_codes,
        )

    def test_manual_mode_fails_when_storm_graph_is_invalid(self) -> None:
        import planner as planner_module

        original = planner_module._run_storm_pipe_stage

        def wrapped(ctx, hydrology):
            original(ctx, hydrology)
            storm = deepcopy(ctx.manager.latest_outputs.get("storm_pipe_summary", {}))
            storm["graph_validation"] = {
                "system": "storm",
                "segment_count": 1,
                "node_count": 2,
                "disconnected_runs": ["P-1"],
                "loop_nodes": [],
                "valid": False,
            }
            ctx.manager.latest_outputs["storm_pipe_summary"] = storm
            ctx.manager.project.meta["storm_pipe_summary"] = deepcopy(storm)

        with patch("planner._run_storm_pipe_stage", side_effect=wrapped):
            plan = build_plan(_manual_payload())
        self.assertIn("MANUAL_STORM_GRAPH_INVALID", _failure_codes(plan))

    def test_manual_mode_fails_when_storm_profile_band_data_is_missing(self) -> None:
        import planner as planner_module

        original = planner_module._run_storm_pipe_stage

        def wrapped(ctx, hydrology):
            original(ctx, hydrology)
            storm = deepcopy(ctx.manager.latest_outputs.get("storm_pipe_summary", {}))
            segments = storm.get("segments") or []
            if segments:
                for key in ("diameter_in", "slope_pct", "start_invert", "end_invert", "flow_cfs", "capacity_cfs", "capacity_ratio"):
                    segments[0].pop(key, None)
            ctx.manager.latest_outputs["storm_pipe_summary"] = storm
            ctx.manager.project.meta["storm_pipe_summary"] = deepcopy(storm)

        with patch("planner._run_storm_pipe_stage", side_effect=wrapped):
            plan = build_plan(_manual_payload(deliverables=["road_profile", "storm_pipe_plan"]))
        self.assertIn("MANUAL_STORM_PROFILE_BAND_DATA_MISSING", _failure_codes(plan))

    def test_manual_mode_fails_when_quantity_traceability_is_incomplete(self) -> None:
        import planner as planner_module

        original = planner_module.compute_plan_quantities

        def wrapped(plan):
            result = original(plan)
            result.explain.setdefault("meta_summary", {})
            result.explain["meta_summary"]["quantity_traceability_complete"] = False
            result.explain["trace_gaps"] = {
                "pipe_length_ft": {
                    "value": result.totals.get("pipe_length_ft"),
                    "derivation_method": "forced_test_gap",
                    "source_object_types": [],
                }
            }
            return result

        with patch("planner.compute_plan_quantities", side_effect=wrapped):
            plan = build_plan(_manual_payload())
        self.assertIn("MANUAL_QUANTITY_TRACEABILITY_INCOMPLETE", _failure_codes(plan))

    def test_manual_mode_fails_on_site_area_inconsistency(self) -> None:
        with patch(
            "planner._canonical_area_accounting",
            return_value={
                "lot_area_sf": 10000.0,
                "impervious_area_sf": 12500.0,
                "impervious_by_action_sf": 12400.0,
                "duplicate_impervious_rectangles": 0,
                "reason_class": "accounting_bug",
                "candidate_values": [12500.0, 12300.0],
            },
        ):
            plan = build_plan(_manual_payload())
        self.assertIn("MANUAL_SITE_AREA_INCONSISTENT", _failure_codes(plan))

    def test_assisted_mode_can_continue_where_manual_mode_fails(self) -> None:
        manual_fields = deepcopy(_manual_payload(deliverables=["road_profile"]))
        manual_fields.pop("meta", None)

        manual_result = orchestrate_manual(manual_fields)
        assisted_result = orchestrate_plan(
            PlannerOrchestratorRequest(
                input_mode="assisted",
                manual_fields=manual_fields,
                allow_ai_fill_for_blanks=True,
            )
        )

        self.assertTrue(manual_result.success)
        self.assertTrue(assisted_result.success)
        self.assertIn("road_profile", ((manual_result.final_plan.get("meta") or {}).get("deliverables") or {}).get("produced") or [])

    def test_engineering_trust_score_drops_when_canonical_truth_degrades(self) -> None:
        baseline = build_plan(_manual_payload())
        baseline_score = ((baseline.get("meta") or {}).get("engineering_status") or {}).get("engineering_trust_score") or 0.0

        import planner as planner_module

        original = planner_module._run_storm_pipe_stage

        def wrapped(ctx, hydrology):
            original(ctx, hydrology)
            storm = deepcopy(ctx.manager.latest_outputs.get("storm_pipe_summary", {}))
            storm["graph_validation"] = {
                "system": "storm",
                "segment_count": 1,
                "node_count": 3,
                "disconnected_runs": [],
                "loop_nodes": [],
                "duplicate_segments": [],
                "duplicate_edges": [],
                "invalid_direction_segments": [{"segment_id": "P-1"}],
                "illegal_branch_nodes": [],
                "orphan_nodes": ["ORPHAN-1"],
                "unreasonable_degree_nodes": [],
                "valid": False,
            }
            storm["hydraulic_validation"] = {
                "system": "storm",
                "geometry_only_segments": ["P-1"],
                "missing_accumulation_segments": ["P-1"],
                "invalid_capacity_ratio_segments": [],
                "downstream_total_inconsistencies": [],
                "valid": False,
            }
            ctx.manager.latest_outputs["storm_pipe_summary"] = storm
            ctx.manager.project.meta["storm_pipe_summary"] = deepcopy(storm)

        with patch("planner._run_storm_pipe_stage", side_effect=wrapped):
            degraded = build_plan(_manual_payload())

        degraded_score = ((degraded.get("meta") or {}).get("engineering_status") or {}).get("engineering_trust_score") or 0.0
        self.assertLess(degraded_score, baseline_score)

    def test_engineering_trust_score_drops_when_manual_validation_fails(self) -> None:
        baseline = build_plan(_manual_payload())
        failed = build_plan(
            _manual_payload(
                project_type="custom_site",
                site_type="custom_site",
                site_plan={"building_width": 48.0, "building_depth": 34.0},
            )
        )
        baseline_score = ((baseline.get("meta") or {}).get("engineering_status") or {}).get("engineering_trust_score") or 0.0
        failed_meta = failed.get("meta") or {}
        failed_score = ((failed_meta.get("engineering_status") or {}).get("engineering_trust_score") or 0.0)
        self.assertTrue((failed_meta.get("manual_validation") or {}).get("failed"))
        self.assertFalse((failed_meta.get("engineering_status") or {}).get("success"))
        self.assertLess(failed_score, baseline_score)

    def test_orchestrate_manual_unwraps_wrapped_entrypoint_payload(self) -> None:
        wrapped = {
            "manual_fields": {
                "project_name": "Wrapped Manual Request",
                "units": "ft",
                "project_type": "commercial_pad",
                "site_type": "commercial_pad",
                "lot": {"x": 0.0, "y": 0.0, "w": 140.0, "h": 110.0},
                "setback": 10.0,
                "site_plan": {"parking_count": 24},
            },
            "strict_mode": False,
        }
        result = orchestrate_manual(wrapped)
        self.assertTrue(result.success)
        self.assertEqual((result.final_plan.get("meta") or {}).get("parking_program", {}).get("requested_target"), 24)


if __name__ == "__main__":
    unittest.main()
