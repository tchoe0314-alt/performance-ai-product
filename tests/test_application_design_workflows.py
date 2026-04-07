import unittest

from fastapi import HTTPException

from backend.application.design_workflows import build_run_summary, final_plan_from_result


class ApplicationDesignWorkflowsTest(unittest.TestCase):
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
        self.assertEqual(summary["reliability_summary"]["trace"]["run_id"], "run_123")

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

    def test_final_plan_from_result_accepts_viable_fallback_utility_export(self):
        plan = final_plan_from_result(
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
        self.assertEqual(plan["actions"][0]["layer"], "UTILITY")

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

    def test_final_plan_from_result_accepts_persisted_storm_segments_without_summary_flags(self):
        plan = final_plan_from_result(
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
        self.assertEqual(plan["actions"][0]["layer"], "PIPE")

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
