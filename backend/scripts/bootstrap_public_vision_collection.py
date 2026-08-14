from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.planning.vision_public_bootstrap import (
    build_public_review_sprint,
    verify_weak_supervision_package,
)
from backend.planning.vision_review_gallery import build_public_review_gallery_html
from backend.scripts.bootstrap_public_vision_dataset import bootstrap_public_vision_region
from backend.scripts.merge_public_vision_datasets import merge_public_vision_packages


COLLECTION_PLAN_VERSION = "civora_public_vision_collection_plan_v1"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Collect a rights-cleared multi-geography NAIP building review corpus from one auditable plan."
    )
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--source-registry", default="vision/datasets/public-source-registry-v1.json", type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reuse a completed, verified region package and collect only unfinished geographies.",
    )
    args = parser.parse_args()
    result = bootstrap_public_vision_collection(
        plan_path=args.plan,
        source_registry_path=args.source_registry,
        output_root=args.output_root,
        resume=args.resume,
    )
    print(json.dumps(result, indent=2))
    return 0 if result["success"] else 2


def bootstrap_public_vision_collection(
    *,
    plan_path: Path,
    source_registry_path: Path,
    output_root: Path,
    resume: bool = False,
) -> Dict[str, Any]:
    plan = _read_object(plan_path)
    if plan.get("version") != COLLECTION_PLAN_VERSION:
        raise SystemExit("Unsupported public vision collection plan.")
    defaults = dict(plan.get("tile_defaults") or {})
    geographies = [dict(item) for item in plan.get("geographies") or [] if isinstance(item, dict)]
    if not geographies:
        raise SystemExit("Collection plan must include at least one geography.")
    geography_ids = [str(item.get("geography_id") or "") for item in geographies]
    if any(not item for item in geography_ids) or len(geography_ids) != len(set(geography_ids)):
        raise SystemExit("Collection geography IDs must be present and unique.")
    split_policy = dict(plan.get("split_policy") or {})
    required_splits = [str(item) for item in split_policy.get("required_splits") or []]
    geography_splits = [str(item.get("split") or "") for item in geographies]
    if split_policy.get("strategy") != "geography_disjoint":
        raise SystemExit("Collection plan must use the geography_disjoint split strategy.")
    if split_policy.get("grouping_field") != "geography_id":
        raise SystemExit("Collection plan split grouping must use geography_id.")
    if any(item not in {"train", "validation", "test"} for item in geography_splits):
        raise SystemExit("Every collection geography must declare train, validation, or test split.")
    if any(split not in geography_splits for split in required_splits):
        raise SystemExit("Collection plan is missing a required geography split.")
    output_root = output_root.expanduser().resolve()
    region_root = output_root / "regions"
    region_root.mkdir(parents=True, exist_ok=True)
    region_results: List[Dict[str, Any]] = []
    package_paths: List[Path] = []
    for geography in geographies:
        geography_id = str(geography["geography_id"])
        region_output = region_root / geography_id
        existing_package = region_output / "weak-coco-package.json"
        existing_manifest = region_output / "source-manifest.json"
        if resume and existing_package.is_file() and existing_manifest.is_file():
            verification = verify_resumable_region(
                region_output,
                geography_id=geography_id,
                expected_split=str(geography["split"]),
            )
            if verification["valid"] is not True:
                raise SystemExit(f"Completed region failed resume verification: {geography_id}")
            package = verification["package"]
            image_ids = verification["image_ids"]
            region_results.append(
                {
                    "geography_id": geography_id,
                    "success": True,
                    "resumed": True,
                    "package": str(existing_package),
                    "image_root": str(region_output / "images"),
                    "imagery_tiles": len(image_ids),
                    "weak_proposals_by_class": _annotation_counts_by_class(package),
                    "promotion_eligible": False,
                }
            )
            package_paths.append(existing_package)
            continue
        result = bootstrap_public_vision_region(
            center_latitude=float(geography["center_latitude"]),
            center_longitude=float(geography["center_longitude"]),
            rows=int(geography.get("rows") or defaults.get("rows") or 2),
            columns=int(geography.get("columns") or defaults.get("columns") or 2),
            tile_meters=float(geography.get("tile_meters") or defaults.get("tile_meters") or 320),
            image_pixels=int(geography.get("image_pixels") or defaults.get("image_pixels") or 512),
            output_root=region_output,
            geography_id=geography_id,
            permanent_split=str(geography["split"]),
            source_registry_path=source_registry_path,
            imagery_source_id=str(plan.get("imagery_source_id") or "usgs_naip_conus"),
            label_source_id=str(plan.get("label_source_id") or "microsoft_global_building_footprints"),
            additional_label_sources=[
                dict(item)
                for item in plan.get("additional_label_sources") or []
                if isinstance(item, dict)
            ],
        )
        region_results.append({"geography_id": geography_id, "resumed": False, **result})
        package_paths.append(Path(result["package"]))

    merged_root = output_root / "merged"
    merged_result = merge_public_vision_packages(
        package_paths=package_paths,
        output_root=merged_root,
        split_policy=split_policy,
    )
    merged_package = _read_object(Path(merged_result["package"]))
    review_sprint = build_public_review_sprint(merged_package)
    review_sprint_path = merged_root / "vision-review-sprint.json"
    review_sprint_path.write_text(json.dumps(review_sprint, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    review_gallery_path = merged_root / "review-gallery.html"
    review_gallery_path.write_text(
        build_public_review_gallery_html(review_sprint, image_prefix="images"),
        encoding="utf-8",
    )
    coverage = _collection_coverage(
        merged_package,
        review_sprint,
        coverage_policy=dict(plan.get("coverage_policy") or {}),
    )
    coverage_path = merged_root / "collection-coverage.json"
    coverage_path.write_text(json.dumps(coverage, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    run_record = {
        "version": "civora_public_vision_collection_run_v1",
        "collection_id": str(plan.get("collection_id") or output_root.name),
        "plan": str(plan_path.expanduser().resolve()),
        "source_registry": str(source_registry_path.expanduser().resolve()),
        "regions": region_results,
        "merged": merged_result,
        "review_sprint": str(review_sprint_path),
        "review_gallery": str(review_gallery_path),
        "coverage": coverage,
        "training_coverage_ready": coverage["training_coverage_ready"],
        "training_coverage_blockers": coverage["training_coverage_blockers"],
        "ground_truth_annotation_count": 0,
        "promotion_eligible": False,
        "truth_label": (
            "This run collected real rights-cleared imagery and weak proposals. It intentionally reports zero ground-truth "
            "annotations until a reviewer acts through the immutable ledger."
        ),
    }
    run_path = output_root / "collection-run.json"
    run_path.write_text(json.dumps(run_record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "success": bool(merged_result.get("success")),
        "collection_run": str(run_path),
        "review_sprint": str(review_sprint_path),
        "review_gallery": str(review_gallery_path),
        "imagery_frames": coverage["imagery_frame_count"],
        "weak_building_proposals": coverage["weak_proposals_by_class"].get("building", 0),
        "weak_proposals_by_class": coverage["weak_proposals_by_class"],
        "weak_proposals_by_split_and_class": coverage["weak_proposals_by_split_and_class"],
        "training_coverage_ready": coverage["training_coverage_ready"],
        "training_coverage_blockers": coverage["training_coverage_blockers"],
        "ground_truth_annotations": 0,
        "geographies": coverage["geographies"],
        "seasons": coverage["seasons"],
        "imagery_quality_bands": coverage["imagery_quality_bands"],
        "promotion_eligible": False,
    }


def verify_resumable_region(
    region_output: Path,
    *,
    geography_id: str,
    expected_split: str,
) -> Dict[str, Any]:
    root = region_output.expanduser().resolve()
    package_path = root / "weak-coco-package.json"
    manifest_path = root / "source-manifest.json"
    blockers: List[str] = []
    if not package_path.is_file() or not manifest_path.is_file():
        return {
            "valid": False,
            "blockers": ["completed_region_artifacts_missing"],
            "package": {},
            "image_ids": set(),
        }
    package = _read_object(package_path)
    manifest = _read_object(manifest_path)
    package_validation = verify_weak_supervision_package(package)
    blockers.extend(package_validation["blockers"])
    expected_label_sources = {
        str(item.get("source_id") or "")
        for item in package.get("licenses") or []
        if isinstance(item, dict)
        and str(item.get("source_role") or "") == "weak_label_proposals_only"
        and str(item.get("source_id") or "")
    }
    observed_label_sources = {
        str(item.get("source_id") or "")
        for item in package.get("label_source_status") or []
        if isinstance(item, dict) and str(item.get("source_id") or "")
    }
    blockers.extend(
        f"completed_region_label_source_status_missing:{source_id}"
        for source_id in sorted(expected_label_sources - observed_label_sources)
    )
    image_ids = {
        int(item.get("id") or 0)
        for item in package.get("images") or []
        if isinstance(item, dict) and int(item.get("id") or 0) > 0
    }
    declared_ids = {
        int(item)
        for item in (package.get("splits") or {}).get(expected_split) or []
        if int(item) > 0
    }
    if package.get("geography_id") != geography_id:
        blockers.append("completed_region_geography_mismatch")
    if not image_ids:
        blockers.append("completed_region_images_missing")
    if image_ids != declared_ids:
        blockers.append("completed_region_split_mismatch")
    if manifest.get("dataset_fingerprint") != package.get("dataset_fingerprint"):
        blockers.append("completed_region_manifest_fingerprint_mismatch")
    image_root = Path(str(package.get("image_root") or root / "images")).expanduser().resolve()
    for image in package.get("images") or []:
        if not isinstance(image, dict):
            continue
        image_path = (image_root / str(image.get("file_name") or "")).resolve()
        if image_root not in image_path.parents or not image_path.is_file():
            blockers.append("completed_region_image_file_missing")
            break
    return {
        "valid": not blockers,
        "blockers": sorted(set(blockers)),
        "package": package,
        "image_ids": image_ids,
    }


def _collection_coverage(
    package: Dict[str, Any],
    review_sprint: Dict[str, Any],
    *,
    coverage_policy: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    images = [dict(item) for item in package.get("images") or [] if isinstance(item, dict)]
    policy = dict(coverage_policy or {})
    required_splits = [str(item) for item in policy.get("required_splits") or ("train", "validation", "test")]
    category_names = {
        int(item.get("id") or 0): str(item.get("name") or "unknown")
        for item in package.get("categories") or []
        if isinstance(item, dict)
    }
    image_splits = {
        int(item.get("id") or 0): str(item.get("split") or "")
        for item in images
    }
    class_names = sorted({name for name in category_names.values() if name})
    by_split_and_class = {
        split: {label: 0 for label in class_names}
        for split in required_splits
    }
    for annotation in package.get("annotations") or []:
        if not isinstance(annotation, dict):
            continue
        split = image_splits.get(int(annotation.get("image_id") or 0), "")
        label = str(
            annotation.get("category_name")
            or category_names.get(int(annotation.get("category_id") or 0))
            or "unknown"
        )
        if split in by_split_and_class and label in by_split_and_class[split]:
            by_split_and_class[split][label] += 1
    minimums = {
        label: max(1, int(value or 1))
        for label, value in dict(policy.get("minimum_proposals_per_class_per_split") or {}).items()
        if str(label) in class_names
    }
    for label in class_names:
        minimums.setdefault(label, 1)
    coverage_blockers = sorted(
        f"class_split_proposal_count_below_minimum:{split}:{label}:{count}<{minimums[label]}"
        for split in required_splits
        for label, count in by_split_and_class.get(split, {}).items()
        if count < minimums[label]
    )
    label_source_status = [
        dict(item)
        for item in package.get("label_source_status") or []
        if isinstance(item, dict)
    ]
    source_datasets = {
        str(item.get("name") or "")
        for item in package.get("source_datasets") or []
        if isinstance(item, dict) and str(item.get("name") or "")
    }
    expected_source_ids = {
        str(item.get("source_id") or "")
        for item in package.get("licenses") or []
        if isinstance(item, dict)
        and str(item.get("source_role") or "") == "weak_label_proposals_only"
        and str(item.get("source_id") or "")
    }
    observed_source_keys = {
        (str(item.get("source_dataset") or ""), str(item.get("source_id") or ""))
        for item in label_source_status
    }
    missing_source_status = sorted(
        f"weak_label_source_status_not_recorded:{source_dataset}:{source_id}"
        for source_dataset in source_datasets
        for source_id in expected_source_ids
        if (source_dataset, source_id) not in observed_source_keys
    )
    source_availability_blockers = sorted(
        {
            *missing_source_status,
            *(
                f"weak_label_source_unavailable:{item.get('source_dataset') or 'region'}:{item.get('source_id') or 'unknown'}"
                for item in label_source_status
                if str(item.get("status") or "") != "ready"
            ),
        }
    )
    return {
        "version": "civora_public_vision_collection_coverage_v1",
        "imagery_frame_count": len(images),
        "weak_proposal_count": len(package.get("annotations") or []),
        "weak_proposals_by_class": _annotation_counts_by_class(package),
        "weak_proposals_by_split_and_class": by_split_and_class,
        "coverage_requirements": {
            "required_splits": required_splits,
            "minimum_proposals_per_class_per_split": minimums,
        },
        "training_coverage_ready": not coverage_blockers,
        "training_coverage_blockers": coverage_blockers,
        "label_source_status": label_source_status,
        "source_availability_evidence_complete": not missing_source_status,
        "source_availability_complete": not source_availability_blockers,
        "source_availability_blockers": source_availability_blockers,
        "ground_truth_annotation_count": int(review_sprint.get("ground_truth_annotation_count") or 0),
        "geographies": sorted({str(item.get("geography_id") or item.get("source_dataset") or "") for item in images if item.get("geography_id") or item.get("source_dataset")}),
        "seasons": sorted({str(item.get("season") or "") for item in images if item.get("season")}),
        "imagery_quality_bands": sorted({str(item.get("imagery_quality_band") or "") for item in images if item.get("imagery_quality_band")}),
        "split_integrity": dict(package.get("split_integrity") or {}),
        "capture_dates": sorted({str(item.get("capture_date") or "") for item in images if item.get("capture_date")}),
        "review_status": "pending_human_review",
        "promotion_eligible": False,
    }


def _annotation_counts_by_class(package: Dict[str, Any]) -> Dict[str, int]:
    category_names = {
        int(item.get("id") or 0): str(item.get("name") or "unknown")
        for item in package.get("categories") or []
        if isinstance(item, dict)
    }
    counts: Dict[str, int] = {}
    for annotation in package.get("annotations") or []:
        if not isinstance(annotation, dict):
            continue
        label = str(
            annotation.get("category_name")
            or category_names.get(int(annotation.get("category_id") or 0))
            or "unknown"
        )
        counts[label] = counts.get(label, 0) + 1
    return dict(sorted(counts.items()))


def _read_object(path: Path) -> Dict[str, Any]:
    try:
        value = json.loads(path.expanduser().resolve().read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        raise SystemExit(f"JSON file is missing or invalid: {path}") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"Expected a JSON object: {path}")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
