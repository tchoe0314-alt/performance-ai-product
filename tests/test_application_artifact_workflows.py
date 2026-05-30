import tempfile
import unittest
from pathlib import Path

from backend.application.artifact_workflows import (
    build_preview_response,
    export_dxf_artifact,
    export_report_artifact,
)
from backend.application.design_workflows import final_plan_from_result
from fastapi import HTTPException


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
    def test_build_preview_response_rebuilds_legacy_frontage_scene_from_parsed_payload(self):
        service = FakeArtifactService()
        response = build_preview_response(
            artifact_service=service,
            result_data={
                "parsed_payload": {
                    "project_type": "mixed_use",
                    "lot": {"w": 620.0, "h": 980.0},
                    "buildings": [
                        {"name": "MF-1", "type": "multifamily", "width": 110, "depth": 58},
                        {"name": "MF-2", "type": "multifamily", "width": 110, "depth": 58},
                        {"name": "MF-3", "type": "multifamily", "width": 110, "depth": 58},
                        {"name": "Retail", "type": "retail", "width": 70, "depth": 45},
                    ],
                },
                "final_plan": {
                    "project_name": "Legacy Frontage",
                    "actions": [
                        {"task": "rectangle", "layer": "BUILDING", "origin": [250, 700], "width": 80, "height": 50, "label": "BLDG"},
                        {"task": "rectangle", "layer": "PAVEMENT", "origin": [180, 520], "width": 260, "height": 28, "label": "FRONTAGE"},
                        {"task": "text_note", "layer": "PAVEMENT", "origin": [290, 534], "text": "FRONTAGE ACCESS"},
                        {"task": "polyline", "layer": "PIPE", "points": [[220, 520], [310, 430], [410, 380]]},
                    ],
                    "meta": {},
                },
            },
        )
        self.assertTrue(response["preview_image_data_url"].startswith("data:image/png;base64,"))
        preview_actions = service.preview_plan["actions"]
        preview_buildings = [
            action for action in preview_actions
            if action.get("layer") == "BUILDING" and action.get("task") == "rectangle"
        ]
        self.assertGreaterEqual(len(preview_buildings), 4)
        self.assertFalse(
            any(
                "FRONTAGE" in str(action.get("label") or "").upper()
                or "FRONTAGE" in str(action.get("text") or "").upper()
                for action in preview_actions
            )
        )
        self.assertTrue(any(action.get("layer") == "PIPE" for action in preview_actions))

    def test_build_preview_response_prefers_richer_request_metadata_payload_for_legacy_scene(self):
        service = FakeArtifactService()
        response = build_preview_response(
            artifact_service=service,
            result_data={
                "parsed_payload": {
                    "project_type": "mixed_use",
                    "lot": {"w": 620.0, "h": 980.0},
                    "buildings": [
                        {"name": "BLDG", "type": "commercial", "width": 80, "depth": 50},
                    ],
                },
                "request_metadata": {
                    "parsed_payload": {
                        "project_type": "mixed_use",
                        "lot": {"w": 620.0, "h": 980.0},
                        "buildings": [
                            {"name": "MF-1", "type": "multifamily", "width": 110, "depth": 58},
                            {"name": "MF-2", "type": "multifamily", "width": 110, "depth": 58},
                            {"name": "MF-3", "type": "multifamily", "width": 110, "depth": 58},
                            {"name": "Retail", "type": "retail", "width": 70, "depth": 45},
                        ],
                    }
                },
                "final_plan": {
                    "project_name": "Legacy Thin Scene",
                    "actions": [
                        {"task": "rectangle", "layer": "BUILDING", "origin": [250, 700], "width": 80, "height": 50, "label": "BLDG"},
                        {"task": "rectangle", "layer": "PAVEMENT", "origin": [180, 520], "width": 260, "height": 28, "label": "FRONTAGE"},
                        {"task": "text_note", "layer": "PAVEMENT", "origin": [290, 534], "text": "FRONTAGE ACCESS"},
                    ],
                    "meta": {},
                },
            },
        )
        self.assertTrue(response["preview_image_data_url"].startswith("data:image/png;base64,"))
        preview_actions = service.preview_plan["actions"]
        preview_buildings = [
            action for action in preview_actions
            if action.get("layer") == "BUILDING" and action.get("task") == "rectangle"
        ]
        self.assertGreaterEqual(len(preview_buildings), 4)
        labels = {str(action.get("label") or "") for action in preview_buildings}
        self.assertIn("MF-1", labels)
        self.assertIn("Retail", labels)

    def test_build_preview_response_rebuilds_legacy_scene_from_project_input_request_shape(self):
        service = FakeArtifactService()
        response = build_preview_response(
            artifact_service=service,
            result_data={
                "project_input": {
                    "manual_fields": {
                        "project_type": "mixed_use",
                        "lot": {"w": 620.0, "h": 980.0},
                        "buildings": [
                            {"name": "MF-1", "type": "multifamily", "width": 110, "depth": 58},
                            {"name": "MF-2", "type": "multifamily", "width": 110, "depth": 58},
                            {"name": "MF-3", "type": "multifamily", "width": 110, "depth": 58},
                            {"name": "Retail", "type": "retail", "width": 70, "depth": 45},
                        ],
                    },
                    "meta": {"project_type": "mixed_use"},
                },
                "final_plan": {
                    "project_name": "Legacy Thin Project Input Scene",
                    "actions": [
                        {"task": "rectangle", "layer": "BUILDING", "origin": [250, 700], "width": 80, "height": 50, "label": "BLDG"},
                        {"task": "rectangle", "layer": "PAVEMENT", "origin": [180, 520], "width": 260, "height": 28, "label": "FRONTAGE"},
                        {"task": "text_note", "layer": "PAVEMENT", "origin": [290, 534], "text": "FRONTAGE ACCESS"},
                    ],
                    "meta": {},
                },
            },
        )
        self.assertTrue(response["preview_image_data_url"].startswith("data:image/png;base64,"))
        preview_actions = service.preview_plan["actions"]
        preview_buildings = [
            action for action in preview_actions
            if action.get("layer") == "BUILDING" and action.get("task") == "rectangle"
        ]
        self.assertGreaterEqual(len(preview_buildings), 4)

    def test_build_preview_response_enriches_thin_result_from_project_record(self):
        service = FakeArtifactService()
        store = FakeProjectStore()
        store.project["project_input"] = {
            "manual_fields": {
                "project_type": "mixed_use",
                "lot": {"w": 620.0, "h": 980.0},
                "buildings": [
                    {"name": "MF-1", "type": "multifamily", "width": 110, "depth": 58},
                    {"name": "MF-2", "type": "multifamily", "width": 110, "depth": 58},
                    {"name": "MF-3", "type": "multifamily", "width": 110, "depth": 58},
                    {"name": "Retail", "type": "retail", "width": 70, "depth": 45},
                ],
            },
            "meta": {"project_type": "mixed_use"},
        }
        response = build_preview_response(
            artifact_service=service,
            project_store=store,
            user_id="u1",
            project_id="p1",
            result_data={
                "final_plan": {
                    "project_name": "Thin Latest Result",
                    "actions": [
                        {"task": "rectangle", "layer": "BUILDING", "origin": [250, 700], "width": 80, "height": 50, "label": "BLDG"},
                        {"task": "rectangle", "layer": "PAVEMENT", "origin": [180, 520], "width": 260, "height": 28, "label": "FRONTAGE"},
                        {"task": "text_note", "layer": "PAVEMENT", "origin": [290, 534], "text": "FRONTAGE ACCESS"},
                    ],
                    "meta": {},
                },
            },
        )
        self.assertTrue(response["preview_image_data_url"].startswith("data:image/png;base64,"))
        preview_actions = service.preview_plan["actions"]
        preview_buildings = [
            action for action in preview_actions
            if action.get("layer") == "BUILDING" and action.get("task") == "rectangle"
        ]
        self.assertGreaterEqual(len(preview_buildings), 4)

    def test_build_preview_response_prefers_richer_project_payload_even_when_counts_match(self):
        service = FakeArtifactService()
        store = FakeProjectStore()
        store.project["project_input"] = {
            "manual_fields": {
                "project_type": "mixed_use",
                "lot": {"w": 620.0, "h": 980.0},
                "buildings": [
                    {"name": "MF-1", "type": "multifamily", "width": 110, "depth": 58},
                    {"name": "MF-2", "type": "multifamily", "width": 110, "depth": 58},
                    {"name": "MF-3", "type": "multifamily", "width": 110, "depth": 58},
                    {"name": "Retail", "type": "retail", "width": 70, "depth": 45},
                ],
                "parking_areas": [
                    {"x": 140.0, "y": 580.0, "w": 120.0, "h": 60.0},
                    {"x": 280.0, "y": 580.0, "w": 120.0, "h": 60.0},
                ],
            },
            "meta": {"project_type": "mixed_use"},
        }
        response = build_preview_response(
            artifact_service=service,
            project_store=store,
            user_id="u1",
            project_id="p1",
            result_data={
                "parsed_payload": {
                    "project_type": "mixed_use",
                    "buildings": [
                        {"name": "BLDG-1", "type": "commercial", "width": 80, "depth": 50},
                        {"name": "BLDG-2", "type": "commercial", "width": 80, "depth": 50},
                        {"name": "BLDG-3", "type": "commercial", "width": 80, "depth": 50},
                        {"name": "BLDG-4", "type": "commercial", "width": 80, "depth": 50},
                    ],
                },
                "final_plan": {
                    "project_name": "Legacy Equal Count Scene",
                    "actions": [
                        {"task": "rectangle", "layer": "BUILDING", "origin": [250, 700], "width": 80, "height": 50, "label": "BLDG"},
                        {"task": "rectangle", "layer": "PAVEMENT", "origin": [180, 520], "width": 260, "height": 28, "label": "FRONTAGE"},
                        {"task": "text_note", "layer": "PAVEMENT", "origin": [290, 534], "text": "FRONTAGE ACCESS"},
                    ],
                    "meta": {},
                },
            },
        )
        self.assertTrue(response["preview_image_data_url"].startswith("data:image/png;base64,"))
        preview_buildings = [
            action for action in service.preview_plan["actions"]
            if action.get("layer") == "BUILDING" and action.get("task") == "rectangle"
        ]
        labels = {str(action.get("label") or "") for action in preview_buildings}
        self.assertIn("MF-1", labels)
        self.assertIn("Retail", labels)

    def test_build_preview_response_can_recover_from_workflow_input_summary(self):
        service = FakeArtifactService()
        store = FakeProjectStore()
        store.project["metadata"] = {
            "workflow": {
                "runs": [
                    {
                        "input_summary": {
                            "project_type": "mixed_use",
                            "site_type": "mixed_use",
                            "street_edge": "bottom",
                            "lot": {"w": 620.0, "h": 980.0},
                            "buildings": [
                                {"name": "MF-1", "type": "multifamily", "width": 110, "depth": 58},
                                {"name": "MF-2", "type": "multifamily", "width": 110, "depth": 58},
                                {"name": "MF-3", "type": "multifamily", "width": 110, "depth": 58},
                                {"name": "Retail", "type": "retail", "width": 70, "depth": 45},
                            ],
                        }
                    }
                ]
            }
        }
        response = build_preview_response(
            artifact_service=service,
            project_store=store,
            user_id="u1",
            project_id="p1",
            result_data={
                "final_plan": {
                    "project_name": "Thin Legacy Workflow Scene",
                    "actions": [
                        {"task": "rectangle", "layer": "BUILDING", "origin": [250, 700], "width": 80, "height": 50, "label": "BLDG"},
                        {"task": "rectangle", "layer": "PAVEMENT", "origin": [180, 520], "width": 260, "height": 28, "label": "FRONTAGE"},
                        {"task": "text_note", "layer": "PAVEMENT", "origin": [290, 534], "text": "FRONTAGE ACCESS"},
                    ],
                    "meta": {},
                },
            },
        )
        self.assertTrue(response["preview_image_data_url"].startswith("data:image/png;base64,"))
        preview_buildings = [
            action for action in service.preview_plan["actions"]
            if action.get("layer") == "BUILDING" and action.get("task") == "rectangle"
        ]
        labels = {str(action.get("label") or "") for action in preview_buildings}
        self.assertIn("MF-1", labels)
        self.assertIn("Retail", labels)

    def test_build_preview_response_can_recover_from_sparse_saved_actions(self):
        service = FakeArtifactService()
        store = FakeProjectStore()
        response = build_preview_response(
            artifact_service=service,
            project_store=store,
            user_id="u1",
            project_id="p1",
            result_data={
                "final_plan": {
                    "project_name": "Sparse Legacy Geometry",
                    "actions": [
                        {"task": "rectangle", "layer": "SITE", "origin": [0, 0], "width": 620, "height": 980},
                        {"task": "rectangle", "layer": "BUILDING", "origin": [120, 720], "width": 110, "height": 58, "label": "MF-1"},
                        {"task": "rectangle", "layer": "BUILDING", "origin": [255, 720], "width": 110, "height": 58, "label": "MF-2"},
                        {"task": "rectangle", "layer": "BUILDING", "origin": [390, 720], "width": 110, "height": 58, "label": "MF-3"},
                        {"task": "rectangle", "layer": "BUILDING", "origin": [275, 360], "width": 70, "height": 45, "label": "Retail"},
                        {"task": "rectangle", "layer": "PAVEMENT", "origin": [180, 520], "width": 260, "height": 28, "label": "FRONTAGE"},
                        {"task": "text_note", "layer": "PAVEMENT", "origin": [290, 534], "text": "FRONTAGE ACCESS"},
                    ],
                    "meta": {},
                },
            },
        )
        self.assertTrue(response["preview_image_data_url"].startswith("data:image/png;base64,"))
        preview_buildings = [
            action for action in service.preview_plan["actions"]
            if action.get("layer") == "BUILDING" and action.get("task") == "rectangle"
        ]
        self.assertGreaterEqual(len(preview_buildings), 4)
        self.assertFalse(
            any(
                "FRONTAGE" in str(action.get("label") or "").upper()
                or "FRONTAGE" in str(action.get("text") or "").upper()
                for action in service.preview_plan["actions"]
            )
        )

    def test_export_dxf_artifact_enriches_thin_result_from_project_record(self):
        service = FakeArtifactService()
        store = FakeProjectStore()
        store.project["project_input"] = {
            "manual_fields": {
                "project_type": "mixed_use",
                "lot": {"w": 620.0, "h": 980.0},
                "buildings": [
                    {"name": "MF-1", "type": "multifamily", "width": 110, "depth": 58},
                    {"name": "MF-2", "type": "multifamily", "width": 110, "depth": 58},
                    {"name": "MF-3", "type": "multifamily", "width": 110, "depth": 58},
                    {"name": "Retail", "type": "retail", "width": 70, "depth": 45},
                ],
            },
            "meta": {"project_type": "mixed_use"},
        }
        path = export_dxf_artifact(
            artifact_service=service,
            project_store=store,
            user_id="u1",
            project_id="p1",
            result_data={
                "final_plan": {
                    "project_name": "Thin DXF Result",
                    "actions": [
                        {"task": "rectangle", "layer": "BUILDING", "origin": [250, 700], "width": 80, "height": 50, "label": "BLDG"},
                        {"task": "rectangle", "layer": "PAVEMENT", "origin": [180, 520], "width": 260, "height": 28, "label": "FRONTAGE"},
                        {"task": "text_note", "layer": "PAVEMENT", "origin": [290, 534], "text": "FRONTAGE ACCESS"},
                    ],
                    "meta": {
                        "drainage": {"export_validation": {"ready": True, "reasons": []}},
                        "storm_pipes": {"graph_validation": {"valid": True}, "hydraulic_validation": {"valid": True}, "segments": []},
                        "utilities": {"export_validation": {"ready": True, "reasons": []}},
                    },
                },
            },
            filename_stem="thin-project",
        )
        self.assertEqual(path.name, "unit-plan.dxf")
        exported_actions = service.dxf_export["final_plan"]["actions"]
        exported_buildings = [
            action for action in exported_actions
            if action.get("layer") == "BUILDING" and action.get("task") == "rectangle"
        ]
        self.assertGreaterEqual(len(exported_buildings), 4)

    def test_export_dxf_artifact_rebuilds_legacy_frontage_scene_from_parsed_payload(self):
        service = FakeArtifactService()
        store = FakeProjectStore()
        result_data = {
            "parsed_payload": {
                "project_type": "mixed_use",
                "lot": {"w": 620.0, "h": 980.0},
                "buildings": [
                    {"name": "MF-1", "type": "multifamily", "width": 110, "depth": 58},
                    {"name": "MF-2", "type": "multifamily", "width": 110, "depth": 58},
                    {"name": "MF-3", "type": "multifamily", "width": 110, "depth": 58},
                    {"name": "Retail", "type": "retail", "width": 70, "depth": 45},
                ],
            },
            "final_plan": {
                "project_name": "Legacy DXF",
                "actions": [
                    {"task": "rectangle", "layer": "BUILDING", "origin": [250, 700], "width": 80, "height": 50, "label": "BLDG"},
                    {"task": "rectangle", "layer": "PAVEMENT", "origin": [180, 520], "width": 260, "height": 28, "label": "FRONTAGE"},
                    {"task": "text_note", "layer": "PAVEMENT", "origin": [290, 534], "text": "FRONTAGE ACCESS"},
                    {"task": "polyline", "layer": "PIPE", "points": [[220, 520], [310, 430], [410, 380]]},
                ],
                "meta": {
                    "drainage": {"export_validation": {"ready": True, "reasons": []}},
                    "storm_pipes": {
                        "segments": [
                            {"points": [[220, 520], [310, 430], [410, 380]]},
                        ],
                        "graph_validation": {"valid": True},
                        "hydraulic_validation": {"valid": True},
                    },
                    "utilities": {"export_validation": {"ready": True, "reasons": []}},
                    "deliverables": {"requested": ["site_plan"], "produced": ["site_plan"]},
                },
            },
        }
        path = export_dxf_artifact(
            artifact_service=service,
            project_store=store,
            user_id="u1",
            project_id="p1",
            result_data=result_data,
            filename_stem="legacy-dxf",
        )
        self.assertEqual(path.name, "unit-plan.dxf")
        export_actions = service.dxf_export["final_plan"]["actions"]
        export_buildings = [
            action for action in export_actions
            if action.get("layer") == "BUILDING" and action.get("task") == "rectangle"
        ]
        self.assertGreaterEqual(len(export_buildings), 4)
        self.assertFalse(
            any(
                "FRONTAGE" in str(action.get("label") or "").upper()
                or "FRONTAGE" in str(action.get("text") or "").upper()
                for action in export_actions
            )
        )
        self.assertTrue(any(action.get("layer") == "PIPE" for action in export_actions))

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
                            "rerun_summary": {
                                "total_reruns": 2,
                                "stage_counts": {"drainage": 2, "storm": 1},
                                "reason_counts": {"storm_validation_retry": 1, "utility_validation_retry": 1},
                            },
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
        self.assertEqual(review["blocked_reasons"], ["failed_deliverable_utility_plan"])
        self.assertEqual(review["requested_deliverables"], ["site_plan", "grading_plan", "utility_plan"])
        self.assertEqual(review["produced_deliverables"], ["site_plan", "grading_plan"])
        self.assertEqual(review["failed_deliverables"], ["utility_plan"])
        self.assertEqual(review["rerun_total"], 2)
        self.assertEqual(review["rerun_stages"], ["drainage", "storm"])
        self.assertEqual(review["rerun_reasons"], ["storm_validation_retry", "utility_validation_retry"])
        self.assertEqual(review["release_status"], "blocked")
        self.assertIn("Blocked", review["release_note"])
        self.assertEqual(review["reliability"]["operational_state"], "retryable")
        self.assertEqual(review["reliability"]["primary_attention"], "storm_graph_invalid")
        self.assertEqual(review["reliability"]["blocked_export_count"], 1)
        self.assertEqual(service.preview_plan["project_name"], "Demo")

    def test_build_preview_response_allows_blocked_export_preview(self):
        service = FakeArtifactService()
        response = build_preview_response(
            artifact_service=service,
            result_data={
                "final_plan": {
                    "project_name": "Blocked Preview",
                    "actions": [{"layer": "PIPE"}],
                    "meta": {
                        "deliverables": {"requested": ["storm_pipe_plan"], "produced": ["storm_pipe_plan"]},
                        "drainage": {"export_validation": {"ready": False, "reasons": ["primary_detention_missing"]}},
                        "storm_pipes": {
                            "graph_validation": {"valid": False},
                            "hydraulic_validation": {"valid": False},
                            "missing_data_segments": [],
                        },
                        "convergence_summary": {
                            "blocked_exports": ["storm"],
                            "blocked_reasons": ["storm_graph_invalid"],
                        },
                    },
                }
            },
        )
        self.assertTrue(response["preview_image_data_url"].startswith("data:image/png;base64,"))
        self.assertEqual(response["summary"]["project_name"], "Blocked Preview")
        self.assertEqual(
            response["summary"]["review"]["blocked_reasons"],
            ["primary_detention_missing", "storm_graph_invalid", "storm_hydraulics_invalid"],
        )
        self.assertEqual(service.preview_plan["project_name"], "Blocked Preview")

    def test_build_preview_response_prefers_final_release_review_over_stale_convergence(self):
        service = FakeArtifactService()
        response = build_preview_response(
            artifact_service=service,
            result_data={
                "final_plan": {
                    "project_name": "Release Review Wins",
                    "actions": [{"layer": "PIPE"}],
                    "meta": {
                        "deliverables": {"requested": ["storm_pipe_plan"], "produced": ["storm_pipe_plan"]},
                        "release_review": {
                            "blocked_exports": [],
                            "blocked_reasons": [],
                            "release_status": "ready",
                            "release_note": "Fallback-ready systems can export.",
                        },
                        "convergence_summary": {
                            "blocked_exports": ["storm", "utilities"],
                            "blocked_reasons": ["storm_graph_invalid", "utility_fallback_used"],
                        },
                    },
                }
            },
        )
        review = response["summary"]["review"]
        self.assertEqual(review["blocked_exports"], [])
        self.assertEqual(review["blocked_reasons"], [])
        self.assertEqual(review["release_status"], "ready")
        self.assertEqual(review["release_note"], "Fallback-ready systems can export.")

    def test_build_preview_response_prefers_stored_run_summary_when_present(self):
        service = FakeArtifactService()
        response = build_preview_response(
            artifact_service=service,
            result_data={
                "run_summary": {
                    "engineering_status": {"trust_score": 72.0},
                    "reliability_summary": {"operational_state": "ready", "release_ready": True},
                    "optimization_summary": {},
                    "convergence_summary": {
                        "converged": True,
                        "passes_run": 1,
                        "unresolved_conflict_count": 0,
                        "assumption_summary": {"count": 0, "categories": [], "examples": []},
                        "fix_summary": {"autofix_actions": []},
                        "rerun_summary": {"total_reruns": 0, "stage_counts": {}, "reason_counts": {}},
                        "dominant_issue_categories": [],
                        "unresolved_issue_categories": [],
                        "blocked_exports": [],
                        "blocked_reasons": [],
                    },
                    "requested_deliverables": ["site_plan"],
                    "produced_deliverables": ["site_plan"],
                    "failed_deliverables": [],
                    "ready_deliverables": ["site_plan"],
                    "extra_deliverables": [],
                    "phase_checkpoints": {
                        "layout": {
                            "label": "Layout",
                            "status": "ready",
                            "ready": True,
                            "deliverables": ["site_plan"],
                            "messages": ["Buildings and parking are saved."],
                        },
                        "grading": {
                            "label": "Grading",
                            "status": "review",
                            "ready": False,
                            "deliverables": ["grading_plan"],
                            "blockers": ["spot grades pending review"],
                        },
                        "combined_view": {
                            "label": "Combined View",
                            "status": "review",
                            "ready": False,
                            "completed_phase_count": 1,
                            "total_phase_count": 5,
                            "blocked_reasons": ["grading review pending"],
                        },
                    },
                },
                "final_plan": {
                    "project_name": "Stored Summary Wins",
                    "actions": [{"layer": "PIPE"}],
                    "meta": {
                        "convergence_summary": {
                            "blocked_exports": ["storm"],
                            "blocked_reasons": ["storm_graph_invalid"],
                        }
                    },
                },
            },
        )
        review = response["summary"]["review"]
        self.assertEqual(review["blocked_exports"], [])
        self.assertEqual(review["blocked_reasons"], [])
        self.assertEqual(review["release_status"], "ready")
        self.assertEqual(review["review_categories"], [])
        self.assertEqual(review["phase_checkpoints"]["layout"]["status"], "ready")
        self.assertEqual(review["phase_checkpoints"]["combined_view"]["total_phase_count"], 5)

    def test_build_preview_response_keeps_current_fallback_utility_blocker(self):
        service = FakeArtifactService()
        response = build_preview_response(
            artifact_service=service,
            result_data={
                "run_summary": {
                    "engineering_status": {"trust_score": 65.0},
                    "reliability_summary": {"operational_state": "retryable", "release_ready": False},
                    "optimization_summary": {},
                    "convergence_summary": {
                        "converged": True,
                        "passes_run": 1,
                        "unresolved_conflict_count": 0,
                        "assumption_summary": {"count": 0, "categories": [], "examples": []},
                        "fix_summary": {"autofix_actions": []},
                        "rerun_summary": {"total_reruns": 0, "stage_counts": {}, "reason_counts": {}},
                        "dominant_issue_categories": [],
                        "unresolved_issue_categories": [],
                        "blocked_exports": ["drainage", "utilities"],
                        "blocked_reasons": ["storm_network_missing", "utility_fallback_used"],
                    },
                    "requested_deliverables": ["grading_plan", "utility_plan"],
                    "produced_deliverables": ["grading_plan", "utility_plan"],
                    "failed_deliverables": [],
                    "ready_deliverables": ["grading_plan", "utility_plan"],
                    "extra_deliverables": [],
                },
                "final_plan": {
                    "project_name": "Current Guard Wins",
                    "actions": [
                        {"layer": "FG_CONTOUR"},
                        {"layer": "UTILITY"},
                    ],
                    "meta": {
                        "grading": {"export_validation": {"ready": False, "reasons": ["grading_export_not_ready"]}},
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
                        "deliverables": {"requested": ["grading_plan", "utility_plan"], "produced": ["grading_plan", "utility_plan"]},
                    },
                },
            },
        )
        review = response["summary"]["review"]
        self.assertEqual(review["blocked_exports"], ["utilities"])
        self.assertEqual(review["blocked_reasons"], ["utility_fallback_used"])

    def test_build_preview_response_prefers_reliability_release_ready_over_review_status(self):
        service = FakeArtifactService()
        response = build_preview_response(
            artifact_service=service,
            result_data={
                "run_summary": {
                    "engineering_status": {"trust_score": 84.0},
                    "reliability_summary": {"operational_state": "ready", "release_ready": True},
                    "optimization_summary": {},
                    "convergence_summary": {
                        "converged": False,
                        "passes_run": 3,
                        "unresolved_conflict_count": 2,
                        "assumption_summary": {"count": 1, "categories": ["design"], "examples": ["Defaulted drive aisle width."]},
                        "fix_summary": {"autofix_actions": []},
                        "rerun_summary": {"total_reruns": 1, "stage_counts": {"layout": 1}, "reason_counts": {"layout_retry": 1}},
                        "dominant_issue_categories": [],
                        "unresolved_issue_categories": ["general", "validation"],
                        "blocked_exports": [],
                        "blocked_reasons": [],
                    },
                    "requested_deliverables": ["site_plan", "grading_plan"],
                    "produced_deliverables": ["site_plan", "grading_plan"],
                    "failed_deliverables": [],
                    "ready_deliverables": ["site_plan", "grading_plan"],
                    "extra_deliverables": [],
                },
                "final_plan": {
                    "project_name": "Release Ready Reliability",
                    "actions": [{"layer": "BUILDING"}],
                    "meta": {},
                },
            },
        )
        review = response["summary"]["review"]
        self.assertEqual(review["release_status"], "ready")
        self.assertEqual(review["review_categories"], [])

    def test_build_preview_response_blocks_explicit_release_review_not_ready(self):
        service = FakeArtifactService()
        response = build_preview_response(
            artifact_service=service,
            result_data={
                "run_summary": {
                    "engineering_status": {"trust_score": 84.0},
                    "reliability_summary": {"operational_state": "ready", "release_ready": True},
                    "optimization_summary": {},
                    "convergence_summary": {
                        "converged": True,
                        "passes_run": 1,
                        "unresolved_conflict_count": 0,
                        "assumption_summary": {"count": 0, "categories": [], "examples": []},
                        "fix_summary": {"autofix_actions": []},
                        "rerun_summary": {"total_reruns": 0, "stage_counts": {}, "reason_counts": {}},
                        "dominant_issue_categories": [],
                        "unresolved_issue_categories": [],
                        "blocked_exports": [],
                        "blocked_reasons": [],
                    },
                    "requested_deliverables": ["site_plan"],
                    "produced_deliverables": ["site_plan"],
                    "failed_deliverables": [],
                    "ready_deliverables": ["site_plan"],
                    "extra_deliverables": [],
                },
                "final_plan": {
                    "project_name": "Release Review False",
                    "actions": [{"layer": "BUILDING"}],
                    "meta": {
                        "release_review": {
                            "release_status": "ready",
                            "release_ready": False,
                        }
                    },
                },
            },
        )

        review = response["summary"]["review"]
        self.assertEqual(review["release_status"], "blocked")
        self.assertFalse(review["release_ready"])
        self.assertIn("release_review_not_ready", review["blocked_reasons"])

    def test_build_preview_response_blocks_explicit_blocked_release_status_without_reasons(self):
        service = FakeArtifactService()
        response = build_preview_response(
            artifact_service=service,
            result_data={
                "run_summary": {
                    "engineering_status": {"trust_score": 84.0},
                    "reliability_summary": {"operational_state": "ready", "release_ready": True},
                    "optimization_summary": {},
                    "convergence_summary": {
                        "converged": True,
                        "passes_run": 1,
                        "unresolved_conflict_count": 0,
                        "assumption_summary": {"count": 0, "categories": [], "examples": []},
                        "fix_summary": {"autofix_actions": []},
                        "rerun_summary": {"total_reruns": 0, "stage_counts": {}, "reason_counts": {}},
                        "dominant_issue_categories": [],
                        "unresolved_issue_categories": [],
                        "blocked_exports": [],
                        "blocked_reasons": [],
                    },
                    "requested_deliverables": ["site_plan"],
                    "produced_deliverables": ["site_plan"],
                    "failed_deliverables": [],
                    "ready_deliverables": ["site_plan"],
                    "extra_deliverables": [],
                },
                "final_plan": {
                    "project_name": "Blocked Status",
                    "actions": [{"layer": "BUILDING"}],
                    "meta": {
                        "release_review": {
                            "release_status": "blocked",
                        }
                    },
                },
            },
        )

        review = response["summary"]["review"]
        self.assertEqual(review["release_status"], "blocked")
        self.assertFalse(review["release_ready"])
        self.assertIn("release_status_blocked", review["blocked_reasons"])

    def test_build_preview_response_blocks_failed_deliverables_from_final_meta(self):
        service = FakeArtifactService()
        response = build_preview_response(
            artifact_service=service,
            result_data={
                "run_summary": {
                    "engineering_status": {"trust_score": 90.0},
                    "reliability_summary": {"operational_state": "ready", "release_ready": True},
                    "optimization_summary": {},
                    "convergence_summary": {
                        "converged": True,
                        "passes_run": 1,
                        "unresolved_conflict_count": 0,
                        "assumption_summary": {"count": 0, "categories": [], "examples": []},
                        "fix_summary": {"autofix_actions": []},
                        "rerun_summary": {"total_reruns": 0, "stage_counts": {}, "reason_counts": {}},
                        "dominant_issue_categories": [],
                        "unresolved_issue_categories": [],
                        "blocked_exports": [],
                        "blocked_reasons": [],
                    },
                    "requested_deliverables": ["site_plan", "report"],
                    "produced_deliverables": ["site_plan"],
                    "failed_deliverables": [],
                    "ready_deliverables": ["site_plan", "report"],
                    "extra_deliverables": [],
                },
                "final_plan": {
                    "project_name": "Failed Meta Deliverable",
                    "actions": [{"layer": "BUILDING"}],
                    "meta": {
                        "release_ready": True,
                        "release_status": "ready",
                        "deliverables": {
                            "requested": ["site_plan", "report"],
                            "produced": ["site_plan"],
                            "failed": ["report"],
                        },
                    },
                },
            },
        )

        review = response["summary"]["review"]
        self.assertEqual(review["release_status"], "blocked")
        self.assertFalse(review["release_ready"])
        self.assertEqual(review["failed_deliverables"], ["report"])
        self.assertIn("failed_deliverable_report", review["blocked_reasons"])

    def test_build_preview_response_blocks_missing_requested_deliverables(self):
        service = FakeArtifactService()
        response = build_preview_response(
            artifact_service=service,
            result_data={
                "run_summary": {
                    "engineering_status": {"trust_score": 90.0},
                    "reliability_summary": {"operational_state": "ready", "release_ready": True},
                    "optimization_summary": {},
                    "convergence_summary": {
                        "converged": True,
                        "passes_run": 1,
                        "unresolved_conflict_count": 0,
                        "assumption_summary": {"count": 0, "categories": [], "examples": []},
                        "fix_summary": {"autofix_actions": []},
                        "rerun_summary": {"total_reruns": 0, "stage_counts": {}, "reason_counts": {}},
                        "dominant_issue_categories": [],
                        "unresolved_issue_categories": [],
                        "blocked_exports": [],
                        "blocked_reasons": [],
                    },
                    "requested_deliverables": ["site_plan", "report"],
                    "produced_deliverables": ["site_plan"],
                    "failed_deliverables": [],
                    "ready_deliverables": ["site_plan"],
                    "extra_deliverables": [],
                },
                "final_plan": {
                    "project_name": "Missing Deliverable",
                    "actions": [{"layer": "BUILDING"}],
                    "meta": {
                        "release_ready": True,
                        "release_status": "ready",
                        "deliverables": {
                            "requested": ["site_plan", "report"],
                            "produced": ["site_plan"],
                            "failed": [],
                        },
                    },
                },
            },
        )

        review = response["summary"]["review"]
        self.assertEqual(review["release_status"], "blocked")
        self.assertFalse(review["release_ready"])
        self.assertEqual(review["ready_deliverables"], ["site_plan"])
        self.assertEqual(review["missing_deliverables"], ["report"])
        self.assertIn("missing_deliverable_report", review["blocked_reasons"])

    def test_build_preview_response_merges_final_deliverable_requests(self):
        service = FakeArtifactService()
        response = build_preview_response(
            artifact_service=service,
            result_data={
                "run_summary": {
                    "engineering_status": {"trust_score": 90.0},
                    "reliability_summary": {"operational_state": "ready", "release_ready": True},
                    "optimization_summary": {},
                    "convergence_summary": {
                        "converged": True,
                        "passes_run": 1,
                        "unresolved_conflict_count": 0,
                        "assumption_summary": {"count": 0, "categories": [], "examples": []},
                        "fix_summary": {"autofix_actions": []},
                        "rerun_summary": {"total_reruns": 0, "stage_counts": {}, "reason_counts": {}},
                        "dominant_issue_categories": [],
                        "unresolved_issue_categories": [],
                        "blocked_exports": [],
                        "blocked_reasons": [],
                    },
                    "requested_deliverables": ["site_plan"],
                    "produced_deliverables": ["site_plan"],
                    "failed_deliverables": [],
                    "ready_deliverables": ["site_plan"],
                    "extra_deliverables": [],
                },
                "final_plan": {
                    "project_name": "Final Requested Deliverable",
                    "actions": [{"layer": "BUILDING"}],
                    "meta": {
                        "release_ready": True,
                        "release_status": "ready",
                        "deliverables": {
                            "requested": ["site_plan", "report"],
                            "produced": ["site_plan"],
                            "failed": [],
                        },
                    },
                },
            },
        )

        review = response["summary"]["review"]
        self.assertEqual(review["requested_deliverables"], ["site_plan", "report"])
        self.assertEqual(review["missing_deliverables"], ["report"])
        self.assertFalse(review["release_ready"])
        self.assertIn("missing_deliverable_report", review["blocked_reasons"])

    def test_build_preview_response_blocks_manual_validation_failures_from_final_meta(self):
        service = FakeArtifactService()
        response = build_preview_response(
            artifact_service=service,
            result_data={
                "run_summary": {
                    "engineering_status": {"trust_score": 90.0},
                    "reliability_summary": {"operational_state": "ready", "release_ready": True},
                    "optimization_summary": {},
                    "convergence_summary": {
                        "converged": True,
                        "passes_run": 1,
                        "unresolved_conflict_count": 0,
                        "assumption_summary": {"count": 0, "categories": [], "examples": []},
                        "fix_summary": {"autofix_actions": []},
                        "rerun_summary": {"total_reruns": 0, "stage_counts": {}, "reason_counts": {}},
                        "dominant_issue_categories": [],
                        "unresolved_issue_categories": [],
                        "blocked_exports": [],
                        "blocked_reasons": [],
                    },
                    "requested_deliverables": ["site_plan"],
                    "produced_deliverables": ["site_plan"],
                    "failed_deliverables": [],
                    "ready_deliverables": ["site_plan"],
                    "extra_deliverables": [],
                    "manual_failures": [],
                    "phase_checkpoints": {
                        "layout": {"label": "Layout", "status": "complete", "ready": True, "has_data": True},
                        "grading": {"label": "Grading", "status": "complete", "ready": True, "has_data": True},
                        "drainage_storm": {"label": "Drainage and Storm", "status": "complete", "ready": True, "has_data": True},
                        "utilities": {"label": "Utilities", "status": "complete", "ready": True, "has_data": True},
                        "coordination_validation": {"label": "Coordination and Validation", "status": "complete", "ready": True, "has_data": True},
                        "combined_view": {"label": "Combined View", "status": "ready", "ready": True, "completed_phase_count": 5, "total_phase_count": 5},
                    },
                },
                "final_plan": {
                    "project_name": "Manual Validation Failed Preview",
                    "actions": [{"layer": "BUILDING"}],
                    "meta": {
                        "release_ready": True,
                        "release_status": "ready",
                        "manual_validation": {
                            "failures": [
                                {
                                    "code": "MANUAL_STORM_HYDRAULIC_INVALID",
                                    "message": "Manual storm hydraulic validation failed.",
                                    "system": "storm",
                                    "rule": "hydraulic_capacity",
                                }
                            ]
                        },
                    },
                },
            },
        )

        review = response["summary"]["review"]
        self.assertEqual(review["release_status"], "blocked")
        self.assertFalse(review["release_ready"])
        self.assertEqual(review["manual_failures"][0]["code"], "MANUAL_STORM_HYDRAULIC_INVALID")
        self.assertIn("manual_validation_manual_storm_hydraulic_invalid", review["blocked_reasons"])
        self.assertEqual(review["phase_checkpoints"]["combined_view"]["status"], "blocked")
        self.assertFalse(review["phase_checkpoints"]["combined_view"]["ready"])
        self.assertIn(
            "manual_validation_manual_storm_hydraulic_invalid",
            review["phase_checkpoints"]["combined_view"]["blocked_reasons"],
        )

    def test_build_preview_response_blocks_reactive_post_rerun_release_failures(self):
        service = FakeArtifactService()
        response = build_preview_response(
            artifact_service=service,
            result_data={
                "run_summary": {
                    "engineering_status": {"trust_score": 90.0},
                    "reliability_summary": {"operational_state": "ready", "release_ready": True},
                    "optimization_summary": {},
                    "convergence_summary": {
                        "converged": True,
                        "passes_run": 1,
                        "unresolved_conflict_count": 0,
                        "assumption_summary": {"count": 0, "categories": [], "examples": []},
                        "fix_summary": {"autofix_actions": []},
                        "rerun_summary": {"total_reruns": 0, "stage_counts": {}, "reason_counts": {}},
                        "dominant_issue_categories": [],
                        "unresolved_issue_categories": [],
                        "blocked_exports": [],
                        "blocked_reasons": [],
                    },
                    "requested_deliverables": ["site_plan"],
                    "produced_deliverables": ["site_plan"],
                    "failed_deliverables": [],
                    "ready_deliverables": ["site_plan"],
                    "extra_deliverables": [],
                    "manual_failures": [],
                    "phase_checkpoints": {
                        "layout": {"label": "Layout", "status": "complete", "ready": True, "has_data": True},
                        "combined_view": {"label": "Combined View", "status": "ready", "ready": True, "completed_phase_count": 1, "total_phase_count": 1},
                    },
                },
                "final_plan": {
                    "project_name": "Reactive Blocked Preview",
                    "actions": [{"layer": "BUILDING"}],
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

        review = response["summary"]["review"]
        self.assertEqual(review["release_status"], "blocked")
        self.assertFalse(review["release_ready"])
        self.assertIn("reactive_post_rerun_not_ready", review["blocked_reasons"])
        self.assertIn("manual_validation_manual_storm_hydraulic_invalid", review["blocked_reasons"])
        self.assertEqual(review["phase_checkpoints"]["combined_view"]["status"], "blocked")
        self.assertFalse(review["phase_checkpoints"]["combined_view"]["ready"])

    def test_build_preview_response_blocks_stale_ready_when_construction_package_blocks(self):
        service = FakeArtifactService()
        response = build_preview_response(
            artifact_service=service,
            result_data={
                "run_summary": {
                    "engineering_status": {"trust_score": 90.0},
                    "reliability_summary": {"operational_state": "ready", "release_ready": True},
                    "optimization_summary": {},
                    "convergence_summary": {
                        "converged": True,
                        "passes_run": 1,
                        "unresolved_conflict_count": 0,
                        "assumption_summary": {"count": 0, "categories": [], "examples": []},
                        "fix_summary": {"autofix_actions": []},
                        "rerun_summary": {"total_reruns": 0, "stage_counts": {}, "reason_counts": {}},
                        "dominant_issue_categories": [],
                        "unresolved_issue_categories": [],
                        "blocked_exports": [],
                        "blocked_reasons": [],
                    },
                    "requested_deliverables": ["site_plan"],
                    "produced_deliverables": ["site_plan"],
                    "failed_deliverables": [],
                    "ready_deliverables": ["site_plan"],
                    "extra_deliverables": [],
                },
                "final_plan": {
                    "project_name": "Blocked Construction Package",
                    "actions": [{"layer": "BUILDING"}],
                    "meta": {
                        "construction_package_manifest": {
                            "release_allowed": False,
                            "blockers": [{"area": "deliverables", "field": "construction_package_artifacts"}],
                            "construction_package_artifact_status": {
                                "package_present": True,
                                "missing": ["cad_export"],
                                "anonymous": [],
                                "stale": ["SHEETS-OLD"],
                                "model_reference_present": True,
                                "model_matches_expected": False,
                                "release_ready_flag": None,
                                "untraced": ["QA-1"],
                                "mismatched": [],
                            },
                        }
                    },
                },
            },
        )
        review = response["summary"]["review"]
        self.assertEqual(review["release_status"], "blocked")
        self.assertIn("construction_package_blocked", review["blocked_reasons"])
        self.assertIn("construction_package_missing_artifacts", review["blocked_reasons"])
        self.assertIn("construction_package_stale_artifacts", review["blocked_reasons"])
        self.assertIn("construction_package_model_mismatch", review["blocked_reasons"])
        self.assertIn("construction_package_release_not_marked_ready", review["blocked_reasons"])
        self.assertIn("construction_package_untraced_artifacts", review["blocked_reasons"])

    def test_build_preview_response_blocks_construction_ready_without_manifest(self):
        service = FakeArtifactService()
        response = build_preview_response(
            artifact_service=service,
            result_data={
                "run_summary": {
                    "engineering_status": {"trust_score": 90.0},
                    "reliability_summary": {"operational_state": "ready", "release_ready": True},
                    "optimization_summary": {},
                    "convergence_summary": {
                        "converged": True,
                        "passes_run": 1,
                        "unresolved_conflict_count": 0,
                        "assumption_summary": {"count": 0, "categories": [], "examples": []},
                        "fix_summary": {"autofix_actions": []},
                        "rerun_summary": {"total_reruns": 0, "stage_counts": {}, "reason_counts": {}},
                        "dominant_issue_categories": [],
                        "unresolved_issue_categories": [],
                        "blocked_exports": [],
                        "blocked_reasons": [],
                    },
                    "requested_deliverables": ["site_plan"],
                    "produced_deliverables": ["site_plan"],
                    "failed_deliverables": [],
                    "ready_deliverables": ["site_plan"],
                    "extra_deliverables": [],
                },
                "final_plan": {
                    "project_name": "Missing Manifest",
                    "actions": [{"layer": "BUILDING"}],
                    "meta": {
                        "construction_readiness": {"ready": True, "status": "construction_ready"},
                    },
                },
            },
        )

        review = response["summary"]["review"]
        self.assertEqual(review["release_status"], "blocked")
        self.assertIn("construction_package_manifest_missing", review["blocked_reasons"])

    def test_build_preview_response_blocks_required_construction_release_without_readiness(self):
        service = FakeArtifactService()
        response = build_preview_response(
            artifact_service=service,
            result_data={
                "run_summary": {
                    "engineering_status": {"trust_score": 90.0},
                    "reliability_summary": {"operational_state": "ready", "release_ready": True},
                    "optimization_summary": {},
                    "convergence_summary": {
                        "converged": True,
                        "passes_run": 1,
                        "unresolved_conflict_count": 0,
                        "assumption_summary": {"count": 0, "categories": [], "examples": []},
                        "fix_summary": {"autofix_actions": []},
                        "rerun_summary": {"total_reruns": 0, "stage_counts": {}, "reason_counts": {}},
                        "dominant_issue_categories": [],
                        "unresolved_issue_categories": [],
                        "blocked_exports": [],
                        "blocked_reasons": [],
                    },
                    "requested_deliverables": ["site_plan"],
                    "produced_deliverables": ["site_plan"],
                    "failed_deliverables": [],
                    "ready_deliverables": ["site_plan"],
                    "extra_deliverables": [],
                },
                "final_plan": {
                    "project_name": "Construction Release Required",
                    "actions": [{"layer": "BUILDING"}],
                    "meta": {"construction_release_required": True},
                },
            },
        )

        review = response["summary"]["review"]
        self.assertEqual(review["release_status"], "blocked")
        self.assertIn("construction_readiness_missing", review["blocked_reasons"])

    def test_build_preview_response_blocks_false_allowed_incomplete_package(self):
        service = FakeArtifactService()
        response = build_preview_response(
            artifact_service=service,
            result_data={
                "run_summary": {
                    "engineering_status": {"trust_score": 90.0},
                    "reliability_summary": {"operational_state": "ready", "release_ready": True},
                    "optimization_summary": {},
                    "convergence_summary": {
                        "converged": True,
                        "passes_run": 1,
                        "unresolved_conflict_count": 0,
                        "assumption_summary": {"count": 0, "categories": [], "examples": []},
                        "fix_summary": {"autofix_actions": []},
                        "rerun_summary": {"total_reruns": 0, "stage_counts": {}, "reason_counts": {}},
                        "dominant_issue_categories": [],
                        "unresolved_issue_categories": [],
                        "blocked_exports": [],
                        "blocked_reasons": [],
                    },
                    "requested_deliverables": ["site_plan"],
                    "produced_deliverables": ["site_plan"],
                    "failed_deliverables": [],
                    "ready_deliverables": ["site_plan"],
                    "extra_deliverables": [],
                },
                "final_plan": {
                    "project_name": "False Allowed Package",
                    "actions": [{"layer": "BUILDING"}],
                    "meta": {
                        "construction_readiness": {"ready": True, "status": "construction_ready"},
                        "construction_package_manifest": {
                            "release_allowed": True,
                            "construction_package_artifact_status": {"complete_for_release": False},
                            "professional_package_release_status": {
                                "model_matches_package": False,
                                "package_matches_review": False,
                            },
                        },
                    },
                },
            },
        )

        review = response["summary"]["review"]
        self.assertEqual(review["release_status"], "blocked")
        self.assertIn("construction_package_incomplete_release", review["blocked_reasons"])
        self.assertIn("construction_professional_release_untraced", review["blocked_reasons"])

    def test_build_preview_response_blocks_invalid_professional_release_metadata(self):
        service = FakeArtifactService()
        response = build_preview_response(
            artifact_service=service,
            result_data={
                "run_summary": {
                    "engineering_status": {"trust_score": 90.0},
                    "reliability_summary": {"operational_state": "ready", "release_ready": True},
                    "optimization_summary": {},
                    "convergence_summary": {
                        "converged": True,
                        "passes_run": 1,
                        "unresolved_conflict_count": 0,
                        "assumption_summary": {"count": 0, "categories": [], "examples": []},
                        "fix_summary": {"autofix_actions": []},
                        "rerun_summary": {"total_reruns": 0, "stage_counts": {}, "reason_counts": {}},
                        "dominant_issue_categories": [],
                        "unresolved_issue_categories": [],
                        "blocked_exports": [],
                        "blocked_reasons": [],
                    },
                    "requested_deliverables": ["site_plan"],
                    "produced_deliverables": ["site_plan"],
                    "failed_deliverables": [],
                    "ready_deliverables": ["site_plan"],
                    "extra_deliverables": [],
                },
                "final_plan": {
                    "project_name": "Invalid Professional Release",
                    "actions": [{"layer": "BUILDING"}],
                    "meta": {
                        "construction_readiness": {"ready": True, "status": "construction_ready"},
                        "construction_package_manifest": {
                            "release_allowed": True,
                            "construction_package_artifact_status": {"complete_for_release": True},
                            "professional_package_release_status": {
                                "professional_release_valid": False,
                                "professional_release_validation": {
                                    "released_for_construction": False,
                                    "blockers": [{"field": "license_number"}],
                                },
                                "model_matches_package": True,
                                "package_matches_review": True,
                            },
                        },
                    },
                },
            },
        )

        review = response["summary"]["review"]
        self.assertEqual(review["release_status"], "blocked")
        self.assertIn("construction_professional_release_invalid", review["blocked_reasons"])
        self.assertNotIn("construction_professional_release_untraced", review["blocked_reasons"])

    def test_build_preview_response_normalizes_phase_checkpoints_for_release_ready_runs(self):
        service = FakeArtifactService()
        response = build_preview_response(
            artifact_service=service,
            result_data={
                "run_summary": {
                    "engineering_status": {"trust_score": 90.0},
                    "reliability_summary": {"operational_state": "ready", "release_ready": True},
                    "optimization_summary": {},
                    "convergence_summary": {
                        "converged": True,
                        "passes_run": 2,
                        "unresolved_conflict_count": 0,
                        "assumption_summary": {"count": 1, "categories": ["design"], "examples": ["Defaulted aisle width."]},
                        "fix_summary": {"autofix_actions": []},
                        "rerun_summary": {"total_reruns": 0, "stage_counts": {}, "reason_counts": {}},
                        "dominant_issue_categories": [],
                        "unresolved_issue_categories": ["coordination", "validation"],
                        "blocked_exports": [],
                        "blocked_reasons": [],
                    },
                    "requested_deliverables": ["site_plan", "grading_plan", "storm_pipe_plan", "utility_plan"],
                    "produced_deliverables": ["site_plan", "grading_plan", "storm_pipe_plan", "utility_plan"],
                    "failed_deliverables": [],
                    "ready_deliverables": ["site_plan", "grading_plan", "storm_pipe_plan", "utility_plan"],
                    "extra_deliverables": [],
                    "phase_checkpoints": {
                        "layout": {"label": "Layout", "status": "partial", "ready": False, "has_data": True, "messages": ["Stage skipped because canonical state is already clean."], "deliverables": ["site_plan"]},
                        "grading": {"label": "Grading", "status": "complete", "ready": True, "has_data": True, "deliverables": ["grading_plan"]},
                        "drainage_storm": {"label": "Drainage and Storm", "status": "complete", "ready": True, "has_data": True, "deliverables": ["storm_pipe_plan"]},
                        "utilities": {"label": "Utilities", "status": "partial", "ready": False, "has_data": True, "messages": ["Sanitary stage skipped because sanitary was not requested."], "deliverables": ["utility_plan"]},
                        "coordination_validation": {"label": "Coordination and Validation", "status": "failed", "ready": False, "has_data": True, "messages": ["Coordination stage completed with unresolved conflicts."], "deliverables": []},
                        "combined_view": {"label": "Combined View", "status": "review", "ready": False, "completed_phase_count": 2, "total_phase_count": 5, "blocked_exports": [], "blocked_reasons": []},
                    },
                },
                "final_plan": {
                    "project_name": "Release Ready Phase Cleanup",
                    "actions": [{"layer": "BUILDING"}],
                    "meta": {},
                },
            },
        )
        review = response["summary"]["review"]
        self.assertEqual(review["release_status"], "ready")
        self.assertEqual(review["phase_checkpoints"]["layout"]["status"], "complete")
        self.assertEqual(review["phase_checkpoints"]["utilities"]["status"], "complete")
        self.assertEqual(review["phase_checkpoints"]["coordination_validation"]["status"], "complete")
        self.assertEqual(review["phase_checkpoints"]["combined_view"]["status"], "ready")
        self.assertEqual(review["phase_checkpoints"]["combined_view"]["completed_phase_count"], 5)

    def test_build_preview_response_normalizes_legacy_ready_status_when_reliability_flag_is_false(self):
        service = FakeArtifactService()
        response = build_preview_response(
            artifact_service=service,
            result_data={
                "run_summary": {
                    "engineering_status": {"trust_score": 74.0},
                    "reliability_summary": {"operational_state": "review", "release_ready": False},
                    "optimization_summary": {},
                    "convergence_summary": {
                        "converged": False,
                        "passes_run": 1,
                        "unresolved_conflict_count": 0,
                        "assumption_summary": {"count": 1, "categories": ["design"], "examples": ["Legacy saved run."]},
                        "fix_summary": {"autofix_actions": []},
                        "rerun_summary": {"total_reruns": 0, "stage_counts": {}, "reason_counts": {}},
                        "dominant_issue_categories": [],
                        "unresolved_issue_categories": ["coordination", "validation"],
                        "blocked_exports": [],
                        "blocked_reasons": [],
                    },
                    "requested_deliverables": ["site_plan", "storm_pipe_plan"],
                    "produced_deliverables": ["site_plan", "storm_pipe_plan"],
                    "failed_deliverables": [],
                    "ready_deliverables": ["site_plan", "storm_pipe_plan"],
                    "extra_deliverables": [],
                    "phase_checkpoints": {
                        "layout": {"label": "Layout", "status": "partial", "ready": False, "has_data": True, "messages": ["Stage skipped because canonical state is already clean."], "deliverables": ["site_plan"]},
                        "grading": {"label": "Grading", "status": "complete", "ready": True, "has_data": True, "deliverables": []},
                        "drainage_storm": {"label": "Drainage and Storm", "status": "complete", "ready": True, "has_data": True, "deliverables": ["storm_pipe_plan"]},
                        "utilities": {"label": "Utilities", "status": "partial", "ready": False, "has_data": False, "messages": ["Sanitary stage skipped because sanitary was not requested."], "deliverables": []},
                        "coordination_validation": {"label": "Coordination and Validation", "status": "failed", "ready": False, "has_data": True, "messages": ["Coordination stage completed with unresolved conflicts."], "deliverables": []},
                        "combined_view": {"label": "Combined View", "status": "review", "ready": False, "completed_phase_count": 2, "total_phase_count": 5, "blocked_exports": [], "blocked_reasons": []},
                    },
                },
                "final_plan": {
                    "project_name": "Legacy Ready Status",
                    "actions": [{"layer": "BUILDING"}],
                    "meta": {"release_review": {"release_status": "ready", "release_note": "Release-ready engineering state."}},
                },
            },
        )
        review = response["summary"]["review"]
        self.assertEqual(review["release_status"], "ready")
        self.assertEqual(review["review_categories"], [])
        self.assertEqual(review["phase_checkpoints"]["combined_view"]["status"], "ready")
        self.assertEqual(review["phase_checkpoints"]["combined_view"]["completed_phase_count"], 5)

    def test_build_preview_response_reconciles_phase_checkpoints_from_stage_statuses(self):
        service = FakeArtifactService()
        response = build_preview_response(
            artifact_service=service,
            result_data={
                "run_summary": {
                    "engineering_status": {"trust_score": 68.0},
                    "reliability_summary": {"operational_state": "review", "release_ready": False},
                    "optimization_summary": {},
                    "convergence_summary": {
                        "converged": False,
                        "passes_run": 3,
                        "unresolved_conflict_count": 0,
                        "assumption_summary": {"count": 1, "categories": ["design"], "examples": ["Staged run."]},
                        "fix_summary": {"autofix_actions": []},
                        "rerun_summary": {"total_reruns": 1, "stage_counts": {"layout": 1}, "reason_counts": {}},
                        "dominant_issue_categories": [],
                        "unresolved_issue_categories": [],
                        "blocked_exports": [],
                        "blocked_reasons": [],
                    },
                    "requested_deliverables": ["site_plan", "grading_plan", "storm_pipe_plan"],
                    "produced_deliverables": ["site_plan", "grading_plan", "storm_pipe_plan"],
                    "failed_deliverables": [],
                    "ready_deliverables": ["site_plan", "grading_plan", "storm_pipe_plan"],
                    "extra_deliverables": [],
                    "phase_checkpoints": {
                        "layout": {"label": "Layout", "status": "partial", "ready": False, "has_data": True},
                        "grading": {"label": "Grading", "status": "partial", "ready": False, "has_data": True},
                        "drainage_storm": {"label": "Drainage and Storm", "status": "complete", "ready": True, "has_data": True},
                        "utilities": {"label": "Utilities", "status": "pending", "ready": False, "has_data": False},
                        "coordination_validation": {"label": "Coordination and Validation", "status": "pending", "ready": False, "has_data": False},
                        "combined_view": {"label": "Combined View", "status": "review", "ready": False, "completed_phase_count": 1, "total_phase_count": 5},
                    },
                },
                "final_plan": {
                    "project_name": "Drainage Checkpoint",
                    "actions": [{"layer": "BUILDING"}, {"layer": "DRAIN"}, {"layer": "PIPE"}, {"layer": "BASIN_BOUNDARY"}],
                    "meta": {
                        "stage_completeness": {
                            "statuses": {
                                "layout": "complete",
                                "grading": "complete",
                                "drainage": "complete",
                                "storm_pipes": "complete",
                            }
                        }
                    },
                },
            },
        )
        review = response["summary"]["review"]
        self.assertEqual(review["phase_checkpoints"]["layout"]["status"], "complete")
        self.assertEqual(review["phase_checkpoints"]["grading"]["status"], "complete")
        self.assertEqual(review["phase_checkpoints"]["drainage_storm"]["status"], "complete")
        self.assertEqual(review["phase_checkpoints"]["combined_view"]["status"], "partial")
        self.assertEqual(review["phase_checkpoints"]["combined_view"]["completed_phase_count"], 3)

    def test_build_preview_response_does_not_count_assumed_stage_as_complete(self):
        service = FakeArtifactService()
        response = build_preview_response(
            artifact_service=service,
            result_data={
                "run_summary": {
                    "engineering_status": {"trust_score": 60.0},
                    "reliability_summary": {"operational_state": "review", "release_ready": False},
                    "optimization_summary": {},
                    "convergence_summary": {"converged": False, "blocked_exports": [], "blocked_reasons": []},
                    "phase_checkpoints": {
                        "layout": {"label": "Layout", "status": "complete", "ready": True, "has_data": True},
                        "grading": {"label": "Grading", "status": "pending", "ready": False, "has_data": False},
                        "drainage_storm": {"label": "Drainage and Storm", "status": "pending", "ready": False, "has_data": False},
                        "utilities": {"label": "Utilities", "status": "pending", "ready": False, "has_data": False},
                        "coordination_validation": {"label": "Coordination and Validation", "status": "pending", "ready": False, "has_data": False},
                        "combined_view": {"label": "Combined View", "status": "partial", "ready": False, "completed_phase_count": 1, "total_phase_count": 5},
                    },
                },
                "final_plan": {
                    "project_name": "Assumed Utilities",
                    "actions": [{"layer": "SITE"}],
                    "meta": {
                        "stage_completeness": {
                            "statuses": {
                                "layout": "complete",
                                "sanitary": "assumed",
                            }
                        }
                    },
                },
            },
        )

        review = response["summary"]["review"]
        self.assertEqual(review["phase_checkpoints"]["utilities"]["status"], "partial")
        self.assertFalse(review["phase_checkpoints"]["utilities"]["ready"])
        self.assertEqual(review["phase_checkpoints"]["combined_view"]["completed_phase_count"], 1)

    def test_build_preview_response_drops_general_when_other_review_categories_exist(self):
        service = FakeArtifactService()
        response = build_preview_response(
            artifact_service=service,
            result_data={
                "run_summary": {
                    "engineering_status": {"trust_score": 61.0},
                    "reliability_summary": {"operational_state": "review", "release_ready": False},
                    "optimization_summary": {},
                    "convergence_summary": {
                        "converged": False,
                        "passes_run": 2,
                        "unresolved_conflict_count": 3,
                        "assumption_summary": {"count": 0, "categories": [], "examples": []},
                        "fix_summary": {"autofix_actions": []},
                        "rerun_summary": {"total_reruns": 0, "stage_counts": {}, "reason_counts": {}},
                        "dominant_issue_categories": [],
                        "unresolved_issue_categories": ["general", "coordination", "validation"],
                        "blocked_exports": [],
                        "blocked_reasons": [],
                    },
                    "requested_deliverables": ["site_plan"],
                    "produced_deliverables": ["site_plan"],
                    "failed_deliverables": [],
                    "ready_deliverables": ["site_plan"],
                    "extra_deliverables": [],
                },
                "final_plan": {
                    "project_name": "Category Cleanup",
                    "actions": [{"layer": "BUILDING"}],
                    "meta": {},
                },
            },
        )
        review = response["summary"]["review"]
        self.assertEqual(review["review_categories"], ["coordination", "validation"])

    def test_final_plan_from_result_still_enforces_export_guard_by_default(self):
        with self.assertRaises(HTTPException):
            final_plan_from_result(
                {
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
                }
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

    def test_export_dxf_artifact_blocks_required_construction_release_without_readiness(self):
        service = FakeArtifactService()
        store = FakeProjectStore()
        result_data = {
            "final_plan": {
                "project_name": "Blocked IFC DXF",
                "actions": [{"task": "polyline", "layer": "LOT", "points": [[0, 0], [1, 0]]}],
                "meta": {"construction_release_required": True},
            }
        }

        with self.assertRaises(HTTPException) as ctx:
            export_dxf_artifact(
                artifact_service=service,
                project_store=store,
                user_id="u1",
                project_id="p1",
                result_data=result_data,
                filename_stem="blocked-ifc",
            )

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("construction_readiness_missing", str(ctx.exception.detail))
        self.assertIsNone(service.dxf_export)

    def test_export_report_artifact_updates_project_workflow(self):
        service = FakeArtifactService()
        store = FakeProjectStore()
        result_data = {
            "success": True,
            "message": "ok",
            "warnings": [],
            "errors": [],
            "final_plan": {
                "project_name": "Report Demo",
                "actions": [{"task": "polyline", "layer": "LOT", "points": [[0, 0], [1, 0], [1, 1], [0, 1]]}],
                "meta": {
                    "engineering_status": {"engineering_trust_score": 88.0},
                    "convergence_summary": {
                        "converged": True,
                        "passes_run": 1,
                        "unresolved_conflict_count": 0,
                        "assumption_summary": {"count": 1, "categories": ["general"], "examples": ["Defaulted outlet concept."]},
                        "fix_summary": {"autofix_actions": []},
                        "dominant_issue_categories": [],
                        "unresolved_issue_categories": [],
                        "blocked_exports": [],
                        "blocked_reasons": [],
                        "rerun_summary": {"total_reruns": 0, "stage_counts": {}, "reason_counts": {}},
                    },
                    "deliverables": {
                        "requested": ["site_plan", "report"],
                        "produced": ["site_plan", "report"],
                        "failed": [],
                    },
                },
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
        release_review = service.report_export["result_data"]["request_metadata"]["release_review"]
        self.assertEqual(release_review["release_status"], "ready")
        self.assertEqual(release_review["reliability"]["operational_state"], "ready")
        self.assertEqual(release_review["requested_deliverables"], ["site_plan", "report"])
        self.assertEqual(
            store.saved_payload["metadata"]["workflow"]["artifacts"][0]["kind"],
            "report",
        )


if __name__ == "__main__":
    unittest.main()
