from __future__ import annotations

import unittest

from backend.planning.finalization import canonical_truth_audit
from core.project_manager import ProjectManager
from engines.quantity_engine import compute_plan_quantities
from output.dxf_exporter import finalize_export_metadata


def _site_plan() -> dict:
    return {
        "project_name": "Phase 1 Truth Gates",
        "units": "ft",
        "actions": [
            {
                "task": "rectangle",
                "layer": "SITE",
                "origin": [0.0, 0.0],
                "width": 100.0,
                "height": 100.0,
                "label": "Site Boundary",
                "canonical_source_id": "site-1",
                "canonical_source_type": "site",
            }
        ],
        "meta": {
            "deliverables": {"requested": ["storm_pipe_plan"], "produced": ["site_plan"]},
            "qa": {"stats": {}},
            "quantities": {"totals": {"lot_area_sf": 10000.0}},
            "coordination": {"unresolved_conflicts": []},
            "parking_program": {
                "requested_target": 1,
                "achieved_count": 1,
                "method": "explicit_input",
                "traceable": True,
                "source_fields": ["test"],
            },
        },
    }


class Phase1TruthGateTests(unittest.TestCase):
    def test_truth_audit_blocks_cache_only_and_dirty_canonical_outputs(self) -> None:
        manager = ProjectManager()
        manager.latest_outputs["storm_pipe_summary"] = {
            "source": "cache-only",
            "segments": [{"id": "storm-cache", "pipe": "CACHE_ONLY"}],
            "total_length_ft": 50.0,
        }
        manager.mark_system_dirty("storm_pipes", reason="Road moved; storm pipes need rerun.", source="test")
        plan = _site_plan()

        audit = canonical_truth_audit(
            {"mode": "site_plan", "deliverables": ["storm_pipe_plan"], "lot": {"w": 100.0, "h": 100.0}},
            plan,
            manager=manager,
            sanitary_requested=lambda _parsed: False,
        )
        checks = {item["code"]: item for item in audit["checks"]}

        self.assertFalse(checks["CANONICAL_ACCEPTED_STATE_CURRENT"]["ok"])
        self.assertTrue(audit["canonical_integrity"]["blocked"])
        self.assertIn("storm_pipes", audit["canonical_integrity"]["cache_only_stages"])
        self.assertIn("storm_pipes", audit["canonical_integrity"]["dirty_stages"])
        self.assertTrue(audit["summary"]["stale_output_blocking"])

    def test_quantity_result_is_not_production_success_when_canonical_integrity_is_blocked(self) -> None:
        plan = _site_plan()
        plan["meta"]["canonical_integrity"] = {
            "blocked": True,
            "blocking_reasons": ["storm_pipes: system is dirty."],
        }

        quantities = compute_plan_quantities(plan)

        self.assertFalse(quantities.success)
        self.assertTrue(quantities.explain["meta_summary"]["canonical_integrity_blocked"])
        self.assertTrue(any("Canonical state" in warning for warning in quantities.warnings))

    def test_export_audit_blocks_when_canonical_integrity_is_blocked(self) -> None:
        plan = _site_plan()
        plan["meta"]["canonical_integrity"] = {
            "blocked": True,
            "blocking_reasons": ["storm_pipes: accepted canonical summary missing."],
        }

        metadata = finalize_export_metadata(plan)

        self.assertFalse(metadata["export_audit"]["success"])
        self.assertFalse(metadata["export_audit"]["ready"])
        self.assertTrue(metadata["export_audit"]["export_blocked"])
        self.assertIn("storm_pipes", metadata["export_audit"]["blocked_reasons"][0])


if __name__ == "__main__":
    unittest.main()
