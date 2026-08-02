from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil
from typing import Any, Dict, List

from backend.planning.vision_public_bootstrap import merge_weak_supervision_packages


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge public weak-supervision packages into one multi-geography corpus.")
    parser.add_argument("--package", action="append", required=True, help="Path to a weak-coco-package.json file.")
    parser.add_argument("--output-root", required=True)
    args = parser.parse_args()

    output_root = Path(args.output_root).expanduser().resolve()
    image_root = output_root / "images"
    image_root.mkdir(parents=True, exist_ok=True)
    packages: List[Dict[str, Any]] = []
    source_names: List[str] = []
    used_names: set[str] = set()
    for ordinal, value in enumerate(args.package, start=1):
        package_path = Path(value).expanduser().resolve()
        package = _read_object(package_path)
        source_name = _unique_source_name(package_path.parent.name, ordinal=ordinal, used=used_names)
        source_names.append(source_name)
        source_image_root = Path(str(package.get("image_root") or package_path.parent / "images")).expanduser().resolve()
        rewritten_images = []
        for raw_image in package.get("images") or []:
            if not isinstance(raw_image, dict):
                continue
            source_file = (source_image_root / str(raw_image.get("file_name") or "")).resolve()
            if source_image_root not in source_file.parents or not source_file.is_file():
                raise SystemExit(f"Registered source image is missing or escaped its image root: {source_file}")
            destination_name = f"{source_name}/{source_file.name}"
            destination = image_root / destination_name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_file, destination)
            rewritten_images.append({**raw_image, "file_name": destination_name})
        packages.append({**package, "images": rewritten_images})

    merged = merge_weak_supervision_packages(packages, source_names=source_names)
    merged["image_root"] = str(image_root)
    package_path = output_root / "weak-coco-package.json"
    review_path = output_root / "review-candidates.geojson"
    manifest_path = output_root / "source-manifest.json"
    _write_json(package_path, merged)
    _write_json(review_path, merged["review_candidates"])
    _write_json(
        manifest_path,
        {
            "version": merged["bootstrap_version"],
            "dataset_fingerprint": merged["dataset_fingerprint"],
            "source_datasets": merged["source_datasets"],
            "imagery_tiles": len(merged["images"]),
            "weak_building_labels": len(merged["annotations"]),
            "splits": merged["splits"],
            "supervision_status": merged["supervision_status"],
            "promotion_eligible": False,
            "promotion_blockers": merged["promotion_blockers"],
        },
    )
    print(
        json.dumps(
            {
                "success": bool(merged["images"] and merged["annotations"]),
                "package": str(package_path),
                "image_root": str(image_root),
                "source_datasets": source_names,
                "imagery_tiles": len(merged["images"]),
                "weak_building_labels": len(merged["annotations"]),
                "splits": merged["splits"],
                "promotion_eligible": False,
                "promotion_blockers": merged["promotion_blockers"],
            },
            indent=2,
        )
    )
    return 0 if merged["images"] and merged["annotations"] else 2


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


if __name__ == "__main__":
    raise SystemExit(main())
