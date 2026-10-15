from copy import deepcopy
import unittest

from fastapi import HTTPException

from backend.application.project_workflows import save_project_record
from backend.services.canonical_project import (
    COLLECTION_SECTIONS, MAPPING_SECTIONS, PROJECT_DOCUMENT_KEY, ProjectDocumentError,
    dumps_project_document, loads_project_document, new_project_document,
    validate_project_document,
)
from backend.services.project_store import _merge_project_input as store_merge
from backend.application.project_workflows import _merge_project_input as workflow_merge


class CanonicalProjectDocumentTests(unittest.TestCase):
    def test_all_roadmap_sections_and_unknown_coordinate_defaults(self):
        doc = new_project_document(name="Pilot")
        self.assertEqual(set(doc), {"schema_version", *MAPPING_SECTIONS, *COLLECTION_SECTIONS})
        self.assertIsNone(doc["units"]["length"])
        self.assertIsNone(doc["coordinate_system"]["horizontal_crs"])
        doc["roads"].append({"id": "road-1"})
        self.assertEqual(new_project_document()["roads"], [])

    def test_exact_round_trip_preserves_every_section_and_native_geometry(self):
        doc = new_project_document(name="Pilot")
        for section in COLLECTION_SECTIONS:
            doc[section] = [{"id": section + "-1", "custom": {"zero": 0, "empty": [], "false": False}}]
        doc["roads"][0]["geometry"] = [[0.125, -5.5], [45.25, 20.0]]
        doc["cul_de_sacs"][0]["parameters"] = {"roadWidthFt": 40, "bulbRadiusFt": 50, "islandRadiusFt": 15}
        doc["extensions"] = {"unknown_legacy_data": {"exact": [None, False, 0]}}
        restored = loads_project_document(dumps_project_document(doc))
        self.assertEqual(restored, doc)
        self.assertEqual(dumps_project_document(restored), dumps_project_document(doc))

    def test_validation_is_detached_from_callers(self):
        doc = new_project_document()
        validated = validate_project_document(doc)
        validated["project"]["name"] = "Changed"
        self.assertEqual(doc["project"]["name"], "")

    def test_invalid_payloads_are_rejected_without_echoing_values(self):
        base = new_project_document()
        cases = [None, {}, {**base, "schema_version": "future"},
                 {**base, "roads": {}}, {**base, "roads": ["private-input"]},
                 {**base, "client": []}, {**base, "unregistered": "private-input"},
                 {**base, "units": {"length": float("nan")}},
                 {**base, "extensions": {1: "private-input"}},
                 {**base, "extensions": {"tuple": (1, 2)}}]
        missing = deepcopy(base)
        del missing["utilities"]
        cases.append(missing)
        for value in cases:
            with self.subTest(value_type=type(value).__name__):
                with self.assertRaises(ProjectDocumentError) as caught:
                    validate_project_document(value)
                self.assertNotIn("private-input", str(caught.exception))

    def test_duplicate_keys_invalid_json_and_nonfinite_values_rejected(self):
        for raw in ('{"schema_version":"old","schema_version":"civora_project_v1"}', '{', 'null'):
            with self.assertRaises(ProjectDocumentError):
                loads_project_document(raw)
        doc = new_project_document()
        doc["site"] = {"elevation": float("inf")}
        with self.assertRaises(ProjectDocumentError):
            dumps_project_document(doc)

    def test_cyclic_values_rejected(self):
        doc = new_project_document()
        doc["extensions"]["cycle"] = doc
        with self.assertRaises(ProjectDocumentError):
            validate_project_document(doc)

    def test_both_merge_layers_replace_snapshots_and_preserve_legacy_behavior(self):
        old = new_project_document()
        old["buildings"] = [{"id": "building-1"}]
        old["site"] = {"setback": 25, "locked": True}
        new = new_project_document()
        new["site"] = {"setback": 0, "locked": False}
        existing = {PROJECT_DOCUMENT_KEY: old, "legacy": ["keep"]}
        incoming = {PROJECT_DOCUMENT_KEY: new, "legacy": []}
        for merge in (store_merge, workflow_merge):
            result = merge(existing, incoming)
            self.assertEqual(result[PROJECT_DOCUMENT_KEY], new)
            self.assertEqual(result["legacy"], ["keep"])
            self.assertEqual(merge(existing, {"other": 1})[PROJECT_DOCUMENT_KEY], old)
            self.assertEqual(existing[PROJECT_DOCUMENT_KEY]["buildings"], [{"id": "building-1"}])

    def test_invalid_workflow_document_returns_422_before_saving(self):
        class NeverSave:
            def save_project(self, **kwargs):
                raise AssertionError("Invalid data reached persistence")
        with self.assertRaises(HTTPException) as caught:
            save_project_record(project_store=NeverSave(), user_id="user", payload_data={
                "name": "Pilot", "project_input": {PROJECT_DOCUMENT_KEY: {}},
            })
        self.assertEqual(caught.exception.status_code, 422)

    def test_nested_legacy_key_is_not_interpreted_as_canonical_slot(self):
        for merge in (store_merge, workflow_merge):
            result = merge(
                {"legacy": {PROJECT_DOCUMENT_KEY: {"unrelated": 1}}},
                {"legacy": {PROJECT_DOCUMENT_KEY: {"other": 2}}},
            )
            self.assertEqual(result["legacy"][PROJECT_DOCUMENT_KEY], {"unrelated": 1, "other": 2})
