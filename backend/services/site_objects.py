"""Versioned canvas objects. Geometry validity is not engineering certification.

Bad outlines remain saveable drafts; malformed documents and group graphs do not.
The legacy placement is a lossless compatibility projection, not a second owner.
"""
from copy import deepcopy
import json
import math
from pathlib import Path

from .canonical_project import ProjectDocumentError

VERSION = "civora_object_v1"
TYPES = json.loads((Path(__file__).resolve().parents[2] / "core/data/site_object_definitions_v1.json").read_text())["types"]


def geometry_issues(item):
    kind = item.get("geometryType") or item.get("geometry_type") or "rect"
    points = item.get("geometry") or []
    issues = []
    definition = TYPES.get(item.get("type"), TYPES["custom"])
    if kind not in definition["geometry"]:
        issues.append("This type needs a closed outline.")
    values = [item.get("x", 0), item.get("y", 0), item.get("w"), item.get("d"), item.get("rotation", 0)]
    if not isinstance(points, list) or any(not isinstance(p, list) or len(p) != 2 for p in points):
        return ["Geometry must contain coordinate pairs."]
    values += [v for p in points for v in p]
    if not all(type(v) in (int, float) and math.isfinite(v) for v in values):
        return ["Geometry must contain finite coordinates."]
    distance = lambda a, b: math.hypot(a[0] - b[0], a[1] - b[1])
    if kind == "rect" and (item["w"] <= 0 or item["d"] <= 0):
        issues.append("Dimensions must be positive.")
    if kind == "point" and len(points) != 1:
        issues.append("A point needs one coordinate.")
    if kind == "polyline" and (len(points) < 2 or any(distance(a, b) <= 1e-7 for a, b in zip(points, points[1:]))):
        issues.append("A line needs distinct connected points.")
    if kind == "polygon":
        ring = points[:-1] if len(points) > 1 and distance(points[0], points[-1]) <= 1e-7 else points
        area = abs(sum(p[0] * ring[(i + 1) % len(ring)][1] - ring[(i + 1) % len(ring)][0] * p[1] for i, p in enumerate(ring))) / 2
        if len(ring) < 3 or area <= 1e-7:
            issues.append("An outline needs at least three points and a nonzero area.")
        cross = lambda a, b, c: (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
        def on(a, b, c):
            return abs(cross(a,b,c)) <= 1e-7 and min(a[0],b[0])-1e-7 <= c[0] <= max(a[0],b[0])+1e-7 and min(a[1],b[1])-1e-7 <= c[1] <= max(a[1],b[1])+1e-7
        for i, a in enumerate(ring):
            b = ring[(i+1) % len(ring)]
            if distance(a,b) <= 1e-7:
                issues.append("An outline has a zero-length edge.")
            for j in range(i+1, len(ring)):
                if j == i+1 or (i == 0 and j == len(ring)-1):
                    continue
                c, d = ring[j], ring[(j+1) % len(ring)]
                if (cross(a,b,c)*cross(a,b,d) < 0 and cross(c,d,a)*cross(c,d,b) < 0) or on(a,b,c) or on(a,b,d) or on(c,d,a) or on(c,d,b):
                    issues.append("The outline crosses or touches itself.")
    if (item.get("meta") or {}).get("semantic_source_mode") == "program_group_bounds" and item.get("type") not in ("custom", "group"):
        issues.append("Group bounds are not a verified combined footprint.")
    return list(dict.fromkeys(issues))


def object_definition(item, units, previous=None):
    if not isinstance(item.get("id"), str) or not item["id"]:
        raise ProjectDocumentError("Objects need stable IDs.")
    meta = item.get("meta") or {}
    if not isinstance(meta,dict) or any(key in item and item[key] is not None and not isinstance(item[key],str) for key in ("label","source","type")):
        raise ProjectDocumentError("Object metadata must use named JSON fields.")
    kind = item.get("type") or "custom"
    definition = TYPES.get(kind, TYPES["custom"])
    issues = geometry_issues(item)
    source = item.get("source") or "unknown"
    relationship_meta = meta.get("canonical_relationships")
    parking_meta = relationship_meta.get("parking") if isinstance(relationship_meta,dict) else None
    parking = parking_meta.get("object_ids") if isinstance(parking_meta,dict) else None
    links = parking if isinstance(parking,list) else meta.get("linked_parking_ids",[])
    relationships = list(dict.fromkeys(v for group in (links,meta.get("combined_from_object_ids",[])) for v in (group if isinstance(group,list) else []) if isinstance(v,str)))
    if isinstance(meta.get("object_relationship_ids_v1"),list):
        relationships=list(dict.fromkeys(v for v in meta["object_relationship_ids_v1"] if isinstance(v,str)))
    relationships=list(dict.fromkeys([*relationships,*[edge["target_id"] for edge in meta.get("dependency_links_v1",[]) if isinstance(edge,dict) and isinstance(edge.get("target_id"),str)]]))
    creator = "system" if item.get("generated") or source == "generated" else "import" if source.startswith("detected") else "user" if source in ("user", "manual_drawn", "user_confirmed") else "unknown"
    geometry_kind = item.get("geometryType") or item.get("geometry_type") or "rect"
    scalar = lambda key: item[key] if item.get(key) is not None else 0
    record = {
        "schema_version": VERSION, "id": item["id"], "name": (item.get("label") or "").strip() or f"{kind.replace('_', ' ')} {item['id'][-6:]}",
        "type": kind, "custom_type_id": meta.get("custom_type_id") if isinstance(meta.get("custom_type_id"), str) else None,
        "geometry": {"kind": geometry_kind, "origin": [scalar("x"), scalar("y")], "size": [scalar("w"), scalar("d"), item.get("h") if item.get("h") is not None else scalar("height_ft")], "rotation": scalar("rotation"), "coordinates": deepcopy(item.get("geometry") or [])},
        "units": {"length": units}, "layer": {"id": meta.get("layer_id", definition["layer"]), "visible": meta.get("ui_hidden") is not True, "locked": item.get("locked") is True},
        "source": {"kind": source, "reference": meta.get("source_id") if isinstance(meta.get("source_id"), str) else None, "verified": meta.get("source_verified") is True},
        "created_by": deepcopy(previous["created_by"]) if previous else {"kind": creator, "actor_id": None},
        "revision": {"number": previous["revision"]["number"] if previous else 1, "last_edit": deepcopy(meta.get("canonical_last_edit"))},
        "validation": {"status": "invalid" if issues else "unverified" if kind == "custom" or kind not in TYPES else "valid", "issues": issues, "paused_systems": definition["systems"] if issues and item.get("placed") is not False else [], "engineering_verified": False},
        "dependency_status": "needs_review" if relationships else "clear",
        "relationships": {"parent_group_id": meta.get("group_id") if isinstance(meta.get("group_id"), str) else None, "object_ids": relationships, "calculation_ids": [v for v in meta.get("calculation_ids", []) if isinstance(v, str)] if isinstance(meta.get("calculation_ids", []), list) else []},
        "export_mapping": {"layer": definition["layer"], "geometry_kind": geometry_kind, "mode": definition.get("export", "reference_only" if kind == "custom" or kind not in TYPES else "review_geometry")},
        "properties": deepcopy(meta.get("custom_properties_v1") or {}),
    }
    content = lambda value: {k:v for k,v in value.items() if k not in ("revision", "validation", "created_by")}
    if previous and content(previous) != content(record):
        record["revision"]["number"] += 1
    return record


def validate_definition(value, object_id):
    bad = lambda: ProjectDocumentError("Saved object definition is invalid.")
    if not isinstance(value, dict) or value.get("schema_version") != VERSION or value.get("id") != object_id:
        raise bad()
    for key in ("geometry", "units", "layer", "source", "created_by", "revision", "validation", "relationships", "export_mapping", "properties"):
        if not isinstance(value.get(key), dict):
            raise bad()
    g = value["geometry"]
    if g.get("kind") not in ("rect", "polygon", "polyline", "point"):
        raise bad()
    for key, count in (("origin",2),("size",3)):
        if not isinstance(g.get(key), list) or len(g[key]) != count or any(type(v) not in (int,float) or not math.isfinite(v) for v in g[key]):
            raise bad()
    if type(g.get("rotation")) not in (int,float) or not math.isfinite(g["rotation"]) or not isinstance(g.get("coordinates"), list):
        raise bad()
    if any(not isinstance(p,list) or len(p) != 2 or any(type(v) not in (int,float) or not math.isfinite(v) for v in p) for p in g["coordinates"]):
        raise bad()
    if not isinstance(value.get("name"),str) or not isinstance(value.get("type"),str) or type(value["revision"].get("number")) is not int or value["revision"]["number"] < 1:
        raise bad()
    if not isinstance(value["layer"].get("id"),str) or any(type(value["layer"].get(k)) is not bool for k in ("visible","locked")):
        raise bad()
    parent = value["relationships"].get("parent_group_id")
    if parent is not None and not isinstance(parent,str):
        raise bad()
    for key in ("object_ids","calculation_ids"):
        if not isinstance(value["relationships"].get(key),list) or any(not isinstance(v,str) for v in value["relationships"][key]):
            raise bad()
    if value["units"].get("length") is not None and not isinstance(value["units"]["length"],str):
        raise bad()
    if not isinstance(value["source"].get("kind"),str) or type(value["source"].get("verified")) is not bool or "reference" not in value["source"] or (value["source"]["reference"] is not None and not isinstance(value["source"]["reference"],str)):
        raise bad()
    if not isinstance(value["created_by"].get("kind"),str) or "actor_id" not in value["created_by"] or (value["created_by"]["actor_id"] is not None and not isinstance(value["created_by"]["actor_id"],str)):
        raise bad()
    if value["validation"].get("status") not in ("valid","invalid","unverified") or value["validation"].get("engineering_verified") is not False:
        raise bad()
    for key in ("issues","paused_systems"):
        if not isinstance(value["validation"].get(key),list) or any(not isinstance(v,str) for v in value["validation"][key]):
            raise bad()
    if value.get("dependency_status") not in ("clear","needs_review") or not isinstance(value["export_mapping"].get("layer"),str) or not isinstance(value["export_mapping"].get("geometry_kind"),str) or value["export_mapping"].get("mode") not in ("reference_only","review_geometry","organization_only"):
        raise bad()


def placement_from_definition(item, value):
    validate_definition(value, item.get("id"))
    original = object_definition(item, value["units"].get("length"))
    result = deepcopy(item)
    for key, new, old in [("label", value["name"], original["name"]), ("type",value["type"],original["type"]), ("source",value["source"]["kind"],original["source"]["kind"]), ("geometryType",value["geometry"]["kind"],original["geometry"]["kind"]), ("geometry",value["geometry"]["coordinates"],original["geometry"]["coordinates"]), ("rotation",value["geometry"]["rotation"],original["geometry"]["rotation"]), ("locked",value["layer"]["locked"],original["layer"]["locked"])]:
        if key == "geometryType" and "geometry_type" in item:
            key = "geometry_type"
        if new != old or (key in item and item[key] is not None):
            result[key] = deepcopy(new)
    for field, names in (("origin",("x","y")),("size",("w","d","height_ft" if "height_ft" in item else "h"))):
        for index, key in enumerate(names):
            if value["geometry"][field][index] != original["geometry"][field][index] or (key in item and item[key] is not None):
                result[key] = value["geometry"][field][index]
    meta = result.get("meta", {}).copy()
    for key, new, old in [("ui_hidden",not value["layer"]["visible"],not original["layer"]["visible"]), ("layer_id",value["layer"]["id"],original["layer"]["id"]), ("group_id",value["relationships"]["parent_group_id"],original["relationships"]["parent_group_id"]), ("custom_type_id",value.get("custom_type_id"),original["custom_type_id"]), ("custom_properties_v1",value["properties"],original["properties"])]:
        if new != old or key in meta:
            meta[key] = deepcopy(new)
    if meta:
        result["meta"] = meta
    for key,new,old in [("source_id",value["source"]["reference"],original["source"]["reference"]),("source_verified",value["source"]["verified"],original["source"]["verified"]),("object_relationship_ids_v1",value["relationships"]["object_ids"],original["relationships"]["object_ids"]),("calculation_ids",value["relationships"]["calculation_ids"],original["relationships"]["calculation_ids"])]:
        if new != old or key in meta:
            meta[key]=deepcopy(new)
    if meta:
        result["meta"]=meta
    return result


def validate_group_graph(objects):
    if any(not isinstance(item,dict) or not isinstance(item.get("id"),str) or not item["id"] for item in objects):
        raise ProjectDocumentError("Objects need stable IDs.")
    by_id = {item["id"]:item for item in objects}
    if len(by_id) != len(objects):
        raise ProjectDocumentError("Canvas object IDs are duplicated.")
    if any(item.get("meta") is not None and not isinstance(item["meta"],dict) for item in objects):
        raise ProjectDocumentError("Object metadata must use named JSON fields.")
    for item in objects:
        seen = {item["id"]}
        parent = (item.get("meta") or {}).get("group_id")
        while parent is not None:
            if not isinstance(parent,str):
                raise ProjectDocumentError("Object group IDs must be strings.")
            if parent in seen or parent not in by_id or by_id[parent].get("type") != "group":
                raise ProjectDocumentError("Object groups have a missing parent or cycle.")
            seen.add(parent)
            parent = (by_id[parent].get("meta") or {}).get("group_id")
    from .dependency_graph import validate_dependency_graph
    validate_dependency_graph(objects)


def calculation_blockers(objects, systems=None):
    requested = set(systems or ("roads", "parking", "grading", "drainage", "utilities"))
    result = []
    if not isinstance(objects,list) or any(not isinstance(item,dict) for item in objects):
        raise ProjectDocumentError("Canvas placements must be objects.")
    for item in objects:
        # Sparse legacy descriptors are not placed geometry. Do not invent it.
        if "w" not in item or "d" not in item:
            continue
        meta=item.get("meta") or {}
        if isinstance(meta,dict):
            if isinstance(meta.get("combined_from_object_ids"),list) and meta["combined_from_object_ids"] and meta.get("semantic_source_mode") != "linework":
                continue
            owner=next((object for object in objects if object.get("id") == meta.get("combined_into_object_id")),None)
            if owner and isinstance(owner.get("meta"),dict) and owner["meta"].get("semantic_source_mode") == "linework":
                continue
        definition = object_definition(item, None)
        paused = sorted(requested.intersection(definition["validation"]["paused_systems"]))
        if paused:
            result.append({"object_id": item["id"], "systems": paused, "issues": definition["validation"]["issues"]})
    return result
