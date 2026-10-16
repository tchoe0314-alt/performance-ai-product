from copy import deepcopy
from backend.planning.production_depth import enrich_storm_production_depth


def source():
    return {"segments": [{"pipe": "P1", "from": "A", "to": "OUT",
        "path": [[0, 0], [100, 0]], "length_ft": 100,
        "start_invert_ft": 100, "end_invert_ft": 99,
        "diameter_in": 12, "flow_cfs": 0.3, "slope_ft_ft": 0.01}],
        "target_outfall": {"name": "OUT", "z": 99}}


def test_generated_profile_views_refresh_after_segment_elevation_change():
    old = enrich_storm_production_depth(source())
    changed = deepcopy(old)
    changed["segments"][0].update(start_invert_ft=110, end_invert_ft=109)
    before = deepcopy(changed)
    new = enrich_storm_production_depth(changed)
    for key in ("hgl_profile", "egl_profile"):
        assert new[key] == new["hydraulic_profile_evidence"][key]
        assert new[key] != old[key]
    assert changed == before


def test_generated_profile_views_clear_when_their_segments_are_removed():
    old = enrich_storm_production_depth(source())
    old["segments"] = []
    new = enrich_storm_production_depth(old)
    for key in ("hgl_profile", "egl_profile"):
        assert new.get(key, []) == []


def test_unrecognized_provided_profile_is_preserved_and_marked_unverified():
    inputs = source()
    inputs["hgl_profile"] = [{"station_ft": 0, "hgl_ft": 123, "source": "provided reference"}]
    new = enrich_storm_production_depth(inputs)
    assert new["hgl_profile"] == inputs["hgl_profile"]
    assert new["hydraulic_profile_views"]["hgl_profile"]["status"] == "provided_unverified"
    assert new["hydraulic_profile_evidence"]["hgl_profile"] != inputs["hgl_profile"]
