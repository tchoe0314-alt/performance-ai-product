"""Source metadata validation. User acceptance/verification records are not approvals."""
from copy import deepcopy
from datetime import date, datetime
from .brief_classification import FIELDS

KEY = "brief_sources_v1"
TYPES = {"survey", "parcel", "gis", "aerial", "terrain", "contours", "zoning", "municipal_standard", "easement", "right_of_way", "wetland", "flood", "geotechnical", "traffic", "utility"}
TEXT = {"id", "name", "type", "origin", "jurisdiction", "effective_date", "imported_at", "version", "verification", "verified_by", "verification_reference", "rights", "rights_reference"}
LISTS = {"object_ids", "calculation_ids", "requirement_ids"}


def validate_brief_sources(value):
    from .canonical_project import ProjectDocumentError
    def fail():
        raise ProjectDocumentError("Invalid source register.")
    if not isinstance(value, dict) or type(value.get("version")) is not int or value["version"] != 1 or set(value) != {"version", "records"} or not isinstance(value["records"], list) or len(value["records"]) > 200:
        fail()
    ids = set()
    for source in value["records"]:
        if not isinstance(source, dict) or set(source) != TEXT | LISTS | {"accepted", "superseded"}:
            fail()
        if any(not isinstance(source[key], str) or len(source[key]) > 2000 for key in TEXT):
            fail()
        if any(not source[key].strip() for key in ("id", "name", "origin")) or source["id"] in ids or source["type"] not in TYPES or type(source["accepted"]) is not bool or type(source["superseded"]) is not bool:
            fail()
        ids.add(source["id"])
        if source["verification"] not in {"unverified", "review_needed", "verification_recorded"} or source["rights"] not in {"unknown", "permission_recorded", "restricted"}:
            fail()
        if source["verification"] == "verification_recorded" and (not source["verified_by"].strip() or not source["verification_reference"].strip()):
            fail()
        if source["rights"] == "permission_recorded" and not source["rights_reference"].strip():
            fail()
        try:
            datetime.fromisoformat(source["imported_at"].replace("Z", "+00:00"))
            if source["effective_date"] and date.fromisoformat(source["effective_date"]).isoformat() != source["effective_date"]:
                fail()
        except ValueError:
            fail()
        for key in LISTS:
            refs = source[key]
            if not isinstance(refs, list) or len(refs) > 500 or any(not isinstance(item, str) or not item.strip() or len(item) > 200 for item in refs) or len(set(refs)) != len(refs):
                fail()
        if set(source["requirement_ids"]) - FIELDS:
            fail()
    return deepcopy(value)
