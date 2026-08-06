from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from threading import Lock
from time import monotonic
from typing import Any, Callable, Dict, Optional, Protocol

from fastapi import HTTPException

from backend.planning.candidate_review_inbox import build_candidate_review_inbox
from backend.planning.common import safe_dict, safe_int, safe_list, safe_str
from backend.planning.vision_ground_truth_flywheel import (
    LEDGER_VERSION as VISION_GROUND_TRUTH_LEDGER_VERSION,
    attach_vision_ground_truth_flywheel,
)


SOURCE_CONTEXT_JOB_TYPE = "source_context"

DETECTION_COVERAGE_CATEGORIES = (
    ("parcel_site_boundary", "Parcel / site boundary", ("parcel_or_site_boundary",), ("parcel_site_boundary",)),
    ("buildings", "Buildings", ("building_footprint",), ("building_footprints",)),
    ("roads_row", "Roads / right-of-way", ("road_or_drive",), ("road_row", "roads_row")),
    ("parking", "Parking areas", ("parking_area",), ()),
    ("sidewalks_paths", "Sidewalks / paths", ("sidewalk_or_path",), ()),
    ("surface_water", "Ponds / basins / surface water", ("water/pond/basin",), ()),
    ("vegetation", "Trees / vegetation", ("vegetation/tree_area",), ()),
    ("terrain_elevation", "Terrain / elevation", ("terrain",), ("terrain_dem_lidar",)),
    ("contours", "Contours", (), ("contours",)),
    ("floodplain", "Floodplain", ("constraint_area",), ()),
    ("wetlands", "Wetlands", ("constraint_area",), ()),
    ("easements", "Easements", ("constraint_area",), ()),
    ("zoning", "Zoning", ("constraint_area",), ()),
    ("utilities", "Existing utilities", ("utility",), ("public_utilities", "existing_utilities")),
)

FIELD_ONLY_CATEGORIES = (
    {
        "key": "survey_control",
        "label": "Survey control / legal boundary",
        "status": "requires_project_source",
        "candidate_count": 0,
        "method": "survey_or_control_upload",
        "message": "Requires a project survey/control source; imagery and public GIS cannot establish survey control.",
    },
    {
        "key": "buried_utility_locates",
        "label": "Buried utility locations",
        "status": "requires_project_source",
        "candidate_count": 0,
        "method": "utility_records_or_field_locate",
        "message": "Requires utility records, as-builts, or field locate evidence; imagery cannot see buried facilities.",
    },
)


class JobQueueProtocol(Protocol):
    def submit_job(
        self,
        *,
        user_id: str,
        job_type: str,
        payload: Dict[str, Any],
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        ...


class ProjectStoreProtocol(Protocol):
    def get_project(self, *, user_id: str, project_id: str) -> Optional[Dict[str, Any]]:
        ...

    def save_project(self, **kwargs: Any) -> Dict[str, Any]:
        ...


def queue_source_context_job(
    *,
    project_store: ProjectStoreProtocol,
    job_queue: JobQueueProtocol,
    user_id: str,
    project_id: Optional[str],
    request_payload: Dict[str, Any],
) -> Dict[str, Any]:
    if project_id and project_store.get_project(user_id=user_id, project_id=project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    job = job_queue.submit_job(
        user_id=user_id,
        job_type=SOURCE_CONTEXT_JOB_TYPE,
        payload=dict(request_payload or {}),
        project_id=project_id,
    )
    return {
        "success": True,
        "job": job,
        "operational_summary": {
            "status": safe_str(job.get("status"), "queued"),
            "job_type": SOURCE_CONTEXT_JOB_TYPE,
            "job_bound": bool(job.get("job_id")),
            "project_bound": bool(project_id),
            "project_id": project_id,
            "job_id": job.get("job_id"),
            "retryable": True,
        },
    }


def build_detection_coverage_report(result: Dict[str, Any]) -> Dict[str, Any]:
    report = safe_dict(result.get("map_feature_detection_report_v1"))
    discovery = safe_dict(result.get("online_existing_conditions_discovery_v1"))
    candidates = [safe_dict(item) for item in safe_list(report.get("feature_candidates"))]
    sources = {
        safe_str(item.get("key")): safe_dict(item)
        for item in safe_list(discovery.get("sources"))
        if safe_str(safe_dict(item).get("key"))
    }
    rows = []
    for key, label, feature_types, source_keys in DETECTION_COVERAGE_CATEGORIES:
        def matches_category(candidate: Dict[str, Any]) -> bool:
            if safe_str(candidate.get("feature_type")) not in feature_types:
                return False
            if key not in {"floodplain", "wetlands", "easements", "zoning"}:
                return True
            properties = safe_dict(candidate.get("properties"))
            hint = " ".join(
                safe_str(value).lower()
                for value in (
                    candidate.get("source_name"),
                    candidate.get("source_type"),
                    candidate.get("source_feature_id"),
                    properties.get("layer"),
                    properties.get("layer_name"),
                    properties.get("type"),
                    properties.get("category"),
                )
                if safe_str(value)
            )
            tokens = {
                "floodplain": ("flood", "fema", "nfhl"),
                "wetlands": ("wetland", "nwi"),
                "easements": ("easement",),
                "zoning": ("zoning", "zone district"),
            }[key]
            return any(token in hint for token in tokens)

        matching_candidates = [
            candidate
            for candidate in candidates
            if matches_category(candidate)
        ]
        source_records = [sources[source_key] for source_key in source_keys if source_key in sources]
        source_candidate_count = sum(safe_int(item.get("candidate_count")) for item in source_records)
        candidate_count = max(len(matching_candidates), source_candidate_count)
        failed = any(safe_str(item.get("status")) == "fetch_failed" for item in source_records)
        unavailable = bool(source_records) and all(
            safe_str(item.get("status")) in {"missing", "unconfigured", "skipped", "not_found"}
            for item in source_records
        )
        if candidate_count:
            status = "found"
            message = f"Found {candidate_count} review candidate{'s' if candidate_count != 1 else ''}."
        elif failed:
            status = "provider_failed"
            message = "A configured source could not complete; retry is available."
        elif unavailable:
            status = "source_unavailable"
            message = "No configured source returned this category."
        else:
            status = "not_observed"
            message = "The available sources did not observe this category."
        rows.append(
            {
                "key": key,
                "label": label,
                "status": status,
                "candidate_count": candidate_count,
                "methods": [safe_str(item.get("provider") or item.get("source_type")) for item in source_records if safe_str(item.get("provider") or item.get("source_type"))],
                "message": message,
            }
        )
    rows.extend(deepcopy(FIELD_ONLY_CATEGORIES))
    found_count = sum(1 for row in rows if row["status"] == "found")
    return {
        "version": "source_context_detection_coverage_v1",
        "status": "complete_with_results" if found_count else "complete_no_observed_features",
        "requested_category_count": len(rows),
        "found_category_count": found_count,
        "not_observed_category_count": sum(1 for row in rows if row["status"] == "not_observed"),
        "unavailable_category_count": sum(1 for row in rows if row["status"] in {"source_unavailable", "provider_failed"}),
        "project_source_required_count": sum(1 for row in rows if row["status"] == "requires_project_source"),
        "categories": rows,
        "review_required": True,
        "truth_label": (
            "Civora attempted every supported source category. Found means a review candidate was observed; "
            "not observed does not prove absence, and survey control or buried utilities require project-specific evidence."
        ),
    }


def build_source_context_job_runner(
    *,
    project_store: ProjectStoreProtocol,
    update_job_progress: Callable[..., None],
    fetch_source_context: Callable[..., Dict[str, Any]],
) -> Callable[[Dict[str, Any]], Dict[str, Any]]:
    cache_lock = Lock()
    source_cache: Dict[str, Dict[str, Any]] = {}
    cache_ttl_seconds = max(0, safe_int(os.getenv("CIVORA_SOURCE_CONTEXT_CACHE_TTL_SECONDS"), 300))
    cache_max_entries = max(1, safe_int(os.getenv("CIVORA_SOURCE_CONTEXT_CACHE_MAX_ENTRIES"), 64))

    def request_fingerprint(*, user_id: str, payload: Dict[str, Any]) -> str:
        encoded = json.dumps(
            {"user_id": user_id, "request": payload},
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def cached_result(cache_key: str) -> tuple[Optional[Dict[str, Any]], float]:
        if not cache_ttl_seconds:
            return None, 0.0
        with cache_lock:
            record = source_cache.get(cache_key)
            if not record:
                return None, 0.0
            age_seconds = max(0.0, monotonic() - float(record.get("stored_at") or 0.0))
            if age_seconds > cache_ttl_seconds:
                source_cache.pop(cache_key, None)
                return None, age_seconds
            return deepcopy(safe_dict(record.get("result"))), age_seconds

    def store_cached_result(cache_key: str, result: Dict[str, Any]) -> None:
        if not cache_ttl_seconds or not result.get("success"):
            return
        with cache_lock:
            source_cache[cache_key] = {"stored_at": monotonic(), "result": deepcopy(result)}
            while len(source_cache) > cache_max_entries:
                oldest_key = min(source_cache, key=lambda key: float(source_cache[key].get("stored_at") or 0.0))
                source_cache.pop(oldest_key, None)

    def source_context_runner(job: Dict[str, Any]) -> Dict[str, Any]:
        payload = dict(job.get("payload") or {})
        force_refresh = bool(payload.pop("force_refresh", False))
        job_id = safe_str(job.get("job_id"))
        user_id = safe_str(job.get("user_id"))
        project_id = safe_str(job.get("project_id"))
        cache_key = request_fingerprint(user_id=user_id, payload=payload)
        if job_id:
            update_job_progress(
                job_id,
                stage="Finding Site Sources",
                detail="Checking location-appropriate local records, public mapped context, terrain, constraints, and imagery sources.",
                progress=20,
            )
        result, cache_age_seconds = (None, 0.0) if force_refresh else cached_result(cache_key)
        cache_status = "hit" if result is not None else ("bypassed" if force_refresh else "miss")
        if result is not None:
            if job_id:
                update_job_progress(
                    job_id,
                    stage="Using Recent Site Sources",
                    detail=f"Using source context checked {max(1, round(cache_age_seconds))} second(s) ago.",
                    progress=72,
                )
        else:
            def report_provider_progress(event: Dict[str, Any]) -> None:
                if not job_id:
                    return
                update_job_progress(
                    job_id,
                    stage=safe_str(event.get("latest_source") or event.get("stage"), "Finding Site Sources"),
                    detail=safe_str(event.get("detail"), "Checking available site sources."),
                    progress=max(20, min(74, safe_int(event.get("progress"), 20))),
                )

            result = dict(fetch_source_context(**payload, progress_callback=report_provider_progress) or {})
            store_cached_result(cache_key, result)
        result["source_context_cache_v1"] = {
            "version": "source_context_cache_v1",
            "status": cache_status,
            "fingerprint": cache_key[:16],
            "age_seconds": round(cache_age_seconds, 3) if cache_status == "hit" else 0,
            "ttl_seconds": cache_ttl_seconds,
            "force_refresh": force_refresh,
            "truth_label": "Cache reuse is limited to an identical recent source request; explicit reruns bypass it.",
        }
        coverage = build_detection_coverage_report(result)
        result["source_context_detection_coverage_v1"] = coverage
        meta_patch = {
            "online_existing_conditions_discovery_v1": result.get("online_existing_conditions_discovery_v1"),
            "map_feature_detection_report_v1": result.get("map_feature_detection_report_v1"),
            "existing_conditions_package": result.get("existing_conditions_package"),
            "existing_conditions_summary": result.get("existing_conditions_summary"),
            "source_context_detection_coverage_v1": coverage,
            "location_source_strategy_v1": result.get("location_source_strategy_v1"),
            "source_context_fetch_metrics_v1": result.get("source_context_fetch_metrics_v1"),
            "source_context_cache_v1": result.get("source_context_cache_v1"),
        }
        project = (
            project_store.get_project(user_id=user_id, project_id=project_id)
            if project_id and user_id
            else None
        )
        if project is not None:
            existing_project_input = safe_dict(project.get("project_input"))
            existing_input_meta = safe_dict(existing_project_input.get("meta"))
            existing_site_inputs = safe_dict(existing_input_meta.get("site_inputs"))
            existing_latest_result = safe_dict(project.get("latest_result"))
            existing_final_plan = safe_dict(existing_latest_result.get("final_plan"))
            existing_final_meta = safe_dict(existing_final_plan.get("meta"))
            for key in (
                "candidate_review_decisions_v1",
                "candidate_review_accepted_drafts_v1",
                "candidate_review_rejected_v1",
                VISION_GROUND_TRUTH_LEDGER_VERSION,
                "civora_vision_split_registry_v1",
            ):
                existing_value = existing_final_meta.get(key)
                if existing_value is None:
                    existing_value = existing_site_inputs.get(key)
                if existing_value is not None:
                    meta_patch[key] = deepcopy(existing_value)
        inbox = build_candidate_review_inbox(meta_patch)
        meta_patch["candidate_review_inbox_v1"] = inbox
        meta_patch = attach_vision_ground_truth_flywheel(meta_patch)
        result["candidate_review_inbox_v1"] = inbox
        result["civora_vision_review_workspace_v1"] = meta_patch["civora_vision_review_workspace_v1"]
        if job_id:
            update_job_progress(
                job_id,
                stage="Preparing Candidate Review",
                detail=f"Preparing {safe_int(inbox.get('candidate_count'))} detected item(s) for accept/reject review.",
                progress=78,
            )
        if project is not None:
            project_input = deepcopy(safe_dict(project.get("project_input")))
            input_meta = deepcopy(safe_dict(project_input.get("meta")))
            site_inputs = deepcopy(safe_dict(input_meta.get("site_inputs")))
            site_inputs.update(meta_patch)
            input_meta["site_inputs"] = site_inputs
            project_input["meta"] = input_meta

            latest_result = deepcopy(safe_dict(project.get("latest_result")))
            final_plan = deepcopy(safe_dict(latest_result.get("final_plan")))
            if final_plan:
                final_meta = deepcopy(safe_dict(final_plan.get("meta")))
                final_meta.update(meta_patch)
                final_plan["meta"] = final_meta
                latest_result["final_plan"] = final_plan
            project_store.save_project(
                user_id=user_id,
                project_id=project_id,
                name=safe_str(project.get("name"), "Untitled Project"),
                description=safe_str(project.get("description")),
                session_id=project.get("session_id"),
                tags=list(project.get("tags") or []),
                project_input=project_input,
                latest_result=latest_result,
                session_state=deepcopy(safe_dict(project.get("session_state"))),
                metadata=deepcopy(safe_dict(project.get("metadata"))),
            )
        result["job_progress"] = {
            "stage": "Site Context Ready",
            "detail": f"Source lookup complete. {safe_int(inbox.get('candidate_count'))} item(s) are ready for review.",
            "progress": 100,
        }
        return result

    return source_context_runner


__all__ = [
    "SOURCE_CONTEXT_JOB_TYPE",
    "build_detection_coverage_report",
    "build_source_context_job_runner",
    "queue_source_context_job",
]
