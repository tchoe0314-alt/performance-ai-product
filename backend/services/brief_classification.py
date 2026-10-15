"""Validate recorded brief intent/provenance; never certify engineering results."""
from copy import deepcopy

KEY = "active_brief_classifications_v1"
FIELDS = {"gross-acreage", "usable-acreage", "building-area", "storeys", "building-use", "parking-ratio", "required-parking", "drive-aisles", "access", "egress", "setbacks", "height", "lot-coverage", "impervious", "open-space", "stormwater", "protected", "priorities"}
PRIORITIES = {"required", "preferred", "assumed", "unknown"}
TRUST = {"user_entered", "user_confirmed", "sourced", "calculated", "externally_verified", "unverified"}


def validate_brief_classifications(value):
    from .canonical_project import ProjectDocumentError
    if not isinstance(value, dict) or type(value.get("version")) is not int or value["version"] != 1 or set(value) != {"version", "fields"} or not isinstance(value["fields"], dict):
        raise ProjectDocumentError("Invalid brief classifications.")
    for key, entry in value["fields"].items():
        if key not in FIELDS or not isinstance(entry, dict) or set(entry) - {"priority", "trust", "value_key", "source_reference"}:
            raise ProjectDocumentError("Invalid brief classification entry.")
        priority, trust, binding, source = (entry.get(name) for name in ("priority", "trust", "value_key", "source_reference"))
        if not isinstance(priority, str) or priority not in PRIORITIES or not isinstance(trust, str) or trust not in TRUST or not isinstance(binding, str) or not binding or len(binding) > 200000 or ("source_reference" in entry and (not isinstance(source, str) or not source.strip() or len(source) > 2000)) or (trust in {"sourced", "externally_verified"} and not source):
            raise ProjectDocumentError("Invalid brief classification entry.")
    return deepcopy(value)
