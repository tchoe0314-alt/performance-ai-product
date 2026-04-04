import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException

from backend.application.project_workflows import (
    artifact_summary,
    delete_project_record,
    get_project_detail,
    list_projects,
    merge_project_metadata,
    result_from_payload,
    save_project_record,
    save_project_workflow_update,
)


class FakeProjectStore:
    def __init__(self, project=None):
        self.project = project
        self.saved_payload = None
        self.deleted = False

    def list_projects(self, *, user_id: str):
        if self.project and user_id == self.project.get("user_id"):
            return [{"project_id": self.project["project_id"], "name": self.project.get("name", "")}]
        return []

    def get_project(self, *, user_id: str, project_id: str):
        if self.project and user_id == self.project.get("user_id") and project_id == self.project.get("project_id"):
            return dict(self.project)
        return None

    def save_project(self, **kwargs):
        self.saved_payload = dict(kwargs)
        self.project = {
            "user_id": kwargs["user_id"],
            "project_id": kwargs["project_id"],
            "name": kwargs["name"],
            "description": kwargs["description"],
            "session_id": kwargs["session_id"],
            "tags": kwargs["tags"],
            "project_input": kwargs["project_input"],
            "latest_result": kwargs["latest_result"],
            "session_state": kwargs["session_state"],
            "metadata": kwargs["metadata"],
        }
        return dict(self.project)

    def delete_project(self, *, user_id: str, project_id: str):
        if self.project and user_id == self.project.get("user_id") and project_id == self.project.get("project_id"):
            self.deleted = True
            self.project = None
            return True
        return False


class ApplicationProjectWorkflowsTest(unittest.TestCase):
    def test_result_from_payload_prefers_saved_project_result(self):
        store = FakeProjectStore(
            {
                "user_id": "u1",
                "project_id": "p1",
                "latest_result": {"final_plan": {"project_name": "Saved"}},
            }
        )
        result = result_from_payload(
            project_store=store,
            user_id="u1",
            project_id="p1",
            result={},
            final_plan={},
        )
        self.assertEqual(result["final_plan"]["project_name"], "Saved")

    def test_result_from_payload_raises_when_missing(self):
        store = FakeProjectStore()
        with self.assertRaises(HTTPException) as ctx:
            result_from_payload(
                project_store=store,
                user_id="u1",
                project_id=None,
                result={},
                final_plan={},
            )
        self.assertEqual(ctx.exception.status_code, 400)

    def test_list_projects_wraps_store_output(self):
        store = FakeProjectStore({"user_id": "u1", "project_id": "p1", "name": "Demo"})
        response = list_projects(project_store=store, user_id="u1")
        self.assertTrue(response["success"])
        self.assertEqual(response["projects"][0]["project_id"], "p1")

    def test_get_project_detail_wraps_store_output(self):
        store = FakeProjectStore({"user_id": "u1", "project_id": "p1", "name": "Demo"})
        response = get_project_detail(project_store=store, user_id="u1", project_id="p1")
        self.assertTrue(response["success"])
        self.assertEqual(response["project"]["name"], "Demo")

    def test_merge_project_metadata_limits_runs_and_artifacts(self):
        metadata = {
            "workflow": {
                "runs": [{"run_id": f"run_{idx}"} for idx in range(25)],
                "artifacts": [{"artifact_id": f"artifact_{idx}"} for idx in range(45)],
            }
        }
        merged = merge_project_metadata(
            metadata,
            run_summary={"run_id": "run_new"},
            artifact_summary={"artifact_id": "artifact_new"},
        )
        self.assertEqual(merged["workflow"]["runs"][0]["run_id"], "run_new")
        self.assertEqual(len(merged["workflow"]["runs"]), 20)
        self.assertEqual(merged["workflow"]["artifacts"][0]["artifact_id"], "artifact_new")
        self.assertEqual(len(merged["workflow"]["artifacts"]), 40)

    def test_save_project_workflow_update_persists_metadata(self):
        store = FakeProjectStore(
            {
                "user_id": "u1",
                "project_id": "p1",
                "name": "Test",
                "description": "",
                "session_id": None,
                "tags": [],
                "project_input": {},
                "latest_result": {"final_plan": {"project_name": "Test"}},
                "session_state": {},
                "metadata": {},
            }
        )
        updated = save_project_workflow_update(
            project_store=store,
            user_id="u1",
            project_id="p1",
            run_summary={"run_id": "run_1"},
            artifact_summary={"artifact_id": "artifact_1"},
        )
        self.assertIsNotNone(updated)
        self.assertEqual(store.saved_payload["metadata"]["workflow"]["runs"][0]["run_id"], "run_1")
        self.assertEqual(
            store.saved_payload["metadata"]["workflow"]["artifacts"][0]["artifact_id"],
            "artifact_1",
        )

    def test_save_project_record_exports_session_and_run_summary(self):
        store = FakeProjectStore(
            {
                "user_id": "u1",
                "project_id": "p1",
                "name": "Test",
                "description": "",
                "session_id": "s1",
                "tags": [],
                "project_input": {},
                "latest_result": {"final_plan": {"project_name": "Test"}},
                "session_state": {},
                "metadata": {},
            }
        )

        response = save_project_record(
            project_store=store,
            user_id="u1",
            payload_data={
                "project_id": "p1",
                "name": "Updated",
                "description": "",
                "session_id": "s1",
                "tags": ["alpha"],
                "project_input": {"prompt": "demo"},
                "latest_result": {"success": True, "final_plan": {"project_name": "Updated", "meta": {}}},
                "metadata": {"source": "ui"},
            },
            export_session_state=lambda session_id: {"session_id": session_id, "messages": []},
            build_run_summary=lambda result, **kwargs: {"run_id": "run_1", "source": kwargs.get("source")},
        )
        self.assertTrue(response["success"])
        self.assertEqual(store.saved_payload["session_state"]["session_id"], "s1")
        self.assertEqual(store.saved_payload["metadata"]["workflow"]["runs"][0]["run_id"], "run_1")

    def test_delete_project_record_reports_not_found(self):
        store = FakeProjectStore()
        with self.assertRaises(HTTPException) as ctx:
            delete_project_record(project_store=store, user_id="u1", project_id="missing")
        self.assertEqual(ctx.exception.status_code, 404)

    def test_delete_project_record_deletes(self):
        store = FakeProjectStore({"user_id": "u1", "project_id": "p1", "name": "Demo"})
        response = delete_project_record(project_store=store, user_id="u1", project_id="p1")
        self.assertTrue(response["success"])
        self.assertEqual(response["project_id"], "p1")

    def test_artifact_summary_uses_filename_and_project_name(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "plan.dxf"
            path.write_text("x")
            summary = artifact_summary(
                path=path,
                artifact_kind="dxf",
                project_id="p1",
                result_data={"final_plan": {"project_name": "Civora Plan"}},
            )
        self.assertEqual(summary["kind"], "dxf")
        self.assertEqual(summary["filename"], "plan.dxf")
        self.assertEqual(summary["project_name"], "Civora Plan")


if __name__ == "__main__":
    unittest.main()
