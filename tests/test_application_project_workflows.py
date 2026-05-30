import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException

from backend.application.project_workflows import (
    artifact_summary,
    delete_project_record,
    get_project_detail,
    get_project_result,
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
            return [dict(self.project)]
        return []

    def get_project(self, *, user_id: str, project_id: str):
        if self.project and user_id == self.project.get("user_id") and project_id == self.project.get("project_id"):
            return dict(self.project)
        return None

    def get_project_shell(self, *, user_id: str, project_id: str):
        project = self.get_project(user_id=user_id, project_id=project_id)
        if project is None:
            return None
        shell = dict(project)
        shell["latest_result"] = {}
        return shell

    def get_project_latest_result(self, *, user_id: str, project_id: str):
        project = self.get_project(user_id=user_id, project_id=project_id)
        if project is None:
            return None
        return dict(project.get("latest_result") or {})

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


class SequentialProjectStore(FakeProjectStore):
    def __init__(self, projects):
        super().__init__(project=dict(projects[-1]) if projects else None)
        self._projects = [dict(project) for project in projects]
        self._get_project_calls = 0

    def get_project(self, *, user_id: str, project_id: str):
        if not self._projects:
            return None
        index = min(self._get_project_calls, len(self._projects) - 1)
        project = self._projects[index]
        self._get_project_calls += 1
        if user_id == project.get("user_id") and project_id == project.get("project_id"):
            return dict(project)
        return None


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
        store = FakeProjectStore(
            {
                "user_id": "u1",
                "project_id": "p1",
                "name": "Demo",
                "metadata": {
                    "workflow": {
                        "summary": {
                            "latest_operational_state": "ready",
                            "latest_primary_attention": "",
                            "latest_release_ready": True,
                            "run_count": 2,
                            "artifact_count": 1,
                            "latest_run_id": "run_1",
                            "latest_artifact_id": "artifact_1",
                        }
                    }
                },
            }
        )
        response = list_projects(project_store=store, user_id="u1")
        self.assertTrue(response["success"])
        self.assertEqual(response["projects"][0]["project_id"], "p1")
        self.assertEqual(response["projects"][0]["operational_summary"]["operational_state"], "ready")

    def test_get_project_detail_wraps_store_output(self):
        store = FakeProjectStore(
            {
                "user_id": "u1",
                "project_id": "p1",
                "name": "Demo",
                "metadata": {
                    "workflow": {
                        "summary": {
                            "latest_operational_state": "retryable",
                            "latest_primary_attention": "storm_hydraulics_invalid",
                            "latest_release_ready": False,
                            "run_count": 3,
                            "artifact_count": 1,
                            "latest_run_id": "run_2",
                            "latest_artifact_id": "artifact_1",
                        }
                    }
                },
            }
        )
        response = get_project_detail(project_store=store, user_id="u1", project_id="p1")
        self.assertTrue(response["success"])
        self.assertEqual(response["project"]["name"], "Demo")
        self.assertEqual(response["project"]["operational_summary"]["primary_attention"], "storm_hydraulics_invalid")
        self.assertEqual(response["project"]["latest_result"], {})

    def test_get_project_result_returns_saved_result_only(self):
        store = FakeProjectStore(
            {
                "user_id": "u1",
                "project_id": "p1",
                "name": "Demo",
                "latest_result": {"final_plan": {"project_name": "Saved Demo"}},
            }
        )
        response = get_project_result(project_store=store, user_id="u1", project_id="p1")
        self.assertTrue(response["success"])
        self.assertEqual(response["project_id"], "p1")
        self.assertEqual(response["latest_result"]["final_plan"]["project_name"], "Saved Demo")

    def test_merge_project_metadata_limits_runs_and_artifacts(self):
        metadata = {
            "workflow": {
                "runs": [{"run_id": f"run_{idx}"} for idx in range(25)],
                "artifacts": [{"artifact_id": f"artifact_{idx}"} for idx in range(45)],
            }
        }
        merged = merge_project_metadata(
            metadata,
            run_summary={
                "run_id": "run_new",
                "created_at": 123.0,
                "source": "unit_test",
                "convergence_summary": {"converged": True},
                "reliability_summary": {
                    "operational_state": "ready",
                    "primary_attention": "",
                    "blocked_export_count": 0,
                    "unresolved_conflict_count": 0,
                    "failed_deliverable_count": 0,
                    "release_ready": True,
                },
            },
            artifact_summary={"artifact_id": "artifact_new"},
        )
        self.assertEqual(merged["workflow"]["runs"][0]["run_id"], "run_new")
        self.assertEqual(len(merged["workflow"]["runs"]), 20)
        self.assertEqual(merged["workflow"]["artifacts"][0]["artifact_id"], "artifact_new")
        self.assertEqual(len(merged["workflow"]["artifacts"]), 40)
        self.assertEqual(merged["workflow"]["summary"]["latest_run_id"], "run_new")
        self.assertEqual(merged["workflow"]["summary"]["latest_operational_state"], "ready")
        self.assertEqual(merged["workflow"]["summary"]["latest_artifact_id"], "artifact_new")

    def test_merge_project_metadata_blocks_release_when_construction_gate_blocks(self):
        merged = merge_project_metadata(
            {},
            run_summary={
                "run_id": "run_blocked",
                "created_at": 123.0,
                "source": "unit_test",
                "convergence_summary": {
                    "converged": True,
                    "blocked_exports": [],
                    "blocked_reasons": ["construction_package_blocked"],
                },
                "reliability_summary": {
                    "operational_state": "ready",
                    "primary_attention": "",
                    "blocked_export_count": 0,
                    "unresolved_conflict_count": 0,
                    "failed_deliverable_count": 0,
                    "release_ready": True,
                },
            },
        )
        summary = merged["workflow"]["summary"]
        self.assertFalse(summary["latest_release_ready"])
        self.assertEqual(summary["latest_release_blockers"], ["construction_package_blocked"])

    def test_merge_project_metadata_blocks_release_when_requested_deliverable_is_missing(self):
        merged = merge_project_metadata(
            {},
            run_summary={
                "run_id": "run_missing_deliverable",
                "created_at": 123.0,
                "source": "unit_test",
                "convergence_summary": {
                    "converged": True,
                    "blocked_exports": [],
                    "blocked_reasons": [],
                },
                "requested_deliverables": ["site_plan", "report"],
                "produced_deliverables": ["site_plan"],
                "missing_deliverables": ["report"],
                "reliability_summary": {
                    "operational_state": "ready",
                    "primary_attention": "",
                    "blocked_export_count": 0,
                    "unresolved_conflict_count": 0,
                    "failed_deliverable_count": 0,
                    "missing_deliverable_count": 1,
                    "release_ready": True,
                },
            },
        )
        summary = merged["workflow"]["summary"]
        self.assertFalse(summary["latest_release_ready"])
        self.assertIn("missing_deliverable_report", summary["latest_release_blockers"])
        self.assertIn("missing_deliverables", summary["latest_release_blockers"])

    def test_merge_project_metadata_derives_missing_deliverables_from_stale_run_summary(self):
        merged = merge_project_metadata(
            {},
            run_summary={
                "run_id": "run_stale_missing_deliverable",
                "created_at": 123.0,
                "source": "unit_test",
                "convergence_summary": {
                    "converged": True,
                    "blocked_exports": [],
                    "blocked_reasons": [],
                },
                "requested_deliverables": ["site_plan", "report"],
                "produced_deliverables": ["site_plan"],
                "reliability_summary": {
                    "operational_state": "ready",
                    "primary_attention": "",
                    "blocked_export_count": 0,
                    "unresolved_conflict_count": 0,
                    "failed_deliverable_count": 0,
                    "missing_deliverable_count": 0,
                    "release_ready": True,
                },
            },
        )
        summary = merged["workflow"]["summary"]
        self.assertFalse(summary["latest_release_ready"])
        self.assertIn("missing_deliverable_report", summary["latest_release_blockers"])

    def test_merge_project_metadata_normalizes_failed_deliverable_names(self):
        merged = merge_project_metadata(
            {},
            run_summary={
                "run_id": "run_failed_deliverable",
                "created_at": 123.0,
                "source": "unit_test",
                "convergence_summary": {
                    "converged": True,
                    "blocked_exports": [],
                    "blocked_reasons": [],
                },
                "deliverables": {
                    "requested": ["site_plan", "report"],
                    "produced": ["site_plan", "report"],
                    "failed": ["report"],
                },
                "reliability_summary": {
                    "operational_state": "ready",
                    "primary_attention": "",
                    "blocked_export_count": 0,
                    "unresolved_conflict_count": 0,
                    "failed_deliverable_count": 0,
                    "release_ready": True,
                },
            },
        )
        summary = merged["workflow"]["summary"]
        self.assertFalse(summary["latest_release_ready"])
        self.assertIn("failed_deliverable_report", summary["latest_release_blockers"])

    def test_merge_project_metadata_explains_false_latest_run_release_ready(self):
        merged = merge_project_metadata(
            {},
            run_summary={
                "run_id": "run_not_ready",
                "created_at": 123.0,
                "source": "unit_test",
                "convergence_summary": {
                    "converged": True,
                    "blocked_exports": [],
                    "blocked_reasons": [],
                },
                "reliability_summary": {
                    "operational_state": "ready",
                    "primary_attention": "",
                    "blocked_export_count": 0,
                    "unresolved_conflict_count": 0,
                    "failed_deliverable_count": 0,
                    "manual_failure_count": 0,
                    "release_ready": False,
                },
            },
        )
        summary = merged["workflow"]["summary"]
        self.assertFalse(summary["latest_release_ready"])
        self.assertEqual(summary["latest_release_blockers"], ["latest_run_release_not_ready"])

    def test_merge_project_metadata_blocks_stale_ready_run_with_errors(self):
        merged = merge_project_metadata(
            {},
            run_summary={
                "run_id": "run_error_stale_ready",
                "created_at": 123.0,
                "source": "unit_test",
                "success": True,
                "error_count": 1,
                "convergence_summary": {
                    "converged": True,
                    "blocked_exports": [],
                    "blocked_reasons": [],
                },
                "reliability_summary": {
                    "operational_state": "ready",
                    "primary_attention": "",
                    "blocked_export_count": 0,
                    "unresolved_conflict_count": 0,
                    "failed_deliverable_count": 0,
                    "manual_failure_count": 0,
                    "release_ready": True,
                },
            },
        )
        summary = merged["workflow"]["summary"]
        self.assertFalse(summary["latest_release_ready"])
        self.assertEqual(summary["latest_release_blockers"], ["planner_errors_present"])

    def test_merge_project_metadata_normalizes_manual_failure_blockers(self):
        merged = merge_project_metadata(
            {},
            run_summary={
                "run_id": "run_manual_blocked",
                "created_at": 123.0,
                "source": "unit_test",
                "convergence_summary": {
                    "converged": True,
                    "blocked_exports": [],
                    "blocked_reasons": [],
                },
                "manual_failures": [
                    {
                        "code": "MANUAL_STORM_HYDRAULIC_INVALID",
                        "message": "Storm hydraulic review failed.",
                    }
                ],
                "reliability_summary": {
                    "operational_state": "ready",
                    "primary_attention": "",
                    "blocked_export_count": 0,
                    "unresolved_conflict_count": 0,
                    "failed_deliverable_count": 0,
                    "manual_failure_count": 1,
                    "release_ready": True,
                },
            },
        )
        summary = merged["workflow"]["summary"]
        self.assertFalse(summary["latest_release_ready"])
        self.assertIn(
            "manual_validation_manual_storm_hydraulic_invalid",
            summary["latest_release_blockers"],
        )
        self.assertIn("manual_validation_failures", summary["latest_release_blockers"])

    def test_merge_project_metadata_blocks_release_when_latest_artifact_is_blocked(self):
        merged = merge_project_metadata(
            {},
            run_summary={
                "run_id": "run_ready",
                "created_at": 123.0,
                "source": "unit_test",
                "convergence_summary": {
                    "converged": True,
                    "blocked_exports": [],
                    "blocked_reasons": [],
                },
                "reliability_summary": {
                    "operational_state": "ready",
                    "primary_attention": "",
                    "blocked_export_count": 0,
                    "unresolved_conflict_count": 0,
                    "failed_deliverable_count": 0,
                    "release_ready": True,
                },
            },
            artifact_summary={
                "artifact_id": "artifact_blocked",
                "kind": "report",
                "release_status": "blocked",
                "release_ready": False,
                "release_blockers": ["construction_readiness_missing"],
            },
        )
        summary = merged["workflow"]["summary"]
        self.assertFalse(summary["latest_release_ready"])
        self.assertEqual(
            summary["latest_release_blockers"],
            ["construction_readiness_missing", "latest_artifact_release_blocked"],
        )
        self.assertEqual(summary["latest_artifact_release_status"], "blocked")
        self.assertFalse(summary["latest_artifact_release_ready"])

    def test_merge_project_metadata_blocks_stale_ready_latest_artifact_with_blockers(self):
        merged = merge_project_metadata(
            {},
            run_summary={
                "run_id": "run_ready",
                "created_at": 123.0,
                "source": "unit_test",
                "convergence_summary": {
                    "converged": True,
                    "blocked_exports": [],
                    "blocked_reasons": [],
                },
                "reliability_summary": {
                    "operational_state": "ready",
                    "primary_attention": "",
                    "blocked_export_count": 0,
                    "unresolved_conflict_count": 0,
                    "failed_deliverable_count": 0,
                    "release_ready": True,
                },
            },
            artifact_summary={
                "artifact_id": "artifact_stale_ready",
                "kind": "report",
                "release_status": "ready",
                "release_ready": True,
                "release_blockers": ["construction_package_release_not_marked_ready"],
            },
        )
        summary = merged["workflow"]["summary"]
        self.assertFalse(summary["latest_release_ready"])
        self.assertFalse(summary["latest_artifact_release_ready"])
        self.assertEqual(
            summary["latest_artifact_release_blockers"],
            ["construction_package_release_not_marked_ready"],
        )
        self.assertEqual(
            summary["latest_release_blockers"],
            ["construction_package_release_not_marked_ready"],
        )

    def test_operational_summary_exposes_project_release_blockers(self):
        store = FakeProjectStore(
            {
                "user_id": "u1",
                "project_id": "p1",
                "name": "Demo",
                "metadata": {
                    "workflow": {
                        "summary": {
                            "latest_operational_state": "ready",
                            "latest_primary_attention": "construction_readiness_blocked",
                            "latest_release_ready": False,
                            "latest_release_blockers": ["construction_readiness_blocked"],
                            "run_count": 1,
                            "artifact_count": 0,
                            "latest_run_id": "run_1",
                            "latest_artifact_id": "",
                        }
                    }
                },
            }
        )
        response = list_projects(project_store=store, user_id="u1")
        operational = response["projects"][0]["operational_summary"]
        self.assertFalse(operational["release_ready"])
        self.assertEqual(operational["release_blockers"], ["construction_readiness_blocked"])

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
            run_summary={
                "run_id": "run_1",
                "created_at": 10.0,
                "source": "unit_test",
                "convergence_summary": {"converged": False},
                "reliability_summary": {
                    "operational_state": "retryable",
                    "primary_attention": "storm_hydraulics_invalid",
                    "blocked_export_count": 1,
                    "unresolved_conflict_count": 2,
                    "failed_deliverable_count": 0,
                    "release_ready": False,
                },
            },
            artifact_summary={"artifact_id": "artifact_1"},
        )
        self.assertIsNotNone(updated)
        self.assertEqual(store.saved_payload["metadata"]["workflow"]["runs"][0]["run_id"], "run_1")
        self.assertEqual(
            store.saved_payload["metadata"]["workflow"]["artifacts"][0]["artifact_id"],
            "artifact_1",
        )
        self.assertEqual(
            store.saved_payload["metadata"]["workflow"]["summary"]["latest_primary_attention"],
            "storm_hydraulics_invalid",
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
        self.assertEqual(store.saved_payload["metadata"]["workflow"]["summary"]["latest_run_id"], "run_1")
        self.assertIn("operational_summary", response["project"])

    def test_save_project_record_preserves_existing_latest_result_when_payload_omits_it(self):
        store = FakeProjectStore(
            {
                "user_id": "u1",
                "project_id": "p1",
                "name": "Test",
                "description": "",
                "session_id": "s1",
                "tags": [],
                "project_input": {},
                "latest_result": {"final_plan": {"project_name": "Saved Partial"}},
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
                "tags": [],
                "project_input": {"prompt": "demo"},
                "metadata": {"source": "autosave"},
            },
        )
        self.assertTrue(response["success"])
        self.assertEqual(
            store.saved_payload["latest_result"]["final_plan"]["project_name"],
            "Saved Partial",
        )

    def test_save_project_record_preserves_existing_latest_result_when_payload_is_empty(self):
        store = FakeProjectStore(
            {
                "user_id": "u1",
                "project_id": "p1",
                "name": "Test",
                "description": "",
                "session_id": "s1",
                "tags": [],
                "project_input": {},
                "latest_result": {"final_plan": {"project_name": "Saved Partial"}},
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
                "tags": [],
                "project_input": {"prompt": "demo"},
                "latest_result": {},
                "metadata": {"source": "autosave"},
            },
        )
        self.assertTrue(response["success"])
        self.assertEqual(
            store.saved_payload["latest_result"]["final_plan"]["project_name"],
            "Saved Partial",
        )

    def test_save_project_record_preserves_fresh_staged_result_from_refreshed_project(self):
        stale_project = {
            "user_id": "u1",
            "project_id": "p1",
            "name": "Test",
            "description": "",
            "session_id": "s1",
            "tags": [],
            "project_input": {},
            "latest_result": {},
            "session_state": {},
            "metadata": {"source": "stale"},
        }
        fresh_project = {
            "user_id": "u1",
            "project_id": "p1",
            "name": "Test",
            "description": "",
            "session_id": "s1",
            "tags": [],
            "project_input": {},
            "latest_result": {
                "final_plan": {"project_name": "Fresh Staged Result", "meta": {"phase": "layout"}}
            },
            "session_state": {},
            "metadata": {
                "workflow": {
                    "summary": {
                        "latest_run_id": "run_layout",
                        "latest_operational_state": "awaiting_approval",
                    }
                }
            },
        }
        store = SequentialProjectStore([stale_project, fresh_project])

        response = save_project_record(
            project_store=store,
            user_id="u1",
            payload_data={
                "project_id": "p1",
                "name": "Updated",
                "description": "",
                "session_id": "s1",
                "tags": [],
                "project_input": {"prompt": "demo"},
                "latest_result": {},
                "metadata": {"source": "autosave"},
            },
        )
        self.assertTrue(response["success"])
        self.assertEqual(
            store.saved_payload["latest_result"]["final_plan"]["project_name"],
            "Fresh Staged Result",
        )
        self.assertEqual(
            store.saved_payload["metadata"]["workflow"]["summary"]["latest_run_id"],
            "run_layout",
        )
        self.assertEqual(store.saved_payload["metadata"]["source"], "autosave")

    def test_save_project_record_preserves_richer_existing_project_input(self):
        store = FakeProjectStore(
            {
                "user_id": "u1",
                "project_id": "p1",
                "name": "Test",
                "description": "",
                "session_id": "s1",
                "tags": [],
                "project_input": {
                    "prompt_text": "Design a mixed-use site with 3 multifamily buildings and 1 retail pad.",
                    "full_design_mode": True,
                    "manual_fields": {
                        "project_name": "Mixed Use",
                        "building_width": 110,
                        "building_depth": 58,
                        "site_plan": {"parking_count": 57},
                        "disciplines": ["corridor", "grading", "drainage", "utility"],
                    },
                    "request_payload": {
                        "prompt_text": "Design a mixed-use site with 3 multifamily buildings and 1 retail pad.",
                    },
                },
                "latest_result": {},
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
                "tags": [],
                "project_input": {
                    "prompt_text": "",
                    "manual_fields": {
                        "project_name": "",
                        "building_width": 0,
                        "building_depth": 0,
                        "site_plan": {"parking_count": 0},
                        "disciplines": ["corridor", "grading", "drainage", "utility"],
                    },
                },
                "metadata": {"source": "autosave"},
            },
        )
        self.assertTrue(response["success"])
        self.assertEqual(
            store.saved_payload["project_input"]["prompt_text"],
            "Design a mixed-use site with 3 multifamily buildings and 1 retail pad.",
        )
        self.assertEqual(store.saved_payload["project_input"]["manual_fields"]["building_width"], 110)
        self.assertEqual(store.saved_payload["project_input"]["manual_fields"]["building_depth"], 58)
        self.assertEqual(
            store.saved_payload["project_input"]["manual_fields"]["site_plan"]["parking_count"],
            57,
        )
        self.assertEqual(
            response["project"]["project_input"]["request_payload"]["prompt_text"],
            "Design a mixed-use site with 3 multifamily buildings and 1 retail pad.",
        )

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

    def test_artifact_summary_carries_release_and_model_trace(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "plan.json"
            path.write_text("x")
            summary = artifact_summary(
                path=path,
                artifact_kind="report",
                project_id="p1",
                result_data={
                    "request_metadata": {
                        "release_review": {
                            "release_status": "blocked",
                            "blocked_reasons": ["construction_package_blocked"],
                            "blocked_exports": ["dxf_export_blocked"],
                        }
                    },
                    "final_plan": {
                        "project_name": "Civora Plan",
                        "meta": {
                            "canonical_model_id": "model-1",
                            "canonical_model_hash": "hash-1",
                            "construction_package_manifest": {"package_id": "pkg-1"},
                        },
                    },
                },
            )
        self.assertEqual(summary["release_status"], "blocked")
        self.assertFalse(summary["release_ready"])
        self.assertEqual(
            summary["release_blockers"],
            [
                "construction_package_blocked",
                "dxf_export_blocked",
                "construction_readiness_missing",
                "construction_package_artifact_status_missing",
                "construction_package_release_not_marked_ready",
                "construction_package_production_not_marked_ready",
            ],
        )
        self.assertEqual(summary["canonical_model_reference"]["canonical_model_id"], "model-1")
        self.assertEqual(summary["canonical_model_reference"]["canonical_model_hash"], "hash-1")
        self.assertEqual(summary["construction_package_id"], "pkg-1")

    def test_artifact_summary_blocks_stale_final_meta_release_ready_with_package_blockers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "plan.json"
            path.write_text("x")
            summary = artifact_summary(
                path=path,
                artifact_kind="report",
                project_id="p1",
                result_data={
                    "final_plan": {
                        "project_name": "Stale Ready Artifact",
                        "meta": {
                            "release_ready": True,
                            "construction_readiness": {"ready": True, "status": "construction_ready"},
                            "construction_package_manifest": {
                                "release_allowed": False,
                                "construction_package_artifact_status": {
                                    "package_present": True,
                                    "missing": [],
                                    "anonymous": [],
                                    "stale": [],
                                    "model_reference_present": True,
                                    "model_matches_expected": True,
                                    "release_ready_flag": None,
                                    "untraced": [],
                                    "mismatched": [],
                                },
                            },
                        },
                    },
                },
            )

        self.assertFalse(summary["release_ready"])
        self.assertIn("construction_package_blocked", summary["release_blockers"])
        self.assertIn("construction_package_release_not_marked_ready", summary["release_blockers"])

    def test_artifact_summary_carries_deliverable_package_alias_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "plan.json"
            path.write_text("x")
            summary = artifact_summary(
                path=path,
                artifact_kind="report",
                project_id="p1",
                result_data={
                    "final_plan": {
                        "project_name": "Alias Package Artifact",
                        "meta": {
                            "release_ready": True,
                            "construction_readiness": {"ready": True, "status": "construction_ready"},
                            "deliverable_package": {
                                "package_id": "pkg-alias-1",
                                "release_allowed": False,
                                "construction_package_artifact_status": {
                                    "package_present": True,
                                    "release_ready_flag": None,
                                    "production_ready_flag": True,
                                },
                            },
                        },
                    },
                },
            )

        self.assertEqual(summary["construction_package_id"], "pkg-alias-1")
        self.assertFalse(summary["release_ready"])
        self.assertIn("construction_package_blocked", summary["release_blockers"])
        self.assertIn("construction_package_release_not_marked_ready", summary["release_blockers"])

    def test_artifact_summary_blocks_explicit_release_review_not_ready(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "plan.json"
            path.write_text("x")
            summary = artifact_summary(
                path=path,
                artifact_kind="report",
                project_id="p1",
                result_data={
                    "request_metadata": {
                        "release_review": {
                            "release_status": "ready",
                            "release_ready": False,
                        }
                    },
                    "final_plan": {
                        "project_name": "Review False Artifact",
                        "meta": {"release_ready": True},
                    },
                },
            )

        self.assertEqual(summary["release_status"], "ready")
        self.assertFalse(summary["release_ready"])
        self.assertIn("release_review_not_ready", summary["release_blockers"])

    def test_artifact_summary_blocks_explicit_blocked_release_status_without_reasons(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "plan.json"
            path.write_text("x")
            summary = artifact_summary(
                path=path,
                artifact_kind="report",
                project_id="p1",
                result_data={
                    "final_plan": {
                        "project_name": "Blocked Status Artifact",
                        "meta": {
                            "release_ready": True,
                            "release_review": {"release_status": "blocked"},
                        },
                    },
                },
            )

        self.assertEqual(summary["release_status"], "blocked")
        self.assertFalse(summary["release_ready"])
        self.assertIn("release_status_blocked", summary["release_blockers"])

    def test_artifact_summary_blocks_failed_deliverables_from_final_meta(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "plan.json"
            path.write_text("x")
            summary = artifact_summary(
                path=path,
                artifact_kind="report",
                project_id="p1",
                result_data={
                    "final_plan": {
                        "project_name": "Failed Deliverable Artifact",
                        "meta": {
                            "release_ready": True,
                            "release_status": "ready",
                            "deliverables": {"failed": ["report"]},
                        },
                    },
                },
            )

        self.assertEqual(summary["release_status"], "ready")
        self.assertFalse(summary["release_ready"])
        self.assertIn("failed_deliverable_report", summary["release_blockers"])

    def test_artifact_summary_blocks_missing_deliverables_from_final_meta(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "plan.json"
            path.write_text("x")
            summary = artifact_summary(
                path=path,
                artifact_kind="report",
                project_id="p1",
                result_data={
                    "final_plan": {
                        "project_name": "Missing Deliverable Artifact",
                        "meta": {
                            "release_ready": True,
                            "release_status": "ready",
                            "deliverables": {"requested": ["site_plan", "report"], "produced": ["site_plan"]},
                        },
                    },
                },
            )

        self.assertEqual(summary["release_status"], "ready")
        self.assertFalse(summary["release_ready"])
        self.assertIn("missing_deliverable_report", summary["release_blockers"])

    def test_artifact_summary_blocks_missing_deliverables_from_release_review(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "plan.json"
            path.write_text("x")
            summary = artifact_summary(
                path=path,
                artifact_kind="report",
                project_id="p1",
                result_data={
                    "request_metadata": {
                        "release_review": {
                            "release_status": "ready",
                            "release_ready": True,
                            "requested_deliverables": ["site_plan", "report"],
                            "produced_deliverables": ["site_plan"],
                            "failed_deliverables": [],
                        }
                    },
                    "final_plan": {
                        "project_name": "Review Missing Deliverable Artifact",
                        "meta": {
                            "release_ready": True,
                            "release_status": "ready",
                        },
                    },
                },
            )

        self.assertEqual(summary["release_status"], "ready")
        self.assertFalse(summary["release_ready"])
        self.assertIn("missing_deliverable_report", summary["release_blockers"])

    def test_artifact_summary_blocks_manual_validation_failures_from_final_meta(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "plan.json"
            path.write_text("x")
            summary = artifact_summary(
                path=path,
                artifact_kind="report",
                project_id="p1",
                result_data={
                    "final_plan": {
                        "project_name": "Manual Failure Artifact",
                        "meta": {
                            "release_ready": True,
                            "release_status": "ready",
                            "manual_validation": {
                                "failures": [
                                    {
                                        "code": "MANUAL_STORM_HYDRAULIC_INVALID",
                                        "message": "Storm hydraulic review failed.",
                                    }
                                ]
                            },
                        },
                    },
                },
            )

        self.assertEqual(summary["release_status"], "ready")
        self.assertFalse(summary["release_ready"])
        self.assertIn(
            "manual_validation_manual_storm_hydraulic_invalid",
            summary["release_blockers"],
        )

    def test_artifact_summary_blocks_reactive_post_rerun_release_blockers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "plan.json"
            path.write_text("x")
            summary = artifact_summary(
                path=path,
                artifact_kind="report",
                project_id="p1",
                result_data={
                    "final_plan": {
                        "project_name": "Reactive Blocked Artifact",
                        "meta": {
                            "release_ready": True,
                            "release_status": "ready",
                            "reactive_update_report": {
                                "post_rerun_production_ready": False,
                                "post_rerun_release_blockers": ["manual_validation_manual_storm_hydraulic_invalid"],
                            },
                        },
                    },
                },
            )

        self.assertEqual(summary["release_status"], "ready")
        self.assertFalse(summary["release_ready"])
        self.assertIn("reactive_post_rerun_not_ready", summary["release_blockers"])
        self.assertIn(
            "manual_validation_manual_storm_hydraulic_invalid",
            summary["release_blockers"],
        )


if __name__ == "__main__":
    unittest.main()
