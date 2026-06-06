import unittest
from dataclasses import dataclass, field
from typing import Optional

from fastapi import HTTPException

from backend.application.design_workflows import (
    build_run_summary,
    final_plan_from_result,
    prepare_reactive_orchestration_payload,
    run_orchestration,
)


class ApplicationDesignWorkflowsTest(unittest.TestCase):
    def test_prepare_reactive_orchestration_payload_attaches_checkpoint_for_focused_system(self):
        checkpoint = {
            "project_name": "Checkpointed",
            "meta": {
                "stage_completeness": {
                    "statuses": {
                        "layout": "complete",
                        "grading": "complete",
                    }
                }
            },
        }

        payload = prepare_reactive_orchestration_payload(
            {
                "project_id": "p1",
                "full_design_mode": False,
                "meta": {"requested_system": "grading"},
                "manual_fields": {},
            },
            checkpoint_final_plan=checkpoint,
        )

        meta = payload["meta"]
        runtime_resume = meta["orchestrator_meta"]["runtime_resume"]
        self.assertEqual(runtime_resume["final_plan"]["project_name"], "Checkpointed")
        self.assertTrue(meta["reactive_partial_rerun_request"]["enabled"])
        self.assertIn("grading", meta["changed_targets"])
        self.assertIn("storm_pipes", meta["stale_outputs"])

    def test_prepare_reactive_orchestration_payload_leaves_full_runs_without_checkpoint(self):
        payload = prepare_reactive_orchestration_payload(
            {
                "project_id": "p1",
                "full_design_mode": True,
                "meta": {"requested_system": "full"},
                "manual_fields": {},
            },
            checkpoint_final_plan={"project_name": "Checkpointed"},
        )

        self.assertNotIn("reactive_partial_rerun_request", payload["meta"])
        self.assertNotIn("orchestrator_meta", payload["meta"])

    def test_run_orchestration_accepts_prompt_fallback_when_prompt_text_missing(self):
        @dataclass
        class FakeRequest:
            input_mode: str
            strict_mode: bool
            full_design_mode: bool = False
            prompt_text: Optional[str] = None
            image_path: Optional[str] = None
            manual_fields: dict = field(default_factory=dict)
            image_width_px: Optional[int] = None
            image_height_px: Optional[int] = None
            pixels_per_unit: Optional[float] = None
            plan_type_hint: Optional[str] = None
            units: str = "ft"
            allow_ai_fill_for_blanks: bool = True
            persist_trace_metadata: bool = True
            meta: dict = field(default_factory=dict)
            progress_callback: Optional[object] = None

        class FakeResult:
            def __init__(self, prompt_text: Optional[str]):
                self.success = True
                self.message = "ok"
                self.parsed_payload = {"project_type": "mixed_use", "prompt_echo": prompt_text}
                self.final_plan = {"actions": [], "meta": {}}
                self.warnings = []
                self.errors = []
                self.issues = []
                self.assumptions = []
                self.metadata = {}

        def fake_load_orchestrator():
            def fake_orchestrate(req):
                return FakeResult(req.prompt_text)

            return FakeRequest, fake_orchestrate

        result = run_orchestration(
            {
                "input_mode": "assisted",
                "prompt": "Design a mixed-use site with three multifamily buildings and one retail pad.",
                "manual_fields": {},
                "meta": {},
            },
            load_orchestrator=fake_load_orchestrator,
            assess_design_readiness=lambda *_args, **_kwargs: None,
        )
        self.assertTrue(result["success"])
        self.assertIn("three multifamily buildings", result["parsed_payload"]["prompt_echo"])

    def test_run_orchestration_preserves_full_design_mode(self):
        @dataclass
        class FakeRequest:
            input_mode: str
            strict_mode: bool
            full_design_mode: bool = False
            prompt_text: Optional[str] = None
            image_path: Optional[str] = None
            manual_fields: dict = field(default_factory=dict)
            image_width_px: Optional[int] = None
            image_height_px: Optional[int] = None
            pixels_per_unit: Optional[float] = None
            plan_type_hint: Optional[str] = None
            units: str = "ft"
            allow_ai_fill_for_blanks: bool = True
            persist_trace_metadata: bool = True
            meta: dict = field(default_factory=dict)
            progress_callback: Optional[object] = None

        class FakeResult:
            def __init__(self, full_design_mode: bool):
                self.success = True
                self.message = "ok"
                self.parsed_payload = {"project_type": "mixed_use"}
                self.final_plan = {"actions": [], "meta": {}}
                self.warnings = []
                self.errors = []
                self.issues = []
                self.assumptions = []
                self.metadata = {"full_design_mode_seen": full_design_mode}

        def fake_load_orchestrator():
            def fake_orchestrate(req):
                return FakeResult(req.full_design_mode)

            return FakeRequest, fake_orchestrate

        result = run_orchestration(
            {
                "input_mode": "assisted",
                "prompt_text": "Design a mixed-use site.",
                "manual_fields": {},
                "full_design_mode": True,
                "meta": {},
            },
            load_orchestrator=fake_load_orchestrator,
            assess_design_readiness=lambda *_args, **_kwargs: None,
        )
        self.assertTrue(result["success"])
        self.assertTrue(result["metadata"]["full_design_mode_seen"])

    def test_run_orchestration_chat_site_update_updates_manual_fields(self):
        seen = {}

        @dataclass
        class FakeRequest:
            input_mode: str
            strict_mode: bool
            full_design_mode: bool = False
            prompt_text: Optional[str] = None
            image_path: Optional[str] = None
            manual_fields: dict = field(default_factory=dict)
            image_width_px: Optional[int] = None
            image_height_px: Optional[int] = None
            pixels_per_unit: Optional[float] = None
            plan_type_hint: Optional[str] = None
            units: str = "ft"
            allow_ai_fill_for_blanks: bool = True
            persist_trace_metadata: bool = True
            meta: dict = field(default_factory=dict)
            progress_callback: Optional[object] = None

        class FakeResult:
            success = True
            message = "ok"
            parsed_payload = {"project_type": "mixed_use"}
            final_plan = {"actions": [], "meta": {}}
            warnings = []
            errors = []
            issues = []
            assumptions = []
            metadata = {}

        def fake_load_orchestrator():
            def fake_orchestrate(req):
                seen["manual_fields"] = req.manual_fields
                seen["meta"] = req.meta
                return FakeResult()

            return FakeRequest, fake_orchestrate

        result = run_orchestration(
            {
                "input_mode": "assisted",
                "allow_ai_fill_for_blanks": True,
                "prompt_text": "make the site 14 acres",
                "manual_fields": {},
                "meta": {
                    "chat_command": {
                        "intent": "site_update",
                        "affected_systems": ["site", "layout"],
                        "command_payload": {
                            "site_area_acres": 14,
                            "lot_width": 781.1,
                            "lot_height": 781.1,
                        },
                    }
                },
            },
            load_orchestrator=fake_load_orchestrator,
            assess_design_readiness=lambda *_args, **_kwargs: None,
        )
        self.assertTrue(result["success"])
        self.assertEqual(seen["manual_fields"]["acreage"], 14)
        self.assertEqual(seen["manual_fields"]["lot"]["area_sf"], 609840.0)
        self.assertEqual(result["metadata"]["chat_command_execution"]["action_taken"], "updated_manual_fields")

    def test_run_orchestration_chat_building_command_updates_manual_fields_with_assumption(self):
        seen = {}

        @dataclass
        class FakeRequest:
            input_mode: str
            strict_mode: bool
            full_design_mode: bool = False
            prompt_text: Optional[str] = None
            image_path: Optional[str] = None
            manual_fields: dict = field(default_factory=dict)
            image_width_px: Optional[int] = None
            image_height_px: Optional[int] = None
            pixels_per_unit: Optional[float] = None
            plan_type_hint: Optional[str] = None
            units: str = "ft"
            allow_ai_fill_for_blanks: bool = True
            persist_trace_metadata: bool = True
            meta: dict = field(default_factory=dict)
            progress_callback: Optional[object] = None

        class FakeResult:
            success = True
            message = "ok"
            parsed_payload = {"project_type": "mixed_use"}
            final_plan = {"actions": [], "meta": {}}
            warnings = []
            errors = []
            issues = []
            assumptions = []
            metadata = {}

        def fake_load_orchestrator():
            def fake_orchestrate(req):
                seen["manual_fields"] = req.manual_fields
                seen["meta"] = req.meta
                return FakeResult()

            return FakeRequest, fake_orchestrate

        result = run_orchestration(
            {
                "input_mode": "assisted",
                "allow_ai_fill_for_blanks": True,
                "prompt_text": "add a 100 by 60 building",
                "manual_fields": {},
                "meta": {
                    "chat_command": {
                        "intent": "object_or_layout_command",
                        "affected_systems": ["layout"],
                        "assumptions": ["Object will be added as draft geometry at a planner-selected feasible location."],
                        "command_payload": {
                            "object_type": "building",
                            "operation": "create",
                            "width": 100,
                            "depth": 60,
                            "assumption_policy": "assisted",
                        },
                    }
                },
            },
            load_orchestrator=fake_load_orchestrator,
            assess_design_readiness=lambda *_args, **_kwargs: None,
        )
        self.assertTrue(result["success"])
        self.assertEqual(seen["manual_fields"]["buildings"][0]["w"], 100)
        self.assertEqual(seen["manual_fields"]["site_plan"]["building_depth"], 60)
        execution = result["metadata"]["chat_command_execution"]
        self.assertEqual(execution["action_taken"], "updated_manual_fields")
        self.assertIn("draft", " ".join(execution["assumptions"]).lower())

    def test_run_orchestration_strict_chat_building_blocks_missing_location(self):
        result = run_orchestration(
            {
                "input_mode": "user",
                "allow_ai_fill_for_blanks": False,
                "prompt_text": "add a 100 by 60 building",
                "manual_fields": {},
                "meta": {
                    "chat_command": {
                        "intent": "object_or_layout_command",
                        "affected_systems": ["layout"],
                        "command_payload": {
                            "object_type": "building",
                            "operation": "create",
                            "width": 100,
                            "depth": 60,
                            "assumption_policy": "strict",
                        },
                    }
                },
            },
            load_orchestrator=lambda: (object, lambda _req: None),
            assess_design_readiness=lambda *_args, **_kwargs: None,
        )
        self.assertFalse(result["success"])
        self.assertEqual(result["metadata"]["chat_command_execution"]["action_taken"], "blocked_before_orchestration")
        self.assertIn("object_location", result["missing_requirements"]["missing_fields"])

    def test_run_orchestration_parsed_command_blocks_without_canonical_edit_support(self):
        result = run_orchestration(
            {
                "input_mode": "assisted",
                "allow_ai_fill_for_blanks": True,
                "prompt_text": "change the road",
                "manual_fields": {},
                "meta": {
                    "chat_command": {
                        "intent": "object_or_layout_command",
                        "affected_systems": ["layout"],
                        "command_payload": {
                            "object_type": "road",
                            "operation": "update",
                            "assumption_policy": "assisted",
                        },
                    }
                },
            },
            load_orchestrator=lambda: (object, lambda _req: None),
            assess_design_readiness=lambda *_args, **_kwargs: None,
        )
        self.assertFalse(result["success"])
        execution = result["metadata"]["chat_command_execution"]
        self.assertEqual(execution["action_taken"], "blocked_before_orchestration")
        self.assertIn("canonical edit support", execution["action_blocked_reason"])

    def test_build_run_summary_reads_engineering_meta(self):
        summary = build_run_summary(
            {
                "success": True,
                "message": "ok",
                "metadata": {"_workflow_run_id": "run_123", "input_mode": "assisted"},
                "parsed_payload": {"strict_mode": False},
                "warnings": [],
                "errors": [],
                "final_plan": {
                    "meta": {
                        "engineering_status": {
                            "success": True,
                            "status": "complete",
                            "engineering_trust_score": 88.0,
                        },
                        "private_alpha_readiness": {
                            "status": "blocked",
                            "full_system_private_alpha_ready": False,
                            "review_only": True,
                            "construction_release_blocked": True,
                            "construction_release_allowed": False,
                            "blocker_count": 3,
                            "warning_count": 1,
                            "launch_recommendation": "blocked_before_private_alpha",
                            "next_actions": ["Attach golden scenario report."],
                        },
                        "truth_audit": {"success": True},
                        "deliverables": {
                            "requested": ["site_plan"],
                            "produced": ["site_plan"],
                            "failed": [],
                        },
                        "stage_completeness": {
                            "all_required_complete": True,
                            "required_stage_count": 2,
                            "complete_stage_count": 2,
                            "statuses": {"layout": "complete"},
                        },
                        "coordination": {"selected_group_strategy": "balanced_group"},
                        "optimization_summary": {
                            "active_goal": "balanced",
                            "overall_score": 82.5,
                            "component_scores": {
                                "parking_fit": 100.0,
                                "earthwork_balance": 78.0,
                                "drainage_capacity": 85.0,
                                "pipe_efficiency": 74.0,
                            },
                            "metrics": {
                                "parking_target": 24,
                                "parking_actual": 24,
                                "earthwork_net_cf": -320.0,
                            },
                            "recommendations": [
                                "Earthwork imbalance is still high; favor grading refinement and pad/road tie-in smoothing."
                            ],
                            "comparison_summary": {
                                "recommended_option_name": "Balanced Option",
                                "runner_up_option_name": "Drainage Option",
                                "score_gap": 6.5,
                                "tradeoff_summary": "Balanced Option beat Drainage Option by 6.5 points.",
                                "what_got_better": [{"label": "drainage"}],
                                "what_got_worse": [{"label": "parking"}],
                                "why_it_won": ["It led on drainage by 8.0 points."],
                            },
                        },
                        "convergence_summary": {
                            "converged": True,
                            "passes_run": 2,
                            "max_passes": 3,
                            "warning_count": 1,
                            "error_count": 0,
                            "unresolved_conflict_count": 0,
                            "assumption_summary": {
                                "count": 2,
                                "categories": ["drainage", "layout"],
                                "examples": [
                                    "Storage sized from Rational Method inflow estimate using planner runoff assumptions.",
                                    "Parking layout inferred from prompt constraints.",
                                ],
                            },
                            "unresolved_issue_categories": [],
                            "qa_issue_categories": ["drainage", "pipes"],
                            "rerun_summary": {
                                "total_reruns": 2,
                                "stage_rerun_counts": {"drainage": 1, "storm_pipes": 1},
                                "dominant_rerun_reasons": {
                                    "drainage": ["Dependency 'grading' is dirty."],
                                    "storm_pipes": ["Dependency 'drainage' is dirty."],
                                },
                                "stages_touched": ["drainage", "storm_pipes"],
                            },
                            "blocked_exports": ["storm"],
                            "blocked_reasons": ["storm_hydraulics_invalid"],
                            "pass_history": [
                                {
                                    "pass_index": 1,
                                    "qa_warning_count": 3,
                                    "qa_error_count": 1,
                                    "coordination_message": "Fix pass required.",
                                    "coordination_success": False,
                                    "fix_attempted": True,
                                    "fix_effective_change": True,
                                    "changed_targets": ["drainage", "storm_pipes"],
                                    "autofix_actions": ["drainage_retry_bias"],
                                    "dominant_issue_categories": ["drainage", "pipes"],
                                    "last_fix_attempt": {
                                        "target_count": 2,
                                        "primary_target": "drainage",
                                        "autofix_actions": ["drainage_retry_bias"],
                                    },
                                },
                                {
                                    "pass_index": 2,
                                    "qa_warning_count": 1,
                                    "qa_error_count": 0,
                                    "coordination_message": "Planner reached acceptable convergence.",
                                    "coordination_success": True,
                                    "fix_attempted": False,
                                    "fix_effective_change": False,
                                    "changed_targets": [],
                                    "autofix_actions": [],
                                    "dominant_issue_categories": [],
                                    "last_fix_attempt": {},
                                },
                            ],
                            "fix_summary": {
                                "effective_change": True,
                                "changed_targets": ["drainage", "storm_pipes"],
                                "autofix_actions": ["drainage_retry_bias"],
                                "dominant_issue_categories": ["drainage", "pipes"],
                                "last_fix_attempt": {
                                    "target_count": 2,
                                    "primary_target": "drainage",
                                    "autofix_actions": ["drainage_retry_bias"],
                                },
                            },
                        },
                    }
                },
            },
            source="unit_test",
        )
        self.assertEqual(summary["run_id"], "run_123")
        self.assertEqual(summary["engineering_status"]["status"], "complete")
        self.assertEqual(summary["private_alpha_readiness"]["status"], "blocked")
        self.assertEqual(summary["private_alpha_readiness"]["blocker_count"], 3)
        self.assertEqual(summary["private_alpha_readiness"]["primary_next_action"], "Attach golden scenario report.")
        self.assertEqual(summary["coordination_summary"]["selected_strategy"], "balanced_group")
        self.assertEqual(summary["optimization_summary"]["active_goal"], "balanced")
        self.assertEqual(summary["optimization_summary"]["component_scores"]["parking_fit"], 100.0)
        self.assertEqual(summary["optimization_summary"]["metrics"]["parking_target"], 24)
        self.assertEqual(summary["optimization_summary"]["comparison_summary"]["runner_up_option_name"], "Drainage Option")
        self.assertTrue(summary["convergence_summary"]["converged"])
        self.assertEqual(summary["convergence_summary"]["fix_summary"]["autofix_actions"], ["drainage_retry_bias"])
        self.assertEqual(summary["convergence_summary"]["assumption_summary"]["categories"], ["drainage", "layout"])
        self.assertEqual(summary["convergence_summary"]["qa_issue_categories"], ["drainage", "pipes"])
        self.assertEqual(summary["convergence_summary"]["rerun_summary"]["total_reruns"], 2)
        self.assertEqual(summary["convergence_summary"]["rerun_summary"]["stage_rerun_counts"]["drainage"], 1)
        self.assertEqual(summary["convergence_summary"]["blocked_exports"], ["storm"])
        self.assertEqual(summary["convergence_summary"]["blocked_reasons"], ["storm_hydraulics_invalid"])
        self.assertEqual(len(summary["convergence_summary"]["pass_history"]), 2)
        self.assertEqual(summary["convergence_summary"]["pass_history"][0]["last_fix_attempt"]["primary_target"], "drainage")
        self.assertTrue(summary["convergence_summary"]["pass_history"][0]["fix_attempted"])
        self.assertEqual(summary["convergence_summary"]["dominant_issue_categories"], ["drainage", "pipes"])
        self.assertEqual(summary["convergence_summary"]["last_fix_attempt"]["primary_target"], "drainage")
        self.assertTrue(summary["reliability_summary"]["retryable"])
        self.assertFalse(summary["reliability_summary"]["release_ready"])
        self.assertEqual(summary["reliability_summary"]["operational_state"], "retryable")
        self.assertEqual(summary["reliability_summary"]["persistence_scope"], "ephemeral")
        self.assertEqual(summary["reliability_summary"]["primary_attention"], "storm_hydraulics_invalid")
        self.assertEqual(summary["reliability_summary"]["blocked_export_count"], 1)
        self.assertEqual(summary["reliability_summary"]["private_alpha_status"], "blocked")
        self.assertFalse(summary["reliability_summary"]["private_alpha_ready"])
        self.assertEqual(summary["reliability_summary"]["private_alpha_blocker_count"], 3)
        self.assertEqual(summary["reliability_summary"]["trace"]["run_id"], "run_123")
        self.assertEqual(summary["phase_checkpoints"]["layout"]["status"], "complete")
        self.assertTrue(summary["phase_checkpoints"]["layout"]["has_data"])
        self.assertEqual(summary["phase_checkpoints"]["drainage_storm"]["status"], "pending")
        self.assertIn("storm", summary["phase_checkpoints"]["drainage_storm"]["blockers"][0])
        self.assertEqual(summary["phase_checkpoints"]["combined_view"]["status"], "blocked")
        self.assertEqual(summary["phase_checkpoints"]["combined_view"]["completed_phase_count"], 1)

    def test_build_run_summary_prefers_release_review_blockers_over_convergence(self):
        summary = build_run_summary(
            {
                "success": True,
                "final_plan": {
                    "actions": [{"layer": "PIPE"}],
                    "meta": {
                        "deliverables": {"requested": ["storm_pipe_plan"], "produced": ["storm_pipe_plan"], "failed": []},
                        "engineering_status": {"success": True, "status": "complete", "engineering_trust_score": 80.0},
                        "convergence_summary": {
                            "converged": True,
                            "blocked_exports": ["storm"],
                            "blocked_reasons": ["storm_graph_invalid"],
                            "unresolved_conflict_count": 0,
                        },
                        "release_review": {
                            "blocked_exports": [],
                            "blocked_reasons": [],
                        },
                    },
                },
            },
            source="unit_test",
        )
        self.assertEqual(summary["convergence_summary"]["blocked_exports"], [])
        self.assertEqual(summary["convergence_summary"]["blocked_reasons"], [])

    def test_build_run_summary_blocks_explicit_blocked_release_status_without_reasons(self):
        summary = build_run_summary(
            {
                "success": True,
                "final_plan": {
                    "actions": [{"layer": "LOT"}],
                    "meta": {
                        "deliverables": {"requested": [], "produced": [], "failed": []},
                        "convergence_summary": {
                            "converged": True,
                            "blocked_exports": [],
                            "blocked_reasons": [],
                            "unresolved_conflict_count": 0,
                        },
                        "release_review": {
                            "release_status": "blocked",
                        },
                    },
                },
            },
            source="unit_test",
        )

        self.assertFalse(summary["reliability_summary"]["release_ready"])
        self.assertEqual(summary["reliability_summary"]["operational_state"], "retryable")
        self.assertIn("release_status_blocked", summary["convergence_summary"]["blocked_reasons"])
        self.assertEqual(
            summary["convergence_summary"]["blocked_reason_details"][0]["code"],
            "release_status_blocked",
        )
        self.assertEqual(
            summary["reliability_summary"]["primary_attention_detail"]["code"],
            "release_status_blocked",
        )
        self.assertEqual(summary["phase_checkpoints"]["combined_view"]["status"], "blocked")

    def test_build_run_summary_blocks_explicit_release_review_not_ready(self):
        summary = build_run_summary(
            {
                "success": True,
                "final_plan": {
                    "actions": [{"layer": "LOT"}],
                    "meta": {
                        "deliverables": {"requested": [], "produced": [], "failed": []},
                        "convergence_summary": {
                            "converged": True,
                            "blocked_exports": [],
                            "blocked_reasons": [],
                            "unresolved_conflict_count": 0,
                        },
                        "release_review": {
                            "release_status": "ready",
                            "release_ready": False,
                        },
                    },
                },
            },
            source="unit_test",
        )

        self.assertFalse(summary["reliability_summary"]["release_ready"])
        self.assertEqual(summary["reliability_summary"]["operational_state"], "retryable")
        self.assertIn("release_review_not_ready", summary["convergence_summary"]["blocked_reasons"])
        self.assertEqual(summary["phase_checkpoints"]["combined_view"]["status"], "blocked")

    def test_build_run_summary_surfaces_failed_deliverables_as_blockers(self):
        summary = build_run_summary(
            {
                "success": True,
                "final_plan": {
                    "actions": [{"layer": "LOT"}],
                    "meta": {
                        "deliverables": {
                            "requested": ["site_plan", "report"],
                            "produced": ["site_plan", "report"],
                            "failed": ["report"],
                        },
                        "convergence_summary": {
                            "converged": True,
                            "blocked_exports": [],
                            "blocked_reasons": [],
                            "unresolved_conflict_count": 0,
                        },
                    },
                },
            },
            source="unit_test",
        )

        self.assertFalse(summary["reliability_summary"]["release_ready"])
        self.assertEqual(summary["ready_deliverables"], ["site_plan"])
        self.assertEqual(summary["produced_deliverables"], ["site_plan", "report"])
        self.assertEqual(summary["convergence_summary"]["blocked_reasons"], ["failed_deliverable_report"])
        self.assertEqual(summary["reliability_summary"]["primary_attention"], "failed_deliverable_report")

    def test_build_run_summary_blocks_missing_requested_deliverables(self):
        summary = build_run_summary(
            {
                "success": True,
                "final_plan": {
                    "actions": [{"layer": "LOT"}],
                    "meta": {
                        "deliverables": {
                            "requested": ["site_plan", "report"],
                            "produced": ["site_plan"],
                            "failed": [],
                        },
                        "convergence_summary": {
                            "converged": True,
                            "blocked_exports": [],
                            "blocked_reasons": [],
                            "unresolved_conflict_count": 0,
                        },
                    },
                },
            },
            source="unit_test",
        )

        self.assertFalse(summary["reliability_summary"]["release_ready"])
        self.assertIn("missing_deliverable_report", summary["convergence_summary"]["blocked_reasons"])
        self.assertEqual(summary["reliability_summary"]["primary_attention"], "missing_deliverable_report")

    def test_build_run_summary_blocks_planner_errors(self):
        summary = build_run_summary(
            {
                "success": True,
                "errors": ["Hydraulic solver failed after retries."],
                "final_plan": {
                    "actions": [{"layer": "PIPE"}],
                    "meta": {
                        "deliverables": {
                            "requested": ["storm_pipe_plan"],
                            "produced": ["storm_pipe_plan"],
                            "failed": [],
                        },
                        "convergence_summary": {
                            "converged": True,
                            "blocked_exports": [],
                            "blocked_reasons": [],
                            "unresolved_conflict_count": 0,
                        },
                    },
                },
            },
            source="unit_test",
        )

        self.assertFalse(summary["reliability_summary"]["release_ready"])
        self.assertEqual(summary["error_count"], 1)
        self.assertIn("planner_errors_present", summary["convergence_summary"]["blocked_reasons"])
        self.assertEqual(summary["reliability_summary"]["primary_attention"], "planner_errors_present")

    def test_build_run_summary_blocks_failed_planner_run(self):
        summary = build_run_summary(
            {
                "success": False,
                "final_plan": {
                    "actions": [{"layer": "LOT"}],
                    "meta": {
                        "deliverables": {
                            "requested": ["site_plan"],
                            "produced": ["site_plan"],
                            "failed": [],
                        },
                        "convergence_summary": {
                            "converged": True,
                            "blocked_exports": [],
                            "blocked_reasons": [],
                            "unresolved_conflict_count": 0,
                        },
                    },
                },
            },
            source="unit_test",
        )

        self.assertFalse(summary["reliability_summary"]["release_ready"])
        self.assertIn("planner_run_failed", summary["convergence_summary"]["blocked_reasons"])
        self.assertEqual(summary["reliability_summary"]["primary_attention"], "planner_run_failed")

    def test_build_run_summary_blocks_manual_validation_failures(self):
        summary = build_run_summary(
            {
                "success": True,
                "final_plan": {
                    "actions": [{"layer": "LOT"}],
                    "meta": {
                        "deliverables": {"requested": [], "produced": [], "failed": []},
                        "manual_validation": {
                            "failures": [
                                {
                                    "code": "MANUAL_STORM_HYDRAULIC_INVALID",
                                    "message": "Manual storm pipe hydraulic validation failed.",
                                    "system": "storm",
                                    "rule": "hydraulic_capacity",
                                }
                            ]
                        },
                        "convergence_summary": {
                            "converged": True,
                            "blocked_exports": [],
                            "blocked_reasons": [],
                            "unresolved_conflict_count": 0,
                        },
                    },
                },
            },
            source="unit_test",
        )

        self.assertFalse(summary["reliability_summary"]["release_ready"])
        self.assertEqual(summary["reliability_summary"]["manual_failure_count"], 1)
        self.assertIn(
            "manual_validation_manual_storm_hydraulic_invalid",
            summary["convergence_summary"]["blocked_reasons"],
        )
        self.assertEqual(
            summary["reliability_summary"]["primary_attention"],
            "manual_validation_manual_storm_hydraulic_invalid",
        )

    def test_build_run_summary_blocks_reactive_post_rerun_release_failures(self):
        summary = build_run_summary(
            {
                "success": True,
                "final_plan": {
                    "actions": [{"layer": "PIPE"}],
                    "meta": {
                        "deliverables": {
                            "requested": ["storm_pipe_plan"],
                            "produced": ["storm_pipe_plan"],
                            "failed": [],
                        },
                        "stage_completeness": {
                            "statuses": {
                                "layout": "complete",
                                "drainage": "complete",
                                "storm_pipes": "complete",
                                "qa": "complete",
                            },
                            "stages": [
                                {"stage_name": "layout", "completeness": "complete"},
                                {"stage_name": "drainage", "completeness": "complete"},
                                {"stage_name": "storm_pipes", "completeness": "complete"},
                                {"stage_name": "qa", "completeness": "complete"},
                            ],
                        },
                        "convergence_summary": {
                            "converged": True,
                            "blocked_exports": [],
                            "blocked_reasons": [],
                            "unresolved_conflict_count": 0,
                        },
                        "reactive_update_report": {
                            "post_rerun_production_ready": False,
                            "post_rerun_release_blockers": ["manual_validation_manual_storm_hydraulic_invalid"],
                        },
                    },
                },
            },
            source="unit_test",
        )

        reasons = summary["convergence_summary"]["blocked_reasons"]
        self.assertFalse(summary["reliability_summary"]["release_ready"])
        self.assertEqual(summary["reliability_summary"]["operational_state"], "retryable")
        self.assertIn("reactive_post_rerun_not_ready", reasons)
        self.assertIn("manual_validation_manual_storm_hydraulic_invalid", reasons)
        self.assertEqual(summary["phase_checkpoints"]["combined_view"]["status"], "blocked")

    def test_build_run_summary_does_not_count_assumed_stage_as_complete(self):
        summary = build_run_summary(
            {
                "success": True,
                "final_plan": {
                    "actions": [{"layer": "SITE"}],
                    "meta": {
                        "stage_completeness": {
                            "statuses": {
                                "layout": "complete",
                                "sanitary": "assumed",
                            },
                            "stages": [
                                {"stage_name": "layout", "completeness": "complete"},
                                {
                                    "stage_name": "sanitary",
                                    "message": "Sanitary placeholder assumed without tie-in evidence.",
                                    "completeness": "assumed",
                                },
                            ],
                        },
                        "deliverables": {"requested": [], "produced": [], "failed": []},
                        "convergence_summary": {
                            "converged": False,
                            "blocked_exports": [],
                            "blocked_reasons": [],
                            "unresolved_conflict_count": 0,
                        },
                    },
                },
            },
            source="unit_test",
        )

        self.assertEqual(summary["phase_checkpoints"]["utilities"]["status"], "partial")
        self.assertFalse(summary["phase_checkpoints"]["utilities"]["ready"])
        self.assertEqual(summary["phase_checkpoints"]["combined_view"]["completed_phase_count"], 1)

    def test_build_run_summary_blocks_release_when_construction_gate_is_blocked(self):
        summary = build_run_summary(
            {
                "success": True,
                "final_plan": {
                    "actions": [{"layer": "SITE"}],
                    "meta": {
                        "deliverables": {"requested": [], "produced": [], "failed": []},
                        "convergence_summary": {
                            "converged": True,
                            "blocked_exports": [],
                            "blocked_reasons": [],
                            "unresolved_conflict_count": 0,
                        },
                        "construction_readiness": {
                            "ready": False,
                            "status": "not_construction_ready",
                            "blockers": [{"area": "qa", "field": "truth_audit"}],
                        },
                    },
                },
            },
            source="unit_test",
        )

        self.assertFalse(summary["reliability_summary"]["release_ready"])
        self.assertEqual(summary["reliability_summary"]["operational_state"], "retryable")
        self.assertIn("construction_readiness_blocked", summary["convergence_summary"]["blocked_reasons"])

    def test_build_run_summary_surfaces_untraced_cost_package_artifact(self):
        summary = build_run_summary(
            {
                "success": True,
                "final_plan": {
                    "actions": [{"layer": "SITE"}],
                    "meta": {
                        "deliverables": {"requested": [], "produced": [], "failed": []},
                        "convergence_summary": {
                            "converged": True,
                            "blocked_exports": [],
                            "blocked_reasons": [],
                            "unresolved_conflict_count": 0,
                        },
                        "construction_readiness": {"ready": True, "status": "construction_ready", "blockers": []},
                        "construction_package_manifest": {
                            "release_allowed": False,
                            "construction_package_artifact_status": {
                                "package_present": True,
                                "missing": [],
                                "anonymous": [],
                                "stale": [],
                                "model_reference_present": True,
                                "model_matches_expected": True,
                                "untraced": [],
                                "mismatched": [],
                                "cost_untraced": ["COST-1"],
                            },
                        },
                    },
                },
            },
            source="unit_test",
        )

        reasons = summary["convergence_summary"]["blocked_reasons"]
        self.assertFalse(summary["reliability_summary"]["release_ready"])
        self.assertIn("construction_package_blocked", reasons)
        self.assertIn("construction_package_cost_untraced", reasons)

    def test_build_run_summary_blocks_false_allowed_package_without_release_proof(self):
        summary = build_run_summary(
            {
                "success": True,
                "final_plan": {
                    "actions": [{"layer": "SITE"}],
                    "meta": {
                        "deliverables": {"requested": [], "produced": [], "failed": []},
                        "convergence_summary": {
                            "converged": True,
                            "blocked_exports": [],
                            "blocked_reasons": [],
                            "unresolved_conflict_count": 0,
                        },
                        "construction_readiness": {"ready": True, "status": "construction_ready", "blockers": []},
                        "construction_package_manifest": {
                            "release_allowed": True,
                            "construction_package_artifact_status": {
                                "complete_for_release": True,
                                "model_matches_expected": True,
                                "release_ready_flag": None,
                            },
                        },
                    },
                },
            },
            source="unit_test",
        )

        reasons = summary["convergence_summary"]["blocked_reasons"]
        self.assertFalse(summary["reliability_summary"]["release_ready"])
        self.assertIn("construction_package_release_not_marked_ready", reasons)
        self.assertIn("construction_professional_release_missing", reasons)

    def test_build_run_summary_blocks_false_allowed_package_with_invalid_professional_proof(self):
        summary = build_run_summary(
            {
                "success": True,
                "final_plan": {
                    "actions": [{"layer": "SITE"}],
                    "meta": {
                        "deliverables": {"requested": [], "produced": [], "failed": []},
                        "convergence_summary": {
                            "converged": True,
                            "blocked_exports": [],
                            "blocked_reasons": [],
                            "unresolved_conflict_count": 0,
                        },
                        "construction_readiness": {"ready": True, "status": "construction_ready", "blockers": []},
                        "construction_package_manifest": {
                            "release_allowed": True,
                            "construction_package_artifact_status": {
                                "complete_for_release": True,
                                "model_matches_expected": True,
                                "release_ready_flag": True,
                            },
                            "professional_package_release_status": {
                                "professional_release_valid": None,
                                "model_matches_package": True,
                                "package_matches_review": True,
                            },
                        },
                    },
                },
            },
            source="unit_test",
        )

        reasons = summary["convergence_summary"]["blocked_reasons"]
        self.assertFalse(summary["reliability_summary"]["release_ready"])
        self.assertIn("construction_professional_release_invalid", reasons)
        self.assertNotIn("construction_professional_release_missing", reasons)

    def test_build_run_summary_marks_release_ready_skipped_phases_complete(self):
        summary = build_run_summary(
            {
                "success": True,
                "final_plan": {
                    "actions": [
                        {"layer": "BUILDING"},
                        {"layer": "PARKING"},
                        {"layer": "FG_CONTOUR"},
                        {"layer": "PIPE"},
                        {"layer": "UTILITY"},
                    ],
                    "meta": {
                        "deliverables": {
                            "requested": ["site_plan", "grading_plan", "storm_pipe_plan", "utility_plan"],
                            "produced": ["site_plan", "grading_plan", "storm_pipe_plan", "utility_plan"],
                            "failed": [],
                        },
                        "convergence_summary": {
                            "converged": True,
                            "unresolved_conflict_count": 0,
                            "blocked_exports": [],
                            "blocked_reasons": [],
                        },
                        "stage_completeness": {
                            "statuses": {
                                "layout": "partial",
                                "grading": "complete",
                                "drainage": "complete",
                                "storm_pipes": "complete",
                                "sanitary": "assumed",
                                "utility_network": "complete",
                                "coordination_resolution": "failed",
                                "qa": "complete",
                            },
                            "stages": [
                                {"stage_name": "layout", "message": "Stage skipped because canonical state is already clean.", "completeness": "partial"},
                                {"stage_name": "grading", "message": "Proposed grading surface built.", "completeness": "complete"},
                                {"stage_name": "drainage", "message": "Drainage network designed.", "completeness": "complete"},
                                {"stage_name": "storm_pipes", "message": "Storm pipe network designed.", "completeness": "complete"},
                                {"stage_name": "sanitary", "message": "Sanitary stage skipped because sanitary was not requested.", "completeness": "assumed"},
                                {"stage_name": "utility_network", "message": "Utility network designed.", "completeness": "complete"},
                                {"stage_name": "coordination_resolution", "message": "Coordination stage completed with unresolved conflicts.", "completeness": "failed"},
                                {"stage_name": "qa", "message": "Validation checks completed.", "completeness": "complete"},
                            ],
                        },
                    },
                },
            },
            source="unit_test",
        )
        self.assertTrue(summary["reliability_summary"]["release_ready"])
        self.assertEqual(summary["phase_checkpoints"]["layout"]["status"], "complete")
        self.assertTrue(summary["phase_checkpoints"]["layout"]["ready"])
        self.assertEqual(summary["phase_checkpoints"]["utilities"]["status"], "complete")
        self.assertTrue(summary["phase_checkpoints"]["utilities"]["ready"])
        self.assertEqual(summary["phase_checkpoints"]["coordination_validation"]["status"], "complete")
        self.assertTrue(summary["phase_checkpoints"]["coordination_validation"]["ready"])
        self.assertEqual(summary["phase_checkpoints"]["combined_view"]["status"], "ready")
        self.assertEqual(summary["phase_checkpoints"]["combined_view"]["completed_phase_count"], 5)

    def test_final_plan_from_result_blocks_unstable_storm_export(self):
        with self.assertRaises(HTTPException) as ctx:
            final_plan_from_result(
                {
                    "final_plan": {
                        "actions": [{"task": "polyline", "layer": "PIPE"}],
                        "meta": {
                            "deliverables": {"requested": ["storm_pipe_plan"], "produced": ["storm_pipe_plan"]},
                            "drainage": {"export_validation": {"ready": False, "reasons": ["primary_detention_missing"]}},
                            "storm_pipes": {
                                "graph_validation": {"valid": False},
                                "hydraulic_validation": {"valid": False},
                                "missing_data_segments": [],
                            },
                        },
                    }
                }
            )
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("primary_detention_missing", str(ctx.exception.detail))

    def test_final_plan_from_result_blocks_grading_fallback_export(self):
        with self.assertRaises(HTTPException) as ctx:
            final_plan_from_result(
                {
                    "final_plan": {
                        "actions": [{"task": "polyline", "layer": "FG_CONTOUR"}],
                        "meta": {
                            "deliverables": {"requested": ["grading_plan"], "produced": ["grading_plan"]},
                            "grading": {"export_validation": {"ready": False, "reasons": ["grading_fallback_used"]}},
                        },
                    }
                }
            )
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("grading_fallback_used", str(ctx.exception.detail))

    def test_final_plan_from_result_blocks_reactive_post_rerun_release_failures(self):
        with self.assertRaises(HTTPException) as ctx:
            final_plan_from_result(
                {
                    "final_plan": {
                        "actions": [{"task": "polyline", "layer": "PIPE"}],
                        "meta": {
                            "deliverables": {"requested": ["storm_pipe_plan"], "produced": ["storm_pipe_plan"]},
                            "reactive_update_report": {
                                "post_rerun_production_ready": False,
                                "post_rerun_release_blockers": ["manual_validation_manual_storm_hydraulic_invalid"],
                            },
                            "storm_pipes": {
                                "graph_validation": {"valid": True},
                                "hydraulic_validation": {"valid": True},
                                "missing_data_segments": [],
                            },
                        },
                    }
                }
            )
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("reactive downstream validation", str(ctx.exception.detail))
        self.assertIn("manual_validation_manual_storm_hydraulic_invalid", str(ctx.exception.detail))

    def test_final_plan_from_result_accepts_grading_layers_when_reason_list_is_empty(self):
        plan = final_plan_from_result(
            {
                "final_plan": {
                    "actions": [{"task": "polyline", "layer": "FG_CONTOUR"}],
                    "meta": {
                        "deliverables": {"requested": ["grading_plan"], "produced": ["grading_plan"]},
                        "grading": {"export_validation": {"ready": False, "reasons": []}},
                    },
                }
            }
        )
        self.assertEqual(plan["actions"][0]["layer"], "FG_CONTOUR")

    def test_final_plan_from_result_blocks_utility_fallback_export(self):
        with self.assertRaises(HTTPException) as ctx:
            final_plan_from_result(
                {
                    "final_plan": {
                        "actions": [{"task": "polyline", "layer": "UTILITY"}],
                        "meta": {
                            "deliverables": {"requested": ["utility_plan"], "produced": ["utility_plan"]},
                            "utilities": {"export_validation": {"ready": False, "reasons": ["utility_fallback_used"]}},
                        },
                    }
                }
            )
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("utility_fallback_used", str(ctx.exception.detail))

    def test_final_plan_from_result_blocks_required_construction_release_without_readiness(self):
        with self.assertRaises(HTTPException) as ctx:
            final_plan_from_result(
                {
                    "final_plan": {
                        "actions": [{"task": "polyline", "layer": "LOT", "points": [[0, 0], [100, 0]]}],
                        "meta": {"construction_release_required": True},
                    }
                }
            )
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("construction_readiness_missing", str(ctx.exception.detail))

    def test_final_plan_from_result_blocks_viable_fallback_utility_export(self):
        with self.assertRaises(HTTPException) as ctx:
            final_plan_from_result(
                {
                    "final_plan": {
                        "actions": [{"task": "polyline", "layer": "UTILITY"}],
                        "meta": {
                            "deliverables": {"requested": ["utility_plan"], "produced": ["utility_plan"]},
                            "utilities": {
                                "export_validation": {"ready": False, "reasons": ["utility_fallback_used"]},
                                "success": True,
                                "fallback_used": True,
                                "route_count": 1,
                                "shallow_segment_count": 0,
                                "gravity_slope_issue_count": 0,
                                "conflict_hooks": {
                                    "utility_segments": [
                                        {
                                            "name": "WATER-1",
                                            "hydraulic_mode": "pressurized",
                                            "route_points": [[10.0, 10.0], [60.0, 10.0], [90.0, 40.0]],
                                            "cover_start_ft": 4.0,
                                            "cover_end_ft": 4.0,
                                        }
                                    ]
                                },
                                "coordination": {
                                    "utility_related_unresolved_conflict_count": 0,
                                    "post_validation_valid": True,
                                },
                            },
                        },
                    }
                }
            )
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("utility_fallback_used", str(ctx.exception.detail))

    def test_final_plan_from_result_accepts_ready_storm_export_validation(self):
        plan = final_plan_from_result(
            {
                "final_plan": {
                    "actions": [{"task": "polyline", "layer": "PIPE"}],
                    "meta": {
                        "deliverables": {"requested": ["storm_pipe_plan"], "produced": ["storm_pipe_plan"]},
                        "drainage": {"export_validation": {"ready": True, "reasons": []}},
                        "storm_pipes": {
                            "export_validation": {"ready": True, "reasons": []},
                            "graph_validation": {"valid": False},
                            "hydraulic_validation": {"valid": False},
                            "missing_data_segments": ["legacy-fallback"],
                        },
                    },
                }
            }
        )
        self.assertEqual(plan["actions"][0]["layer"], "PIPE")

    def test_final_plan_from_result_blocks_persisted_storm_segments_without_summary_flags(self):
        with self.assertRaises(HTTPException) as ctx:
            final_plan_from_result(
                {
                    "final_plan": {
                        "actions": [{"task": "polyline", "layer": "PIPE"}],
                        "meta": {
                            "deliverables": {"requested": ["storm_pipe_plan"], "produced": ["storm_pipe_plan"]},
                            "drainage": {
                                "export_validation": {
                                    "ready": False,
                                    "reasons": [
                                        "storm_network_missing",
                                        "storm_graph_invalid",
                                        "storm_hydraulics_invalid",
                                    ],
                                }
                            },
                            "storm_pipes": {
                                "graph_validation": None,
                                "hydraulic_validation": None,
                                "missing_data_segments": None,
                                "storm_pipe_segments": [
                                    {
                                        "id": "P-001",
                                        "route_points": [[0.0, 0.0], [50.0, 0.0], [100.0, 25.0]],
                                        "length_ft": 110.0,
                                        "diameter_in": 24.0,
                                        "flow_cfs": 0.4,
                                        "source": "surface_fallback",
                                    }
                                ],
                                "source": "surface_fallback",
                            },
                        },
                    }
                }
            )
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("storm_graph_invalid", str(ctx.exception.detail))

    def test_final_plan_from_result_accepts_visible_grading_layers_when_export_flag_is_stale(self):
        plan = final_plan_from_result(
            {
                "final_plan": {
                    "actions": [
                        {"task": "polyline", "layer": "FG_CONTOUR"},
                        {"task": "point", "layer": "SPOT_FG"},
                    ],
                    "meta": {
                        "deliverables": {"requested": ["grading_plan"], "produced": ["grading_plan"]},
                        "grading": {"export_validation": {"ready": False, "reasons": ["grading_export_not_ready"]}},
                    },
                }
            }
        )
        self.assertEqual(plan["actions"][0]["layer"], "FG_CONTOUR")

    def test_final_plan_from_result_accepts_grading_deliverables_when_flag_is_generic(self):
        plan = final_plan_from_result(
            {
                "final_plan": {
                    "actions": [{"task": "polyline", "layer": "ROAD"}],
                    "meta": {
                        "deliverables": {
                            "requested": ["grading_plan"],
                            "produced": ["grading_plan", "contours", "spot_grades"],
                        },
                        "grading": {"export_validation": {"ready": False, "reasons": ["grading_export_not_ready"]}},
                    },
                }
            }
        )
        self.assertEqual(plan["actions"][0]["layer"], "ROAD")


if __name__ == "__main__":
    unittest.main()
