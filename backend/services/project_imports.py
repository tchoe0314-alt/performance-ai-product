"""Keep client-imported calculation payloads without trusting execution claims."""
from copy import deepcopy


def _unverified_result(result: dict) -> dict:
    imported = deepcopy(result)
    if imported.get("metadata") is not None and not isinstance(imported["metadata"], dict):
        raise ValueError("Imported result metadata must be an object.")
    metadata = dict(imported.get("metadata") or {})
    claimed_revision = metadata.pop("calculation_engine_revision", None)
    metadata["client_import_v1"] = {"verified_execution": False, "source": "public_project_creation",
                                   "claimed_engine_revision": claimed_revision}
    imported["metadata"] = metadata
    if isinstance(imported.get("final_plan"), dict):
        if imported["final_plan"].get("meta") is not None and not isinstance(imported["final_plan"]["meta"], dict):
            raise ValueError("Imported plan metadata must be an object.")
        plan_meta = dict(imported["final_plan"].get("meta") or {})
        plan_meta.pop("calculation_engine_revision", None)
        imported["final_plan"]["meta"] = plan_meta
    return imported


def unverify_project_import(payload: dict) -> dict:
    """New-project API only; server execution and managed duplicates bypass it."""
    imported = deepcopy(payload)
    if isinstance(imported.get("latest_result"), dict) and imported["latest_result"]:
        imported["latest_result"] = _unverified_result(imported["latest_result"])
    document = (imported.get("project_input") or {}).get("canonical_project_v1")
    if isinstance(document, dict) and isinstance(document.get("calculation_results"), list):
        for item in document["calculation_results"]:
            if isinstance(item, dict) and isinstance(item.get("result_v1"), dict):
                item["result_v1"] = _unverified_result(item["result_v1"])
    return imported
