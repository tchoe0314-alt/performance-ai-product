import unittest
from unittest.mock import patch

from backend.planning.runtime import RoutingDecision
from planner import build_reactive_partial_plan


class ReactivePartialRerunEntrypointTests(unittest.TestCase):
    def test_partial_entrypoint_requires_checkpoint_plan(self) -> None:
        with self.assertRaises(ValueError):
            build_reactive_partial_plan({"project_name": "No Checkpoint"}, changed_stages=["grading"])

    def test_partial_entrypoint_restores_checkpoint_and_marks_only_impacted_stages_dirty(self) -> None:
        captured = {}
        checkpoint = {
            "project_name": "Checkpoint",
            "actions": [{"task": "rectangle", "layer": "BUILDING", "x": 0, "y": 0, "w": 10, "h": 10}],
            "meta": {
                "stage_completeness": {
                    "statuses": {
                        "layout": "complete",
                        "grading": "complete",
                        "drainage": "complete",
                        "storm_pipes": "complete",
                    }
                },
                "grading": {"proposed_surface": {"id": "surface-1"}},
                "drainage": {"structures": [{"id": "inlet-1"}]},
                "storm_pipes": {"segments": [{"id": "storm-1"}]},
            },
        }

        def fake_build_plan_from_parsed(payload, route, progress_callback=None):
            captured["payload"] = payload
            captured["route"] = route
            return {
                "project_name": "Reactive Partial",
                "actions": [],
                "meta": {
                    "stage_results": [
                        {"stage_name": "grading", "success": True, "meta": {"completeness": "complete"}},
                        {"stage_name": "drainage", "success": True, "meta": {"completeness": "complete"}},
                    ]
                },
            }

        def fake_finalize_plan(raw, *, parsed, route):
            final = dict(raw)
            final.setdefault("meta", {})
            final["meta"]["parsed_meta"] = dict(parsed.get("meta") or {})
            final["meta"]["route_path"] = route.path
            return final

        with patch("planner.choose_routing_path", return_value=RoutingDecision(path="model_first", reasons=[])), patch(
            "planner.build_plan_from_parsed",
            side_effect=fake_build_plan_from_parsed,
        ), patch("planner.finalize_plan", side_effect=fake_finalize_plan):
            final = build_reactive_partial_plan(
                {
                    "project_name": "Reactive",
                    "meta": {
                        "reactive_checkpoint_final_plan": checkpoint,
                    },
                },
                changed_stages=["grading"],
            )

        payload_meta = captured["payload"]["meta"]
        resume_plan = payload_meta["orchestrator_meta"]["runtime_resume"]["final_plan"]
        dirty_state = payload_meta["system_dirty_state"]
        self.assertEqual(resume_plan["project_name"], "Checkpoint")
        self.assertEqual(dirty_state["grading"]["state"], "dirty")
        self.assertEqual(dirty_state["drainage"]["state"], "dirty")
        self.assertIn("storm_pipes", dirty_state)
        self.assertNotIn("layout", dirty_state)
        self.assertEqual(payload_meta["reactive_partial_rerun"]["checkpoint_restored"], True)
        self.assertEqual(final["meta"]["route_path"], "model_first")
        self.assertTrue(final["meta"]["reactive_partial_rerun"]["enabled"])


if __name__ == "__main__":
    unittest.main()
