"""P02 pure compatibility characterization: no engine repair, API/DB or network.

Fixtures are hand-authored synthetic contracts, not snapshots regenerated from output.
Existing static object-type definitions are preloaded explicitly before the P01 guard,
which otherwise rejects every /data/ path. No customer storage is read.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import re
import sys
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))
from p01_evidence import readonly_assertions

# Reviewed pure-module imports. site_objects loads core/data/site_object_definitions_v1.json.
from backend.services.canonical_project import (
    PROJECT_DOCUMENT_KEY as KEY, ProjectDocumentError, dumps_project_document,
    loads_project_document, new_project_document, validate_project_document,
)
from backend.services.canonical_canvas import resolve_canvas_input, with_canvas_snapshot
from backend.services.canonical_record import OWNER, portable_document, project_view, seal_record


def fixture(name):
    return json.loads((HERE / "fixtures" / name).read_text())


class CompatibilityTests(unittest.TestCase):
    def run(self, result=None):
        with readonly_assertions():
            return super().run(result)

    def legacy(self): return fixture("p02_legacy_input.json")

    def sealed(self):
        return seal_record({"project_id": "p02-project", "name": "P02 synthetic", "organization_id": "p02-org",
                            "description": "Synthetic only", "project_input": self.legacy(),
                            "metadata": {"workflow": {"version_history": [{"id": "p02-version", "verified": False}],
                                                       "artifacts": [{"id": "p02-artifact", "scope": "review-only"}]}},
                            "latest_result": {"success": True, "assumptions": ["Synthetic, not engineering verified"],
                                "final_plan": {"actions": [], "meta": {"quantities": {"synthetic_area": 200},
                                    "cost_estimate": {"total": 1, "currency": "USD"},
                                    "source_confidence_map_v1": {"verified": False}, "assumptions": ["Unverified input"]}}}})

    def test_C01_hand_authored_v1_snapshot(self):
        self.assertEqual(new_project_document(name="P02 synthetic"), fixture("p02_empty_v1.json"))
    def test_C02_v1_json_roundtrip(self):
        document = fixture("p02_empty_v1.json")
        self.assertEqual(loads_project_document(dumps_project_document(document)), document)
    def test_C03_unknown_project_versions_rejected(self):
        for version in ("civora_project_v2", "civora_project_v0", None, True, 1):
            with self.subTest(version=version), self.assertRaises(ProjectDocumentError):
                validate_project_document({**fixture("p02_empty_v1.json"), "schema_version": version})
    def test_C04_missing_section_rejected(self):
        document = fixture("p02_empty_v1.json"); del document["units"]
        with self.assertRaises(ProjectDocumentError): validate_project_document(document)
    def test_C05_extension_json_preserved(self):
        document = fixture("p02_empty_v1.json")
        document["extensions"]["future_vendor"] = {"values": [False, 0, None, "", {"x": 1.25}]}
        self.assertEqual(loads_project_document(dumps_project_document(document)), document)
    def test_C06_nonfinite_rejected(self):
        for value in (float("nan"), float("inf"), -float("inf")):
            document = fixture("p02_empty_v1.json"); document["extensions"]["value"] = value
            with self.subTest(value=str(value)), self.assertRaises(ProjectDocumentError): dumps_project_document(document)
    def test_C07_duplicate_json_keys_rejected(self):
        with self.assertRaises(ProjectDocumentError): loads_project_document('{"schema_version":"civora_project_v1","schema_version":"civora_project_v1"}')
    def test_C08_canvas_roundtrip_exact_legacy(self):
        legacy = self.legacy(); original = deepcopy(legacy)
        restored = resolve_canvas_input(with_canvas_snapshot(legacy)); restored.pop(KEY)
        self.assertEqual(restored, original); self.assertEqual(legacy, original)
    def test_C09_canvas_roundtrip_after_json(self):
        legacy = self.legacy()
        restored = resolve_canvas_input(json.loads(json.dumps(with_canvas_snapshot(legacy), allow_nan=False))); restored.pop(KEY)
        self.assertEqual(restored, legacy)
    def test_C10_canonical_wins_over_stale_legacy_geometry(self):
        compiled = with_canvas_snapshot(self.legacy())
        compiled["manual_fields"]["site_objects"][0]["x"] = 999
        self.assertEqual(resolve_canvas_input(compiled)["manual_fields"]["site_objects"][0]["x"], 12.5)
    def test_C11_canonical_object_geometry_wins_over_wrapper(self):
        compiled = with_canvas_snapshot(self.legacy())
        compiled[KEY]["buildings"][0]["object_v1"]["geometry"]["origin"][0] = 20
        self.assertEqual(resolve_canvas_input(compiled)["manual_fields"]["site_objects"][0]["x"], 20)
    def test_C12_unknown_units_remain_unknown(self):
        compiled = with_canvas_snapshot(self.legacy()); compiled[KEY]["units"]["length"] = None
        fields = resolve_canvas_input(compiled)["manual_fields"]
        self.assertNotIn("units", fields)
        self.assertIsNone(compiled[KEY]["coordinate_system"]["horizontal_crs"])
        self.assertIsNone(compiled[KEY]["coordinate_system"]["vertical_datum"])
    def test_C13_metric_values_not_converted_or_guessed(self):
        compiled = with_canvas_snapshot(self.legacy())
        self.assertEqual(compiled[KEY]["units"]["length"], "m")
        self.assertEqual(resolve_canvas_input(compiled)["manual_fields"]["site_objects"][0]["w"], 20)
    def test_C14_program_only_legacy_stays_legacy(self):
        legacy = {"manual_fields": {"building_width": 20, "units": "m"}, "meta": {"site_inputs": {"verified": False}}}
        self.assertEqual(resolve_canvas_input(with_canvas_snapshot(legacy)), legacy)
    def test_C15_unowned_sections_survive_recompile(self):
        prior = fixture("p02_empty_v1.json")
        prior["extensions"]["future_owner"] = {"retain": True}
        prior["roads"] = [{"external_record": {"id": "keep"}}]
        prior["sources"] = [{"id": "source-keep", "verified": False}]
        compiled = with_canvas_snapshot(self.legacy(), prior)
        for _ in range(3): compiled = with_canvas_snapshot(compiled)
        self.assertEqual(compiled[KEY]["extensions"]["future_owner"], {"retain": True})
        self.assertIn(prior["roads"][0], compiled[KEY]["roads"])
        self.assertEqual(compiled[KEY]["sources"], prior["sources"])
    def test_C16_stable_ids_and_order(self):
        compiled = with_canvas_snapshot(self.legacy())
        for _ in range(3): compiled = with_canvas_snapshot(compiled)
        self.assertEqual([o["id"] for o in resolve_canvas_input(compiled)["manual_fields"]["site_objects"]],
                         ["p02-building", "p02-road", "p02-other"])
    def test_C17_malformed_references_rejected(self):
        for change in ("duplicate", "out_of_range", "boolean", "incomplete"):
            compiled = with_canvas_snapshot(self.legacy())
            refs = compiled[KEY]["extensions"]["canvas_workspace_v1"]["object_order"]
            if change == "duplicate": refs.append(deepcopy(refs[0]))
            elif change == "out_of_range": refs[0]["index"] = 999
            elif change == "boolean": refs[0]["index"] = True
            else: refs.pop()
            with self.subTest(change=change), self.assertRaises(ProjectDocumentError): resolve_canvas_input(compiled)
    def test_C18_source_and_quality_not_promoted(self):
        compiled = with_canvas_snapshot(self.legacy())
        definition = compiled[KEY]["buildings"][0]["object_v1"]
        self.assertFalse(definition["source"]["verified"])
        self.assertFalse(definition["validation"]["engineering_verified"])
        self.assertEqual(resolve_canvas_input(compiled)["meta"], self.legacy()["meta"])
    def test_C19_result_facets_restore_exact_synthetic_result(self):
        sealed = self.sealed()
        restored = project_view(sealed)
        self.assertEqual(restored["latest_result"]["final_plan"]["meta"]["quantities"], {"synthetic_area": 200})
        self.assertEqual(restored["latest_result"]["assumptions"], ["Synthetic, not engineering verified"])
        self.assertNotIn("quantities", sealed["latest_result"]["final_plan"]["meta"])
    def test_C20_portable_aggregate_preserves_results_and_geometry(self):
        sealed = self.sealed(); before = deepcopy(sealed)
        detached = loads_project_document(dumps_project_document(portable_document(sealed)))
        restored = project_view({"project_input": {KEY: detached}})
        self.assertEqual(restored["project_input"]["manual_fields"], self.legacy()["manual_fields"])
        self.assertEqual(restored["latest_result"], project_view(sealed)["latest_result"])
        self.assertEqual(sealed, before)
    def test_C21_canonical_controls_and_sources_override_shadows(self):
        sealed = self.sealed(); inputs = sealed["project_input"]
        inputs["meta"]["site_inputs"]["source"]["verified"] = True
        inputs["input_mode"] = "stale-shadow"
        restored = resolve_canvas_input(inputs)
        self.assertFalse(restored["meta"]["site_inputs"]["source"]["verified"])
        self.assertEqual(restored["input_mode"], "user")
    def test_C22_no_edit_preserves_edit_history(self):
        sealed = self.sealed()
        again = seal_record(sealed, previous=sealed, latest_result_supplied=False)
        self.assertEqual(again["project_input"]["meta"]["edit_history_v1"], sealed["project_input"]["meta"]["edit_history_v1"])
        self.assertEqual(again["project_input"][KEY]["export_history"], sealed["project_input"][KEY]["export_history"])
    def test_C23_unknown_adapter_version_rejected(self):
        compiled = with_canvas_snapshot(self.legacy())
        compiled[KEY]["extensions"]["canvas_workspace_v1"]["version"] = 2
        with self.assertRaises(ProjectDocumentError): resolve_canvas_input(compiled)
        sealed = self.sealed(); sealed["project_input"][KEY]["extensions"][OWNER]["version"] = 2
        with self.assertRaises(ProjectDocumentError): resolve_canvas_input(sealed["project_input"])
    def test_C24_ambiguous_legacy_surface_metadata_not_invented(self):
        legacy = self.legacy()
        legacy["meta"]["site_inputs"]["legacy_grid"] = {"values": [[100, 100], [100, 100]], "cell_size": 10, "bounds": [0, 0, 20, 20]}
        restored = resolve_canvas_input(with_canvas_snapshot(legacy))
        self.assertEqual(restored["meta"]["site_inputs"]["legacy_grid"], legacy["meta"]["site_inputs"]["legacy_grid"])
        self.assertNotIn("sampling", restored["meta"]["site_inputs"]["legacy_grid"])
    def test_C25_typescript_schema_sections_match_python_static_only(self):
        from backend.services.canonical_project import MAPPING_SECTIONS, COLLECTION_SECTIONS
        text = (ROOT / "apps/web/app/utils/canonicalCanvasProject.ts").read_text()
        for name, expected in (("mappings", MAPPING_SECTIONS), ("collections", COLLECTION_SECTIONS)):
            body = re.search(r"const " + name + r" = \[(.*?)\] as const", text, re.S)
            self.assertIsNotNone(body)
            self.assertEqual(re.findall(r'"([^"\n]+)"', body.group(1)), list(expected))
    def test_C26_detached_validation_does_not_mutate_fixture(self):
        document = fixture("p02_empty_v1.json"); before = deepcopy(document)
        detached = validate_project_document(document); detached["project"]["name"] = "Different"
        self.assertEqual(document, before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
