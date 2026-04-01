import unittest

from planner import _validate_network_graph, _validate_storm_hydraulics


class Phase1DeepValidationTest(unittest.TestCase):
    def test_graph_validation_detects_invalid_directionality_and_duplicates(self) -> None:
        graph = _validate_network_graph(
            {
                "segments": [
                    {
                        "id": "storm-1",
                        "pipe": "P-1",
                        "from": "N1",
                        "to": "N2",
                        "start_invert": 100.0,
                        "end_invert": 100.2,
                        "slope_ft_ft": -0.01,
                    },
                    {
                        "id": "storm-1",
                        "pipe": "P-1-DUP",
                        "from": "N1",
                        "to": "N2",
                        "start_invert": 100.0,
                        "end_invert": 99.0,
                        "slope_ft_ft": 0.02,
                    },
                ]
            },
            "storm",
        )

        self.assertFalse(graph["valid"])
        self.assertTrue(graph["invalid_direction_segments"])
        self.assertEqual(graph["duplicate_segments"], ["storm-1"])
        self.assertTrue(graph["duplicate_edges"])

    def test_graph_validation_detects_orphan_nodes(self) -> None:
        graph = _validate_network_graph(
            {
                "segments": [
                    {
                        "id": "san-1",
                        "name": "SAN-1",
                        "start_name": "SMH-1",
                        "end_name": "SMH-2",
                        "start_invert_ft": 100.0,
                        "end_invert_ft": 99.0,
                        "slope_ft_ft": 0.02,
                    }
                ],
                "manholes": [
                    {"id": "mh-1", "name": "SMH-1"},
                    {"id": "mh-2", "name": "SMH-2"},
                    {"id": "mh-3", "name": "SMH-3"},
                ],
            },
            "sanitary",
        )

        self.assertFalse(graph["valid"])
        self.assertIn("mh-3", graph["orphan_nodes"])

    def test_hydraulic_validation_detects_geometry_only_and_accumulation_gaps(self) -> None:
        validation = _validate_storm_hydraulics(
            {
                "segments": [
                    {
                        "id": "storm-1",
                        "pipe": "P-1",
                        "from": "IN-1",
                        "to": "J-1",
                        "flow_cfs": 0.0,
                        "capacity_cfs": 0.0,
                        "slope_ft_ft": 0.0,
                    },
                    {
                        "id": "storm-2",
                        "pipe": "P-2",
                        "from": "J-1",
                        "to": "OUT-1",
                        "flow_cfs": 1.5,
                        "capacity_cfs": 1.0,
                        "capacity_ratio": 1.5,
                        "slope_ft_ft": 0.02,
                    },
                ]
            }
        )

        self.assertFalse(validation["valid"])
        self.assertIn("storm-1", validation["geometry_only_segments"])
        self.assertIn("storm-1", validation["missing_accumulation_segments"])
        self.assertTrue(validation["invalid_capacity_ratio_segments"])


if __name__ == "__main__":
    unittest.main()
