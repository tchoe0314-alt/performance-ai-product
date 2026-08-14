from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import json
from types import SimpleNamespace

import pytest

from backend.scripts import run_vision_model_diagnostic as diagnostic_script
from backend.scripts import calibrate_vision_model_thresholds as calibration_script
from backend.scripts.evaluate_vision_model import _scope_predictions_for_coco_split
from backend.planning.vision_evidence_integrity import coco_dataset_fingerprint
from backend.planning.vision_model_calibration import calibrate_detection_thresholds


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = REPO_ROOT / "backend" / "scripts"


def _coco_fixture() -> dict:
    return {
        "categories": [{"id": 1, "name": "building"}],
        "images": [
            {
                "id": 1,
                "file_name": "train.png",
                "imagery_frame_id": "train-frame",
                "split": "train",
            },
            {
                "id": 2,
                "file_name": "test.png",
                "imagery_frame_id": "test-frame",
                "split": "test",
            },
        ],
        "annotations": [],
        "splits": {"train": [1], "validation": [], "test": [2]},
    }


def test_vision_cli_help_works_outside_repository_cwd(tmp_path: Path) -> None:
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)

    for script_name in (
        "evaluate_vision_model.py",
        "calibrate_vision_model_thresholds.py",
        "run_vision_model_diagnostic.py",
        "run_vision_heuristic_diagnostic.py",
    ):
        result = subprocess.run(
            [sys.executable, str(SCRIPT_ROOT / script_name), "--help"],
            cwd=tmp_path,
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

        assert result.returncode == 0, f"{script_name}: {result.stderr}"
        assert "usage:" in result.stdout.lower()
        assert script_name in result.stdout


def test_prediction_scope_rejects_missing_and_unknown_scope() -> None:
    result = _scope_predictions_for_coco_split(
        [
            {"kind": "building"},
            {"kind": "building", "file_name": "not-in-dataset.png"},
            {"kind": "building", "image_id": 999},
        ],
        _coco_fixture(),
        split="test",
    )

    assert result["valid"] is False
    assert result["selected"] == []
    assert result["selected_prediction_count"] == 0
    assert result["blockers"] == [
        "prediction_scope_missing_or_unknown:1",
        "prediction_scope_missing_or_unknown:2",
        "prediction_scope_unknown_image:3",
    ]


def test_prediction_scope_ignores_known_ids_outside_selected_split() -> None:
    test_prediction = {"kind": "building", "imagery_frame_id": "test-frame"}
    result = _scope_predictions_for_coco_split(
        [
            {"kind": "building", "image_id": 1},
            {"kind": "building", "file_name": "train.png"},
            test_prediction,
        ],
        _coco_fixture(),
        split="test",
    )

    assert result["valid"] is True
    assert result["selected"] == [test_prediction]
    assert result["selected_prediction_count"] == 1
    assert result["ignored_outside_split_count"] == 2
    assert result["evaluation_image_count"] == 1
    assert result["blockers"] == []


def test_standalone_evaluators_reject_test_use_before_opening_evidence(tmp_path: Path) -> None:
    missing = tmp_path / "must-not-be-opened.json"
    generic = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_ROOT / "evaluate_vision_model.py"),
            "--predictions",
            str(missing),
            "--ground-truth",
            str(missing),
            "--output",
            str(tmp_path / "quality.json"),
            "--split",
            "test",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert generic.returncode != 0
    assert "Standalone test evaluation is disabled before evidence files are opened" in generic.stderr
    assert "No such file" not in generic.stderr

    heuristic = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_ROOT / "run_vision_heuristic_diagnostic.py"),
            "--dataset",
            str(missing),
            "--image-root",
            str(tmp_path),
            "--output",
            str(tmp_path / "heuristic.json"),
            "--split",
            "test",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert heuristic.returncode != 0
    assert "Standalone frozen-test baseline evaluation is disabled" in heuristic.stderr
    assert "No such file" not in heuristic.stderr


def test_calibration_rejects_ground_truth_not_identical_to_validation_package(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dataset = {
        "categories": [{"id": 1, "name": "building"}],
        "images": [{"id": 1, "file_name": "validation.png", "split": "validation"}],
        "annotations": [
            {
                "id": 1,
                "image_id": 1,
                "category_id": 1,
                "bbox": [0, 0, 10, 10],
                "area": 100,
                "segmentation": [[0, 0, 10, 0, 10, 10, 0, 10]],
                "iscrowd": 0,
            }
        ],
        "splits": {"train": [], "validation": [1], "test": []},
        "supervision_status": "reviewer_labeled",
        "ground_truth_attestation": {"status": "human_reviewed_annotations"},
    }
    dataset["coco_evidence_fingerprint"] = coco_dataset_fingerprint(dataset)
    fingerprint = dataset["coco_evidence_fingerprint"]
    dataset_path = tmp_path / "validation.json"
    predictions_path = tmp_path / "predictions.json"
    ground_truth_path = tmp_path / "ground-truth.json"
    output_path = tmp_path / "calibration.json"
    dataset_path.write_text(json.dumps(dataset), encoding="utf-8")
    predictions_path.write_text(
        json.dumps(
            {
                "evaluation_split": "validation",
                "dataset_fingerprint": fingerprint,
                "validation_dataset_fingerprint": fingerprint,
                "evidence_family_fingerprint": fingerprint,
                "training_dataset_fingerprint": fingerprint,
                "model_artifact_sha256": "a" * 64,
                "predictions": [],
            }
        ),
        encoding="utf-8",
    )
    ground_truth_path.write_text(
        json.dumps(
            {
                "evaluation_split": "validation",
                "dataset_fingerprint": fingerprint,
                "validation_calibration_eligible": True,
                "ground_truth": [],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "calibrate_vision_model_thresholds.py",
            "--predictions",
            str(predictions_path),
            "--ground-truth",
            str(ground_truth_path),
            "--dataset",
            str(dataset_path),
            "--output",
            str(output_path),
        ],
    )

    with pytest.raises(SystemExit, match="do not match the reviewed validation dataset package"):
        calibration_script.main()

    assert not output_path.exists()


def test_frozen_test_preflight_rejects_noneligible_validation_calibration(tmp_path: Path) -> None:
    calibration = calibrate_detection_thresholds(
        [],
        [],
        dataset_fingerprint="f" * 64,
        confidence_values=[0.5],
        minimum_component_pixels_values=[24],
        source_supervision_status="weak_labels_pending_review",
        validation_dataset_fingerprint="d" * 64,
        training_dataset_fingerprint="d" * 64,
        validation_package_sha256="e" * 64,
        model_artifact_sha256="a" * 64,
    )
    calibration_path = tmp_path / "calibration.json"
    calibration_path.write_text(json.dumps(calibration), encoding="utf-8")
    args = SimpleNamespace(calibration=str(calibration_path), split="test")

    with pytest.raises(SystemExit, match="Threshold calibration is invalid"):
        diagnostic_script._load_threshold_calibration(
            args,
            evidence_family_fingerprint="f" * 64,
            training_fingerprint="d" * 64,
            model_artifact_sha256="a" * 64,
            validation_package_sha256="e" * 64,
        )


def test_model_diagnostic_requires_ledger_before_opening_test_images(tmp_path: Path) -> None:
    dataset = _coco_fixture()
    dataset_path = tmp_path / "dataset.json"
    training_path = tmp_path / "training.json"
    classes_path = tmp_path / "classes.json"
    model_path = tmp_path / "model.onnx"
    dataset_path.write_text(json.dumps(dataset), encoding="utf-8")
    training_path.write_text(json.dumps(dataset), encoding="utf-8")
    classes_path.write_text(json.dumps({"0": "background", "1": "building"}), encoding="utf-8")
    model_path.write_bytes(b"not-a-real-model")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_ROOT / "run_vision_model_diagnostic.py"),
            "--model",
            str(model_path),
            "--classes",
            str(classes_path),
            "--dataset",
            str(dataset_path),
            "--training-dataset",
            str(training_path),
            "--image-root",
            str(tmp_path / "missing-images"),
            "--output-dir",
            str(tmp_path / "output"),
            "--split",
            "test",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "--evaluation-reservation-manifest is required" in result.stderr
    assert "Diagnostic image is missing" not in result.stderr


def test_invalid_candidate_preflight_does_not_consume_or_open_frozen_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model_path = tmp_path / "candidate.onnx"
    classes_path = tmp_path / "classes.json"
    reservation_path = tmp_path / "reservation.json"
    calibration_path = tmp_path / "calibration.json"
    evaluation_path = tmp_path / "frozen-test.json"
    training_path = tmp_path / "training.json"
    image_root = tmp_path / "images"
    image_root.mkdir()
    model_path.write_bytes(b"invalid-model")
    classes_path.write_text("{}", encoding="utf-8")
    reservation_path.write_text("{}", encoding="utf-8")
    calibration_path.write_text("{}", encoding="utf-8")
    evaluation_path.write_text("{}", encoding="utf-8")
    training_path.write_text("{}", encoding="utf-8")
    frozen_reads: list[Path] = []
    reserve_calls: list[dict] = []

    def fake_read_object(path: Path) -> dict:
        if path == classes_path:
            return {"0": "background", "1": "building"}
        if path == reservation_path:
            return {
                "required_model_classes": ["building"],
                "evidence_family_fingerprint": "f" * 64,
                "training_dataset_fingerprint": "d" * 64,
                "evaluation_dataset_fingerprint": "e" * 64,
            }
        raise AssertionError(f"Unexpected JSON read before reservation: {path}")

    monkeypatch.setattr(diagnostic_script, "_read_object", fake_read_object)
    monkeypatch.setattr(
        diagnostic_script,
        "validate_evaluation_reservation_manifest",
        lambda *_args, **_kwargs: {"valid": True, "blockers": []},
    )
    monkeypatch.setattr(diagnostic_script, "file_sha256", lambda _path: "a" * 64)
    monkeypatch.setattr(diagnostic_script, "_load_threshold_calibration", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        diagnostic_script,
        "_preflight_candidate_runtime",
        lambda **_kwargs: (_ for _ in ()).throw(SystemExit("Candidate runtime preflight failed: invalid ONNX")),
    )
    monkeypatch.setattr(
        diagnostic_script,
        "reserve_test_consumption",
        lambda *_args, **_kwargs: reserve_calls.append({}) or {},
    )
    monkeypatch.setattr(
        diagnostic_script,
        "_read_file_bytes",
        lambda path: frozen_reads.append(path) or b"must-not-open",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_vision_model_diagnostic.py",
            "--model",
            str(model_path),
            "--classes",
            str(classes_path),
            "--dataset",
            str(evaluation_path),
            "--training-dataset",
            str(training_path),
            "--evaluation-reservation-manifest",
            str(reservation_path),
            "--test-consumption-ledger",
            str(tmp_path / "ledger.json"),
            "--calibration",
            str(calibration_path),
            "--image-root",
            str(image_root),
            "--output-dir",
            str(tmp_path / "output"),
            "--split",
            "test",
        ],
    )

    with pytest.raises(SystemExit, match="Candidate runtime preflight failed"):
        diagnostic_script.main()

    assert reserve_calls == []
    assert frozen_reads == []
    assert not (tmp_path / "ledger.json").exists()


def test_frozen_evidence_cannot_alias_a_candidate_or_configuration_path(tmp_path: Path) -> None:
    frozen_path = tmp_path / "frozen-test.json"
    frozen_path.write_text("{}", encoding="utf-8")
    image_root = tmp_path / "images"
    image_root.mkdir()

    with pytest.raises(SystemExit, match="physically distinct"):
        diagnostic_script._validate_isolated_test_paths(
            {
                "model": frozen_path,
                "frozen test package": frozen_path,
                "development package": tmp_path / "development.json",
            },
            ledger_path=tmp_path / "evidence" / "ledger.json",
            image_root=image_root,
            output_dir=tmp_path / "output",
        )

    with pytest.raises(SystemExit, match="outside the evidence image root"):
        diagnostic_script._validate_isolated_test_paths(
            {"model": image_root / "test-frame.png"},
            ledger_path=tmp_path / "evidence" / "ledger.json",
            image_root=image_root,
            output_dir=tmp_path / "output",
        )
