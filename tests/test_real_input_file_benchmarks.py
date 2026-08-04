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
    validate_imported_existing_conditions_package,
)
from backend.planning.existing_conditions_package import build_existing_conditions_package
from backend.planning.existing_conditions import summarize_existing_conditions


FIXTURE_DIR = Path(__file__).resolve().parents[1] / "backend" / "fixtures" / "real_input_benchmarks"
CONTROL_CRS = {"epsg": "EPSG:2276", "units": "ft", "horizontal_datum": "NAD83", "source": "benchmark survey control note"}


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
            geotiff_import = import_geotiff_surface(FIXTURE_DIR / "surface_grid.tif", coordinate_system=CONTROL_CRS)
            las_import = import_las_point_cloud(FIXTURE_DIR / "surface_points.las", coordinate_system=CONTROL_CRS)

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

        self.assertEqual(benchmark_rows["GeoTIFF/DEM"]["support"], "supported")
        self.assertEqual(benchmark_rows["GeoTIFF/DEM"]["canonical_vs_metadata"], "canonical")
        self.assertIn("terrain_surface", benchmark_rows["GeoTIFF/DEM"]["canonical_targets"])

        self.assertEqual(benchmark_rows["LAS/LiDAR"]["support"], "supported")
        self.assertEqual(benchmark_rows["LAS/LiDAR"]["canonical_vs_metadata"], "canonical")
        self.assertIn("lidar_point_cloud", benchmark_rows["LAS/LiDAR"]["canonical_targets"])

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
        registration = validation["source_registration_audit_v1"]
        self.assertEqual(registration["status"], "aligned")
        self.assertGreaterEqual(registration["registered_source_count"], 3)
        self.assertTrue(registration["comparisons"])
        self.assertFalse(registration["blockers"])
        self.assertFalse(validation["production_usable"])
        self.assertEqual(
            {item["field"] for item in validation["blockers"]},
            {"survey_benchmark", "survey_datum", "survey_benchmark_elevation", "survey_control_verified"},
        )

    def test_spatially_disjoint_sources_are_blocked_even_when_crs_matches(self) -> None:
        survey = import_survey_csv(FIXTURE_DIR / "survey_points.csv", coordinate_system=CONTROL_CRS)
        far_gis = {
            "success": True,
            "source": "far-away-parcel.geojson",
            "source_type": "geojson",
            "coordinate_system": CONTROL_CRS,
            "layers": {
                "parcels": [
                    {
                        "source": "fixture parcel",
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [
                                [
                                    [900000.0, 900000.0],
                                    [900200.0, 900000.0],
                                    [900200.0, 900200.0],
                                    [900000.0, 900200.0],
                                    [900000.0, 900000.0],
                                ]
                            ],
                        },
                    }
                ]
            },
        }

        merged = merge_imported_existing_conditions(survey, far_gis)
        validation = merged["import_validation"]
        registration = validation["source_registration_audit_v1"]

        self.assertEqual(registration["status"], "blocked")
        self.assertFalse(registration["production_usable"])
        self.assertEqual(registration["anchor_source_id"], "survey_points")
        self.assertIn("source_registration", {item["field"] for item in validation["blockers"]})
        mismatch = next(item for item in registration["comparisons"] if item["source_id"] == "gis:parcels")
        self.assertFalse(mismatch["aligned"])
        self.assertGreater(mismatch["gap"], mismatch["allowed_gap"])

    def test_real_input_benchmark_can_attach_survey_control_package_v1(self) -> None:
        survey = import_survey_csv(FIXTURE_DIR / "survey_points.csv", coordinate_system=CONTROL_CRS)
        geojson = import_geojson(FIXTURE_DIR / "constraints.geojson", coordinate_system=CONTROL_CRS)
        landxml = import_landxml_metadata(FIXTURE_DIR / "surface_pipe.landxml", coordinate_system=CONTROL_CRS)
        merged = merge_imported_existing_conditions(survey, geojson, landxml)
        merged["survey"].update(
            {
                "benchmark": "REAL-BM-1",
                "benchmark_elevation": 612.42,
                "horizontal_datum": "NAD83",
                "datum": "NAVD88",
                "control_verified": True,
                "survey_date": "2026-06-01",
                "surveyor": "Fixture Surveyor",
                "surveyor_license": "TX-00000",
            }
        )
        merged["import_validation"] = validate_imported_existing_conditions_package(merged)
        package_meta = {
            "survey": merged["survey"],
            "gis_layers": merged["gis_layers"],
            "coordinate_system": merged["coordinate_system"],
            "surfaces": merged["surfaces"],
            "sources": merged["sources"],
            "existing_conditions_import_validation": merged["import_validation"],
            "existing_conditions_package": {"acceptance": {"accepted": True, "accepted_by": "fixture"}},
        }
        package_meta["existing_conditions_summary"] = summarize_existing_conditions({"meta": package_meta})

        package = build_existing_conditions_package({"meta": package_meta})

        self.assertEqual(package["survey_control_package"]["version"], "survey_control_package_v1")
        self.assertTrue(package["survey_control_package"]["production_usable"])
        self.assertEqual(package["terrain_source_confidence"]["label"], "survey-backed")

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


if __name__ == "__main__":
    unittest.main()
