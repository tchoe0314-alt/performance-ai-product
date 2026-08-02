from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from backend.planning.vision_ground_truth_flywheel import DATASET_VERSION, ground_truth_dataset_fingerprint


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


class ExportVisionGroundTruthDatasetTests(unittest.TestCase):
    def test_cli_merges_deduplicates_and_writes_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            first = temp / "first.json"
            second = temp / "second.json"
            output = temp / "merged.json"
            coverage = temp / "coverage.json"
            first.write_text(json.dumps(_dataset()), encoding="utf-8")
            second.write_text(json.dumps(_dataset()), encoding="utf-8")

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
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            merged = json.loads(output.read_text(encoding="utf-8"))
            coverage_report = json.loads(coverage.read_text(encoding="utf-8"))
            self.assertEqual(merged["annotation_count"], 1)
            self.assertEqual(merged["counts_by_split"], {"test": 0, "train": 1, "validation": 0})
            self.assertIn("building_footprint", coverage_report["blocked_classes"])

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

            completed = subprocess.run(
                [sys.executable, str(SCRIPT), str(first), str(second), "--output", str(output)],
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
