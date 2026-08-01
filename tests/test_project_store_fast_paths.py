import tempfile
import unittest
from pathlib import Path
from unittest import mock

from backend.application.project_workflows import review_project_candidates, save_project_record
from backend.planning.candidate_review_inbox import build_candidate_review_inbox
from backend.services.auth_store import AuthStore
from backend.services.database import Database
from backend.services.project_store import ProjectStore


class ProjectStoreFastPathTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name) / "civora-fast-path.db")
        registered = AuthStore(self.db).register_user(
            email="fast-path@example.com",
            password="password123",
            name="Fast Path",
        )
        self.user_id = registered["user"]["user_id"]
        self.store = ProjectStore(self.db)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    @staticmethod
    def _site_inputs():
        map_report = {
            "feature_candidates": [
                {
                    "candidate_id": "building-1",
                    "feature_type": "building_footprint",
                    "source_type": "official_gis",
                    "source_name": "City buildings",
                    "confidence": 0.9,
                    "acceptance_status": "pending",
                }
            ]
        }
        return {
            "address": "201 W Colfax Ave, Denver, CO 80202",
            "map_feature_detection_report_v1": map_report,
            "candidate_review_inbox_v1": build_candidate_review_inbox(
                {"map_feature_detection_report_v1": map_report}
            ),
        }

    def _saved_project(self):
        return self.store.save_project(
            user_id=self.user_id,
            project_id=None,
            name="Untitled Project",
            project_input={"meta": {"site_inputs": self._site_inputs()}},
            latest_result={
                "large-result-sentinel": ["generated-payload"] * 1000,
                "final_plan": {"project_name": "Generated"},
            },
        )

    def test_project_shell_does_not_deserialize_generated_result(self) -> None:
        saved = self._saved_project()
        import backend.services.project_store as project_store_module

        original_loads = project_store_module._json_loads

        def guarded_loads(value, default):
            if isinstance(value, str) and "large-result-sentinel" in value:
                raise AssertionError("project shell parsed the generated result")
            return original_loads(value, default)

        with mock.patch.object(project_store_module, "_json_loads", side_effect=guarded_loads):
            shell = self.store.get_project_shell(
                user_id=self.user_id,
                project_id=saved["project_id"],
            )

        self.assertIsNotNone(shell)
        self.assertEqual(shell["latest_result"], {})
        self.assertTrue(shell["has_result"])
        self.assertEqual(shell["name"], "201 W Colfax Ave Site")
        latest = self.store.get_project_latest_result(
            user_id=self.user_id,
            project_id=saved["project_id"],
        )
        self.assertIn("large-result-sentinel", latest)

    def test_candidate_decision_uses_shell_and_preserves_generated_result(self) -> None:
        saved = self._saved_project()

        with mock.patch.object(
            self.store,
            "get_project",
            side_effect=AssertionError("candidate review loaded the full project"),
        ):
            result = review_project_candidates(
                project_store=self.store,
                user_id=self.user_id,
                project_id=saved["project_id"],
                candidate_ids=["building-1"],
                action="accept",
                reviewer_id=self.user_id,
            )

        self.assertEqual(result["candidate_review_inbox_v1"]["counts"]["accepted"], 1)
        self.assertEqual(result["candidate_review_inbox_v1"]["counts"]["pending"], 0)
        self.assertEqual(result["project"]["name"], "201 W Colfax Ave Site")
        latest = self.store.get_project_latest_result(
            user_id=self.user_id,
            project_id=saved["project_id"],
        )
        self.assertIn("large-result-sentinel", latest)
        shell = self.store.get_project_shell(
            user_id=self.user_id,
            project_id=saved["project_id"],
        )
        inbox = shell["project_input"]["meta"]["site_inputs"]["candidate_review_inbox_v1"]
        self.assertEqual(inbox["counts"]["accepted"], 1)

    def test_autosave_uses_shell_and_preserves_generated_result(self) -> None:
        saved = self._saved_project()

        with mock.patch.object(
            self.store,
            "get_project",
            side_effect=AssertionError("autosave loaded the full project"),
        ), mock.patch.object(
            self.store,
            "get_project_latest_result",
            side_effect=AssertionError("autosave parsed the generated result"),
        ):
            response = save_project_record(
                project_store=self.store,
                user_id=self.user_id,
                payload_data={
                    "project_id": saved["project_id"],
                    "name": "Untitled Project",
                    "project_input": {"manual_fields": {"project_name": "Denver Review"}},
                    "metadata": {"source": "autosave"},
                },
            )

        self.assertTrue(response["success"])
        self.assertTrue(response["project"]["has_result"])
        self.assertEqual(response["project"]["name"], "201 W Colfax Ave Site")
        latest = self.store.get_project_latest_result(
            user_id=self.user_id,
            project_id=saved["project_id"],
        )
        self.assertIn("large-result-sentinel", latest)
        shell = self.store.get_project_shell(
            user_id=self.user_id,
            project_id=saved["project_id"],
        )
        self.assertEqual(shell["metadata"]["source"], "autosave")
        self.assertEqual(
            shell["project_input"]["manual_fields"]["project_name"],
            "Denver Review",
        )

    def test_stale_autosave_cannot_rollback_candidate_decision(self) -> None:
        saved = self._saved_project()
        stale_project_input = self.store.get_project_shell(
            user_id=self.user_id,
            project_id=saved["project_id"],
        )["project_input"]
        review_project_candidates(
            project_store=self.store,
            user_id=self.user_id,
            project_id=saved["project_id"],
            candidate_ids=["building-1"],
            action="accept",
            reviewer_id=self.user_id,
        )

        save_project_record(
            project_store=self.store,
            user_id=self.user_id,
            payload_data={
                "project_id": saved["project_id"],
                "name": "Untitled Project",
                "project_input": stale_project_input,
                "metadata": {"source": "late_autosave"},
            },
        )

        shell = self.store.get_project_shell(
            user_id=self.user_id,
            project_id=saved["project_id"],
        )
        site_inputs = shell["project_input"]["meta"]["site_inputs"]
        self.assertEqual(site_inputs["candidate_review_inbox_v1"]["counts"]["accepted"], 1)
        self.assertEqual(site_inputs["candidate_review_inbox_v1"]["counts"]["pending"], 0)
        self.assertEqual(len(site_inputs["candidate_review_decisions_v1"]), 1)

    def test_new_address_can_replace_candidate_review_state(self) -> None:
        saved = self._saved_project()
        review_project_candidates(
            project_store=self.store,
            user_id=self.user_id,
            project_id=saved["project_id"],
            candidate_ids=["building-1"],
            action="accept",
            reviewer_id=self.user_id,
        )
        new_site_inputs = self._site_inputs()
        new_site_inputs["address"] = "20525 Margo St, Gretna, NE 68028"

        self.store.save_project_shell(
            user_id=self.user_id,
            project_id=saved["project_id"],
            name="Untitled Project",
            project_input={"meta": {"site_inputs": new_site_inputs}},
        )

        shell = self.store.get_project_shell(
            user_id=self.user_id,
            project_id=saved["project_id"],
        )
        site_inputs = shell["project_input"]["meta"]["site_inputs"]
        self.assertEqual(site_inputs["address"], "20525 Margo St, Gretna, NE 68028")
        self.assertEqual(site_inputs["candidate_review_inbox_v1"]["counts"]["pending"], 1)
        self.assertNotIn("candidate_review_decisions_v1", site_inputs)


if __name__ == "__main__":
    unittest.main()
