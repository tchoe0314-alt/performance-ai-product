from copy import deepcopy
import pytest
from backend.services.dependency_graph import dependency_records, link_kind, validate_dependency_graph, validate_fixed_changes
from backend.services.canonical_project import ProjectDocumentError
from backend.services.canonical_canvas import with_canvas_snapshot, resolve_canvas_input
from backend.services.canonical_record import seal_record

def item(key, kind, meta=None):
    return {"id": key, "type": kind, "label": key, "x": 100 if key == "a" else 300, "y": 100, "w": 50, "d": 50, "meta": meta or {}}

PAIRS = [("road", "parking"), ("building", "parking"), ("building", "setback_zone"), ("road", "road"), ("road", "entrance"), ("basin", "open_space"), ("building", "utility_corridor")]

@pytest.mark.parametrize("kinds", PAIRS)
@pytest.mark.parametrize("policy", ["ask", "follow", "fixed", "independent"])
def test_all_relationship_types_persist_exactly(kinds, policy):
    a, b = item("a", kinds[0]), item("b", kinds[1], {"cul_de_sac_v1": {"version": 1}} if kinds == ("road", "road") else {})
    edge = {"id": "edge", "kind": link_kind(a, b), "target_id": "b", "policy": policy}
    a["meta"]["dependency_links_v1"] = [edge]
    value = with_canvas_snapshot({"manual_fields": {"units": "ft", "site_objects": [a, b]}})
    assert value["canonical_project_v1"]["dependencies"][0] == {"owner": "dependency_graph_v1", "source_id": "a", **edge, "review_only": True}
    assert resolve_canvas_input(value)["manual_fields"]["site_objects"][0]["meta"]["dependency_links_v1"] == [edge]

@pytest.mark.parametrize("fault", ["missing", "self", "duplicate", "type", "policy", "cycle", "drivers", "quantity"])
def test_corrupt_graph_rejected(fault):
    a, b, c = item("a", "driveway"), item("b", "driveway"), item("c", "parking")
    edge = {"id": "edge", "kind": "access_road", "target_id": "b", "policy": "ask"}
    a["meta"]["dependency_links_v1"] = [edge]
    if fault == "missing": edge["target_id"] = "missing"
    if fault == "self": edge["target_id"] = "a"
    if fault == "duplicate": a["meta"]["dependency_links_v1"].append(deepcopy(edge))
    if fault == "type": edge["kind"] = "utility_building"
    if fault == "policy": edge["policy"] = {"bad": True}
    if fault == "cycle": b["meta"]["dependency_links_v1"] = [{**edge, "id": "back", "target_id": "a"}]
    if fault == "drivers":
        edge.update(kind="road_parking", target_id="c")
        b["meta"]["dependency_links_v1"] = [{**edge, "id": "other"}]
    if fault == "quantity": a["meta"]["quantity_relationship_v1"] = []
    with pytest.raises(ProjectDocumentError): validate_dependency_graph([a, b, c])

def test_independent_edges_do_not_create_geometry_cycles_and_quantities_are_draft_only():
    a, b = item("a", "driveway"), item("b", "driveway")
    for source, target in [(a, b), (b, a)]:
        source["meta"]["dependency_links_v1"] = [{"id": source["id"], "kind": "access_road", "target_id": target["id"], "policy": "independent"}]
        source["meta"]["quantity_relationship_v1"] = "ask"
    records = dependency_records([a, b]); assert len(records) == 4
    assert all(record["review_only"] for record in records)

def test_fixed_save_is_blocked_until_explicit_policy_override():
    a, b = item("a", "road"), item("b", "parking")
    a["meta"]["dependency_links_v1"] = [{"id": "edge", "kind": "road_parking", "target_id": "b", "policy": "fixed"}]
    old = seal_record({"project_id": "p", "project_input": with_canvas_snapshot({"manual_fields": {"units": "ft", "site_objects": [a, b]}})})
    moved = deepcopy([a, b]); moved[1]["x"] = 400
    with pytest.raises(ProjectDocumentError):
        validate_fixed_changes([a, b], moved)
    with pytest.raises(ProjectDocumentError):
        seal_record({"project_id": "p", "project_input": with_canvas_snapshot({"manual_fields": {"units": "ft", "site_objects": moved}})}, previous=old)
    moved[0]["meta"]["dependency_links_v1"][0]["policy"] = "independent"
    saved = seal_record({"project_id": "p", "project_input": with_canvas_snapshot({"manual_fields": {"units": "ft", "site_objects": moved}})}, previous=old)
    assert saved["project_input"]["manual_fields"]["site_objects"][1]["x"] == 400

def test_recompile_preserves_external_dependency_records():
    a = item("a", "building", {"quantity_relationship_v1": "follow"})
    first = with_canvas_snapshot({"manual_fields": {"units": "ft", "site_objects": [a]}})
    first["canonical_project_v1"]["dependencies"].append({"id": "external", "owner": "external"})
    second = with_canvas_snapshot(first)
    assert len(second["canonical_project_v1"]["dependencies"]) == 2
    assert {"id": "external", "owner": "external"} in second["canonical_project_v1"]["dependencies"]

def test_server_rebuilds_owned_dependencies_from_objects_not_forged_document_projection():
    a, b = item("a", "road"), item("b", "parking")
    a["meta"]["dependency_links_v1"] = [{"id": "edge", "kind": "road_parking", "target_id": "b", "policy": "ask"}]
    value = with_canvas_snapshot({"manual_fields": {"units": "ft", "site_objects": [a, b]}})
    value["canonical_project_v1"]["dependencies"][0]["policy"] = "follow"
    value["canonical_project_v1"]["dependencies"].append({"owner": "dependency_graph_v1", "id": "forged"})
    saved = seal_record({"project_id": "p", "project_input": value})
    edges = saved["project_input"]["canonical_project_v1"]["dependencies"]
    assert len(edges) == 1 and edges[0]["policy"] == "ask"

def test_null_parking_and_duplicate_edge_identity_fail_closed():
    a, b, c = item("a", "road"), item("b", "parking"), item("c", "entrance")
    a["meta"]["canonical_relationships"] = {"parking": None}
    with pytest.raises(ProjectDocumentError): validate_dependency_graph([a, b, c])
    a["meta"] = {"dependency_links_v1": [
        {"id": "same", "kind": "road_parking", "target_id": "b", "policy": "independent"},
        {"id": "same", "kind": "access_road", "target_id": "c", "policy": "independent"},
    ]}
    with pytest.raises(ProjectDocumentError): validate_dependency_graph([a, b, c])
