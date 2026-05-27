import unittest

import planner


class ImportedConditionsPlannerIntegrationTests(unittest.TestCase):
    def test_build_plan_preserves_imported_existing_conditions_and_standards(self) -> None:
        plan = planner.build_plan(
            {
                "project_name": "Imported Conditions",
                "units": "ft",
                "mode": "site_plan",
                "lot": {"x": 0.0, "y": 0.0, "w": 120.0, "h": 100.0},
                "site_plan": {"building_width": 40.0, "building_depth": 30.0, "parking_count": 12},
                "meta": {
                    "survey": {
                        "source": "imported_survey_csv",
                        "point_count": 4,
                        "points": [
                            {"x": 0.0, "y": 0.0, "z": 100.0},
                            {"x": 120.0, "y": 0.0, "z": 101.0},
                            {"x": 0.0, "y": 100.0, "z": 99.5},
                            {"x": 120.0, "y": 100.0, "z": 100.5},
                        ],
                    },
                    "gis_layers": {"parcels": [{"id": "P-1"}]},
                    "coordinate_system": {"epsg": "EPSG:2276", "units": "ft", "source": "test"},
                    "standards_acceptance": {
                        "accepted_rules": [
                            {
                                "rule_id": "test_rule",
                                "discipline": "grading",
                                "topic": "test",
                                "candidate_value": "accepted",
                                "status": "accepted",
                            }
                        ]
                    },
                },
            }
        )

        meta = plan.get("meta") or {}
        summary = meta.get("existing_conditions_summary") or {}

        self.assertTrue(summary["survey"]["ready"])
        self.assertTrue(summary["coordinate_system"]["ready"])
        self.assertEqual((meta.get("grading") or {}).get("source_quality"), "survey")
        self.assertEqual(((meta.get("civil_design_readiness") or {}).get("systems") or {})["standards"]["metrics"]["accepted_rule_count"], 1)


if __name__ == "__main__":
    unittest.main()
