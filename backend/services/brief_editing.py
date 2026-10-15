"""Validate preserved brief originals; recorded provenance is not certification."""
from copy import deepcopy
from math import isfinite

KEY = "brief_edit_originals_v1"
from .brief_requirements import DEFINITIONS
FIELDS = {"building-area", "building-use", "required-parking", "setbacks", *DEFINITIONS}


def validate_brief_originals(value):
    from .canonical_project import ProjectDocumentError
    from .brief_classification import validate_brief_classifications
    if not isinstance(value, dict) or type(value.get("version")) is not int or value["version"] != 1 or set(value) != {"version", "fields"} or not isinstance(value["fields"], dict):
        raise ProjectDocumentError("Invalid brief originals.")
    for field, original in value["fields"].items():
        if field not in FIELDS or not isinstance(original, dict) or "value" not in original or set(original) - {"value", "classification", "source_record_key"}:
            raise ProjectDocumentError("Invalid brief original.")
        raw = original["value"]
        limit = 2000 if DEFINITIONS.get(field, (None, None))[1] == "text" else 200
        if not (raw is None or isinstance(raw, str) and len(raw) <= limit or type(raw) in {int, float} and isfinite(raw)):
            raise ProjectDocumentError("Invalid brief original.")
        if "classification" in original:
            validate_brief_classifications({"version": 1, "fields": {field: original["classification"]}})
        if "source_record_key" in original and (not isinstance(original["source_record_key"], str) or not original["source_record_key"] or len(original["source_record_key"]) > 200000):
            raise ProjectDocumentError("Invalid original source binding.")
    return deepcopy(value)
