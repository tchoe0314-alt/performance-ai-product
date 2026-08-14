from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.planning.vision_public_bootstrap import (
    build_scoped_weak_supervision_package,
    merge_weak_supervision_packages,
    verify_weak_supervision_package,
    weak_supervision_package_fingerprint,
)
from backend.planning.vision_evidence_integrity import (
    build_evaluation_reservation_manifest,
    build_frozen_split_manifest,
    coco_dataset_fingerprint,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge public weak-supervision packages into one multi-geography corpus.")
    parser.add_argument("--package", action="append", required=True, help="Path to a weak-coco-package.json file.")
    parser.add_argument("--output-root", required=True)
    args = parser.parse_args()
    result = merge_public_vision_packages(
        package_paths=[Path(value) for value in args.package],
        output_root=Path(args.output_root),
    )
    print(json.dumps(result, indent=2))
    return 0 if result["success"] else 2


def merge_public_vision_packages(
    *,
    package_paths: List[Path],
    output_root: Path,
    split_policy: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    if not package_paths:
        raise SystemExit("At least one public weak-supervision package is required.")

    output_root = output_root.expanduser().resolve()
    image_root = output_root / "images"
    image_root.mkdir(parents=True, exist_ok=True)
    packages: List[Dict[str, Any]] = []
    source_names: List[str] = []
    source_images: Dict[tuple[str, str], Path] = {}
    used_names: set[str] = set()
    for ordinal, value in enumerate(package_paths, start=1):
        package_path = value.expanduser().resolve()
        package = _read_object(package_path)
        validation = verify_weak_supervision_package(package)
        if not validation["valid"]:
            raise SystemExit(
                f"Source package failed verification before merge: {package_path}: "
                + ", ".join(validation["blockers"])
            )
        source_name = _unique_source_name(package_path.parent.name, ordinal=ordinal, used=used_names)
        source_names.append(source_name)
        source_image_root = Path(str(package.get("image_root") or package_path.parent / "images")).expanduser().resolve()
        for raw_image in package.get("images") or []:
            if not isinstance(raw_image, dict):
                continue
            source_file = (source_image_root / str(raw_image.get("file_name") or "")).resolve()
            if source_image_root not in source_file.parents or not source_file.is_file():
                raise SystemExit(f"Registered source image is missing or escaped its image root: {source_file}")
            expected_sha256 = str(raw_image.get("source_sha256") or "")
            if not expected_sha256 or _file_sha256(source_file) != expected_sha256:
                raise SystemExit(f"Registered source image fingerprint mismatch: {source_file}")
            source_images[(source_name, str(raw_image.get("file_name") or ""))] = source_file
        packages.append(package)

    merged = merge_weak_supervision_packages(
        packages,
        source_names=source_names,
        split_policy=split_policy,
    )
    for image in merged["images"]:
        source_name = str(image.get("source_dataset") or "")
        source_file_name = str(image.get("file_name") or "")
        source_file = source_images.get((source_name, source_file_name))
        if source_file is None:
            raise SystemExit(f"Merged source image mapping is missing: {source_name}/{source_file_name}")
        destination_name = f"{source_name}/{source_file.name}"
        destination = image_root / destination_name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_file, destination)
        image["file_name"] = destination_name
    merged["dataset_fingerprint"] = weak_supervision_package_fingerprint(merged)
    validation = verify_weak_supervision_package(merged)
    if not validation["valid"]:
        raise SystemExit("Merged package failed verification: " + ", ".join(validation["blockers"]))
    merged["coco_evidence_fingerprint"] = coco_dataset_fingerprint(merged)
    merged["frozen_split_manifest"] = build_frozen_split_manifest(merged)
    merged["image_root"] = str(image_root)
    available_splits = {
        str(item.get("split") or "")
        for item in merged["images"]
        if isinstance(item, dict) and str(item.get("split") or "")
    }
    training_package = (
        build_scoped_weak_supervision_package(
            merged,
            included_splits=("train", "validation"),
            dataset_role="training_and_validation",
        )
        if {"train", "validation"}.issubset(available_splits)
        else None
    )
    frozen_test_package = (
        build_scoped_weak_supervision_package(
            merged,
            included_splits=("test",),
            dataset_role="frozen_test",
        )
        if "test" in available_splits
        else None
    )
    package_path = output_root / "weak-coco-package.json"
    training_package_path = output_root / "training-validation-coco-package.json"
    frozen_test_package_path = output_root / "frozen-test-coco-package.json"
    review_path = output_root / "review-candidates.geojson"
    manifest_path = output_root / "source-manifest.json"
    _write_json(package_path, merged)
    if training_package is not None:
        _write_json(training_package_path, training_package)
    if frozen_test_package is not None:
        _write_json(frozen_test_package_path, frozen_test_package)
    evaluation_reservation_path = output_root / "evaluation-reservation-manifest.json"
    evaluation_reservation = None
    if training_package is not None and frozen_test_package is not None:
        evaluation_reservation = build_evaluation_reservation_manifest(
            frozen_test_package,
            training_package,
            evaluation_package_sha256=_file_sha256(frozen_test_package_path),
            training_package_sha256=_file_sha256(training_package_path),
            required_classes=[
                str(item.get("name") or "")
                for item in frozen_test_package.get("categories") or []
                if isinstance(item, dict) and str(item.get("name") or "")
            ],
        )
        _write_json(evaluation_reservation_path, evaluation_reservation)
    _write_json(review_path, merged["review_candidates"])
    _write_json(
        manifest_path,
        {
            "version": merged["bootstrap_version"],
            "dataset_fingerprint": merged["dataset_fingerprint"],
            "coco_evidence_fingerprint": merged["coco_evidence_fingerprint"],
            "frozen_split_manifest": merged["frozen_split_manifest"],
            "training_validation_package": (
                {
                    "path": training_package_path.name,
                    "dataset_fingerprint": training_package["dataset_fingerprint"],
                    "coco_evidence_fingerprint": training_package["coco_evidence_fingerprint"],
                    "image_count": len(training_package["images"]),
                    "annotation_count": len(training_package["annotations"]),
                }
                if training_package is not None
                else None
            ),
            "frozen_test_package": (
                {
                    "path": frozen_test_package_path.name,
                    "dataset_fingerprint": frozen_test_package["dataset_fingerprint"],
                    "coco_evidence_fingerprint": frozen_test_package["coco_evidence_fingerprint"],
                    "image_count": len(frozen_test_package["images"]),
                    "annotation_count": len(frozen_test_package["annotations"]),
                    "frozen_split_manifest": frozen_test_package["frozen_split_manifest"],
                }
                if frozen_test_package is not None
                else None
            ),
            "evaluation_reservation_manifest": (
                {
                    "path": evaluation_reservation_path.name,
                    "manifest_sha256": evaluation_reservation["manifest_sha256"],
                    "evaluation_package_sha256": evaluation_reservation["evaluation_package_sha256"],
                    "training_package_sha256": evaluation_reservation["training_package_sha256"],
                }
                if evaluation_reservation is not None
                else None
            ),
            "source_datasets": merged["source_datasets"],
            "label_source_status": merged.get("label_source_status", []),
            "imagery_tiles": len(merged["images"]),
            "weak_building_labels": len(merged["annotations"]),
            "splits": merged["splits"],
            "split_policy": merged["split_policy"],
            "split_integrity": merged["split_integrity"],
            "supervision_status": merged["supervision_status"],
            "promotion_eligible": False,
            "promotion_blockers": merged["promotion_blockers"],
        },
    )
    return {
        "success": bool(merged["images"] and merged["annotations"]),
        "package": str(package_path),
        "training_validation_package": str(training_package_path) if training_package is not None else "",
        "frozen_test_package": str(frozen_test_package_path) if frozen_test_package is not None else "",
        "evaluation_reservation_manifest": (
            str(evaluation_reservation_path) if evaluation_reservation is not None else ""
        ),
        "image_root": str(image_root),
        "source_datasets": source_names,
        "label_source_status": merged.get("label_source_status", []),
        "imagery_tiles": len(merged["images"]),
        "weak_building_labels": len(merged["annotations"]),
        "splits": merged["splits"],
        "split_integrity": merged["split_integrity"],
        "promotion_eligible": False,
        "promotion_blockers": merged["promotion_blockers"],
        "coco_evidence_fingerprint": merged["coco_evidence_fingerprint"],
        "frozen_split_manifest": merged["frozen_split_manifest"],
    }


def _unique_source_name(value: str, *, ordinal: int, used: set[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or f"source-{ordinal}"
    candidate = base
    suffix = 2
    while candidate in used:
        candidate = f"{base}-{suffix}"
        suffix += 1
    used.add(candidate)
    return candidate


def _read_object(path: Path) -> Dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"Package not found: {path}") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"Package must contain a JSON object: {path}")
    return value


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
