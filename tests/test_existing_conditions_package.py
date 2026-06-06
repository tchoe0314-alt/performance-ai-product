import unittest

from backend.planning.existing_conditions_package import build_existing_conditions_package


def _complete_meta(*, accepted: bool = True) -> dict:
    layers = {
        layer: [{"id": layer, "source": f"{layer}_source"}]
        for layer in ("parcels", "easements", "row", "floodplain", "wetlands", "existing_utilities")
    }
    meta = {
        "survey": {
            "source": "imported_existing_conditions",
            "point_count": 4,
            "benchmark": "BM-1",
            "datum": "NAVD88",
            "control_verified": True,
            "points": [
                {"x": 0.0, "y": 0.0, "z": 100.0},
                {"x": 10.0, "y": 0.0, "z": 101.0},
                {"x": 0.0, "y": 10.0, "z": 99.0},
                {"x": 10.0, "y": 10.0, "z": 100.0},
            ],
        },
        "gis_layers": layers,
        "coordinate_system": {"epsg": "EPSG:2276", "units": "ft", "source": "survey_control"},
        "sources": [{"source": "survey.csv", "source_type": "survey_csv", "success": True}],
        "existing_conditions_import_validation": {
            "success": True,
            "production_usable": True,
            "blockers": [],
            "warnings": [],
            "source_count": 1,
            "layer_counts": {layer: 1 for layer in layers},
            "terrain_source_confidence": {"label": "survey-backed"},
            "production_requirements": [
                {"field": "survey_source", "ready": True},
                {"field": "survey_datum_control", "ready": True},
                {"field": "coordinate_system", "ready": True},
                {"field": "terrain_source_confidence", "ready": True},
                {"field": "canonical_imports", "ready": True},
            ],
            "importer_production_matrix": [
                {
                    "source": "survey.csv",
                    "source_type": "survey_csv",
                    "success": True,
                    "canonicalized": True,
                    "metadata_only": False,
                    "production_usable": True,
                }
            ],
        },
        "existing_conditions_package": {
            "acceptance": {"accepted": accepted, "accepted_by": "u1" if accepted else ""},
        },
    }
    return meta


class ExistingConditionsPackageTests(unittest.TestCase):
    def test_complete_accepted_import_package_is_ready(self) -> None:
        package = build_existing_conditions_package({"meta": _complete_meta(accepted=True)})

        self.assertEqual(package["status"], "ready")
        self.assertTrue(package["production_ready"])
        self.assertTrue(package["review_usable"])
        self.assertTrue(package["accepted"])
        self.assertFalse(package["metadata_only"])
        self.assertFalse(package["blockers"])
        self.assertEqual(package["gate"]["status"], "ready")
        self.assertEqual(package["terrain_source_confidence"]["label"], "survey-backed")
        self.assertTrue(package["production_requirements"][0]["ready"])
        self.assertTrue(package["importer_production_matrix"][0]["production_usable"])

    def test_complete_unaccepted_import_package_needs_review(self) -> None:
        package = build_existing_conditions_package({"meta": _complete_meta(accepted=False)})

        self.assertEqual(package["status"], "needs_review")
        self.assertFalse(package["production_ready"])
        self.assertTrue(package["review_usable"])
        self.assertFalse(package["accepted"])
        warning_fields = {item["field"] for item in package["warnings"]}
        self.assertIn("package_acceptance", warning_fields)

    def test_metadata_only_package_is_blocked(self) -> None:
        meta = _complete_meta(accepted=True)
        meta.pop("existing_conditions_import_validation")

        package = build_existing_conditions_package({"meta": meta})

        self.assertEqual(package["status"], "blocked")
        self.assertTrue(package["metadata_only"])
        fields = {item["field"] for item in package["blockers"]}
        self.assertIn("import_validation", fields)

    def test_summary_missing_requirements_block_package(self) -> None:
        package = build_existing_conditions_package({"meta": {}})

        self.assertEqual(package["status"], "blocked")
        fields = {item["field"] for item in package["blockers"]}
        self.assertIn("survey_surface", fields)
        self.assertIn("gis_layers", fields)
        self.assertIn("coordinate_system", fields)
        self.assertIn("import_validation", fields)
        self.assertTrue(package["blocker_details"])

    def test_blocked_validation_package_reports_gate_requirements(self) -> None:
        meta = _complete_meta(accepted=True)
        meta["existing_conditions_import_validation"] = {
            "success": False,
            "production_usable": False,
            "blockers": [{"field": "metadata_only_imports", "reason": "Metadata-only imports cannot satisfy production."}],
            "warnings": [],
            "source_count": 1,
            "terrain_source_confidence": {"label": "missing"},
            "production_requirements": [{"field": "canonical_imports", "ready": False}],
            "importer_production_matrix": [
                {
                    "source": "network.landxml",
                    "source_type": "landxml",
                    "success": True,
                    "canonicalized": False,
                    "metadata_only": True,
                    "production_usable": False,
                }
            ],
        }

        package = build_existing_conditions_package({"meta": meta})

        self.assertEqual(package["status"], "blocked")
        self.assertEqual(package["gate"]["status"], "blocked")
        self.assertEqual(package["gate"]["terrain_source_confidence"], "missing")
        self.assertFalse(package["production_requirements"][0]["ready"])
        self.assertTrue(package["importer_production_matrix"][0]["metadata_only"])


if __name__ == "__main__":
    unittest.main()
