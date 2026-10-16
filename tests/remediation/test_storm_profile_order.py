from copy import deepcopy
from itertools import permutations
import pytest
from backend.planning.production_depth import enrich_storm_production_depth, _ordered_storm_chain


def test_chain_backwater_is_independent_of_serialized_segment_order():
    segments = []
    for name, start, end, x, z in [("P1", "A", "B", 0, 100), ("P2", "B", "OUT", 100, 99)]:
        segments.append({"pipe": name, "from": start, "to": end,
            "path": [[x, 0], [x + 100, 0]], "length_ft": 100,
            "start_invert_ft": z, "end_invert_ft": z - 1,
            "diameter_in": 12, "flow_cfs": 0.3, "slope_ft_ft": 0.01})
    source = {"segments": segments, "target_outfall": {"name": "OUT", "z": 99.5}}
    before = deepcopy(source)
    forward = enrich_storm_production_depth(source)
    reverse = enrich_storm_production_depth({**source, "segments": list(reversed(segments))})
    assert forward["backwater_validation"] == reverse["backwater_validation"]
    assert source == before


def test_chain_stationing_uses_connectivity_for_every_three_pipe_permutation():
    segments = [{"pipe": "P1", "from": "A", "to": "B"},
                {"pipe": "P2", "from": "B", "to": "C"},
                {"pipe": "P3", "from": "C", "to": "OUT"}]
    for ordering in permutations(segments):
        result, verified = _ordered_storm_chain(ordering)
        assert verified
        assert [item["pipe"] for item in result] == ["P1", "P2", "P3"]


@pytest.mark.parametrize("edges", [
    [("A", "B"), ("A", "C")],
    [("A", "C"), ("B", "C")],
    [("A", "B"), ("B", "A")],
    [("A", "B"), ("C", "D")],
    [("A", "A")], [("", "B")],
])
def test_non_chain_cannot_claim_continuous_profile_stationing(edges):
    _, verified = _ordered_storm_chain([{"from": a, "to": b} for a, b in edges])
    assert verified is False
