import unittest

from engines.quantity_engine import compute_plan_quantities


class CoordinationQuantityAlignmentTest(unittest.TestCase):
    def test_quantities_include_coordination_counts_from_canonical_state(self) -> None:
        plan = {
            "project_name": "Coordination Quantities",
            "units": "ft",
            "actions": [],
            "meta": {
                "coordination": {
                    "resolved_count": 3,
                    "unresolved_count": 1,
                },
                "manager_export": {
                    "metrics": {
                        "coordination_resolved_conflict_count": {"value": 2},
                        "coordination_unresolved_conflict_count": {"value": 1},
                    }
                },
            },
        }

        result = compute_plan_quantities(plan)

        self.assertTrue(result.success)
        self.assertEqual(result.totals["coordination_resolved_conflict_count"], 3)
        self.assertEqual(result.totals["coordination_unresolved_conflict_count"], 1)
        self.assertTrue(result.explain["meta_summary"]["canonical_coordination_used"])
        feature_rows = {row["feature"]: row["count"] for row in result.tables["feature_counts"]}
        self.assertEqual(feature_rows["coordination_conflicts_resolved"], 3)
        self.assertEqual(feature_rows["coordination_conflicts_unresolved"], 1)

    def test_quantity_audit_includes_traceable_canonical_sources(self) -> None:
        plan = {
            "project_name": "Trace Audit",
            "units": "ft",
            "actions": [
                {
                    "task": "polyline",
                    "points": [[0.0, 0.0], [10.0, 0.0]],
                    "layer": "PIPE",
                    "label": "P-1",
                    "canonical_source_id": "storm-seg-1",
                    "canonical_source_type": "storm_pipe_segment",
                },
                {
                    "task": "polyline",
                    "points": [[0.0, 5.0], [8.0, 5.0]],
                    "layer": "SAN",
                    "label": "SAN-1",
                    "canonical_source_id": "san-seg-1",
                    "canonical_source_type": "sanitary_segment",
                },
            ],
            "meta": {
                "storm_pipes": {
                    "segments": [{"id": "storm-seg-1", "pipe": "P-1", "from": "A", "to": "B", "flow_cfs": 1.0, "capacity_cfs": 2.0, "slope_ft_ft": 0.02, "contributing_area_ac": 0.4}],
                },
                "sanitary": {
                    "segments": [{"id": "san-seg-1", "name": "SAN-1", "segment_role": "main"}],
                    "manholes": [{"id": "mh-1", "name": "SMH-1"}],
                },
            },
        }

        result = compute_plan_quantities(plan)

        self.assertTrue(result.success)
        audit = result.explain["quantity_audit"]
        self.assertTrue(result.explain["meta_summary"]["quantity_traceability_complete"])
        self.assertEqual(audit["pipe_length_ft"]["source_object_ids"], ["storm-seg-1"])
        self.assertEqual(audit["sanitary_length_ft"]["source_object_ids"], ["san-seg-1"])
        self.assertTrue(audit["pipe_length_ft"]["trace_complete"])


if __name__ == "__main__":
    unittest.main()
