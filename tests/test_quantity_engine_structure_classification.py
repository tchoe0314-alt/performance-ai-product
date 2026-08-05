import unittest

from engines.quantity_engine import compute_plan_quantities


class QuantityEngineStructureClassificationTest(unittest.TestCase):
    def test_sanitary_manholes_do_not_inflate_building_area_or_trace(self):
        result = compute_plan_quantities(
            {
                "actions": [
                    {
                        "task": "rectangle",
                        "layer": "BUILDING",
                        "origin": [0, 0],
                        "width": 100,
                        "height": 50,
                        "canonical_source_id": "building-1",
                        "canonical_source_type": "building",
                    },
                    {
                        "task": "circle",
                        "layer": "STRUCTURE",
                        "center": [20, 20],
                        "radius": 2,
                        "label": "SMH-1",
                        "canonical_source_id": "SMH-1",
                        "canonical_source_type": "sanitary_manhole",
                    },
                ],
                "meta": {},
            }
        )

        self.assertEqual(result.totals["building_area_sf"], 5000.0)
        building_trace = result.explain["quantity_audit"]["building_area_sf"]["source_object_ids"]
        self.assertEqual(building_trace, ["building-1"])
        self.assertNotIn("SMH-1", building_trace)


if __name__ == "__main__":
    unittest.main()
