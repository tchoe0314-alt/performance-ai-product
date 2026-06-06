import unittest

from backend.application.chat_workflows import decide_chat


class ApplicationChatWorkflowsTest(unittest.TestCase):
    def test_decide_chat_requires_message(self):
        with self.assertRaises(ValueError):
            decide_chat({}, decide_chat_message=lambda payload: payload)

    def test_decide_chat_delegates_to_parser(self):
        called = {}

        def fake_decider(payload):
            called["payload"] = dict(payload)
            return {"success": True, "intent": "conversation"}

        result = decide_chat(
            {"message": "hello", "context": {"strategy_mode": "assisted"}},
            decide_chat_message=fake_decider,
        )
        self.assertEqual(result["intent"], "conversation")
        self.assertEqual(called["payload"]["message"], "hello")

    def test_decide_chat_hydrates_canonical_project_context(self):
        called = {}

        class FakeProjectStore:
            def get_project(self, *, user_id, project_id):
                return {
                    "project_id": project_id,
                    "name": "Saved Project",
                    "description": "",
                    "session_id": None,
                    "tags": [],
                    "project_input": {"project_type": "mixed_use"},
                    "latest_result": {
                        "success": True,
                        "final_plan": {
                            "meta": {
                                "convergence_summary": {
                                    "blocked_reasons": ["storm_graph_invalid"],
                                },
                                "deliverables": {"produced": ["preview"]},
                            }
                        },
                    },
                    "session_state": {},
                    "metadata": {},
                }

            def save_project(self, **_kwargs):
                return {}

        def fake_decider(payload):
            called["context"] = dict(payload["context"])
            return {"success": True, "intent": "conversation"}

        result = decide_chat(
            {
                "message": "why is storm blocked",
                "context": {
                    "current_project": {"project_id": "project_123", "name": "Stale Project"},
                    "convergence_summary": {},
                },
            },
            decide_chat_message=fake_decider,
            project_store=FakeProjectStore(),
            user_id="user_1",
        )
        self.assertEqual(result["intent"], "conversation")
        self.assertTrue(called["context"]["has_plan"])
        self.assertEqual(called["context"]["current_project"]["name"], "Saved Project")
        self.assertEqual(called["context"]["convergence_summary"]["blocked_reasons"], ["storm_graph_invalid"])

    def test_decide_chat_hydrates_export_audit_blockers(self):
        called = {}

        class FakeProjectStore:
            def get_project(self, *, user_id, project_id):
                return {
                    "project_id": project_id,
                    "name": "Saved Project",
                    "description": "",
                    "session_id": None,
                    "tags": [],
                    "project_input": {},
                    "latest_result": {
                        "success": True,
                        "final_plan": {
                            "meta": {
                                "export_audit": {
                                    "export_blocked": True,
                                    "blocked_reasons": ["canonical_id_traceability_missing"],
                                },
                            }
                        },
                    },
                    "session_state": {},
                    "metadata": {},
                }

            def save_project(self, **_kwargs):
                return {}

        def fake_decider(payload):
            called["context"] = dict(payload["context"])
            return {"success": True, "intent": "conversation"}

        decide_chat(
            {
                "message": "what do I need before export",
                "context": {"current_project": {"project_id": "project_123"}},
            },
            decide_chat_message=fake_decider,
            project_store=FakeProjectStore(),
            user_id="user_1",
        )
        self.assertEqual(called["context"]["current_export_audit"]["blocked_reasons"], ["canonical_id_traceability_missing"])
        self.assertIn("canonical_id_traceability_missing", called["context"]["convergence_summary"]["blocked_reasons"])
        self.assertIn("export", called["context"]["convergence_summary"]["blocked_exports"])


if __name__ == "__main__":
    unittest.main()
