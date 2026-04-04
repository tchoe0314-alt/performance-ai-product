import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException

from backend.application.artifact_workflows import (
    build_preview_response,
    export_dxf_artifact,
    export_report_artifact,
)


class FakeArtifactService:
    def __init__(self):
        self.preview_plan = None
        self.dxf_export = None
        self.report_export = None

    def build_preview_png(self, final_plan):
        self.preview_plan = dict(final_plan)
        return b"png-bytes"

    def export_dxf(self, *, user_id, final_plan, stem=None):
        self.dxf_export = {"user_id": user_id, "final_plan": dict(final_plan), "stem": stem}
        path = Path(tempfile.gettempdir()) / "unit-plan.dxf"
        path.write_text("dxf")
        return path

    def export_report_json(self, *, user_id, result_data, stem=None):
        self.report_export = {"user_id": user_id, "result_data": dict(result_data), "stem": stem}
        path = Path(tempfile.gettempdir()) / "unit-report.json"
        path.write_text("{}")
        return path


class FakeProjectStore:
    def __init__(self):
        self.project = {
            "user_id": "u1",
            "project_id": "p1",
            "name": "Test",
            "description": "",
            "session_id": None,
            "tags": [],
            "project_input": {},
            "latest_result": {},
            "session_state": {},
            "metadata": {},
        }
        self.saved_payload = None

    def get_project(self, *, user_id, project_id):
        if user_id == "u1" and project_id == "p1":
            return dict(self.project)
        return None

    def save_project(self, **kwargs):
        self.saved_payload = dict(kwargs)
        self.project.update(kwargs)
        return dict(self.project)


class ApplicationArtifactWorkflowsTest(unittest.TestCase):
    def test_build_preview_response_serializes_png(self):
        service = FakeArtifactService()
        response = build_preview_response(
            artifact_service=service,
            result_data={
                "success": True,
                "message": "ok",
                "warnings": [],
                "errors": [],
                "metadata": {"_workflow_run_id": "run_preview"},
                "final_plan": {
                    "project_name": "Demo",
                    "units": "ft",
                    "actions": [1, 2],
                    "meta": {
                        "grading": {"export_validation": {"ready": True, "reasons": []}},
                        "drainage": {"export_validation": {"ready": True, "reasons": []}},
                        "storm_pipes": {
                            "graph_validation": {"valid": True},
                            "hydraulic_validation": {"valid": True},
                            "missing_data_segments": [],
                        },
                        "utilities": {"export_validation": {"ready": True, "reasons": []}},
                        "engineering_status": {"engineering_trust_score": 92.0},
                        "convergence_summary": {
                            "converged": True,
                            "passes_run": 2,
                            "unresolved_conflict_count": 0,
                            "assumption_summary": {
                                "count": 2,
                                "categories": ["drainage", "grading"],
                                "examples": ["Assumed outlet release basis."],
                            },
                            "fix_summary": {
                                "autofix_actions": ["storm_validation_retry"],
                            },
                            "dominant_issue_categories": ["storm"],
                            "unresolved_issue_categories": ["utility_review"],
                            "blocked_exports": ["storm"],
                            "blocked_reasons": ["storm_graph_invalid"],
                        },
                        "deliverables": {
                            "requested": ["site_plan", "grading_plan", "utility_plan"],
                            "produced": ["site_plan", "grading_plan"],
                            "failed": ["utility_plan"],
                        },
                    },
                },
            },
        )
        self.assertTrue(response["preview_image_data_url"].startswith("data:image/png;base64,"))
        self.assertEqual(response["summary"]["project_name"], "Demo")
        review = response["summary"]["review"]
        self.assertEqual(review["trust_score"], 92.0)
        self.assertEqual(review["assumption_count"], 2)
        self.assertEqual(review["autofix_actions"], ["storm_validation_retry"])
        self.assertEqual(review["blocked_reasons"], ["storm_graph_invalid"])
        self.assertEqual(review["requested_deliverables"], ["site_plan", "grading_plan", "utility_plan"])
        self.assertEqual(review["produced_deliverables"], ["site_plan", "grading_plan"])
        self.assertEqual(review["failed_deliverables"], ["utility_plan"])
        self.assertEqual(review["release_status"], "blocked")
        self.assertIn("Blocked", review["release_note"])
        self.assertEqual(service.preview_plan["project_name"], "Demo")

    def test_build_preview_response_respects_export_guard(self):
        service = FakeArtifactService()
        with self.assertRaises(HTTPException):
            build_preview_response(
                artifact_service=service,
                result_data={
                    "final_plan": {
                        "actions": [{"layer": "PIPE"}],
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
                },
            )

    def test_export_dxf_artifact_updates_project_workflow(self):
        service = FakeArtifactService()
        store = FakeProjectStore()
        result_data = {
            "final_plan": {
                "project_name": "DXF Demo",
                "actions": [{"task": "polyline", "layer": "LOT", "points": [[0, 0], [1, 0], [1, 1], [0, 1]]}],
            }
        }
        path = export_dxf_artifact(
            artifact_service=service,
            project_store=store,
            user_id="u1",
            project_id="p1",
            result_data=result_data,
            filename_stem="demo-plan",
        )
        self.assertEqual(path.name, "unit-plan.dxf")
        self.assertEqual(service.dxf_export["stem"], "demo-plan")
        self.assertEqual(
            store.saved_payload["metadata"]["workflow"]["artifacts"][0]["kind"],
            "dxf",
        )

    def test_export_report_artifact_updates_project_workflow(self):
        service = FakeArtifactService()
        store = FakeProjectStore()
        result_data = {
            "final_plan": {
                "project_name": "Report Demo",
                "actions": [{"task": "polyline", "layer": "LOT", "points": [[0, 0], [1, 0], [1, 1], [0, 1]]}],
            }
        }
        path = export_report_artifact(
            artifact_service=service,
            project_store=store,
            user_id="u1",
            project_id="p1",
            result_data=result_data,
            filename_stem="demo-report",
        )
        self.assertEqual(path.name, "unit-report.json")
        self.assertEqual(service.report_export["stem"], "demo-report")
        self.assertEqual(
            store.saved_payload["metadata"]["workflow"]["artifacts"][0]["kind"],
            "report",
        )


if __name__ == "__main__":
    unittest.main()
