import unittest

from backend.planning.finalization import produced_deliverables


class FinalizationDeliverablesTest(unittest.TestCase):
    def test_profile_deliverables_require_canonical_profiles(self) -> None:
        plan = {
            "actions": [
                {
                    "task": "text",
                    "layer": "NOTE",
                    "text": "Road profile will be generated after alignment approval.",
                }
            ],
            "meta": {},
        }

        produced = produced_deliverables(plan)

        self.assertNotIn("profiles", produced)
        self.assertNotIn("road_profile", produced)

    def test_cross_section_deliverables_require_canonical_sections(self) -> None:
        plan = {
            "actions": [
                {
                    "task": "text",
                    "layer": "NOTE",
                    "label": "Typical section placeholder",
                }
            ],
            "meta": {},
        }

        self.assertNotIn("cross_sections", produced_deliverables(plan))

    def test_profile_and_section_deliverables_are_packaged_from_canonical_records(self) -> None:
        plan = {
            "actions": [{"task": "polyline", "layer": "ROAD", "points": [[0.0, 0.0], [100.0, 0.0]]}],
            "meta": {
                "profiles": [{"name": "ROAD PROFILE 1", "alignment_owner": "ROAD ALIGNMENT 1"}],
                "cross_sections": [{"name": "ROAD SECTION 1", "alignment_owner": "ROAD ALIGNMENT 1"}],
            },
        }

        produced = produced_deliverables(plan)

        self.assertIn("profiles", produced)
        self.assertIn("road_profile", produced)
        self.assertIn("cross_sections", produced)


if __name__ == "__main__":
    unittest.main()
