from copy import deepcopy
import math

from backend.planning.production_depth import enrich_water_production_depth


def test_water_enrichment_prefers_current_routed_geometry_over_derived_cache():
    old = {"name": "W1", "system_type": "water", "start_node": "SRC", "end_node": "A",
           "route_points": [[0, 0], [10, 0]], "length_ft": 10,
           "diameter_in": 8, "flow_gpm": 10}
    new = {**old, "route_points": [[0, 0], [20, 0]], "length_ft": 20}
    source = {"source_pressure_psi": 60, "source_node": "SRC",
              "water_segments": [old], "segments": [old],
              "conflict_hooks": {"utility_system_type": "water", "utility_segments": [new]}}
    before = deepcopy(source)
    result = enrich_water_production_depth(source)
    assert result["water_segments"][0]["length_ft"] == 20
    assert result["water_segments"][0]["route_points"] == [[0, 0], [20, 0]]
    assert source == before


def test_manual_plan_route_takeoffs_match_published_measurements():
    from planner import build_plan
    from tests.test_manual_mode_validation import _manual_payload
    plan = build_plan(_manual_payload())
    meta = plan["meta"]
    assert meta["quantities"]["success"], meta["quantities"]["message"]
    for stage, key, metric in (("storm_pipes", "segments", "pipe_length_ft"),
                               ("utilities", "conflict_hooks", "utility_length_ft")):
        summary = meta[stage]
        segments = summary[key] if key == "segments" else summary[key]["utility_segments"]
        expected = round(math.fsum(segment["length_ft"] for segment in segments), 3)
        assert summary["total_length_ft"] == expected
        assert meta["quantities"]["totals"][metric] == expected
