from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from backend.planning.vision_public_bootstrap import build_public_review_sprint
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
    args = parser.parse_args()
    result = bootstrap_public_vision_collection(
        plan_path=args.plan,
        source_registry_path=args.source_registry,
        output_root=args.output_root,
    )
    print(json.dumps(result, indent=2))
    return 0 if result["success"] else 2


def bootstrap_public_vision_collection(
    *,
    plan_path: Path,
    source_registry_path: Path,
    output_root: Path,
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
        result = bootstrap_public_vision_region(
            center_latitude=float(geography["center_latitude"]),
            center_longitude=float(geography["center_longitude"]),
            rows=int(geography.get("rows") or defaults.get("rows") or 2),
            columns=int(geography.get("columns") or defaults.get("columns") or 2),
            tile_meters=float(geography.get("tile_meters") or defaults.get("tile_meters") or 320),
            image_pixels=int(geography.get("image_pixels") or defaults.get("image_pixels") or 512),
            output_root=region_root / geography_id,
            geography_id=geography_id,
            permanent_split=str(geography["split"]),
            source_registry_path=source_registry_path,
            imagery_source_id=str(plan.get("imagery_source_id") or "usgs_naip_conus"),
            label_source_id=str(plan.get("label_source_id") or "microsoft_global_building_footprints"),
        )
        region_results.append({"geography_id": geography_id, **result})
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
    coverage = _collection_coverage(merged_package, review_sprint)
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
        "weak_building_proposals": coverage["weak_proposal_count"],
        "ground_truth_annotations": 0,
        "geographies": coverage["geographies"],
        "seasons": coverage["seasons"],
        "imagery_quality_bands": coverage["imagery_quality_bands"],
        "promotion_eligible": False,
    }


def _collection_coverage(package: Dict[str, Any], review_sprint: Dict[str, Any]) -> Dict[str, Any]:
    images = [dict(item) for item in package.get("images") or [] if isinstance(item, dict)]
    return {
        "version": "civora_public_vision_collection_coverage_v1",
        "imagery_frame_count": len(images),
        "weak_proposal_count": len(package.get("annotations") or []),
        "ground_truth_annotation_count": int(review_sprint.get("ground_truth_annotation_count") or 0),
        "geographies": sorted({str(item.get("geography_id") or item.get("source_dataset") or "") for item in images if item.get("geography_id") or item.get("source_dataset")}),
        "seasons": sorted({str(item.get("season") or "") for item in images if item.get("season")}),
        "imagery_quality_bands": sorted({str(item.get("imagery_quality_band") or "") for item in images if item.get("imagery_quality_band")}),
        "split_integrity": dict(package.get("split_integrity") or {}),
        "capture_dates": sorted({str(item.get("capture_date") or "") for item in images if item.get("capture_date")}),
        "review_status": "pending_human_review",
        "promotion_eligible": False,
    }


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
