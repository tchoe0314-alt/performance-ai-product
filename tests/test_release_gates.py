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

    def test_release_allowed_package_still_surfaces_artifact_defects(self) -> None:
        meta = {
            "construction_readiness": {"ready": True},
            "construction_package": {
                "release_allowed": True,
                "construction_package_artifact_status": {
                    "complete_for_release": False,
                    "release_ready_flag": True,
                    "package_present": True,
                    "package_identity_present": False,
                    "missing": ["qa_report"],
                    "anonymous": ["sheets"],
                    "stale": ["C-300"],
                    "model_reference_present": True,
                    "model_matches_expected": False,
                    "untraced": ["cad_export"],
                    "mismatched": ["construction_manifest"],
                    "cost_untraced": ["cost_estimate"],
                    "cost_mismatched": ["takeoff"],
                },
                "professional_package_release_status": {
                    "professional_release_valid": True,
                    "model_matches_package": True,
                    "package_matches_review": True,
                },
            },
        }

        blockers = construction_release_blockers_from_meta(
            meta,
            requires_construction_release=True,
        )

        self.assertIn("construction_package_incomplete_release", blockers)
        self.assertIn("construction_package_identity_missing", blockers)
        self.assertIn("construction_package_missing_artifacts", blockers)
        self.assertIn("construction_package_anonymous_artifacts", blockers)
        self.assertIn("construction_package_stale_artifacts", blockers)
        self.assertIn("construction_package_model_mismatch", blockers)
        self.assertIn("construction_package_untraced_artifacts", blockers)
        self.assertIn("construction_package_mismatched_artifacts", blockers)
        self.assertIn("construction_package_cost_untraced", blockers)
        self.assertIn("construction_package_cost_mismatched", blockers)

    def test_top_level_professional_release_status_blocks_untraced_release(self) -> None:
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
            "professional_package_release_status": {
                "professional_release_valid": True,
                "model_matches_package": False,
                "package_matches_review": True,
            },
        }

        blockers = construction_release_blockers_from_meta(
            meta,
            requires_construction_release=True,
        )

        self.assertIn("construction_professional_release_untraced", blockers)
        self.assertNotIn("construction_professional_release_missing", blockers)

    def test_release_allowed_package_requires_artifact_status_audit(self) -> None:
        meta = {
            "construction_readiness": {"ready": True},
            "construction_package": {
                "release_allowed": True,
                "professional_package_release_status": {
                    "professional_release_valid": True,
                    "model_matches_package": True,
                    "package_matches_review": True,
                },
            },
        }

        blockers = construction_release_blockers_from_meta(
            meta,
            requires_construction_release=True,
        )

        self.assertIn("construction_package_artifact_status_missing", blockers)
        self.assertIn("construction_package_release_not_marked_ready", blockers)

    def test_blocked_package_still_requires_artifact_status_audit(self) -> None:
        meta = {
            "construction_readiness": {"ready": True},
            "construction_package": {
                "release_allowed": False,
                "professional_package_release_status": {
                    "professional_release_valid": True,
                    "model_matches_package": True,
                    "package_matches_review": True,
                },
            },
        }

        blockers = construction_release_blockers_from_meta(
            meta,
            requires_construction_release=True,
        )

        self.assertIn("construction_package_blocked", blockers)
        self.assertIn("construction_package_artifact_status_missing", blockers)

    def test_top_level_professional_release_status_blocks_invalid_release(self) -> None:
        meta = {
            "construction_readiness": {"ready": True},
            "construction_package": {
                "release_allowed": False,
                "construction_package_artifact_status": {
                    "complete_for_release": True,
                    "release_ready_flag": True,
                    "model_matches_expected": True,
                },
            },
            "professional_package_release_status": {
                "professional_release_valid": False,
                "model_matches_package": True,
                "package_matches_review": True,
            },
        }

        blockers = construction_release_blockers_from_meta(
            meta,
            requires_construction_release=True,
        )

        self.assertIn("construction_package_blocked", blockers)
        self.assertIn("construction_professional_release_invalid", blockers)


if __name__ == "__main__":
    unittest.main()
