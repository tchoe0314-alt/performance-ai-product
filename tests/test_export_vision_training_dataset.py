from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

from backend.planning.vision_detection_learning import DATASET_VERSION
from backend.planning.vision_evidence_integrity import (
    validate_evaluation_reservation_manifest,
    validate_reservation_against_evidence,
)


ROOT = Path(__file__).resolve().parents[1]
EXPORT_SCRIPT = ROOT / "backend" / "scripts" / "export_vision_training_dataset.py"
PROMOTE_SCRIPT = ROOT / "backend" / "scripts" / "promote_vision_model.py"


def _frame_for_split(split: str, seed: str) -> str:
    for index in range(10000):
        frame_id = f"reviewed-frame-{split}-{index}"
        bucket = int(hashlib.sha256(f"{seed}:{frame_id}".encode()).hexdigest()[:8], 16) % 100
        actual = "train" if bucket < 80 else "validation" if bucket < 90 else "test"
        if actual == split:
            return frame_id
    raise AssertionError(f"Could not construct deterministic {split} fixture.")


def test_reviewed_export_emits_physically_isolated_packages_and_reservation(tmp_path: Path) -> None:
    seed = "split-export-fixture"
    frame_ids = {split: _frame_for_split(split, seed) for split in ("train", "validation", "test")}
    frames = []
    examples = []
    assets = []
    for ordinal, (split, frame_id) in enumerate(frame_ids.items(), start=1):
        rights = {"training_use_allowed": True, "storage_allowed": True}
        frames.append(
            {
                "frame_id": frame_id,
                "pixel_width": 128,
                "pixel_height": 128,
                "source_rights": rights,
            }
        )
        examples.append(
            {
                "example_id": f"example-{split}",
                "imagery_frame_id": frame_id,
                "original_feature_type": "building_footprint",
                "review_action": "accept",
                "pixel_geometry": {
                    "type": "Polygon",
                    "coordinates": [[[10, 10], [50, 10], [50, 50], [10, 50], [10, 10]]],
                },
                "training_eligible": True,
                "training_blockers": [],
            }
        )
        assets.append(
            {
                "imagery_frame_id": frame_id,
                "asset_id": f"asset-{split}",
                "file_name": f"tiles/{frame_id}.png",
                "width": 128,
                "height": 128,
                "sha256": str(ordinal) * 64,
                "source_rights": rights,
            }
        )
    learning = tmp_path / "learning.json"
    registry = tmp_path / "assets.json"
    attestation = tmp_path / "attestation.json"
    scope = tmp_path / "scope.json"
    output = tmp_path / "reviewed-coco.json"
    learning.write_text(json.dumps({"version": DATASET_VERSION, "imagery_frames": frames, "examples": examples}))
    registry.write_text(json.dumps({"assets": assets}))
    attestation.write_text(
        json.dumps(
            {
                "status": "human_reviewed_annotations",
                "dataset_name": "fixture",
                "license": "internal-rights-cleared",
                "independent_test_split": True,
                "test_images_excluded_from_training": True,
            }
        )
    )
    scope.write_text(
        json.dumps({"geography_count": 5, "season_count": 2, "imagery_quality_band_count": 2})
    )

    completed = subprocess.run(
        [
            sys.executable,
            str(EXPORT_SCRIPT),
            "--learning-package",
            str(learning),
            "--asset-registry",
            str(registry),
            "--output",
            str(output),
            "--split-seed",
            seed,
            "--ground-truth-attestation",
            str(attestation),
            "--evaluation-scope",
            str(scope),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    summary = json.loads(completed.stdout)
    assert summary["split_artifacts_ready"] is True
    training = json.loads(Path(summary["training_validation_output"]).read_text())
    evaluation = json.loads(Path(summary["frozen_test_output"]).read_text())
    reservation = json.loads(Path(summary["evaluation_reservation_output"]).read_text())
    assert training["dataset_role"] == "training_and_validation"
    assert training["splits"]["test"] == []
    assert "evaluation_scope" not in training
    assert "evidence_integrity" not in training
    assert "frozen_split_manifest" not in training
    assert evaluation["dataset_role"] == "frozen_test"
    assert evaluation["splits"]["train"] == []
    assert validate_evaluation_reservation_manifest(reservation)["valid"] is True
    assert validate_reservation_against_evidence(
        reservation,
        evaluation,
        training,
        evaluation_package_sha256=reservation["evaluation_package_sha256"],
        training_package_sha256=reservation["training_package_sha256"],
        required_classes=["building"],
    )["valid"] is True


def test_promotion_cli_rejects_combined_dataset_before_model_promotion(tmp_path: Path) -> None:
    combined = tmp_path / "combined.json"
    quality = tmp_path / "quality.json"
    classes = tmp_path / "classes.json"
    model = tmp_path / "model.onnx"
    combined.write_text(
        json.dumps(
            {
                "version": "civora_vision_coco_package_v1",
                "dataset_role": "combined_audit",
                "contains_image_bytes": False,
                "eligible_image_count": 1,
                "supervision_status": "reviewer_labeled",
                "splits": {"train": [1], "validation": [], "test": []},
            }
        )
    )
    quality.write_text(json.dumps({"dataset_fingerprint": "a" * 64}))
    classes.write_text(json.dumps({"0": "background", "1": "building"}))
    model.write_bytes(b"not-a-real-model")

    completed = subprocess.run(
        [
            sys.executable,
            str(PROMOTE_SCRIPT),
            "--model",
            str(model),
            "--quality-report",
            str(quality),
            "--training-dataset-package",
            str(combined),
            "--evaluation-dataset-package",
            str(combined),
            "--classes",
            str(classes),
            "--name",
            "fixture",
            "--version",
            "v1",
            "--approved-by",
            "reviewer",
            "--model-license",
            "internal",
            "--training-code-revision",
            "fixture",
            "--output",
            str(tmp_path / "manifest.json"),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode != 0
    assert "physically isolated training_and_validation package" in completed.stderr
