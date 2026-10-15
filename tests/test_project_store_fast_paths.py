import tempfile
import unittest
from pathlib import Path
from unittest import mock

from backend.application.project_workflows import review_project_candidates, save_project_record
from backend.planning.candidate_review_inbox import build_candidate_review_inbox
from backend.services.auth_store import AuthStore
from backend.services.database import Database
from backend.services.project_store import ProjectStore
from backend.services.canonical_project import PROJECT_DOCUMENT_KEY, ProjectDocumentError, new_project_document
from backend.services.canonical_canvas import resolve_canvas_input, with_canvas_snapshot


class ProjectStoreFastPathTests(unittest.TestCase):
    def assertCanonicalContentPreserved(self, actual, expected):
        # Persistence adds project identity and owned result/history adapters.
        # Every incoming independent collection must still survive exactly.
        for section, value in expected.items():
            if section in {"project", "site", "extensions"}:
                for key, item in value.items():
                    self.assertEqual(actual[section][key], item)
            elif isinstance(value, list):
                self.assertEqual([item for item in actual[section] if item.get("owner") != "project_record_v1"], value)
            else:
                self.assertEqual(actual[section], value)

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

    def test_canvas_adapter_reopens_and_internal_legacy_writes_stay_coherent(self) -> None:
        compiled = with_canvas_snapshot({"manual_fields": {"site_objects": [
            {"id": "office", "type": "office_building", "x": 125.25, "y": 100, "w": 160, "d": 90},
        ]}, "meta": {"site_inputs": {"address": "Fixture"}}})
        saved = self.store.save_project(user_id=self.user_id, project_id=None, name="Pilot", project_input=compiled)
        for full in (True, False):
            restored = self.store.get_project(user_id=self.user_id, project_id=saved["project_id"])
            incoming = resolve_canvas_input(restored["project_input"])
            incoming["manual_fields"]["site_objects"][0]["x"] += 10
            expected = incoming["manual_fields"]["site_objects"][0]["x"]
            saver = self.store.save_project if full else self.store.save_project_shell
            saver(user_id=self.user_id, project_id=saved["project_id"], name="Pilot", project_input=incoming,
                  expected_revision=restored["revision_token"])
            reopened = ProjectStore(Database(Path(self.tmp.name) / "civora-fast-path.db"))
            persisted = reopened.get_project(user_id=self.user_id, project_id=saved["project_id"])
            self.assertEqual(resolve_canvas_input(persisted["project_input"])["manual_fields"]["site_objects"][0]["x"], expected)

    def test_new_canonical_snapshot_beats_conflicting_legacy_save_shadow(self) -> None:
        compiled = with_canvas_snapshot({"manual_fields": {"site_objects": [
            {"id": "office", "type": "office_building", "x": 125.25, "y": 100, "w": 160, "d": 90},
        ]}})
        compiled["manual_fields"]["site_objects"][0]["x"] = 999
        saved = self.store.save_project(user_id=self.user_id, project_id=None, name="Pilot", project_input=compiled)
        self.assertEqual(saved["project_input"]["manual_fields"]["site_objects"][0]["x"], 125.25)

    def test_canonical_snapshot_reopens_and_full_and_shell_saves_clear_objects(self) -> None:
        document = new_project_document(name="Canonical pilot")
        document["roads"] = [{"id": "road-1", "geometry": [[0.125, -2], [40, 80]], "width": 40}]
        document["buildings"] = [{"id": "building-1"}]
        document["extensions"] = {"import_metadata": {"custom": False}}
        saved = self.store.save_project(
            user_id=self.user_id, project_id=None, name="Canonical pilot",
            project_input={PROJECT_DOCUMENT_KEY: document, "legacy": {"sentinel": "preserve"}},
            latest_result={"sentinel": "generated"},
        )
        reopened = ProjectStore(Database(Path(self.tmp.name) / "civora-fast-path.db"))
        restored = reopened.get_project(user_id=self.user_id, project_id=saved["project_id"])
        self.assertCanonicalContentPreserved(restored["project_input"][PROJECT_DOCUMENT_KEY], document)
        self.assertIsNone(reopened.get_project(user_id="different-user", project_id=saved["project_id"]))
        for shell in (False, True):
            document["buildings"] = []
            document["roads"] = [] if shell else document["roads"]
            saver = reopened.save_project_shell if shell else reopened.save_project
            saver(user_id=self.user_id, project_id=saved["project_id"], name="Canonical pilot",
                  project_input={PROJECT_DOCUMENT_KEY: document},
                  expected_revision=reopened.get_project(user_id=self.user_id,project_id=saved["project_id"])["revision_token"])
            persisted = reopened.get_project(user_id=self.user_id, project_id=saved["project_id"])
            self.assertCanonicalContentPreserved(persisted["project_input"][PROJECT_DOCUMENT_KEY], document)
            self.assertEqual(persisted["project_input"]["legacy"], {"sentinel": "preserve"})
            self.assertEqual(persisted["latest_result"], {"sentinel": "generated"})

    def test_invalid_canonical_snapshot_never_overwrites_saved_project(self) -> None:
        saved = self._saved_project()
        for saver in (self.store.save_project, self.store.save_project_shell):
            with self.assertRaises(ProjectDocumentError):
                saver(user_id=self.user_id, project_id=saved["project_id"], name="Invalid update",
                      project_input={PROJECT_DOCUMENT_KEY: {}},expected_revision=saved["revision_token"])
            unchanged = self.store.get_project(user_id=self.user_id, project_id=saved["project_id"])
            self.assertEqual(unchanged["name"], saved["name"])
            self.assertEqual(unchanged["project_input"], saved["project_input"])

    def test_workflow_full_and_autosave_paths_preserve_canonical_deletions(self) -> None:
        document = new_project_document()
        document["utilities"] = [{"id": "pipe-1", "geometry": [[0, 1], [40, 1]]}]
        saved = self.store.save_project(user_id=self.user_id, project_id=None, name="Pilot",
                                        project_input={PROJECT_DOCUMENT_KEY: document})
        for full_save in (True, False):
            document["utilities"] = []
            payload = {"project_id": saved["project_id"], "name": "Pilot",
                       "project_input": {PROJECT_DOCUMENT_KEY: document},
                       "expected_revision":self.store.get_project(user_id=self.user_id,project_id=saved["project_id"])["revision_token"]}
            if full_save:
                payload["latest_result"] = {"sentinel": "generated"}
            result = save_project_record(project_store=self.store, user_id=self.user_id, payload_data=payload)
            self.assertTrue(result["success"])
            persisted = self.store.get_project(user_id=self.user_id, project_id=saved["project_id"])
            expected = {**document, "project": {"name": "Pilot"}}
            self.assertCanonicalContentPreserved(persisted["project_input"][PROJECT_DOCUMENT_KEY], expected)
            if full_save:
                document["utilities"] = [{"id": "pipe-2"}]
                self.store.save_project_shell(expected_revision=self.store.get_project(user_id=self.user_id, project_id=saved["project_id"])["revision_token"], user_id=self.user_id, project_id=saved["project_id"], name="Pilot",
                                              project_input={PROJECT_DOCUMENT_KEY: document})

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

    def test_native_road_and_pipe_metadata_survive_database_reopen(self) -> None:
        objects = [
            {"id": "road", "type": "road", "x": 24.25, "y": 24.5, "w": 100, "d": 220.621778,
             "placed": True, "geometry_type": "polygon", "geometry": [[24.25, 24.5], [124.25, 24.5], [74.25, 245.121778]],
             "meta": {"cul_de_sac_v1": {"version": 1, "bulbRadiusFt": 50, "roadWidthFt": 40, "islandRadiusFt": 15, "transitionRadiusFt": 20, "coordinateUnits": "ft"}}},
            {"id": "pipe", "type": "utility_corridor", "placed": True, "geometry_type": "polyline",
             "geometry": [[10.125, 50], [140.75, 50]], "meta": {"asset_kind": "pipe", "pipe_diameter_ft": 1,
             "vertical_extent_v1": {"version": 1, "minFt": -6, "maxFt": -5, "datum": "benchmark", "source": "reviewed test drawing", "reviewed": True, "requiredClearanceFt": 1}}},
        ]
        saved = self.store.save_project(user_id=self.user_id, project_id=None, name="Typed object study",
                                        project_input={"manual_fields": {"site_objects": objects}}, latest_result={})
        reopened = ProjectStore(Database(Path(self.tmp.name) / "civora-fast-path.db"))
        restored = reopened.get_project(user_id=self.user_id, project_id=saved["project_id"])
        self.assertEqual(restored["project_input"]["manual_fields"]["site_objects"], objects)
        self.assertIsNone(reopened.get_project(user_id="different-user", project_id=saved["project_id"]))

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
                    "expected_revision": saved["revision_token"],
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

        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as conflict:
            save_project_record(
                project_store=self.store,
                user_id=self.user_id,
                payload_data={
                    "project_id": saved["project_id"],
                    "name": "Untitled Project",
                    "project_input": stale_project_input,
                    "metadata": {"source": "late_autosave"},
                    "expected_revision": saved["revision_token"],
                },
            )
        self.assertEqual(conflict.exception.status_code, 409)

        shell = self.store.get_project_shell(
            user_id=self.user_id,
            project_id=saved["project_id"],
        )
        site_inputs = shell["project_input"]["meta"]["site_inputs"]
        self.assertEqual(site_inputs["candidate_review_inbox_v1"]["counts"]["accepted"], 1)
        self.assertEqual(site_inputs["candidate_review_inbox_v1"]["counts"]["pending"], 0)
        self.assertEqual(len(site_inputs["candidate_review_decisions_v1"]), 1)
        self.assertEqual(len(site_inputs["civora_vision_ground_truth_ledger_v1"]["events"]), 1)
        self.assertTrue(site_inputs["civora_vision_review_workspace_v1"]["ledger_summary"]["integrity_valid"])

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

        self.store.save_project_shell(expected_revision=self.store.get_project(user_id=self.user_id, project_id=saved["project_id"])["revision_token"],
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
        self.assertNotIn("civora_vision_ground_truth_ledger_v1", site_inputs)
        self.assertNotIn("civora_vision_split_registry_v1", site_inputs)


if __name__ == "__main__":
    unittest.main()
