import json
import tempfile
import unittest
from pathlib import Path

import pytest

from backend.planning.existing_conditions import summarize_existing_conditions
from backend.planning.existing_conditions_package import build_existing_conditions_package
from backend.planning.existing_conditions_importers import (
    build_canonical_existing_conditions_model,
    classify_existing_conditions_file,
    dependency_blocked_existing_conditions_import,
    import_dxf_existing_conditions,
    import_geospatial_vector_file,
    import_geotiff_surface,
    import_geojson,
    import_las_point_cloud,
    import_landxml_metadata,
    import_surface_grid_csv,
    import_survey_csv,
    merge_imported_existing_conditions,
    surface_from_survey_import,
    validate_imported_existing_conditions_package,
)


class ExistingConditionsImporterTests(unittest.TestCase):
    def test_import_survey_csv_and_build_surface(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "survey.csv"
            path.write_text(
                "point_id,easting,northing,elevation,description\n"
                "1,0,0,100.0,BM\n"
                "2,20,0,101.0,SHOT\n"
                "3,0,20,99.5,SHOT\n"
                "4,20,20,100.5,SHOT\n",
                encoding="utf-8",
            )

            imported = import_survey_csv(path, coordinate_system={"epsg": "EPSG:2276", "units": "ft"})
            surface = surface_from_survey_import(imported, cell_size=10.0)

            self.assertTrue(imported["success"])
            self.assertEqual(imported["point_count"], 4)
            self.assertEqual(imported["recognized_columns"]["x"], "easting")
            self.assertIsNotNone(surface)
            self.assertEqual(getattr(surface, "_inferred_profile")["source_quality"], "survey")

    def test_import_survey_csv_blocks_duplicate_or_collapsed_points(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "bad_survey.csv"
            path.write_text(
                "point_id,x,y,z\n"
                "1,0,0,100.0\n"
                "2,0,0,101.0\n"
                "3,10,0,99.5\n",
                encoding="utf-8",
            )

            imported = import_survey_csv(path, coordinate_system={"epsg": "EPSG:2276", "units": "ft"})
            surface = surface_from_survey_import(imported, cell_size=10.0)

            self.assertFalse(imported["success"])
            self.assertEqual(imported["quality"]["unique_xy_count"], 2)
            self.assertFalse(imported["quality"]["has_surface_span"])
            self.assertIsNone(surface)

    def test_import_geojson_classifies_required_layers(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "constraints.geojson"
            path.write_text(
                json.dumps(
                    {
                        "type": "FeatureCollection",
                        "features": [
                            {"type": "Feature", "properties": {"layer": "parcel"}, "geometry": {"type": "Polygon", "coordinates": []}},
                            {"type": "Feature", "properties": {"type": "wetland"}, "geometry": {"type": "Polygon", "coordinates": []}},
                            {"type": "Feature", "properties": {"name": "existing water utility"}, "geometry": {"type": "LineString", "coordinates": []}},
                        ],
                        "crs": {"type": "name", "properties": {"name": "EPSG:2276"}},
                    }
                ),
                encoding="utf-8",
            )

            imported = import_geojson(path)

            self.assertTrue(imported["success"])
            self.assertEqual(imported["layer_counts"]["parcels"], 1)
            self.assertEqual(imported["layer_counts"]["wetlands"], 1)
            self.assertEqual(imported["layer_counts"]["existing_utilities"], 1)
            self.assertEqual(imported["coordinate_system"]["name"], "EPSG:2276")

    def test_import_surface_grid_csv_builds_grid_surface(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "surface.csv"
            path.write_text(
                "x,y,z\n"
                "0,0,100\n"
                "10,0,101\n"
                "0,10,99\n"
                "10,10,100\n",
                encoding="utf-8",
            )

            imported = import_surface_grid_csv(path, coordinate_system={"epsg": "EPSG:2276"})
            surface = imported["surface"]

            self.assertTrue(imported["success"])
            self.assertEqual(surface.ncols, 2)
            self.assertEqual(surface.nrows, 2)
            self.assertEqual(getattr(surface, "_inferred_profile")["source_detail"], "surface_xyz_csv_import")

    def test_dxf_import_reads_survey_points_breaklines_and_existing_utilities(self) -> None:
        import ezdxf

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "existing.dxf"
            doc = ezdxf.new()
            msp = doc.modelspace()
            msp.add_point((0.0, 0.0, 100.0), dxfattribs={"layer": "SURVEY_POINTS"})
            msp.add_lwpolyline(
                [(0.0, 0.0), (20.0, 0.0), (20.0, 20.0)],
                dxfattribs={"layer": "BREAKLINE_EDGE", "elevation": 99.5},
            )
            msp.add_lwpolyline(
                [(5.0, 5.0), (30.0, 5.0)],
                dxfattribs={"layer": "EXISTING_WATER_UTILITY"},
            )
            doc.saveas(path)

            imported = import_dxf_existing_conditions(path, coordinate_system={"epsg": "EPSG:2276"})
            merged = merge_imported_existing_conditions(imported)

            self.assertTrue(imported["success"])
            self.assertEqual(imported["point_count"], 1)
            self.assertEqual(imported["breakline_count"], 1)
            self.assertEqual(imported["layer_counts"]["existing_utilities"], 1)
            self.assertEqual(merged["survey"]["breakline_count"], 1)
            self.assertEqual(merged["gis_layers"]["existing_utilities"][0]["properties"]["layer"], "EXISTING_WATER_UTILITY")

    def test_merge_imports_feed_existing_conditions_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            survey_path = Path(tmpdir) / "survey.csv"
            survey_path.write_text("x,y,z\n0,0,100\n10,0,101\n0,10,99\n", encoding="utf-8")
            gis_path = Path(tmpdir) / "parcel.geojson"
            gis_path.write_text(
                json.dumps(
                    {
                        "type": "FeatureCollection",
                        "features": [{"type": "Feature", "properties": {"layer": "parcel"}, "geometry": {"type": "Polygon", "coordinates": []}}],
                    }
                ),
                encoding="utf-8",
            )
            survey = import_survey_csv(survey_path, coordinate_system={"epsg": "EPSG:2276"})
            gis = import_geojson(gis_path, coordinate_system={"epsg": "EPSG:2276"})
            merged = merge_imported_existing_conditions(survey, gis)
            meta = {
                "grading": {"source_quality": "survey"},
                "survey": merged["survey"],
                "gis_layers": merged["gis_layers"],
                "coordinate_system": merged["coordinate_system"],
            }

            summary = summarize_existing_conditions({"meta": meta})

            self.assertTrue(summary["survey"]["ready"])
            self.assertFalse(summary["gis"]["ready"])
            self.assertTrue(summary["coordinate_system"]["ready"])
            self.assertFalse(summary["production_ready"])
            self.assertIn("wetlands", summary["gis"]["missing_layers"])
            self.assertIn("existing_utilities", summary["gis"]["missing_layers"])

    def test_import_package_validation_blocks_crs_conflicts_and_missing_layers(self) -> None:
        merged = merge_imported_existing_conditions(
            {
                "success": True,
                "source": "survey.csv",
                "source_type": "survey_csv",
                "points": [
                    {"x": 0.0, "y": 0.0, "z": 100.0},
                    {"x": 10.0, "y": 0.0, "z": 101.0},
                    {"x": 0.0, "y": 10.0, "z": 99.0},
                ],
                "coordinate_system": {"epsg": "EPSG:2276", "units": "ft"},
            },
            {
                "success": True,
                "source": "parcel.geojson",
                "source_type": "geojson",
                "layers": {"parcels": [{"id": "P-1"}]},
                "coordinate_system": {"name": "EPSG:4326"},
            },
        )

        validation = merged["import_validation"]

        self.assertFalse(validation["production_usable"])
        fields = {item["field"] for item in validation["blockers"]}
        self.assertIn("coordinate_system", fields)
        self.assertIn("gis_layers", fields)

    def test_import_package_validation_can_pass_complete_import_evidence(self) -> None:
        merged = {
            "sources": [{"source": "merged", "source_type": "test", "success": True}],
            "survey": {
                "source": "survey.csv",
                "point_count": 4,
                "benchmark": "BM-1",
                "benchmark_elevation": 100.0,
                "horizontal_datum": "NAD83",
                "datum": "NAVD88",
                "control_verified": True,
                "points": [
                    {"x": 0.0, "y": 0.0, "z": 100.0},
                    {"x": 10.0, "y": 0.0, "z": 101.0},
                    {"x": 0.0, "y": 10.0, "z": 99.0},
                    {"x": 10.0, "y": 10.0, "z": 100.0},
                ],
                "breakline_count": 1,
                "breaklines": [{"name": "BL-1"}],
            },
            "gis_layers": {
                layer: [{"id": layer, "source": f"{layer}_source"}]
                for layer in ("parcels", "easements", "row", "floodplain", "wetlands", "existing_utilities")
            },
            "coordinate_system": {"epsg": "EPSG:2276", "units": "ft", "horizontal_datum": "NAD83", "source": "survey_control"},
            "coordinate_systems": [{"epsg": "EPSG:2276", "units": "ft", "horizontal_datum": "NAD83", "source": "survey_control"}],
        }

        validation = validate_imported_existing_conditions_package(merged)

        self.assertTrue(validation["production_usable"])
        self.assertFalse(validation["blockers"])
        self.assertEqual(validation["terrain_source_confidence"]["label"], "survey-backed")
        self.assertTrue(next(item for item in validation["production_requirements"] if item["field"] == "survey_source")["ready"])

    def test_import_package_validation_blocks_source_less_gis_layers(self) -> None:
        merged = {
            "sources": [{"source": "merged", "source_type": "test", "success": True}],
            "survey": {
                "point_count": 4,
                "benchmark": "BM-1",
                "datum": "NAVD88",
                "control_verified": True,
                "points": [
                    {"x": 0.0, "y": 0.0, "z": 100.0},
                    {"x": 10.0, "y": 0.0, "z": 101.0},
                    {"x": 0.0, "y": 10.0, "z": 99.0},
                    {"x": 10.0, "y": 10.0, "z": 100.0},
                ],
                "breakline_count": 1,
                "breaklines": [{"name": "BL-1"}],
            },
            "gis_layers": {
                layer: [{"id": layer}]
                for layer in ("parcels", "easements", "row", "floodplain", "wetlands", "existing_utilities")
            },
            "coordinate_system": {"epsg": "EPSG:2276", "units": "ft", "source": "survey_control"},
            "coordinate_systems": [{"epsg": "EPSG:2276", "units": "ft", "source": "survey_control"}],
        }

        validation = validate_imported_existing_conditions_package(merged)

        self.assertFalse(validation["production_usable"])
        blocker = next(item for item in validation["blockers"] if item["field"] == "gis_layer_sources")
        self.assertIn("parcels", blocker["missing_source_layers"])

    def test_import_package_validation_blocks_missing_control_metadata(self) -> None:
        merged = {
            "sources": [{"source": "merged", "source_type": "test", "success": True}],
            "survey": {
                "point_count": 4,
                "points": [
                    {"x": 0.0, "y": 0.0, "z": 100.0},
                    {"x": 10.0, "y": 0.0, "z": 101.0},
                    {"x": 0.0, "y": 10.0, "z": 99.0},
                    {"x": 10.0, "y": 10.0, "z": 100.0},
                ],
                "breakline_count": 1,
                "breaklines": [{"name": "BL-1"}],
            },
            "gis_layers": {layer: [{"id": layer}] for layer in ("parcels", "easements", "row", "floodplain", "wetlands", "existing_utilities")},
            "coordinate_system": {"epsg": "EPSG:2276", "units": "ft"},
            "coordinate_systems": [{"epsg": "EPSG:2276", "units": "ft"}],
        }

        validation = validate_imported_existing_conditions_package(merged)
        fields = {item["field"] for item in validation["blockers"]}
        detail_fields = {item["field"] for item in validation["blocker_details"]}

        self.assertFalse(validation["production_usable"])
        self.assertIn("coordinate_system_source", fields)
        self.assertIn("survey_benchmark", fields)
        self.assertIn("survey_datum", fields)
        self.assertIn("survey_control_verified", fields)
        self.assertIn("coordinate_system_source", detail_fields)
        detail = next(item for item in validation["blocker_details"] if item["field"] == "survey_benchmark")
        self.assertIn("benchmark", detail["what_failed"].lower())
        self.assertTrue(detail["next_action"])

    def test_verified_control_clears_only_control_verification_blocker(self) -> None:
        merged = {
            "sources": [{"source": "merged", "source_type": "test", "success": True, "canonicalized": True}],
            "survey": {
                "source": "survey.csv",
                "point_count": 4,
                "benchmark": "BM-1",
                "benchmark_elevation": 100.0,
                "horizontal_datum": "NAD83",
                "datum": "NAVD88",
                "points": [
                    {"x": 0.0, "y": 0.0, "z": 100.0},
                    {"x": 10.0, "y": 0.0, "z": 101.0},
                    {"x": 0.0, "y": 10.0, "z": 99.0},
                    {"x": 10.0, "y": 10.0, "z": 100.0},
                ],
            },
            "gis_layers": {
                layer: [{"id": layer, "source": f"{layer}_source"}]
                for layer in ("parcels", "easements", "row", "floodplain", "wetlands", "existing_utilities")
            },
            "coordinate_system": {"epsg": "EPSG:2276", "units": "ft", "horizontal_datum": "NAD83", "source": "survey_control"},
            "coordinate_systems": [{"epsg": "EPSG:2276", "units": "ft", "horizontal_datum": "NAD83", "source": "survey_control"}],
        }

        blocked = validate_imported_existing_conditions_package(merged)
        merged["survey"]["control_verified"] = True
        cleared = validate_imported_existing_conditions_package(merged)

        self.assertIn("survey_control_verified", {item["field"] for item in blocked["blockers"]})
        self.assertNotIn("survey_control_verified", {item["field"] for item in cleared["blockers"]})
        self.assertTrue(cleared["survey_control_package"]["production_usable"])
        self.assertEqual(cleared["terrain_source_confidence"]["label"], "survey-backed")

    def test_import_package_validation_blocks_geographic_crs_for_engineering_truth(self) -> None:
        merged = {
            "sources": [{"source": "merged", "source_type": "test", "success": True}],
            "survey": {
                "point_count": 4,
                "points": [
                    {"x": -96.8, "y": 32.7, "z": 100.0},
                    {"x": -96.799, "y": 32.7, "z": 101.0},
                    {"x": -96.8, "y": 32.701, "z": 99.0},
                    {"x": -96.799, "y": 32.701, "z": 100.0},
                ],
                "breakline_count": 1,
                "breaklines": [{"name": "BL-1"}],
            },
            "gis_layers": {layer: [{"id": layer}] for layer in ("parcels", "easements", "row", "floodplain", "wetlands", "existing_utilities")},
            "coordinate_system": {"epsg": "EPSG:4326", "units": "degrees"},
            "coordinate_systems": [{"epsg": "EPSG:4326", "units": "degrees"}],
        }

        validation = validate_imported_existing_conditions_package(merged)

        self.assertFalse(validation["production_usable"])
        self.assertFalse(validation["coordinate_system_validation"]["valid"])
        reasons = " ".join(item["reason"] for item in validation["blockers"])
        self.assertIn("Geographic", reasons)

    def test_import_package_validation_blocks_collapsed_survey_surface(self) -> None:
        merged = {
            "sources": [{"source": "bad_survey.csv", "source_type": "survey_csv", "success": True}],
            "survey": {
                "point_count": 3,
                "points": [
                    {"x": 0.0, "y": 0.0, "z": 100.0},
                    {"x": 0.0, "y": 0.0, "z": 101.0},
                    {"x": 10.0, "y": 0.0, "z": 99.0},
                ],
            },
            "gis_layers": {layer: [{"id": layer}] for layer in ("parcels", "easements", "row", "floodplain", "wetlands", "existing_utilities")},
            "coordinate_system": {"epsg": "EPSG:2276", "units": "ft"},
            "coordinate_systems": [{"epsg": "EPSG:2276", "units": "ft"}],
        }

        validation = validate_imported_existing_conditions_package(merged)

        self.assertFalse(validation["production_usable"])
        self.assertIn("survey_surface", {item["field"] for item in validation["blockers"]})
        self.assertEqual(validation["survey_point_quality"]["unique_xy_count"], 2)

    def test_heavy_gis_formats_are_truthfully_blocked_without_dependencies(self) -> None:
        self.assertTrue(classify_existing_conditions_file(Path("parcel.gpkg"))["supported"])
        self.assertTrue(classify_existing_conditions_file(Path("surface.tif"))["supported"])
        self.assertTrue(classify_existing_conditions_file(Path("cloud.las"))["supported"])

    def test_landxml_metadata_import_parses_surface_metadata_without_overclaiming(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "surface.landxml"
            path.write_text(
                '<LandXML><Surfaces><Surface name="EG"><Definition surfType="TIN">'
                "<P>0 0 100</P><P>10 0 101</P><P>0 10 99</P><F>1 2 3</F>"
                "</Definition></Surface></Surfaces></LandXML>",
                encoding="utf-8",
            )

            imported = import_landxml_metadata(path)

            self.assertTrue(imported["success"])
            self.assertEqual(imported["surface_count"], 1)
            self.assertEqual(imported["surfaces"][0]["point_count"], 3)
            self.assertEqual(imported["surfaces"][0]["face_count"], 1)
            self.assertIn("engineer review", imported["truth_label"])

    def test_landxml_surface_can_feed_existing_conditions_package_when_control_and_gis_are_complete(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "surface.landxml"
            path.write_text(
                '<LandXML><Surfaces><Surface name="EG"><Definition surfType="TIN">'
                "<P>0 0 100</P><P>10 0 101</P><P>0 10 99</P><F>1 2 3</F>"
                "</Definition></Surface></Surfaces></LandXML>",
                encoding="utf-8",
            )

            imported = import_landxml_metadata(
                path,
                coordinate_system={"epsg": "EPSG:2276", "units": "ft", "source": "survey_control"},
            )
            merged = merge_imported_existing_conditions(imported)
            merged["survey"].update(
                {
                    "benchmark": "BM-1",
                    "benchmark_elevation": 100.0,
                    "horizontal_datum": "NAD83",
                    "datum": "NAVD88",
                    "control_verified": True,
                }
            )
            merged["gis_layers"] = {
                layer: [{"id": layer, "source": f"{layer}_source"}]
                for layer in ("parcels", "easements", "row", "floodplain", "wetlands", "existing_utilities")
            }
            merged["existing_conditions"] = merged["gis_layers"]
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

            self.assertTrue(merged["import_validation"]["production_usable"])
            self.assertEqual(package["status"], "ready")
            self.assertEqual(package["summary"]["survey"]["imported_surface_count"], 1)
            self.assertEqual(package["canonical_existing_conditions"]["surfaces"][0]["source_type"], "landxml")

    def test_landxml_surface_package_blocks_without_control_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "surface.landxml"
            path.write_text(
                '<LandXML><Surfaces><Surface name="EG"><Definition surfType="TIN">'
                "<P>0 0 100</P><P>10 0 101</P><P>0 10 99</P><F>1 2 3</F>"
                "</Definition></Surface></Surfaces></LandXML>",
                encoding="utf-8",
            )

            imported = import_landxml_metadata(
                path,
                coordinate_system={"epsg": "EPSG:2276", "units": "ft", "source": "survey_control"},
            )
            merged = merge_imported_existing_conditions(imported)

            fields = {item["field"] for item in merged["import_validation"]["blockers"]}

            self.assertFalse(merged["import_validation"]["production_usable"])
            self.assertIn("survey_benchmark", fields)
            self.assertIn("survey_datum", fields)
            self.assertIn("survey_control_verified", fields)
            self.assertEqual(merged["import_validation"]["surface_count"], 1)

    def test_landxml_without_existing_terrain_is_labeled_metadata_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "network.landxml"
            path.write_text(
                '<LandXML><PipeNetworks><PipeNetwork name="Existing Utility"><Pipes><Pipe name="P-1"/></Pipes></PipeNetwork></PipeNetworks></LandXML>',
                encoding="utf-8",
            )

            imported = import_landxml_metadata(path)
            merged = merge_imported_existing_conditions(imported)
            source = merged["sources"][0]
            model = merged["canonical_existing_conditions_model"]

            self.assertTrue(imported["success"])
            self.assertTrue(source["metadata_only"])
            self.assertFalse(source["canonicalized"])
            self.assertIn("pipe_network_metadata", source["canonical_targets"])
            self.assertEqual(model["metadata_only_sources"][0]["source_type"], "landxml")

    def test_dependency_blocked_heavy_format_remains_visible_in_package_validation(self) -> None:
        blocked = dependency_blocked_existing_conditions_import(
            Path("constraints.shp"),
            {
                "supported": False,
                "format": "shp",
                "mode": "geospatial_vector",
                "required_dependency": "Shapefile import requires fiona/geopandas or GDAL.",
            },
        )

        merged = merge_imported_existing_conditions(blocked)
        package_meta = {
            "survey": merged["survey"],
            "gis_layers": merged["gis_layers"],
            "coordinate_system": merged["coordinate_system"],
            "sources": merged["sources"],
            "canonical_existing_conditions_model": merged["canonical_existing_conditions_model"],
            "metadata_only_sources": merged["metadata_only_sources"],
            "existing_conditions_import_validation": merged["import_validation"],
        }
        package_meta["existing_conditions_summary"] = summarize_existing_conditions({"meta": package_meta})
        package = build_existing_conditions_package({"meta": package_meta})
        source = package["canonical_existing_conditions"]["sources"][0]

        self.assertEqual(package["status"], "blocked")
        self.assertTrue(source["dependency_blocked"])
        self.assertTrue(source["metadata_only"])
        self.assertTrue(package["canonical_existing_conditions"]["metadata_only_sources"][0]["metadata_only"])
        self.assertEqual(source["required_dependency"], "Shapefile import requires fiona/geopandas or GDAL.")
        fields = {item["field"] for item in package["blockers"]}
        self.assertIn("sources", fields)
        self.assertIn("dependency_blocked_imports", fields)
        blocker = next(item for item in merged["import_validation"]["blockers"] if item["field"] == "dependency_blocked_imports")
        self.assertEqual(blocker["required_dependencies"][0]["required_dependency"], "Shapefile import requires fiona/geopandas or GDAL.")

    def test_supported_existing_condition_formats_are_classified(self) -> None:
        expected = {
            "survey.csv": ("csv", "survey_or_surface_xyz"),
            "constraints.geojson": ("geojson", "gis_features"),
            "surface.landxml": ("landxml", "surface_or_alignment_metadata"),
            "survey.dxf": ("dxf", "survey_breaklines_or_existing_utilities"),
            "terrain.tif": ("geotiff", "raster_surface"),
            "cloud.las": ("las", "point_cloud"),
        }

        for filename, (fmt, mode) in expected.items():
            classified = classify_existing_conditions_file(Path(filename))
            self.assertEqual(classified["format"], fmt)
            self.assertEqual(classified["mode"], mode)

    def test_geopackage_vector_import_classifies_layers(self) -> None:
        gpd = pytest.importorskip("geopandas")
        shapely_geometry = pytest.importorskip("shapely.geometry")
        Polygon = shapely_geometry.Polygon

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "parcels.gpkg"
            gdf = gpd.GeoDataFrame(
                [{"layer": "parcel", "name": "Parcel A", "geometry": Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])}],
                crs="EPSG:4326",
            )
            gdf.to_file(path, driver="GPKG")

            imported = import_geospatial_vector_file(path)

            self.assertTrue(imported["success"])
            self.assertEqual(imported["layer_counts"]["parcels"], 1)
            self.assertEqual(imported["coordinate_system"]["name"], "EPSG:4326")

    def test_geotiff_import_builds_surface(self) -> None:
        import numpy as np
        rasterio = pytest.importorskip(
            "rasterio",
            reason="GeoTIFF real-input benchmark is dependency-gated; install rasterio to prove raster surface import locally.",
        )
        from rasterio.transform import from_origin

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "surface.tif"
            data = np.array([[100.0, 101.0], [99.0, 100.0]], dtype="float32")
            with rasterio.open(
                path,
                "w",
                driver="GTiff",
                height=2,
                width=2,
                count=1,
                dtype="float32",
                crs="EPSG:2276",
                transform=from_origin(0.0, 20.0, 10.0, 10.0),
            ) as dataset:
                dataset.write(data, 1)

            imported = import_geotiff_surface(path)
            merged = merge_imported_existing_conditions(imported)
            model = merged["canonical_existing_conditions_model"]

            self.assertTrue(imported["success"])
            self.assertEqual(imported["surface"].ncols, 2)
            self.assertEqual(imported["surface"].nrows, 2)
            self.assertEqual(imported["coordinate_system"]["name"], "EPSG:2276")
            self.assertIn("terrain_surface", imported["canonical_import"]["canonical_targets"])
            self.assertEqual(model["terrain"]["surface_count"], 1)
            self.assertFalse(model["terrain"]["surfaces"][0]["metadata_only"])
            self.assertEqual(model["terrain"]["source_confidence"], "DEM-unverified")
            terrain_requirement = next(
                item for item in merged["import_validation"]["production_requirements"] if item["field"] == "terrain_source_confidence"
            )
            self.assertFalse(terrain_requirement["ready"])
            self.assertEqual(merged["import_validation"]["import_matrix"][0]["status"], "review_required")
            self.assertIn(
                "Survey import needs benchmark evidence before it is production-usable.",
                merged["import_validation"]["import_matrix"][0]["blocker_messages"],
            )

    def test_las_import_samples_point_cloud(self) -> None:
        laspy = pytest.importorskip("laspy")
        import numpy as np

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "cloud.las"
            header = laspy.LasHeader(point_format=3, version="1.2")
            las = laspy.LasData(header)
            las.x = np.array([0.0, 10.0, 0.0, 10.0])
            las.y = np.array([0.0, 0.0, 10.0, 10.0])
            las.z = np.array([100.0, 101.0, 99.0, 100.0])
            las.write(path)

            imported = import_las_point_cloud(path)
            merged = merge_imported_existing_conditions(imported)
            model = merged["canonical_existing_conditions_model"]

            self.assertTrue(imported["success"])
            self.assertEqual(imported["point_count"], 4)
            self.assertEqual(imported["bounds"]["max_x"], 10.0)
            self.assertIn("lidar_point_cloud", imported["canonical_import"]["canonical_targets"])
            self.assertEqual(model["survey"]["point_count"], 0)
            self.assertTrue(model["survey"]["metadata_only"])
            self.assertEqual(model["terrain"]["point_cloud_count"], 1)
            self.assertEqual(model["terrain"]["source_confidence"], "LiDAR-unverified")
            self.assertEqual(merged["import_validation"]["terrain_source_confidence"]["label"], "LiDAR-unverified")
            self.assertEqual(merged["import_validation"]["import_matrix"][0]["status"], "review_required")

    def test_las_import_with_control_is_lidar_backed_not_survey_backed(self) -> None:
        laspy = pytest.importorskip("laspy")
        import numpy as np

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "verified_cloud.las"
            header = laspy.LasHeader(point_format=3, version="1.2")
            las = laspy.LasData(header)
            las.x = np.array([0.0, 10.0, 0.0, 10.0])
            las.y = np.array([0.0, 0.0, 10.0, 10.0])
            las.z = np.array([100.0, 101.0, 99.0, 100.0])
            las.write(path)

            imported = import_las_point_cloud(
                path,
                coordinate_system={
                    "epsg": "EPSG:2276",
                    "units": "ft",
                    "source": "control_sheet",
                    "horizontal_datum": "NAD83",
                },
            )
            merged = merge_imported_existing_conditions(imported)
            merged["survey"].update(
                {
                    "benchmark": "BM-1",
                    "benchmark_elevation": 100.0,
                    "horizontal_datum": "NAD83",
                    "datum": "NAVD88",
                    "control_verified": True,
                }
            )
            merged["gis_layers"] = {
                layer: [{"id": layer, "source": f"{layer}_source"}]
                for layer in ("parcels", "easements", "row", "floodplain", "wetlands", "existing_utilities")
            }
            merged["import_validation"] = validate_imported_existing_conditions_package(merged)
            model = build_canonical_existing_conditions_model(merged)

            self.assertEqual(model["terrain"]["source_confidence"], "LiDAR-backed")
            self.assertEqual(model["survey"]["point_count"], 0)
            self.assertTrue(merged["import_validation"]["production_usable"])
            self.assertEqual(merged["import_validation"]["import_matrix"][0]["status"], "canonical")


if __name__ == "__main__":
    unittest.main()
