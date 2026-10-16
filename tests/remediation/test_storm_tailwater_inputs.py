import pytest
from backend.planning.production_depth import enrich_storm_production_depth


@pytest.mark.parametrize("elevation", [96.25, 0.0, -10.0])
def test_explicit_tailwater_and_its_source_are_not_replaced_by_outfall_z(elevation):
    source = {"tailwater_elev_ft": elevation, "tailwater_source": "reviewed river boundary",
              "target_outfall": {"name": "OUT", "z": 100.0}, "segments": []}
    result = enrich_storm_production_depth(source)
    assert result["tailwater_elev_ft"] == elevation
    assert result["tailwater_source"] == "reviewed river boundary"
    assert result["backwater_validation"]["tailwater_elev_ft"] == elevation
    assert source["tailwater_elev_ft"] == elevation


@pytest.mark.parametrize("elevation", [None, float("nan"), float("inf"), True, "invalid"])
def test_invalid_explicit_tailwater_cannot_silently_use_outfall_geometry(elevation):
    result = enrich_storm_production_depth({"tailwater_elev_ft": elevation,
        "target_outfall": {"name": "OUT", "z": 100.0}, "segments": []})
    assert result["backwater_validation"]["valid"] is False
    assert "tailwater_elev_ft" in result["backwater_validation"]["missing_inputs"]
    assert result.get("tailwater_elev_ft") is None


def test_legacy_outfall_fallback_is_identified_as_an_assumption():
    result = enrich_storm_production_depth({"target_outfall": {"name": "OUT", "z": 96.0}})
    assert result["tailwater_elev_ft"] == 96.0
    assert result["tailwater_input_validation"]["assumed_from_outfall"] is True
