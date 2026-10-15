"""Lossless canvas compatibility gateway during Phase 1.1 migration.

Canvas records own geometry; existing manual-field projections own the legacy
engineering input shape. Other document sections and source-review metadata are
preserved rather than invented or silently overwritten.
"""
from copy import deepcopy
from typing import Any

from .canonical_project import (
    COLLECTION_SECTIONS, PROJECT_DOCUMENT_KEY, ProjectDocumentError,
    new_project_document, validate_project_document,
)
from .site_objects import object_definition, placement_from_definition, validate_group_graph

GROUPS = {
    "building": "buildings", "retail_building": "buildings", "multifamily_building": "buildings",
    "industrial_building": "buildings", "office_building": "buildings", "pad": "buildings",
    "road": "roads", "driveway": "roads", "entrance": "access_points", "parking": "parking",
    "sidewalk": "sidewalks", "setback_zone": "setbacks", "landscape": "landscape_areas",
    "open_space": "landscape_areas", "basin": "stormwater_features", "inlet": "stormwater_features",
    "outfall": "stormwater_features", "utility_corridor": "utilities", "hydrant": "utilities", "manhole": "utilities",
}


def _owned(value: Any) -> bool:
    return isinstance(value, dict) and isinstance(value.get("canvas_placement_v1"), dict)


def _bucket(document: dict, section: str) -> Any:
    if section == "parcel_geometry":
        return document["parcel_geometry"].get("canvas_placements_v1")
    if section == "other":
        return document["extensions"].get("canvas_other_placements_v1")
    return document[section]


def _validate_type_library(document: dict):
    from .object_type_store import validate_custom_type
    library = document["extensions"].get("object_type_library_v1", {})
    if not isinstance(library,dict):
        raise ProjectDocumentError("Saved object type library is invalid.")
    for key, value in library.items():
        try:
            definition = validate_custom_type(value)
        except ValueError as exc:
            raise ProjectDocumentError(str(exc)) from exc
        if definition["id"] != key:
            raise ProjectDocumentError("Saved object type reference is invalid.")


def with_canvas_snapshot(project_input: dict, previous: Any = None) -> dict:
    base = previous if previous is not None else project_input.get(PROJECT_DOCUMENT_KEY)
    document = new_project_document() if base is None else validate_project_document(base)
    fields = deepcopy(project_input.get("manual_fields") or {})
    objects = fields.pop("site_objects", None)
    if not isinstance(objects, list):
        return deepcopy(project_input)
    if any(not isinstance(item, dict) for item in objects):
        raise ProjectDocumentError("Canvas placements must be objects.")
    validate_group_graph(objects)
    previous_objects = {}
    for section in (*COLLECTION_SECTIONS, "parcel_geometry", "other"):
        for wrapper in _bucket(document, section) or []:
            if _owned(wrapper) and isinstance(wrapper.get("object_v1"), dict):
                previous_objects[wrapper["canvas_placement_v1"].get("id")] = wrapper["object_v1"]
    for section in COLLECTION_SECTIONS:
        document[section] = [item for item in document[section] if not _owned(item)]
    document["parcel_geometry"]["canvas_placements_v1"] = []
    document["extensions"]["canvas_other_placements_v1"] = []
    library = document["extensions"].setdefault("object_type_library_v1", {})
    if not isinstance(library,dict):
        raise ProjectDocumentError("Saved object type library is invalid.")
    from .object_type_store import validate_custom_type
    for item in objects:
        custom = (item.get("meta") or {}).get("custom_type_definition_v1")
        if custom is not None:
            try:
                custom = validate_custom_type(custom)
            except ValueError as exc:
                raise ProjectDocumentError(str(exc)) from exc
            library[custom["id"]] = custom
    order = []
    for item in objects:
        meta = item.get("meta") if isinstance(item.get("meta"), dict) else {}
        object_type = item.get("type") if isinstance(item.get("type"), str) else ""
        section = (
            "parcel_geometry" if item.get("type") == "site" else
            "cul_de_sacs" if isinstance(meta.get("cul_de_sac_v1"), dict) else
            GROUPS.get(object_type, "other")
        )
        target = _bucket(document, section)
        order.append({"section": section, "index": len(target)})
        target.append({"canvas_placement_v1": item, "object_v1": object_definition(item, fields.get("units"), previous_objects.get(item.get("id")))})
    from .dependency_graph import dependency_records, OWNER as DEPENDENCY_OWNER
    document["dependencies"] = [edge for edge in document["dependencies"] if edge.get("owner") != DEPENDENCY_OWNER] + dependency_records(objects)
    document["extensions"]["canvas_workspace_v1"] = {"version": 1, "manual_fields": fields, "object_order": order}
    document["project"]["name"] = fields.get("project_name", "")
    document["units"]["length"] = fields.get("units")
    return {**deepcopy(project_input), PROJECT_DOCUMENT_KEY: validate_project_document(document)}


def resolve_canvas_input(project_input: dict) -> dict:
    from .canonical_record import resolve_model_input
    project_input = resolve_model_input(project_input)
    if PROJECT_DOCUMENT_KEY not in project_input:
        return deepcopy(project_input)
    document = validate_project_document(project_input[PROJECT_DOCUMENT_KEY])
    _validate_type_library(document)
    workspace = document["extensions"].get("canvas_workspace_v1")
    if workspace is None:
        return deepcopy(project_input)
    if (
        not isinstance(workspace, dict) or type(workspace.get("version")) is not int or workspace.get("version") != 1
        or not isinstance(workspace.get("manual_fields"), dict)
        or not isinstance(workspace.get("object_order"), list)
    ):
        raise ProjectDocumentError("Saved canvas adapter is invalid.")
    allowed = {*COLLECTION_SECTIONS, "parcel_geometry", "other"}
    seen = set()
    objects = []
    for reference in workspace["object_order"]:
        if not isinstance(reference, dict):
            raise ProjectDocumentError("Saved canvas object reference is invalid.")
        section, index = reference.get("section"), reference.get("index")
        if not isinstance(section, str) or section not in allowed or type(index) is not int or index < 0:
            raise ProjectDocumentError("Saved canvas object reference is invalid.")
        target = _bucket(document, section)
        item = target[index] if isinstance(target, list) and index < len(target) else None
        if (section, index) in seen or not _owned(item):
            raise ProjectDocumentError("Saved canvas object reference is missing or duplicated.")
        seen.add((section, index))
        objects.append(placement_from_definition(item["canvas_placement_v1"], item["object_v1"]) if "object_v1" in item else deepcopy(item["canvas_placement_v1"]))
    total = sum(sum(_owned(item) for item in target) for section in allowed if isinstance(target := _bucket(document, section), list))
    if total != len(objects):
        raise ProjectDocumentError("Saved canvas object references are incomplete.")
    validate_group_graph(objects)
    fields = deepcopy(workspace["manual_fields"])
    length_unit = document["units"].get("length")
    if length_unit is not None and not isinstance(length_unit, str):
        raise ProjectDocumentError("Saved project length units are invalid.")
    if isinstance(length_unit, str) and length_unit.strip():
        fields["units"] = length_unit
    else:
        fields.pop("units", None)
    return {**deepcopy(project_input), PROJECT_DOCUMENT_KEY: document,
            "manual_fields": {**fields, "site_objects": objects}}


def reconcile_canvas_save(existing: dict, incoming: dict, merged: dict) -> dict:
    """Canonical writes win; still-unmigrated server writers refresh the adapter.

    These are existing legacy writes, not a new public edit API. Cross-client
    revision conflict handling remains a separate Phase 1.1/1.3 requirement.
    """
    document = merged.get(PROJECT_DOCUMENT_KEY)
    if not isinstance(document, dict):
        return merged
    from .canonical_record import with_model_snapshot
    explicit_document = incoming.get(PROJECT_DOCUMENT_KEY)
    if explicit_document is not None and explicit_document != existing.get(PROJECT_DOCUMENT_KEY):
        return resolve_canvas_input(merged)
    if "manual_fields" in incoming and incoming["manual_fields"] != existing.get("manual_fields"):
        merged = with_canvas_snapshot(merged, document)
    return resolve_canvas_input(with_model_snapshot(merged))


def seal_canvas_objects(document: dict, previous: dict | None = None, *, actor_user_id: str | None = None, prior_object_ids: set | None = None) -> dict:
    """Recompute quality and revision against stored state, never client claims."""
    _validate_type_library(document)
    old = {}
    prior_ids = set(prior_object_ids or ())
    for section in (*COLLECTION_SECTIONS, "parcel_geometry", "other"):
        for wrapper in _bucket(previous, section) or [] if previous else []:
            if _owned(wrapper):
                prior_ids.add(wrapper["canvas_placement_v1"].get("id"))
            if _owned(wrapper) and isinstance(wrapper.get("object_v1"), dict):
                old[wrapper["canvas_placement_v1"].get("id")] = wrapper["object_v1"]
    placements = []
    for section in (*COLLECTION_SECTIONS, "parcel_geometry", "other"):
        for wrapper in _bucket(document, section) or []:
            if not _owned(wrapper):
                continue
            raw = wrapper["canvas_placement_v1"]
            item = placement_from_definition(raw, wrapper["object_v1"]) if "object_v1" in wrapper else deepcopy(raw)
            wrapper["object_v1"] = object_definition(item, document["units"].get("length"), old.get(item.get("id")))
            if actor_user_id and item["id"] not in prior_ids and wrapper["object_v1"]["created_by"]["kind"] in ("user", "import"):
                wrapper["object_v1"]["created_by"]["actor_id"] = actor_user_id
            placements.append(item)
    validate_group_graph(placements)
    from .dependency_graph import dependency_records, OWNER as DEPENDENCY_OWNER
    document["dependencies"] = [edge for edge in document["dependencies"] if edge.get("owner") != DEPENDENCY_OWNER] + dependency_records(placements)
    from .object_type_store import validate_custom_type
    library = document["extensions"].setdefault("object_type_library_v1", {})
    if not isinstance(library,dict):
        raise ProjectDocumentError("Saved object type library is invalid.")
    for item in placements:
        custom = (item.get("meta") or {}).get("custom_type_definition_v1")
        if custom is not None:
            try:
                definition = validate_custom_type(custom)
            except ValueError as exc:
                raise ProjectDocumentError(str(exc)) from exc
            library[definition["id"]] = definition
    return document
