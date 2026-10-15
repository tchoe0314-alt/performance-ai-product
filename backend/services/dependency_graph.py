"""Persisted relationship integrity. Geometry links are draft intent, not engineering approval."""
from .canonical_project import ProjectDocumentError

OWNER = "dependency_graph_v1"
POLICIES = {"follow", "ask", "fixed", "independent"}


def link_kind(source, target):
    kind = source.get("type") or ""
    target_kind = target.get("type")
    if kind in ("building", "pad") or kind.endswith("_building"):
        if target_kind == "parking": return "building_parking"
        if target_kind == "setback_zone": return "building_setback"
        if target_kind in ("utility_corridor", "hydrant", "manhole", "inlet", "outfall"): return "utility_building"
    if kind in ("road", "driveway", "access_drive", "drive_aisle"):
        if target_kind == "parking": return "road_parking"
        if target_kind == "road" and (target.get("meta") or {}).get("cul_de_sac_v1"): return "road_culdesac"
        if target_kind in ("entrance", "driveway", "access_drive"): return "access_road"
    if kind == "basin" and (target_kind in ("open_space", "landscape") or (target.get("meta") or {}).get("semantic_role") == "drainage_area"):
        return "pond_drainage"
    return None


def links_for(source, objects):
    meta = source.get("meta") or {}
    links = meta.get("dependency_links_v1", [])
    if not isinstance(links, list) or len(links) > 1000 or any(not isinstance(edge, dict) for edge in links):
        raise ProjectDocumentError("Invalid dependency links.")
    relationships = meta.get("canonical_relationships") or {}
    parking = relationships.get("parking") if isinstance(relationships, dict) else None
    if isinstance(relationships, dict) and "parking" in relationships and not isinstance(parking, dict):
        raise ProjectDocumentError("Invalid parking relationship.")
    ids = parking.get("object_ids", []) if isinstance(parking, dict) else [o["id"] for o in objects if o.get("type") == "parking" and (o.get("meta") or {}).get("canonical_parent_id") == source["id"]]
    if not isinstance(ids, list) or any(not isinstance(value, str) for value in ids):
        raise ProjectDocumentError("Invalid parking relationship.")
    policy = parking.get("policy", "ask") if isinstance(parking, dict) else "ask"
    if not isinstance(policy, str) or policy not in POLICIES: raise ProjectDocumentError("Invalid dependency policy.")
    return [*links, *[{"id": f"parking:{source['id']}:{target}", "kind": "building_parking", "target_id": target, "policy": policy} for target in ids if not any(edge.get("target_id") == target for edge in links)]]


def validate_dependency_graph(objects):
    by_id = {o["id"]: o for o in objects}
    outgoing = {key: [] for key in by_id}
    incoming = {}
    edge_ids = set()
    for source in objects:
        seen = set()
        for edge in links_for(source, objects):
            target_id = edge.get("target_id")
            target = by_id.get(target_id) if isinstance(target_id, str) else None
            if not target or target_id == source["id"] or target_id in seen or not isinstance(edge.get("id"), str) or not edge["id"] or edge["id"] in edge_ids or not isinstance(edge.get("policy"), str) or edge["policy"] not in POLICIES or link_kind(source, target) != edge.get("kind") or edge.get("kind") is None:
                raise ProjectDocumentError("A dependency has a missing, duplicate or incompatible object.")
            seen.add(target_id)
            edge_ids.add(edge["id"])
            if edge["policy"] != "independent":
                if target_id in incoming and incoming[target_id] != source["id"]:
                    raise ProjectDocumentError("A linked object cannot have two geometry drivers.")
                incoming[target_id] = source["id"]
                outgoing[source["id"]].append(target_id)
        quantity = (source.get("meta") or {}).get("quantity_relationship_v1")
        if quantity is not None and (not isinstance(quantity, str) or quantity not in POLICIES):
            raise ProjectDocumentError("Invalid quantity relationship.")
        if quantity is not None:
            identity = f"quantity:{source['id']}"
            if identity in edge_ids: raise ProjectDocumentError("Duplicate quantity relationship identity.")
            edge_ids.add(identity)
    degree = {key: int(key in incoming) for key in by_id}
    ready = [key for key, value in degree.items() if not value]
    count = 0
    while ready:
        key = ready.pop(); count += 1
        for child in outgoing[key]:
            degree[child] -= 1
            if not degree[child]: ready.append(child)
    if count != len(by_id): raise ProjectDocumentError("Dependency cycles are not allowed.")


def dependency_records(objects):
    validate_dependency_graph(objects)
    records = [{"owner": OWNER, "id": edge["id"], "source_id": source["id"], **edge, "review_only": True} for source in objects for edge in links_for(source, objects)]
    records.extend({"owner": OWNER, "id": f"quantity:{source['id']}", "source_id": source["id"], "target_id": f"quantity:{source['id']}", "kind": "quantity_geometry", "policy": source["meta"]["quantity_relationship_v1"], "review_only": True} for source in objects if (source.get("meta") or {}).get("quantity_relationship_v1"))
    return records


def validate_fixed_changes(previous, current):
    """Changing/removing the policy is the explicit override, never an incidental move."""
    old = {item["id"]: item for item in previous}
    new = {item["id"]: item for item in current}
    keys = ("x", "y", "w", "d", "rotation", "geometry", "type")
    geometry = lambda item: [*[item.get(key, 0 if key in ("x", "y", "rotation") else None) for key in keys], item.get("geometry_type", item.get("geometryType")), (item.get("meta") or {}).get("cul_de_sac_v1")]
    for source in current:
        if source["id"] not in old: continue
        prior = {edge["target_id"]: edge for edge in links_for(old[source["id"]], previous)}
        for edge in links_for(source, current):
            target = edge["target_id"]
            if edge["policy"] == "fixed" and prior.get(target, {}).get("policy") == "fixed" and target in old and target in new and geometry(old[target]) != geometry(new[target]):
                raise ProjectDocumentError("A linked object is Fixed. Change its relationship policy before editing its geometry.")
