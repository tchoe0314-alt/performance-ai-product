from copy import deepcopy
import unittest
from types import SimpleNamespace
from fastapi import HTTPException
from backend.application.design_workflows import prepare_reactive_orchestration_payload, run_orchestration

from backend.services.canonical_canvas import reconcile_canvas_save, resolve_canvas_input, with_canvas_snapshot
from backend.services.canonical_project import PROJECT_DOCUMENT_KEY, ProjectDocumentError, new_project_document


class CanonicalCanvasGatewayTests(unittest.TestCase):
    def test_direct_and_queued_api_models_preserve_documents_and_omit_absent_slot(self):
        from backend.api.app import OrchestratePayload, QueueOrchestratePayload, _orchestration_request_payload, _queue_request_payload_with_project
        self.assertNotIn(PROJECT_DOCUMENT_KEY, _orchestration_request_payload(OrchestratePayload()))
        payload = with_canvas_snapshot(self.fixture())
        payload["manual_fields"]["site_objects"][0]["x"] = 999
        direct = _orchestration_request_payload(OrchestratePayload(**payload))
        _, queued = _queue_request_payload_with_project(QueueOrchestratePayload(request=OrchestratePayload(**payload)))
        for result in (direct, queued):
            self.assertEqual(result["manual_fields"]["site_objects"][0]["x"], 125.25)
            self.assertEqual(result[PROJECT_DOCUMENT_KEY], payload[PROJECT_DOCUMENT_KEY])
        with self.assertRaises(HTTPException) as caught:
            _orchestration_request_payload(OrchestratePayload(canonical_project_v1={}))
        self.assertEqual(caught.exception.status_code, 422)

    def test_calculation_preparation_and_engine_receive_canonical_geometry_and_units(self):
        payload = with_canvas_snapshot(self.fixture())
        payload["manual_fields"]["site_objects"][0]["x"] = 999
        payload["canonical_project_v1"]["units"]["length"] = "m"
        seen = []
        def engine(request):
            seen.append(request)
            return SimpleNamespace(success=True, message="ok", parsed_payload={}, final_plan={"actions": [], "meta": {}},
                                   warnings=[], errors=[], issues=[], assumptions=[], metadata={})
        prepared = prepare_reactive_orchestration_payload(payload)
        self.assertEqual(prepared["manual_fields"]["site_objects"][0]["x"], 125.25)
        result = run_orchestration(payload, load_orchestrator=lambda: (SimpleNamespace, engine), assess_design_readiness=lambda *_: None)
        self.assertTrue(result["success"])
        self.assertEqual(seen[0].manual_fields["site_objects"][0]["x"], 125.25)
        self.assertEqual(seen[0].units, "m")

    def test_invalid_calculation_document_blocks_before_loading_engine(self):
        def unexpected():
            raise AssertionError("Invalid document reached engine loading")
        with self.assertRaises(HTTPException) as caught:
            run_orchestration({PROJECT_DOCUMENT_KEY: {}}, load_orchestrator=unexpected, assess_design_readiness=lambda *_: None)
        self.assertEqual(caught.exception.status_code, 422)

    def test_unknown_canonical_units_do_not_silently_run_as_feet(self):
        payload = with_canvas_snapshot(self.fixture())
        payload[PROJECT_DOCUMENT_KEY]["units"]["length"] = None
        with self.assertRaises(HTTPException) as caught:
            run_orchestration(payload, load_orchestrator=lambda: self.fail("Engine must not load"), assess_design_readiness=lambda *_: None)
        self.assertEqual(caught.exception.status_code, 422)

    def fixture(self):
        return {"prompt_text": "Legacy chat controls", "manual_fields": {"units": "ft", "project_name": "Pilot",
            "site_objects": [
                {"id": "building", "type": "office_building", "x": 125.25, "y": -2, "w": 160, "d": 90, "rotation": 17},
                {"id": "road", "type": "road", "meta": {"cul_de_sac_v1": {"roadWidthFt": 40, "bulbRadiusFt": 50}}},
                {"id": "pipe", "type": "utility_corridor", "geometry": [[0.125, 1], [40.75, 1]],
                 "meta": {"vertical_extent_v1": {"minFt": -6, "maxFt": -5, "reviewed": True}}},
                {"id": "other", "type": "future_type", "unknown": {"retain": [False, 0]}},
            ]}, "meta": {"site_inputs": {"candidate_review_decisions_v1": []}}}

    def test_exact_geometry_and_unknown_data_round_trip(self):
        legacy = self.fixture()
        before = deepcopy(legacy)
        compiled = with_canvas_snapshot(legacy)
        resolved = resolve_canvas_input(compiled)
        del resolved[PROJECT_DOCUMENT_KEY]
        self.assertEqual(resolved, before)
        self.assertEqual(legacy, before)
        self.assertEqual(len(compiled[PROJECT_DOCUMENT_KEY]["buildings"]), 1)
        self.assertEqual(len(compiled[PROJECT_DOCUMENT_KEY]["cul_de_sacs"]), 1)
        self.assertEqual(len(compiled[PROJECT_DOCUMENT_KEY]["utilities"]), 1)

    def test_canonical_geometry_wins_over_legacy_shadow(self):
        compiled = with_canvas_snapshot(self.fixture())
        compiled["manual_fields"]["site_objects"][0]["x"] = 999
        self.assertEqual(resolve_canvas_input(compiled)["manual_fields"]["site_objects"][0]["x"], 125.25)

    def test_unmapped_sections_and_records_survive_recompile(self):
        prior = new_project_document()
        prior["client"] = {"name": "Client"}
        prior["revisions"] = [{"id": "revision-1"}]
        prior["buildings"] = [{"unmigrated_record": {"retain": True}}]
        compiled = with_canvas_snapshot(self.fixture(), prior)
        for _ in range(3): compiled = with_canvas_snapshot(compiled)
        doc = compiled[PROJECT_DOCUMENT_KEY]
        self.assertEqual(doc["client"], prior["client"])
        self.assertEqual(doc["revisions"], prior["revisions"])
        self.assertEqual(len(doc["buildings"]), 2)

    def test_empty_canvas_is_an_explicit_snapshot(self):
        compiled = with_canvas_snapshot(self.fixture())
        incoming = deepcopy(compiled)
        incoming["manual_fields"]["site_objects"] = []
        cleared = with_canvas_snapshot(incoming)
        saved = reconcile_canvas_save(compiled, cleared, cleared)
        self.assertEqual(resolve_canvas_input(saved)["manual_fields"]["site_objects"], [])

    def test_legacy_server_writer_refreshes_snapshot_and_keeps_source_review(self):
        existing = with_canvas_snapshot(self.fixture())
        incoming = deepcopy(existing)
        incoming["manual_fields"]["site_objects"][0]["x"] = 150.5
        incoming["meta"]["site_inputs"]["candidate_review_decisions_v1"] = [{"action": "accept"}]
        reconciled = reconcile_canvas_save(existing, incoming, incoming)
        self.assertEqual(resolve_canvas_input(reconciled)["manual_fields"]["site_objects"][0]["x"], 150.5)
        self.assertEqual(resolve_canvas_input(reconciled)["meta"], incoming["meta"])
        self.assertEqual(resolve_canvas_input(existing)["manual_fields"]["site_objects"][0]["x"], 125.25)

    def test_malformed_references_reject_partial_geometry(self):
        for change in ("duplicate", "missing", "unknown", "bool", "incomplete"):
            compiled = with_canvas_snapshot(self.fixture())
            refs = compiled[PROJECT_DOCUMENT_KEY]["extensions"]["canvas_workspace_v1"]["object_order"]
            if change == "duplicate": refs.append(refs[0])
            elif change == "missing": refs[0]["index"] = 999
            elif change == "unknown": refs[0]["section"] = "project"
            elif change == "bool": refs[0]["index"] = True
            else: refs.pop()
            with self.subTest(change=change), self.assertRaises(ProjectDocumentError): resolve_canvas_input(compiled)

    def test_legacy_and_foundation_only_documents_remain_compatible(self):
        legacy = self.fixture()
        self.assertEqual(resolve_canvas_input(legacy), legacy)
        legacy[PROJECT_DOCUMENT_KEY] = new_project_document()
        self.assertEqual(resolve_canvas_input(legacy), legacy)
