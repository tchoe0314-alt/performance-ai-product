"""Optimistic design revisions and explicit replacement recovery snapshots."""
from copy import deepcopy
from hashlib import sha256
import json
from typing import Any


class ProjectRevisionConflict(ValueError):
    def __init__(self, current_revision: str):
        super().__init__("This project changed in another tab. Save a copy or explicitly replace the original.")
        self.current_revision = current_revision


def project_revision(record: dict[str, Any]) -> str:
    design = {key: deepcopy(record.get(key)) for key in (
        "name", "description", "session_id", "tags", "project_input", "session_state",
    )}
    # Calculation/archive publication is not a competing geometry edit.
    document = (design.get("project_input") or {}).get("canonical_project_v1")
    if isinstance(document, dict):
        for section in ("calculation_results", "quantities", "revisions", "export_history"):
            document.pop(section, None)
        for section in ("sources", "assumptions", "alternatives"):
            document[section] = [item for item in document[section] if item.get("owner") != "project_record_v1"]
        state = document.get("extensions", {}).get("project_record_v1")
        if isinstance(state, dict):
            state.pop("active_result_id", None)
    return sha256(json.dumps(design, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def check_revision(record: dict[str, Any], expected: str | None) -> None:
    if expected is not None and expected != project_revision(record):
        raise ProjectRevisionConflict(project_revision(record))


def result_revision(record: dict[str, Any]) -> str:
    return sha256(json.dumps(record.get("latest_result") or {}, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def merge_save_metadata(existing: dict, incoming: dict, *, replaced_record: dict | None = None) -> dict:
    metadata = {**deepcopy(existing), **deepcopy(incoming)}
    # Workflow history is server-owned. A browser autosave must not erase an
    # artifact/calculation that committed after its original project read.
    if existing.get("workflow"):
        workflow = {**deepcopy(incoming.get("workflow") or {}), **deepcopy(existing["workflow"])}
        for section, identity in (("runs", "run_id"), ("artifacts", "artifact_id")):
            seen = set()
            records = []
            for item in [*(existing["workflow"].get(section) or []), *((incoming.get("workflow") or {}).get(section) or [])]:
                key = item.get(identity)
                if key not in seen:
                    records.append(deepcopy(item))
                    seen.add(key)
            workflow[section] = records[:40 if section == "artifacts" else 20]
        metadata["workflow"] = workflow
    backups = deepcopy(existing.get("branch_recovery_v1") or [])
    if replaced_record is not None:
        snapshot = deepcopy(replaced_record)
        snapshot.pop("operational_summary", None)
        snapshot["metadata"].pop("branch_recovery_v1", None)
        document = (snapshot.get("project_input") or {}).get("canonical_project_v1")
        if isinstance(document, dict):
            document["revisions"] = [item for item in document["revisions"] if "branch_recovery_v1" not in item]
        backups.insert(0, {"revision": project_revision(replaced_record), "project": snapshot})
    if backups:
        metadata["branch_recovery_v1"] = backups[:20]
    return metadata
