import json
import pytest
from backend.planning.existing_conditions_importers import import_geojson


@pytest.mark.parametrize("geometry", [
    {"type": "Polygon", "coordinates": "invalid"},
    {"type": "Polygon", "coordinates": []},
    {"type": "Point", "coordinates": [True, 1]},
    {"type": "Point", "coordinates": [float("nan"), 1]},
    {"type": [], "coordinates": [0, 0]},
    {"type": "LineString", "coordinates": [[0, 0]]},
    {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1]]]},
    None,
])
def test_invalid_geometry_cannot_become_a_successful_source(tmp_path, geometry):
    path = tmp_path / "parcel.geojson"
    path.write_text(json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {}, "geometry": geometry}]}))
    result = import_geojson(path)
    assert result["success"] is False
    assert not any(result["layers"].values())


def test_closed_polygon_preserves_coordinates_and_source(tmp_path):
    coordinates = [[[1000, 2000], [1100, 2000], [1100, 2050], [1000, 2000]]]
    path = tmp_path / "parcel.geojson"
    path.write_text(json.dumps({"type": "Feature", "properties": {},
        "geometry": {"type": "Polygon", "coordinates": coordinates}}))
    result = import_geojson(path)
    assert result["success"]
    assert result["layers"]["parcels"][0]["geometry"]["coordinates"] == coordinates
