from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import shutil
import tempfile
from typing import Any, Dict, Iterable, List
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from PIL import Image

from backend.planning.vision_public_bootstrap import (
    build_geographic_tile_grid,
    build_weak_supervision_package,
    feature_intersects_bbox,
    normalize_microsoft_partition_url,
    quadkeys_for_bbox,
)


DEFAULT_USGS_IMAGE_SERVER = "https://imagery.nationalmap.gov/arcgis/rest/services/USGSNAIPPlus/ImageServer"
DEFAULT_BUILDING_INDEX = "https://bfppub.blob.core.windows.net/%24web/2026-07-24/dataset-links.csv"
ALLOWED_SOURCE_HOSTS = {
    "imagery.nationalmap.gov",
    "bfppub.blob.core.windows.net",
    "bfppub.z5.web.core.windows.net",
}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a real weak-supervision starter set from public USGS imagery and Microsoft footprints."
    )
    parser.add_argument("--center-lat", type=float, required=True)
    parser.add_argument("--center-lon", type=float, required=True)
    parser.add_argument("--rows", type=int, default=4)
    parser.add_argument("--columns", type=int, default=4)
    parser.add_argument("--tile-meters", type=float, default=320.0)
    parser.add_argument("--image-pixels", type=int, default=512)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--usgs-image-server", default=DEFAULT_USGS_IMAGE_SERVER)
    parser.add_argument("--building-index-url", default=DEFAULT_BUILDING_INDEX)
    parser.add_argument("--country", default="UnitedStates")
    parser.add_argument("--quadkey-level", type=int, default=9)
    args = parser.parse_args()

    output_root = Path(args.output_root).expanduser().resolve()
    image_root = output_root / "images"
    cache_root = output_root / "cache"
    image_root.mkdir(parents=True, exist_ok=True)
    cache_root.mkdir(parents=True, exist_ok=True)
    tiles = build_geographic_tile_grid(
        center_longitude=args.center_lon,
        center_latitude=args.center_lat,
        rows=args.rows,
        columns=args.columns,
        tile_meters=args.tile_meters,
        image_pixels=args.image_pixels,
    )
    for tile in tiles:
        destination = image_root / str(tile["file_name"])
        image_url = _usgs_export_url(args.usgs_image_server, tile["bbox_wgs84"], args.image_pixels)
        _download_image(image_url, destination)
        with Image.open(destination) as image:
            if image.size != (args.image_pixels, args.image_pixels):
                raise SystemExit(f"USGS image dimensions did not match the requested tile: {destination}")
        tile["sha256"] = _file_sha256(destination)
        tile["source_url"] = image_url

    region_bbox = {
        "west": min(tile["bbox_wgs84"]["west"] for tile in tiles),
        "south": min(tile["bbox_wgs84"]["south"] for tile in tiles),
        "east": max(tile["bbox_wgs84"]["east"] for tile in tiles),
        "north": max(tile["bbox_wgs84"]["north"] for tile in tiles),
    }
    index_text = _download_text(args.building_index_url)
    partition_urls = _partition_urls(
        index_text,
        country=args.country,
        quadkeys=quadkeys_for_bbox(region_bbox, level=args.quadkey_level),
    )
    if not partition_urls:
        raise SystemExit("No Microsoft building-footprint partition matched the requested region.")
    footprints: List[Dict[str, Any]] = []
    for partition_url in partition_urls:
        cache_path = cache_root / (hashlib.sha256(partition_url.encode("utf-8")).hexdigest()[:16] + ".jsonl.gz")
        if not cache_path.is_file():
            _download_file(partition_url, cache_path)
        footprints.extend(_read_footprints(cache_path, region_bbox))
    package = build_weak_supervision_package(
        tiles=tiles,
        footprint_features=footprints,
        imagery_source={
            "name": "USGS National Map NAIP Plus (CONUS bootstrap)",
            "url": "https://data.usgs.gov/datacatalog/data/USGS:9edd9f6b-f825-47f8-8d40-50fc99995c52",
            "license": "public-domain",
            "source_rights": {
                "license": "public-domain",
                "training_use_allowed": True,
                "storage_allowed": True,
                "rights_source": "https://www.usgs.gov/centers/eros/science/usgs-eros-archive-aerial-photography-national-agriculture-imagery-program-naip",
            },
        },
        label_source={
            "name": "Microsoft Global ML Building Footprints",
            "url": "https://github.com/microsoft/GlobalMLBuildingFootprints",
            "license": "CDLA-Permissive-2.0",
            "source_rights": {
                "license": "CDLA-Permissive-2.0",
                "training_use_allowed": True,
                "storage_allowed": True,
                "rights_source": "https://github.com/microsoft/GlobalMLBuildingFootprints/blob/main/LICENSE",
            },
        },
    )
    package["source_region_bbox_wgs84"] = region_bbox
    package["source_partition_urls"] = partition_urls
    package["image_root"] = str(image_root)
    package_path = output_root / "weak-coco-package.json"
    review_path = output_root / "review-candidates.geojson"
    manifest_path = output_root / "source-manifest.json"
    package_path.write_text(json.dumps(package, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    review_path.write_text(json.dumps(package["review_candidates"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest_path.write_text(
        json.dumps(
            {
                "version": package["bootstrap_version"],
                "dataset_fingerprint": package["dataset_fingerprint"],
                "imagery_tiles": len(package["images"]),
                "weak_building_labels": len(package["annotations"]),
                "source_region_bbox_wgs84": region_bbox,
                "supervision_status": package["supervision_status"],
                "promotion_eligible": False,
                "promotion_blockers": package["promotion_blockers"],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "success": bool(package["images"] and package["annotations"]),
                "package": str(package_path),
                "image_root": str(image_root),
                "review_candidates": str(review_path),
                "imagery_tiles": len(package["images"]),
                "weak_building_labels": len(package["annotations"]),
                "splits": package["splits"],
                "promotion_eligible": False,
                "promotion_blockers": package["promotion_blockers"],
            },
            indent=2,
        )
    )
    return 0 if package["images"] and package["annotations"] else 2


def _usgs_export_url(base_url: str, bbox: Dict[str, Any], pixels: int) -> str:
    _require_allowed_https(base_url)
    params = urlencode(
        {
            "bbox": f"{bbox['west']},{bbox['south']},{bbox['east']},{bbox['north']}",
            "bboxSR": "4326",
            "imageSR": "4326",
            "size": f"{pixels},{pixels}",
            "format": "png",
            "interpolation": "RSP_BilinearInterpolation",
            "f": "image",
        }
    )
    return base_url.rstrip("/") + "/exportImage?" + params


def _download_image(url: str, destination: Path) -> None:
    _require_allowed_https(url)
    request = Request(url, headers={"User-Agent": "CivoraVisionBootstrap/1.0 (support@civora.ai)"})
    with urlopen(request, timeout=90) as response:
        content_type = str(response.headers.get("content-type") or "").lower()
        if not content_type.startswith("image/"):
            raise SystemExit(f"Expected an image from {urlsplit(url).hostname}; received {content_type or 'unknown'}.")
        with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as handle:
            shutil.copyfileobj(response, handle)
            temp_path = Path(handle.name)
    temp_path.replace(destination)


def _download_file(url: str, destination: Path) -> None:
    normalized = normalize_microsoft_partition_url(url)
    _require_allowed_https(normalized)
    request = Request(normalized, headers={"User-Agent": "CivoraVisionBootstrap/1.0 (support@civora.ai)"})
    with urlopen(request, timeout=180) as response, tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as handle:
        shutil.copyfileobj(response, handle)
        temp_path = Path(handle.name)
    temp_path.replace(destination)


def _download_text(url: str) -> str:
    _require_allowed_https(url)
    request = Request(url, headers={"User-Agent": "CivoraVisionBootstrap/1.0 (support@civora.ai)"})
    with urlopen(request, timeout=90) as response:
        return response.read().decode("utf-8-sig")


def _partition_urls(index_text: str, *, country: str, quadkeys: Iterable[str]) -> List[str]:
    expected = set(quadkeys)
    result = []
    for row in csv.DictReader(io.StringIO(index_text)):
        if row.get("Location") != country or row.get("QuadKey") not in expected:
            continue
        result.append(normalize_microsoft_partition_url(row.get("Url")))
    return sorted(set(result))


def _read_footprints(path: Path, bbox: Dict[str, Any]) -> List[Dict[str, Any]]:
    result = []
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            try:
                feature = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(feature, dict) and feature_intersects_bbox(feature, bbox):
                result.append(feature)
    return result


def _require_allowed_https(url: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_SOURCE_HOSTS:
        raise SystemExit("Bootstrap source URL must use an approved HTTPS USGS or Microsoft host.")


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
