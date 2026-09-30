from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import fmean
from typing import Any, Dict, Optional

from backend.planning.existing_conditions_importers import import_geotiff_surface


BENCHMARK_ID = "usgs-real-terrain-001"
BENCHMARK_VERSION = "1.0.0"
SOURCE_URL = (
    "https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer/exportImage"
    "?bbox=-117.16140,32.73500,-117.16080,32.73560&bboxSR=4326&imageSR=4326"
    "&size=64,64&format=tiff&pixelType=F32&f=image"
)
USGS_RIGHTS_URL = "https://www.usgs.gov/3d-elevation-program/about-3dep-products-services"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _independent_raster_read(path: Path) -> Dict[str, Any]:
    import rasterio

    with rasterio.open(path) as dataset:
        band = dataset.read(1, masked=True)
        values = [float(value) for value in band.compressed()]
        return {
            "width": dataset.width,
            "height": dataset.height,
            "crs": str(dataset.crs),
            "valid_cell_count": len(values),
            "minimum": min(values),
            "maximum": max(values),
            "mean": fmean(values),
        }


def run_usgs_real_terrain_benchmark(
    source_path: Path,
    *,
    expected_sha256: Optional[str] = None,
    output_path: Optional[Path] = None,
) -> Dict[str, Any]:
    source_path = Path(source_path)
    source_hash = _sha256(source_path)
    imported = import_geotiff_surface(source_path)
    surface = imported.get("surface")
    independent = _independent_raster_read(source_path)

    comparisons = []

    def compare(metric: str, expected: Any, observed: Any, tolerance: float = 0.0) -> None:
        if isinstance(expected, (int, float)) and isinstance(observed, (int, float)):
            passed = abs(float(expected) - float(observed)) <= tolerance
        else:
            passed = expected == observed
        comparisons.append(
            {
                "metric": metric,
                "expected": expected,
                "observed": observed,
                "tolerance": tolerance,
                "tolerance_type": "absolute",
                "passed": passed,
            }
        )

    compare("source_sha256", expected_sha256 or source_hash, source_hash)
    compare("raster_width", independent["width"], getattr(surface, "ncols", None))
    compare("raster_height", independent["height"], getattr(surface, "nrows", None))
    compare("coordinate_system", independent["crs"], (imported.get("coordinate_system") or {}).get("name"))

    imported_values = [
        float(value)
        for row in (getattr(surface, "values", None) or [])
        for value in row
        if value is not None
    ]
    compare("valid_cell_count", independent["valid_cell_count"], len(imported_values))
    compare("minimum_elevation_m", independent["minimum"], min(imported_values) if imported_values else None, 1e-6)
    compare("maximum_elevation_m", independent["maximum"], max(imported_values) if imported_values else None, 1e-6)
    compare("mean_elevation_m", independent["mean"], fmean(imported_values) if imported_values else None, 1e-6)

    failed = [item for item in comparisons if not item["passed"]]
    blockers = [
        "accepted_boundary_missing",
        "survey_control_missing",
        "survey_benchmark_missing",
        "vertical_datum_acceptance_missing",
        "independent_engineer_review_pending",
    ]
    report = {
        "benchmark_id": BENCHMARK_ID,
        "benchmark_version": BENCHMARK_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "failed" if failed or not imported.get("success") else "passed_with_expected_blockers",
        "automated_passed": bool(imported.get("success")) and not failed,
        "construction_ready": False,
        "source": {
            "publisher": "U.S. Geological Survey, 3D Elevation Program",
            "url": SOURCE_URL,
            "rights": "Public domain; available without use restrictions.",
            "rights_url": USGS_RIGHTS_URL,
            "path": str(source_path),
            "sha256": source_hash,
            "bbox_wgs84": [-117.16140, 32.73500, -117.16080, 32.73560],
            "requested_size": [64, 64],
            "requested_pixel_type": "F32",
        },
        "import": {
            "success": bool(imported.get("success")),
            "coordinate_system": imported.get("coordinate_system"),
            "warnings": imported.get("warnings") or [],
            "truth_label": imported.get("truth_label"),
        },
        "independent_read": independent,
        "comparisons": comparisons,
        "failed_comparisons": failed,
        "blockers": blockers,
        "intended_use": "Real-terrain import regression and preparation for independent civil-engineering review.",
        "prohibited_claims": ["professional survey", "permit ready", "construction ready"],
    }
    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


__all__ = ["BENCHMARK_ID", "BENCHMARK_VERSION", "SOURCE_URL", "run_usgs_real_terrain_benchmark"]
