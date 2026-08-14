from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from backend.planning.vision_ground_truth_flywheel import (
    DATASET_VERSION,
    LEARNING_CONSENT_VERSION,
    ground_truth_dataset_fingerprint,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "backend" / "scripts" / "export_vision_ground_truth_dataset.py"


def _dataset() -> dict:
    dataset = {
        "version": DATASET_VERSION,
        "ledger_head_hash": "fixture-ledger-head",
        "ledger_integrity": {"valid": True},
        "split_registry": {
            "assignments": {"frame-1": "train"},
            "valid": True,
        },
        "examples": [
            {
                "annotation_id": "annotation-1",
                "frame_id": "frame-1",
                "split": "train",
                "feature_type": "building_footprint",
                "blockers": [],
                "source_snapshots": [],
            }
        ],
        "negative_frames": [],
        "export_ready": True,
        "export_blockers": [],
    }
    dataset["dataset_fingerprint"] = ground_truth_dataset_fingerprint(dataset)
    return dataset


def _consent(dataset: dict) -> dict:
    return {
        "version": LEARNING_CONSENT_VERSION,
        "status": "granted",
        "scopes": ["model_training", "cross_project_aggregation"],
        "dataset_fingerprint": dataset["dataset_fingerprint"],
        "granted_by_role": "company_admin",
        "granted_at": "2026-08-13T00:00:00Z",
        "revocable": True,
        "private_identifiers_exported": False,
    }


class ExportVisionGroundTruthDatasetTests(unittest.TestCase):
    def test_cli_merges_deduplicates_and_writes_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            first = temp / "first.json"
            second = temp / "second.json"
            output = temp / "merged.json"
            coverage = temp / "coverage.json"
            privacy = temp / "privacy.json"
            dataset = _dataset()
            first.write_text(json.dumps(dataset), encoding="utf-8")
            second.write_text(json.dumps(dataset), encoding="utf-8")
            consent = temp / "consent.json"
            consent.write_text(json.dumps(_consent(dataset)), encoding="utf-8")

            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    str(first),
                    str(second),
                    "--output",
                    str(output),
                    "--coverage-output",
                    str(coverage),
                    "--privacy-aggregate-output",
                    str(privacy),
                    "--learning-consent",
                    str(consent),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            merged = json.loads(output.read_text(encoding="utf-8"))
            coverage_report = json.loads(coverage.read_text(encoding="utf-8"))
            privacy_report = json.loads(privacy.read_text(encoding="utf-8"))
            self.assertEqual(merged["annotation_count"], 1)
            self.assertEqual(merged["counts_by_split"], {"test": 0, "train": 1, "validation": 0})
            self.assertIn("building_footprint", coverage_report["blocked_classes"])
            self.assertTrue(coverage_report["learning_consent_ready"])
            self.assertTrue(coverage_report["privacy_safe_aggregate_validation"]["valid"])
            self.assertFalse(privacy_report["contains_project_or_reviewer_identifiers"])
            self.assertNotIn("annotation-1", json.dumps(privacy_report))

    def test_cli_fails_closed_on_permanent_split_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            first = temp / "first.json"
            second = temp / "second.json"
            output = temp / "blocked.json"
            first.write_text(json.dumps(_dataset()), encoding="utf-8")
            conflicting = deepcopy(_dataset())
            conflicting["dataset_fingerprint"] = "conflicting-dataset"
            conflicting["split_registry"]["assignments"]["frame-1"] = "test"
            conflicting["examples"][0]["annotation_id"] = "annotation-2"
            conflicting["examples"][0]["split"] = "test"
            conflicting["dataset_fingerprint"] = ground_truth_dataset_fingerprint(conflicting)
            second.write_text(json.dumps(conflicting), encoding="utf-8")
            first_consent = temp / "first-consent.json"
            second_consent = temp / "second-consent.json"
            first_consent.write_text(json.dumps(_consent(_dataset())), encoding="utf-8")
            second_consent.write_text(json.dumps(_consent(conflicting)), encoding="utf-8")

            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    str(first),
                    str(second),
                    "--output",
                    str(output),
                    "--learning-consent",
                    str(first_consent),
                    "--learning-consent",
                    str(second_consent),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 2)
            blocked = json.loads(output.read_text(encoding="utf-8"))
            self.assertFalse(blocked["export_ready"])
            self.assertIn("conflicting_permanent_split:frame-1", blocked["export_blockers"])


if __name__ == "__main__":
    unittest.main()
