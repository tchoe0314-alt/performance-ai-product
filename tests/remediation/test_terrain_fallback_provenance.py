from backend.planning import grading_support as grading


def test_unavailable_terrain_retains_explicit_inferred_provenance(monkeypatch):
    monkeypatch.setattr(grading, "build_terrain_surface", lambda **kwargs: None)
    surface = grading.build_existing_surface({"lot": {"x":0,"y":0,"w":10,"h":10},
        "meta": {"site_inputs": {"address":"Synthetic address", "geocode":{"lat":40,"lng":-100}}}},
        infer_surface_profile=lambda _: {"downhill_dx":1,"downhill_dy":0,"slope_ratio":0.02},
        normalize_vector=lambda x,y:(1,0))
    profile = surface._inferred_profile
    assert profile["terrain_attempted"] is True
    assert profile["terrain_unavailable"] is True
    assert profile["terrain_used"] is False
    assert profile["source_quality"] == "address_context"
    assert "Terrain unavailable or incomplete" in profile["source_detail"]
    assert "Not surveyed elevations" in profile["source_detail"]
