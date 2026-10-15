"""Validated append-only edit graph sealed at the existing locked project boundary."""
from copy import deepcopy
import math
import time
import uuid

from .canonical_project import ProjectDocumentError
from .site_objects import validate_group_graph

KEY = "edit_history_v1"


def editable_input(inputs):
    meta = inputs.get("meta") or {}
    result = {"manual_fields": deepcopy(inputs.get("manual_fields") or {}),
              "image_path": inputs.get("image_path"),
              "input_mode": inputs.get("input_mode") or "user", "meta": {"site_inputs": deepcopy(meta.get("site_inputs") or {})}}
    for key in ("requested_site_program_v1", "reactive_edit_policy_preference", "edit_controls_v1"):
        if key in meta:
            result["meta"][key] = deepcopy(meta[key])
    return result


def _snapshot(value):
    if not isinstance(value, dict) or not isinstance(value.get("manual_fields"), dict) or not isinstance(value.get("meta", {}),dict) or "canonical_project_v1" in value or KEY in (value.get("meta") or {}):
        raise ProjectDocumentError("Invalid edit snapshot.")
    objects = value["manual_fields"].get("site_objects", [])
    if not isinstance(objects, list):
        raise ProjectDocumentError("Invalid edit objects.")
    validate_group_graph(objects)
    def check_json(item, depth=0):
        if depth>80:
            raise ProjectDocumentError("Edit snapshot nesting is too deep.")
        if isinstance(item, float) and not math.isfinite(item):
            raise ProjectDocumentError("Edit snapshots need finite numbers.")
        if isinstance(item, dict):
            for child in item.values(): check_json(child,depth+1)
        elif isinstance(item, list):
            for child in item: check_json(child,depth+1)
        elif item is not None and not isinstance(item,(str,int,float,bool)):
            raise ProjectDocumentError("Edit snapshots must contain JSON values.")
    check_json(value)


def semantic_input(inputs):
    value=editable_input(inputs)
    for key in ("site_objects", "buildings"):
        for item in value["manual_fields"].get(key, []) or []:
            if not isinstance(item,dict) or not item.get("id"): continue
            item["locked"]=item.get("locked") is True
            item["generated"]=item.get("generated") is True
            if item.get("systemDependencies") is None:
                item["systemDependencies"]=["roads","parking","grading","drainage","utilities"]
    return value


def validate_ledger(value):
    if not isinstance(value, dict) or type(value.get("version")) is not int or value.get("version") != 1 or "head" not in value or not isinstance(value.get("transactions"), list) or not isinstance(value.get("redo"), list) or len(value["transactions"]) > 10000:
        raise ProjectDocumentError("Invalid saved edit history.")
    _snapshot(value.get("baseline"))
    activity=value.get("activity_v1",[])
    if not isinstance(activity,list) or len(activity)>100 or any(not isinstance(item,dict) or not all(isinstance(item.get(key),str) for key in ("id","label","detail")) or type(item.get("createdAt")) not in (int,float) or not math.isfinite(item["createdAt"]) or "undo" in item for item in activity):
        raise ProjectDocumentError("Invalid saved activity feed.")
    known = {}
    for tx in value["transactions"]:
        if not isinstance(tx, dict) or "parent_id" not in tx or not isinstance(tx.get("id"), str) or not tx["id"] or tx["id"] in known or not isinstance(tx.get("reason"), str) or type(tx.get("timestamp")) not in (int,float) or not math.isfinite(tx["timestamp"]) or tx.get("undo") != "restore_before":
            raise ProjectDocumentError("Invalid edit transaction.")
        actor = tx.get("actor")
        if not isinstance(actor, dict) or actor.get("kind") not in {"user", "system"} or not (actor.get("user_id") is None or isinstance(actor["user_id"], str)):
            raise ProjectDocumentError("Invalid transaction actor.")
        for key in ("affected_object_ids", "calculation_invalidations", "warnings"):
            if not isinstance(tx.get(key), list) or not all(isinstance(item, str) for item in tx[key]):
                raise ProjectDocumentError("Invalid transaction metadata.")
        description=tx.get("undo_description")
        if description is not None and (not isinstance(description,dict) or description.get("kind") not in {"add","add_many","delete","delete_many","update","combine","explode","bulk_update"} or not isinstance(description.get("label"),str) or not isinstance(description.get("object_label"),str) or type(description.get("count")) is not int or description["count"]<0 or not isinstance(description.get("object_ids"),list) or not all(isinstance(item,str) for item in description["object_ids"])):
            raise ProjectDocumentError("Invalid undo description.")
        _snapshot(tx.get("before"))
        _snapshot(tx.get("after"))
        parent = tx.get("parent_id")
        before = value["baseline"] if parent is None else known.get(parent, {}).get("after") if isinstance(parent, str) else None
        if before is None or tx["before"] != before:
            raise ProjectDocumentError("Broken edit history chain.")
        known[tx["id"]] = tx
    head = value.get("head")
    if head is not None and (not isinstance(head, str) or head not in known):
        raise ProjectDocumentError("Invalid edit history head.")
    for item in reversed(value["redo"]):
        tx = known.get(item) if isinstance(item, str) else None
        if tx is None or tx["parent_id"] != head:
            raise ProjectDocumentError("Invalid redo branch.")
        head = item
    return deepcopy(value)


def seal_edit_history(inputs, previous_inputs, actor_user_id=None):
    incoming = (inputs.get("meta") or {}).get(KEY)
    prior = (previous_inputs.get("meta") or {}).get(KEY)
    if incoming is None and prior is None:
        # Adopt legacy and backend-only writers without rewriting existing geometry.
        baseline = editable_input(previous_inputs or inputs)
        ledger = {"version": 1, "baseline": baseline, "transactions": [], "head": None, "redo": []}
    else:
        ledger = validate_ledger(incoming if incoming is not None else prior)
    if prior is not None:
        old = validate_ledger(prior)
        if ledger["baseline"] != old["baseline"]:
            raise ProjectDocumentError("Saved edit history cannot be rewritten.")
        by_id={tx["id"]:tx for tx in old["transactions"]}
        additions=[]
        for supplied in ledger["transactions"]:
            stored=by_id.get(supplied["id"])
            if stored is not None:
                if {k:v for k,v in supplied.items() if k!="actor"}!={k:v for k,v in stored.items() if k!="actor"}:
                    raise ProjectDocumentError("Saved edit transactions cannot be rewritten.")
            else:additions.append(supplied)
        if not additions and len(ledger["transactions"])<len(old["transactions"]):
            # Late legacy workers cannot erase or move the newer graph's cursor.
            ledger=deepcopy(old)
        else:
            # Approved replacement/fork paths retain both immutable branches.
            # Project revision checks still decide whether the save is authorized.
            ledger["transactions"]=deepcopy(old["transactions"])+additions
        offset=len(old["transactions"])
    else:
        offset = 0
    for tx in ledger["transactions"][offset:]:
        tx["actor"] = {"kind": "user" if actor_user_id else "system", "user_id": actor_user_id}
    known = {tx["id"]: tx for tx in ledger["transactions"]}
    current = known[ledger["head"]]["after"] if ledger["head"] else ledger["baseline"]
    actual = editable_input(inputs)
    if semantic_input(current) != semantic_input(actual):
        old_objects = {item["id"]: item for item in current["manual_fields"].get("site_objects", []) if isinstance(item, dict) and item.get("id")}
        new_objects = {item["id"]: item for item in actual["manual_fields"].get("site_objects", []) if isinstance(item, dict) and item.get("id")}
        tx = {"id": "edit-" + str(uuid.uuid4()), "parent_id": ledger["head"], "before": deepcopy(current), "after": actual,
              "affected_object_ids": [key for key in dict.fromkeys([*old_objects, *new_objects]) if old_objects.get(key) != new_objects.get(key)],
              "reason": "Saved workspace revision", "actor": {"kind": "user" if actor_user_id else "system", "user_id": actor_user_id},
              "calculation_invalidations": ["roads", "parking", "grading", "drainage", "utilities"], "warnings": [],
              "timestamp": int(time.time() * 1000), "undo": "restore_before"}
        ledger["transactions"].append(tx)
        ledger["head"] = tx["id"]
        ledger["redo"] = []
    return validate_ledger(ledger)
