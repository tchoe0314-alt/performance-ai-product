import unittest

import planner
from backend.planning.existing_conditions import summarize_existing_conditions
from core.civil_design import civil_design_readiness


class ExistingConditionsTests(unittest.TestCase):
    def test_missing_existing_conditions_are_explicit_production_blockers(self) -> None:
        summary = summarize_existing_conditions({"meta": {"grading": {"source_quality": "terrain"}}})

        fields = {item["field"] for item in summary["missing_requirements"]}

        self.assertFalse(summary["production_ready"])
        self.assertIn("survey_surface", fields)
        self.assertIn("gis_layers", fields)
        self.assertIn("coordinate_system", fields)

    def test_survey_gis_and_coordinate_system_clear_existing_conditions_gate(self) -> None:
        summary = summarize_existing_conditions(
            {
                "meta": {
                    "grading": {"source_quality": "survey"},
                    "survey": {"point_count": 8, "source": "uploaded_csv", "benchmark": "BM-1"},
                    "gis_layers": {
                        "parcels": [{"id": "P-1"}],
                        "easements": [{"id": "E-1"}],
                        "row": [{"id": "ROW-1"}],
                        "floodplain": {"verified_absent": True, "source": "FEMA FIRM panel"},
                        "wetlands": {"verified_absent": True, "source": "NWI review"},
                        "existing_utilities": [{"id": "EX-W"}],
                    },
                    "coordinate_system": {"epsg": "EPSG:2276", "units": "ft", "source": "survey"},
                }
            }
        )

        self.assertTrue(summary["production_ready"])
        self.assertTrue(summary["survey"]["ready"])
        self.assertTrue(summary["gis"]["ready"])
        self.assertTrue(summary["coordinate_system"]["ready"])

    def test_partial_gis_layers_do_not_clear_production_existing_conditions(self) -> None:
        summary = summarize_existing_conditions(
            {
                "meta": {
                    "grading": {"source_quality": "survey"},
                    "survey": {"point_count": 8, "source": "uploaded_csv", "benchmark": "BM-1"},
                    "gis_layers": {"parcels": [{"id": "P-1"}]},
                    "coordinate_system": {"epsg": "EPSG:2276", "units": "ft", "source": "survey"},
                }
            }
        )

        self.assertFalse(summary["production_ready"])
        self.assertFalse(summary["gis"]["ready"])
        self.assertIn("wetlands", summary["gis"]["missing_layers"])
        self.assertIn("existing_utilities", summary["gis"]["missing_layers"])

    def test_survey_source_name_alone_does_not_clear_survey_readiness(self) -> None:
        summary = summarize_existing_conditions(
            {
                "meta": {
                    "survey": {"source": "survey.csv"},
                    "gis_layers": {
                        "parcels": [{"id": "P-1"}],
                        "easements": [{"id": "E-1"}],
                        "row": [{"id": "ROW-1"}],
                        "floodplain": {"verified_absent": True, "source": "FEMA FIRM"},
                        "wetlands": {"verified_absent": True, "source": "NWI"},
                        "existing_utilities": {"verified_absent": True, "source": "utility atlas"},
                    },
                    "coordinate_system": {"epsg": "EPSG:2276", "units": "ft", "source": "survey"},
                }
            }
        )

        self.assertFalse(summary["survey"]["ready"])
        self.assertFalse(summary["production_ready"])
        self.assertIn("survey_surface", {item["field"] for item in summary["missing_requirements"]})

    def test_survey_points_without_control_do_not_clear_production_readiness(self) -> None:
        summary = summarize_existing_conditions(
            {
                "meta": {
                    "grading": {"source_quality": "survey"},
                    "survey": {"point_count": 8, "source": "uploaded_csv"},
                    "gis_layers": {
                        "parcels": [{"id": "P-1"}],
                        "easements": [{"id": "E-1"}],
                        "row": [{"id": "ROW-1"}],
                        "floodplain": {"verified_absent": True, "source": "FEMA FIRM"},
                        "wetlands": {"verified_absent": True, "source": "NWI"},
                        "existing_utilities": {"verified_absent": True, "source": "utility atlas"},
                    },
                    "coordinate_system": {"epsg": "EPSG:2276", "units": "ft", "source": "survey"},
                }
            }
        )

        fields = {item["field"] for item in summary["missing_requirements"]}

        self.assertTrue(summary["survey"]["ready"])
        self.assertFalse(summary["survey"]["has_control"])
        self.assertFalse(summary["production_ready"])
        self.assertIn("survey_control", fields)

    def test_geographic_coordinate_system_is_not_production_ready(self) -> None:
        summary = summarize_existing_conditions(
            {
                "meta": {
                    "grading": {"source_quality": "survey"},
                    "survey": {"point_count": 8, "source": "uploaded_csv", "benchmark": "BM-1"},
                    "gis_layers": {"parcels": [{"id": "P-1"}]},
                    "coordinate_system": {"epsg": "EPSG:4326", "units": "degrees", "source": "geojson"},
                }
            }
        )
        fields = {item["field"] for item in summary["missing_requirements"]}

        self.assertFalse(summary["production_ready"])
        self.assertTrue(summary["coordinate_system"]["ready"])
        self.assertFalse(summary["coordinate_system"]["production_usable"])
        self.assertIn("coordinate_system", fields)

    def test_project_units_do_not_silently_clear_coordinate_system_units(self) -> None:
        summary = summarize_existing_conditions(
            {
                "meta": {
                    "units": "ft",
                    "grading": {"source_quality": "survey"},
                    "survey": {"point_count": 8, "source": "uploaded_csv", "benchmark": "BM-1"},
                    "gis_layers": {
                        "parcels": [{"id": "P-1"}],
                        "easements": [{"id": "E-1"}],
                        "row": [{"id": "ROW-1"}],
                        "floodplain": {"verified_absent": True, "source": "FEMA FIRM"},
                        "wetlands": {"verified_absent": True, "source": "NWI"},
                        "existing_utilities": {"verified_absent": True, "source": "utility atlas"},
                    },
                    "coordinate_system": {"epsg": "EPSG:2276", "source": "survey"},
                }
            }
        )

        fields = {item["field"] for item in summary["missing_requirements"]}

        self.assertTrue(summary["coordinate_system"]["ready"])
        self.assertFalse(summary["coordinate_system"]["units_provided"])
        self.assertFalse(summary["coordinate_system"]["production_usable"])
        self.assertFalse(summary["production_ready"])
        self.assertIn("coordinate_system", fields)
        self.assertTrue(summary["coordinate_system"]["blocker_details"])

    def test_civil_readiness_blocks_missing_coordinate_system(self) -> None:
        readiness = civil_design_readiness({"meta": {"grading": {"source_quality": "survey"}, "survey": {"point_count": 4}, "gis_layers": {"parcels": [{}]}}})
        gaps = {(item["area"], item["field"]) for item in readiness["production_blockers"]}

        self.assertIn(("existing_conditions", "coordinate_system"), gaps)

    def test_build_plan_attaches_existing_conditions_summary(self) -> None:
        plan = planner.build_plan(
            {
                "project_name": "Existing Conditions Smoke",
                "units": "ft",
                "mode": "site_plan",
                "lot": {"x": 0.0, "y": 0.0, "w": 120.0, "h": 100.0},
                "site_plan": {"building_width": 40.0, "building_depth": 30.0, "parking_count": 12},
            }
        )
        meta = plan.get("meta") or {}
        summary = meta.get("existing_conditions_summary") or {}

        self.assertEqual(summary.get("version"), "existing_conditions_v1")
        self.assertFalse(summary.get("production_ready"))
        self.assertIn("coordinate_system", {item["field"] for item in summary.get("missing_requirements") or []})


if __name__ == "__main__":
    unittest.main()
