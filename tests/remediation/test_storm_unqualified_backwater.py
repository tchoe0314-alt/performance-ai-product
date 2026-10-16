from itertools import permutations
from backend.planning.production_depth import enrich_storm_production_depth


def test_branched_network_does_not_publish_unqualified_backwater_numbers():
    segments = [{"pipe": name, "from": start, "to": "OUT", "length_ft": 100,
        "path": [[x, 0], [100, 0]], "start_invert_ft": 100, "end_invert_ft": 99,
        "diameter_in": 12, "flow_cfs": 0.3, "slope_ft_ft": 0.01}
        for name, start, x in [("P1", "A", 0), ("P2", "B", 200)]]
    outcomes = []
    for order in permutations(segments):
        result = enrich_storm_production_depth({"segments": list(order),
            "target_outfall": {"name": "OUT", "z": 101}})
        validation = result["backwater_validation"]
        assert validation["valid"] is False
        assert "qualified_network_backwater_method" in validation["missing_inputs"]
        assert validation.get("profile", []) == []
        assert validation.get("surcharged_segments", []) == []
        assert "terminal_hgl_ft" not in validation
        assert "max_tailwater_surcharge_ft" not in validation
        outcomes.append(validation)
    assert outcomes[0] == outcomes[1]
