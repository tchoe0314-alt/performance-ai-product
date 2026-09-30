from pathlib import Path

import numpy as np
import pytest

from backend.application.usgs_real_terrain_benchmark import run_usgs_real_terrain_benchmark


def test_usgs_real_terrain_benchmark_cross_checks_import_and_stays_review_only(tmp_path: Path) -> None:
    rasterio = pytest.importorskip("rasterio")
    from rasterio.transform import from_origin

    source = tmp_path / "terrain.tif"
    data = np.array([[100.0, 101.0], [99.0, 100.0]], dtype="float32")
    with rasterio.open(
        source,
        "w",
        driver="GTiff",
        height=2,
        width=2,
        count=1,
        dtype="float32",
        crs="EPSG:4326",
        transform=from_origin(-117.2, 32.8, 0.0001, 0.0001),
    ) as dataset:
        dataset.write(data, 1)

    output = tmp_path / "report.json"
    report = run_usgs_real_terrain_benchmark(source, output_path=output)

    assert report["status"] == "passed_with_expected_blockers"
    assert report["automated_passed"] is True
    assert report["construction_ready"] is False
    assert report["failed_comparisons"] == []
    assert "independent_engineer_review_pending" in report["blockers"]
    assert output.exists()


def test_usgs_real_terrain_benchmark_fails_on_hash_mismatch(tmp_path: Path) -> None:
    rasterio = pytest.importorskip("rasterio")
    from rasterio.transform import from_origin

    source = tmp_path / "terrain.tif"
    with rasterio.open(
        source,
        "w",
        driver="GTiff",
        height=1,
        width=1,
        count=1,
        dtype="float32",
        crs="EPSG:4326",
        transform=from_origin(0.0, 1.0, 1.0, 1.0),
    ) as dataset:
        dataset.write(np.array([[1.0]], dtype="float32"), 1)

    report = run_usgs_real_terrain_benchmark(source, expected_sha256="0" * 64)

    assert report["status"] == "failed"
    assert report["automated_passed"] is False
    assert [item["metric"] for item in report["failed_comparisons"]] == ["source_sha256"]
