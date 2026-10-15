"""Versioned project document boundary; legacy UI adapters are not yet migrated.

Canonical snapshots are complete replacements, never sparse legacy merge patches.
Detailed per-object engineering contracts belong to Phase 1.2.
"""
from __future__ import annotations

from copy import deepcopy
import json
import math
from typing import Any

PROJECT_DOCUMENT_KEY = "canonical_project_v1"
SCHEMA_VERSION = "civora_project_v1"
MAPPING_SECTIONS = (
    "project", "client", "site", "units", "coordinate_system", "parcel_geometry",
    "extensions",
)
COLLECTION_SECTIONS = (
    "buildings", "roads", "access_points", "cul_de_sacs", "parking", "sidewalks",
    "setbacks", "easements", "landscape_areas", "stormwater_features",
    "grading_concepts", "utilities", "annotations", "constraints", "dependencies",
    "sources", "assumptions", "calculation_results", "quantities", "alternatives",
    "revisions", "export_history",
)


class ProjectDocumentError(ValueError):
    """Invalid canonical payload; messages never include submitted values."""


def new_project_document(*, name: str = "") -> dict[str, Any]:
    document: dict[str, Any] = {"schema_version": SCHEMA_VERSION}
    document.update({key: {} for key in MAPPING_SECTIONS})
    document.update({key: [] for key in COLLECTION_SECTIONS})
    document["project"] = {"name": name}
    # Unknown is explicit: never guess feet, a CRS, or an elevation datum.
    document["units"] = {"length": None, "area": None, "volume": None}
    document["coordinate_system"] = {
        "horizontal_crs": None, "vertical_datum": None, "origin": None,
    }
    return validate_project_document(document)


def _check_json(value: Any) -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float) and math.isfinite(value):
        return
    if isinstance(value, list):
        for item in value:
            _check_json(item)
        return
    if isinstance(value, dict) and all(isinstance(key, str) for key in value):
        for item in value.values():
            _check_json(item)
        return
    raise ProjectDocumentError("Canonical project must contain only finite JSON data.")


def validate_project_document(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("schema_version") != SCHEMA_VERSION:
        raise ProjectDocumentError("Unsupported canonical project schema version.")
    expected = {"schema_version", *MAPPING_SECTIONS, *COLLECTION_SECTIONS}
    if set(value) != expected:
        raise ProjectDocumentError("Canonical project requires every defined section; custom fields belong in extensions.")
    for key in MAPPING_SECTIONS:
        if not isinstance(value[key], dict):
            raise ProjectDocumentError(f"Canonical project section {key} must be an object.")
    for key in COLLECTION_SECTIONS:
        if not isinstance(value[key], list) or any(not isinstance(item, dict) for item in value[key]):
            raise ProjectDocumentError(f"Canonical project section {key} must be a list of objects.")
    try:
        _check_json(value)
        from .brief_classification import KEY, validate_brief_classifications
        site_inputs = value["site"].get("site_inputs_v1") or {}
        if isinstance(site_inputs, dict) and KEY in site_inputs:
            validate_brief_classifications(site_inputs[KEY])
        from .brief_editing import KEY as ORIGINALS_KEY, validate_brief_originals
        if isinstance(site_inputs, dict) and ORIGINALS_KEY in site_inputs:
            validate_brief_originals(site_inputs[ORIGINALS_KEY])
        from .brief_sources import KEY as SOURCES_KEY, validate_brief_sources
        if isinstance(site_inputs, dict) and SOURCES_KEY in site_inputs:
            validate_brief_sources(site_inputs[SOURCES_KEY])
        from .brief_requirements import KEY as REQUIREMENTS_KEY, validate_brief_requirements
        if isinstance(site_inputs, dict) and REQUIREMENTS_KEY in site_inputs:
            validate_brief_requirements(site_inputs[REQUIREMENTS_KEY])
        return deepcopy(value)
    except RecursionError as exc:
        raise ProjectDocumentError("Canonical project nesting is excessive or cyclic.") from exc


def validate_project_input(project_input: dict[str, Any]) -> dict[str, Any]:
    result = dict(project_input)
    from .brief_classification import KEY, validate_brief_classifications
    site_inputs = (result.get("meta") or {}).get("site_inputs") or {}
    if isinstance(site_inputs, dict) and KEY in site_inputs:
        validate_brief_classifications(site_inputs[KEY])
    from .brief_editing import KEY as ORIGINALS_KEY, validate_brief_originals
    if isinstance(site_inputs, dict) and ORIGINALS_KEY in site_inputs:
        validate_brief_originals(site_inputs[ORIGINALS_KEY])
    from .brief_sources import KEY as SOURCES_KEY, validate_brief_sources
    if isinstance(site_inputs, dict) and SOURCES_KEY in site_inputs:
        validate_brief_sources(site_inputs[SOURCES_KEY])
    from .brief_requirements import KEY as REQUIREMENTS_KEY, validate_brief_requirements
    if isinstance(site_inputs, dict) and REQUIREMENTS_KEY in site_inputs:
        validate_brief_requirements(site_inputs[REQUIREMENTS_KEY])
    if PROJECT_DOCUMENT_KEY in result:
        result[PROJECT_DOCUMENT_KEY] = validate_project_document(result[PROJECT_DOCUMENT_KEY])
    return result


def dumps_project_document(value: Any) -> str:
    return json.dumps(validate_project_document(value), allow_nan=False, sort_keys=True, separators=(",", ":"))


def _unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ProjectDocumentError("Canonical project JSON contains duplicate keys.")
        result[key] = value
    return result


def loads_project_document(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value, object_pairs_hook=_unique_keys)
    except (json.JSONDecodeError, TypeError, RecursionError) as exc:
        raise ProjectDocumentError("Invalid canonical project JSON.") from exc
    return validate_project_document(parsed)
