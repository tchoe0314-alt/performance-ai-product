from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, List

from backend.planning.existing_conditions_importers import (
    classify_existing_conditions_file,
    dependency_blocked_existing_conditions_import,
    import_dxf_existing_conditions,
    import_geojson,
    import_geotiff_surface,
    import_las_point_cloud,
    import_landxml_metadata,
    import_survey_csv,
    merge_imported_existing_conditions,
)


FIXTURE_DIR = Path(__file__).resolve().parents[1] / "backend" / "fixtures" / "real_input_benchmarks"
CONTROL_CRS = {"epsg": "EPSG:2276", "units": "ft", "source": "benchmark survey control note"}


def _blocker_fields(merged: Dict[str, Any]) -> List[str]:
    return sorted({str(item.get("field")) for item in merged["import_validation"]["blockers"]})


def _matrix_row(input_type: str, imported: Dict[str, Any], merged: Dict[str, Any]) -> Dict[str, Any]:
    source = merged["sources"][0] if merged.get("sources") else {}
    validation = merged["import_validation"]
    if source.get("dependency_blocked"):
        support = "limited"
    elif not imported.get("success"):
        support = "unsupported"
    elif source.get("metadata_only"):
        support = "limited"
    else:
        support = "supported"
    return {
        "input_type": input_type,
        "support": support,
        "canonical_vs_metadata": "metadata-only" if source.get("metadata_only") else "canonical",
        "canonical_targets": list(source.get("canonical_targets") or []),
        "requires_crs_datum_control_source": True,
        "production_ready": bool(validation["production_usable"]),
        "blockers": _blocker_fields(merged),
    }


class RealInputFileBenchmarkTests(unittest.TestCase):
    maxDiff = None

    def test_real_input_import_benchmark_matrix_is_truthful(self) -> None:
        survey = import_survey_csv(FIXTURE_DIR / "survey_points.csv", coordinate_system=CONTROL_CRS)
        geojson = import_geojson(FIXTURE_DIR / "constraints.geojson", coordinate_system=CONTROL_CRS)
        landxml = import_landxml_metadata(FIXTURE_DIR / "surface_pipe.landxml", coordinate_system=CONTROL_CRS)

        with tempfile.TemporaryDirectory() as tmpdir:
            dxf_import = self._build_dxf_benchmark(Path(tmpdir) / "survey.dxf")
            geotiff_import = self._build_optional_geotiff_benchmark(Path(tmpdir) / "surface.tif")
            las_import = self._build_optional_las_benchmark(Path(tmpdir) / "cloud.las")

        imports = {
            "CSV survey points": survey,
            "GeoJSON/GIS constraints": geojson,
            "LandXML surface/pipe data": landxml,
            "DXF survey": dxf_import,
            "GeoTIFF/DEM": geotiff_import,
            "LAS/LiDAR": las_import,
        }
        benchmark_rows = {
            name: _matrix_row(name, imported, merge_imported_existing_conditions(imported))
            for name, imported in imports.items()
        }

        self.assertEqual(benchmark_rows["CSV survey points"]["support"], "supported")
        self.assertEqual(benchmark_rows["CSV survey points"]["canonical_vs_metadata"], "canonical")
        self.assertIn("survey_points", benchmark_rows["CSV survey points"]["canonical_targets"])
        self.assertIn("survey_benchmark", benchmark_rows["CSV survey points"]["blockers"])
        self.assertIn("gis_layers", benchmark_rows["CSV survey points"]["blockers"])

        self.assertEqual(benchmark_rows["GeoJSON/GIS constraints"]["support"], "supported")
        self.assertEqual(benchmark_rows["GeoJSON/GIS constraints"]["canonical_targets"], ["gis_layers"])
        self.assertIn("survey_surface", benchmark_rows["GeoJSON/GIS constraints"]["blockers"])

        self.assertEqual(benchmark_rows["LandXML surface/pipe data"]["support"], "supported")
        self.assertEqual(benchmark_rows["LandXML surface/pipe data"]["canonical_vs_metadata"], "canonical")
        self.assertIn("terrain_surface_metadata", benchmark_rows["LandXML surface/pipe data"]["canonical_targets"])
        self.assertIn("pipe_network_metadata", benchmark_rows["LandXML surface/pipe data"]["canonical_targets"])
        self.assertIn("gis_layers", benchmark_rows["LandXML surface/pipe data"]["blockers"])

        self.assertIn(benchmark_rows["DXF survey"]["support"], {"supported", "limited"})
        if benchmark_rows["DXF survey"]["support"] == "supported":
            self.assertIn("survey_points", benchmark_rows["DXF survey"]["canonical_targets"])
            self.assertIn("breaklines", benchmark_rows["DXF survey"]["canonical_targets"])
        else:
            self.assertEqual(benchmark_rows["DXF survey"]["canonical_vs_metadata"], "metadata-only")

        self.assertIn(benchmark_rows["GeoTIFF/DEM"]["support"], {"supported", "limited"})
        if benchmark_rows["GeoTIFF/DEM"]["support"] == "supported":
            self.assertIn("terrain_surface", benchmark_rows["GeoTIFF/DEM"]["canonical_targets"])
        else:
            self.assertEqual(benchmark_rows["GeoTIFF/DEM"]["canonical_vs_metadata"], "metadata-only")
            self.assertIn("dependency_blocked_imports", benchmark_rows["GeoTIFF/DEM"]["blockers"])

        self.assertIn(benchmark_rows["LAS/LiDAR"]["support"], {"supported", "limited"})
        if benchmark_rows["LAS/LiDAR"]["support"] == "supported":
            self.assertIn("lidar_point_cloud", benchmark_rows["LAS/LiDAR"]["canonical_targets"])
        else:
            self.assertEqual(benchmark_rows["LAS/LiDAR"]["canonical_vs_metadata"], "metadata-only")
            self.assertIn("dependency_blocked_imports", benchmark_rows["LAS/LiDAR"]["blockers"])

        for row in benchmark_rows.values():
            self.assertFalse(row["production_ready"], row)
            self.assertTrue(row["requires_crs_datum_control_source"])

    def test_combined_real_input_fixtures_create_canonical_evidence_but_not_production_readiness(self) -> None:
        survey = import_survey_csv(FIXTURE_DIR / "survey_points.csv", coordinate_system=CONTROL_CRS)
        geojson = import_geojson(FIXTURE_DIR / "constraints.geojson", coordinate_system=CONTROL_CRS)
        landxml = import_landxml_metadata(FIXTURE_DIR / "surface_pipe.landxml", coordinate_system=CONTROL_CRS)

        merged = merge_imported_existing_conditions(survey, geojson, landxml)
        model = merged["canonical_existing_conditions_model"]
        validation = merged["import_validation"]

        self.assertTrue(model["canonicalized"])
        self.assertFalse(model["metadata_only"])
        self.assertEqual(model["survey"]["point_count"], 5)
        self.assertEqual(model["terrain"]["surface_count"], 1)
        self.assertEqual(model["gis_layer_counts"]["parcels"], 1)
        self.assertEqual(model["gis_layer_counts"]["existing_utilities"], 1)
        self.assertIn("survey_points", model["canonical_targets"])
        self.assertIn("terrain_surface_metadata", model["canonical_targets"])
        self.assertIn("gis_layers", model["canonical_targets"])
        self.assertFalse(validation["production_usable"])
        self.assertEqual(
            {item["field"] for item in validation["blockers"]},
            {"survey_benchmark", "survey_datum", "survey_control_verified"},
        )

    def _build_dxf_benchmark(self, path: Path) -> Dict[str, Any]:
        classification = classify_existing_conditions_file(path)
        if not classification["supported"]:
            return dependency_blocked_existing_conditions_import(path, classification)
        import ezdxf

        doc = ezdxf.new()
        msp = doc.modelspace()
        msp.add_point((5000.0, 10000.0, 612.42), dxfattribs={"layer": "SURVEY_POINTS"})
        msp.add_point((5125.0, 10000.0, 611.95), dxfattribs={"layer": "SURVEY_POINTS"})
        msp.add_point((5000.0, 10150.0, 610.88), dxfattribs={"layer": "SURVEY_POINTS"})
        msp.add_lwpolyline(
            [(5000.0, 10000.0), (5125.0, 10000.0), (5125.0, 10150.0)],
            dxfattribs={"layer": "BREAKLINE_EDGE", "elevation": 611.0},
        )
        msp.add_lwpolyline(
            [(5000.0, 9990.0), (5200.0, 9990.0)],
            dxfattribs={"layer": "EXISTING_WATER_UTILITY"},
        )
        doc.saveas(path)
        return import_dxf_existing_conditions(path, coordinate_system=CONTROL_CRS)

    def _build_optional_geotiff_benchmark(self, path: Path) -> Dict[str, Any]:
        classification = classify_existing_conditions_file(path)
        if not classification["supported"]:
            return dependency_blocked_existing_conditions_import(path, classification)
        import numpy as np
        import rasterio
        from rasterio.transform import from_origin

        data = np.array([[612.4, 612.0], [611.0, 610.4]], dtype="float32")
        with rasterio.open(
            path,
            "w",
            driver="GTiff",
            height=2,
            width=2,
            count=1,
            dtype="float32",
            crs="EPSG:2276",
            transform=from_origin(5000.0, 10150.0, 75.0, 75.0),
        ) as dataset:
            dataset.write(data, 1)
        return import_geotiff_surface(path, coordinate_system=CONTROL_CRS)

    def _build_optional_las_benchmark(self, path: Path) -> Dict[str, Any]:
        classification = classify_existing_conditions_file(path)
        if not classification["supported"]:
            return dependency_blocked_existing_conditions_import(path, classification)
        import laspy
        import numpy as np

        header = laspy.LasHeader(point_format=3, version="1.2")
        las = laspy.LasData(header)
        las.x = np.array([5000.0, 5125.0, 5000.0, 5125.0])
        las.y = np.array([10000.0, 10000.0, 10150.0, 10150.0])
        las.z = np.array([612.4, 612.0, 611.0, 610.4])
        las.write(path)
        return import_las_point_cloud(path, coordinate_system=CONTROL_CRS)


if __name__ == "__main__":
    unittest.main()
