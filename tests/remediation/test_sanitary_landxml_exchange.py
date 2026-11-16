import xml.etree.ElementTree as ET

import pytest

from backend.planning.infrastructure_stage_runners import _sanitary_exchange_snapshot
from backend.planning.landxml_exchange import build_landxml_exchange, verify_exchange


def sanitary_summary():
    return {
        "segments": [{"name": "SAN-MAIN-1", "route_points": [[0, 0], [100, 0], [100, 50]],
                      "length_ft": 150, "diameter_in": 8, "start_invert_ft": 95, "end_invert_ft": 92}],
        "manholes": [
            {"id": "SMH-1", "x": 0, "y": 0, "rim_elev_ft": 102},
            {"id": "SMH-2", "x": 100, "y": 0, "rim_elev_ft": 102},
            {"id": "SMH-3", "x": 100, "y": 50, "rim_elev_ft": 101},
        ],
    }


def test_sanitary_bend_splits_at_canonical_manhole_and_exports_exact_inverts():
    summary = sanitary_summary()
    summary["exchange_network_v1"] = _sanitary_exchange_snapshot(summary)
    snapshot = summary["exchange_network_v1"]
    assert [segment["length_ft"] for segment in snapshot["segments"]] == [100, 50]
    assert snapshot["segments"][0]["invert_end_ft"] == pytest.approx(93)
    by_name = {structure["name"]: structure for structure in snapshot["structures"]}
    assert by_name["SMH-2"]["sump_elevation_ft"] == pytest.approx(93)
    verified = verify_exchange(ET.fromstring(build_landxml_exchange({"units": "ft", "meta": {"sanitary": summary}})))
    assert verified["local_contract_verified"], verified
    assert (verified["pipe_count"], verified["structure_count"]) == (2, 3)


def test_sanitary_bend_without_canonical_manhole_is_blocked():
    summary = sanitary_summary()
    summary["manholes"].pop(1)
    with pytest.raises(ValueError, match="bend without a canonical manhole"):
        _sanitary_exchange_snapshot(summary)
