from copy import deepcopy
import pytest

from backend.services.canonical_canvas import with_canvas_snapshot
from backend.services.canonical_results import (
    ENGINE_REVISION, bind_canvas_result, canvas_result_freshness,
)


@pytest.mark.parametrize("old_revision", [f"engineering_core_2026_10_v{version}" for version in range(2, 11)])
def test_old_terrain_method_is_unverified_despite_matching_geometry(old_revision):
    inputs=with_canvas_snapshot({"manual_fields":{"units":"ft","site_objects":[
        {"id":"building","type":"office_building","x":0,"y":0,"w":10,"d":10}]}})
    old={"success":True,"metadata":{"calculation_engine_revision":old_revision},
        "final_plan":{"meta":{"calculation_engine_revision":old_revision}}}
    before=deepcopy(old)
    bound=bind_canvas_result(old,inputs)
    assert old == before
    assert bound["metadata"]["calculation_engine_revision"] == old_revision
    assert canvas_result_freshness(bound,inputs)["status"] == "unverified"
    assert canvas_result_freshness(bound,inputs)["reason"] == "calculation_engine_revision_unknown_or_obsolete"
    # Only the execution boundary may identify a new result. This stamp is not
    # professional accuracy certification and must never be used for migration.
    new=bind_canvas_result({"success":True},inputs,calculation_executed=True)
    assert ENGINE_REVISION == "engineering_core_2026_10_v11"
    assert canvas_result_freshness(new,inputs)["status"] == "current"
