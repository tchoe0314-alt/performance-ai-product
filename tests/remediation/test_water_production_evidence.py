from backend.planning.production_depth import enrich_water_production_depth


def segment(start,end,name):
    return {"name":name,"system_type":"water","start_node":start,"end_node":end,
        "route_points":[[0,0],[100,0]],"diameter_in":2,"flow_gpm":75,
        "material":"synthetic","source":"synthetic"}


def test_zero_source_pressure_cannot_be_replaced_by_positive_fallback():
    result=enrich_water_production_depth({"source_pressure_psi":0,"available_pressure_psi":72,
        "source_node":"SRC","conflict_hooks":{"utility_system_type":"water",
        "utility_segments":[segment("SRC","A","pipe")]}})
    assert result["pressure_validation"]["source_pressure_psi"] == 0
    assert result["pressure_validation"]["valid"] is False


def test_unsupported_loop_has_unknown_not_zero_computed_pressure():
    result=enrich_water_production_depth({"source_pressure_psi":72,"source_node":"SRC",
        "conflict_hooks":{"utility_system_type":"water","utility_segments":[
            segment("SRC","A","one"),segment("A","SRC","two")]}})
    pressure=result["pressure_validation"]
    assert pressure["valid"] is False
    assert pressure["pressure_graph"]["success"] is False
    assert pressure["min_pressure_psi"] is None
    assert pressure["residual_pressure_margin_psi"] is None
