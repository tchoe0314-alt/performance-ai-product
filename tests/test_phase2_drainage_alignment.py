import unittest

from engines.error_check_engine import run_plan_checks
from engines.quantity_engine import compute_plan_quantities


class Phase2DrainageAlignmentTests(unittest.TestCase):
    def test_canonical_drainage_metadata_satisfies_inlet_detection(self) -> None:
        plan = {
            "project_name": "Drainage Contract",
            "units": "ft",
            "actions": [],
            "meta": {
                "drainage": {
                    "schema_version": "v1",
                    "source": "unit_test",
                    "structures": [
                        {
                            "name": "CI-1",
                            "object_type": "inlet",
                            "structure_type": "curb_inlet",
                            "canonical_type": "curb_inlet",
                            "layer": "DRAIN",
                            "x": 10.0,
                            "y": 12.0,
                            "z": 99.5,
                        }
                    ],
                    "basins": [
                        {
                            "name": "POND-1",
                            "object_type": "basin",
                            "canonical_type": "detention_basin",
                            "layer": "BASIN_BOUNDARY",
                            "area_sf": 450.0,
                        }
                    ],
                    "pipes": [
                        {
                            "name": "PIPE-1",
                            "object_type": "pipe_run",
                            "canonical_type": "storm_pipe",
                            "layer": "PIPE",
                            "path": [[10.0, 12.0], [25.0, 6.0]],
                            "length_ft": 16.155,
                        }
                    ],
                    "stats": {
                        "inlet_count": 1,
                        "structure_count": 1,
                        "basin_count": 1,
                        "pipe_count": 1,
                        "pipe_total_length_ft": 16.155,
                        "has_flow_paths": True,
                    },
                }
            },
        }

        issues = run_plan_checks({"mode": "drainage"}, plan)
        issue_codes = {item.get("code") for item in issues}
        self.assertNotIn("INLET_SIGNAL_WEAK", issue_codes)
        self.assertNotIn("DRAINAGE_FLOW_MISSING", issue_codes)
        self.assertNotIn("PIPE_LAYOUT_MISSING", issue_codes)

        quantities = compute_plan_quantities(plan)
        self.assertEqual(quantities.totals["inlet_count"], 1)
        self.assertEqual(quantities.totals["pond_count"], 1)
        self.assertEqual(quantities.totals["pipe_feature_count"], 1)
        self.assertEqual(quantities.totals["pipe_length_ft"], 16.155)


if __name__ == "__main__":
    unittest.main()
