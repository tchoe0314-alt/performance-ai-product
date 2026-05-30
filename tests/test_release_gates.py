import unittest

from backend.planning.release_gates import (
    construction_release_blockers_from_meta,
    final_plan_requires_construction_release,
)


class ReleaseGateTests(unittest.TestCase):
    def test_legacy_construction_package_alias_requires_release_and_blocks_stale_package(self) -> None:
        plan = {
            "meta": {
                "construction_readiness": {"ready": True},
                "construction_package": {
                    "release_allowed": False,
                    "construction_package_artifact_status": {
                        "release_ready_flag": True,
                        "stale": ["C-300"],
                    },
                },
            }
        }

        self.assertTrue(final_plan_requires_construction_release(plan))
        blockers = construction_release_blockers_from_meta(
            plan["meta"],
            requires_construction_release=final_plan_requires_construction_release(plan),
        )

        self.assertIn("construction_package_blocked", blockers)
        self.assertIn("construction_package_stale_artifacts", blockers)

    def test_legacy_construction_package_alias_requires_professional_release_proof(self) -> None:
        meta = {
            "construction_readiness": {"ready": True},
            "construction_package": {
                "release_allowed": True,
                "construction_package_artifact_status": {
                    "complete_for_release": True,
                    "release_ready_flag": True,
                    "model_matches_expected": True,
                },
            },
        }

        blockers = construction_release_blockers_from_meta(
            meta,
            requires_construction_release=True,
        )

        self.assertIn("construction_professional_release_missing", blockers)


if __name__ == "__main__":
    unittest.main()
