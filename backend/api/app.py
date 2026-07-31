from __future__ import annotations

import json
import os
from pathlib import Path
import time
import uuid
import urllib.parse
from collections import deque
import hashlib
import threading
from typing import Any, Dict, List, Optional

try:
    threading.stack_size(int(os.getenv("CIVORA_THREAD_STACK_BYTES") or str(512 * 1024)))
except (RuntimeError, ValueError):
    pass

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
import httpx
from anyio import to_thread

from parsers.chat_intent_parser import assess_design_readiness, decide_chat_message
from backend.application.design_workflows import (
    build_run_summary as application_build_run_summary,
    count_unresolved_conflicts as application_count_unresolved_conflicts,
    final_plan_from_result as application_final_plan_from_result,
    prepare_reactive_orchestration_payload as application_prepare_reactive_orchestration_payload,
    run_orchestration as application_run_orchestration,
)
from backend.application.artifact_workflows import (
    build_preview_response as application_build_preview_response,
    export_dxf_artifact as application_export_dxf_artifact,
    export_report_artifact as application_export_report_artifact,
)
from backend.application.auth_workflows import (
    auth_status as application_auth_status,
    current_user_response as application_current_user_response,
    login_user as application_login_user,
    logout_user as application_logout_user,
    register_user as application_register_user,
)
from backend.application.chat_workflows import decide_chat as application_decide_chat
from backend.application.cost_workflows import (
    normalize_unit_price_book_response as application_normalize_unit_price_book_response,
    unit_price_book_from_csv_response as application_unit_price_book_from_csv_response,
    validate_unit_price_book_response as application_validate_unit_price_book_response,
)
from backend.application.file_workflows import (
    build_local_gis_provider_registry as application_build_local_gis_provider_registry,
    check_local_gis_provider_registry as application_check_local_gis_provider_registry,
    download_artifact_response as application_download_artifact_response,
    existing_conditions_online_sources as application_existing_conditions_online_sources,
    fetch_existing_conditions_online as application_fetch_existing_conditions_online,
    get_uploaded_image_response as application_get_uploaded_image_response,
    estimate_slope_from_survey as application_estimate_slope_from_survey,
    read_survey_points as application_read_survey_points,
    upload_existing_conditions_file as application_upload_existing_conditions_file,
    upload_image_file as application_upload_image_file,
    upload_survey_file as application_upload_survey_file,
)
from backend.application.memory_logging import (
    current_rss_mb,
    log_memory,
    peak_rss_mb,
    runtime_monitoring_snapshot,
    runtime_process_monitoring_snapshot,
)
from backend.application.plan_pdf_workflows import (
    build_plan_pdf_analysis_job_runner as application_build_plan_pdf_analysis_job_runner,
    download_project_plan_pdf_report as application_download_project_plan_pdf_report,
    get_project_plan_pdf_report as application_get_project_plan_pdf_report,
    update_project_plan_pdf_element as application_update_project_plan_pdf_element,
    upload_plan_pdf_file as application_upload_plan_pdf_file,
)
from backend.planning.alpha_monitoring import build_alpha_monitoring_report
from backend.planning.utility_catalogs import GLOBAL_UTILITY_CATALOG_MANAGER
from backend.application.job_workflows import (
    build_artifact_export_job_runner as application_build_artifact_export_job_runner,
    build_drainage_job_runner as application_build_drainage_job_runner,
    build_orchestrate_job_runner as application_build_orchestrate_job_runner,
    cancel_existing_job as application_cancel_existing_job,
    continue_existing_job as application_continue_existing_job,
    queue_drainage_job as application_queue_drainage_job,
    queue_artifact_export_job as application_queue_artifact_export_job,
    queue_orchestrate_job as application_queue_orchestrate_job,
    revise_existing_job as application_revise_existing_job,
    retry_existing_job as application_retry_existing_job,
)
from backend.application.project_workflows import (
    artifact_summary as application_artifact_summary,
    delete_project_record as application_delete_project_record,
    get_project_candidate_review_inbox as application_get_project_candidate_review_inbox,
    get_project_design_alternatives as application_get_project_design_alternatives,
    get_project_detail as application_get_project_detail,
    get_project_result as application_get_project_result,
    get_project_source_confidence_map as application_get_project_source_confidence_map,
    list_projects as application_list_projects,
    merge_project_metadata as application_merge_project_metadata,
    result_from_payload as application_result_from_payload,
    review_project_candidates as application_review_project_candidates,
    save_project_record as application_save_project_record,
    save_project_workflow_update as application_save_project_workflow_update,
    update_project_design_alternatives as application_update_project_design_alternatives,
)
from backend.application.session_workflows import maybe_export_session as application_maybe_export_session
from backend.application.standards_workflows import (
    accept_standards_response as application_accept_standards_response,
    controlled_single_source_lookup_response as application_controlled_single_source_lookup_response,
    discover_standards_response as application_discover_standards_response,
    extract_standards_candidates_response as application_extract_standards_candidates_response,
    fetch_live_standards_source_candidate_response as application_fetch_live_standards_source_candidate_response,
    run_golden_scenarios_response as application_run_golden_scenarios_response,
    standards_live_source_policy_response as application_standards_live_source_policy_response,
    standards_review_packet_response as application_standards_review_packet_response,
)
from backend.application.template_workflows import (
    activate_customer_template_response as application_activate_customer_template_response,
    customer_template_registry_response as application_customer_template_registry_response,
    explain_missing_customer_template_response as application_explain_missing_customer_template_response,
    export_customer_templates_response as application_export_customer_templates_response,
    import_customer_template_response as application_import_customer_template_response,
)
from backend.application.professional_workflows import (
    professional_release_response as application_professional_release_response,
    validate_professional_release_response as application_validate_professional_release_response,
)
from backend.application.production_env_validator_v1 import validate_production_env_v1
from backend.services.artifact_service import ArtifactService
from backend.services.auth_store import AuthStore
from backend.services.billing import build_billing_status, usage_gate
from backend.services.database import Database
from backend.services.job_queue import JobQueueService
from backend.services.project_store import ProjectStore
from backend.planning.map_feature_detection import build_map_feature_detection_report, location_context_from_geocode

try:
    from core.config import ALPHA_REVIEW_ONLY, APP_NAME, APP_VERSION, CONSTRUCTION_RELEASES_ENABLED, PRODUCT_MODE
except Exception:
    APP_NAME = "Civora AI"
    APP_VERSION = "0.1.0"
    PRODUCT_MODE = "private_alpha"
    ALPHA_REVIEW_ONLY = True
    CONSTRUCTION_RELEASES_ENABLED = False


BASE_DIR = Path(__file__).resolve().parents[2]
STORAGE_DIR = Path(
    os.getenv("PERFORMANCE_AI_STORAGE_DIR")
    or os.getenv("PERFORMANCE_AI_DATA_DIR")
    or (BASE_DIR / "data")
).resolve()
UPLOAD_DIR = STORAGE_DIR / "uploads"
DATA_DIR = STORAGE_DIR
DB_PATH = DATA_DIR / "performance_ai.db"
START_TIME = time.time()
RUNTIME_INSTANCE_ID = f"{os.getpid()}-{int(START_TIME * 1000)}"
ARTIFACT_DIR = DATA_DIR / "artifacts"
CHAT_LEARNING_PATH = DATA_DIR / "chat_learning.jsonl"
CHAT_TRAINING_PATH = DATA_DIR / "chat_training.jsonl"
CHAT_LEARNING_REPORT_PATH = DATA_DIR / "chat_learning_report.json"
CRON_SECRET = str(os.getenv("CIVORA_CRON_SECRET") or "").strip()
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

DEPLOYED_FRONTEND_ORIGINS = ("https://www.civoraai.com", "https://civoraai.com")
LOCAL_PILOT_CORS_ORIGINS = ("http://localhost:3000", "http://127.0.0.1:3000")


def _clean_origin_list(values: List[str]) -> list[str]:
    cleaned: list[str] = []
    for item in values:
        value = str(item or "").strip().rstrip("/")
        if value and value not in cleaned:
            cleaned.append(value)
    return cleaned


def _cors_allow_origins() -> list[str]:
    raw = str(os.getenv("CORS_ALLOW_ORIGINS") or "").strip()
    if raw == "*":
        if PRODUCT_MODE in {"development", "local"}:
            return ["*"]
        raw = ""
    origins = raw.split(",") if raw else list(DEPLOYED_FRONTEND_ORIGINS)
    if _env_flag("CIVORA_ALLOW_LOCAL_PILOT_CORS", False):
        local_raw = str(os.getenv("CIVORA_LOCAL_PILOT_CORS_ORIGINS") or ",".join(LOCAL_PILOT_CORS_ORIGINS))
        origins.extend(local_raw.split(","))
    return _clean_origin_list(origins)


def _env_flag(name: str, default: bool = False) -> bool:
    raw = str(os.getenv(name) or "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _public_registration_allowed() -> bool:
    if PRODUCT_MODE in {"development", "local", "private_alpha"}:
        return True
    return _env_flag("CIVORA_ALLOW_PUBLIC_REGISTRATION", False)


_RATE_LIMIT_DEFAULTS: Dict[str, tuple[int, int]] = {
    "auth": (30, 60),
    "health": (120, 60),
    "debug": (30, 60),
    "geocode": (30, 60),
    "upload": (20, 60),
    "chat": (60, 60),
    "planner": (20, 60),
    "export": (60, 60),
}
_RATE_LIMIT_EVENTS: Dict[str, deque[float]] = {}
_RATE_LIMIT_LOCK = threading.Lock()


def _env_int(name: str, default: int) -> int:
    try:
        value = int(str(os.getenv(name) or "").strip())
    except Exception:
        return int(default)
    return value if value > 0 else int(default)


def _rate_limit_config(bucket: str) -> tuple[int, int]:
    default_limit, default_window = _RATE_LIMIT_DEFAULTS.get(bucket, (60, 60))
    env_name = f"CIVORA_RATE_LIMIT_{bucket.upper()}_PER_MINUTE"
    return _env_int(env_name, default_limit), default_window


def _request_rate_limit_key(request: Request, authorization: Optional[str]) -> str:
    forwarded = str(request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    client_host = forwarded or (request.client.host if request.client else "unknown")
    token = _bearer_token(authorization)
    if token:
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]
        return f"token:{token_hash}:{client_host}"
    return f"ip:{client_host}"


def _check_rate_limit(bucket: str, key: str, *, limit: int, window_seconds: int, now: Optional[float] = None) -> None:
    current = float(now if now is not None else time.time())
    state_key = f"{bucket}:{key}"
    cutoff = current - float(window_seconds)
    with _RATE_LIMIT_LOCK:
        events = _RATE_LIMIT_EVENTS.setdefault(state_key, deque())
        while events and events[0] <= cutoff:
            events.popleft()
        if len(events) >= limit:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded for {bucket}. Wait about {window_seconds} seconds, then try again.",
            )
        events.append(current)


def rate_limit(bucket: str):
    def dependency(request: Request, authorization: Optional[str] = Header(default=None)) -> None:
        limit, window_seconds = _rate_limit_config(bucket)
        _check_rate_limit(
            bucket,
            _request_rate_limit_key(request, authorization),
            limit=limit,
            window_seconds=window_seconds,
        )

    return dependency


DB = Database(DB_PATH)
AUTH_STORE = AuthStore(DB)
PROJECT_STORE = ProjectStore(DB)
JOB_QUEUE = JobQueueService(DB)
ARTIFACTS = ArtifactService(ARTIFACT_DIR)

try:
    import session_state as session_state_mod
except Exception:
    session_state_mod = None


class RegisterPayload(BaseModel):
    email: str
    password: str
    name: str = ""


class GeocodePayload(BaseModel):
    address: str


class GeocodeResponse(BaseModel):
    success: bool = True
    status: str = "ready"
    blocked: bool = False
    lat: Optional[float] = None
    lng: Optional[float] = None
    display_name: str = ""
    provider: str = ""
    confidence: Optional[float] = None
    name: str = ""
    formatted_address: str = ""
    place_name: str = ""
    normalized_address: str = ""
    message: str = ""
    warnings: List[str] = Field(default_factory=list)
    blockers: List[Dict[str, Any]] = Field(default_factory=list)
    crs: Dict[str, Any] = Field(default_factory=dict)
    location_context: Dict[str, Any] = Field(default_factory=dict)


class LoginPayload(BaseModel):
    email: str
    password: str


class OrchestratePayload(BaseModel):
    project_id: Optional[str] = None
    full_design_mode: bool = False
    input_mode: str = "assisted"
    strict_mode: bool = False
    prompt_text: Optional[str] = None
    prompt: Optional[str] = None
    image_path: Optional[str] = None
    manual_fields: Dict[str, Any] = Field(default_factory=dict)
    image_width_px: Optional[int] = None
    image_height_px: Optional[int] = None
    pixels_per_unit: Optional[float] = None
    plan_type_hint: Optional[str] = None
    units: str = "ft"
    allow_ai_fill_for_blanks: bool = True
    persist_trace_metadata: bool = True
    meta: Dict[str, Any] = Field(default_factory=dict)


class ChatLearningCronPayload(BaseModel):
    max_examples: int = 500
    max_synthetic: int = 60
    max_unrated: int = 300
    exclude_unrated: bool = False


class ChatLearningReportPayload(BaseModel):
    report_path: Optional[str] = None


class SaveProjectPayload(BaseModel):
    project_id: Optional[str] = None
    organization_id: Optional[str] = None
    name: str
    description: str = ""
    session_id: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    project_input: Dict[str, Any] = Field(default_factory=dict)
    latest_result: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ProjectInvitePayload(BaseModel):
    email: str
    role: str = "viewer"


class CandidateReviewPayload(BaseModel):
    candidate_ids: List[str] = Field(default_factory=list)
    action: str
    reason: str = ""


class DesignAlternativesPayload(BaseModel):
    action: str = "generate"
    requested_count: int = 3
    option_number: Optional[int] = None
    alternative_id: str = ""
    reason: str = ""


class PlanPdfElementUpdatePayload(BaseModel):
    text: Optional[str] = None
    review_status: Optional[str] = None
    bbox: Optional[Dict[str, Any]] = None
    move_target: Optional[Dict[str, Any]] = None


class QueueOrchestratePayload(BaseModel):
    project_id: Optional[str] = None
    request: OrchestratePayload


class QueueDrainagePayload(BaseModel):
    project_id: Optional[str] = None
    request: OrchestratePayload


class ArtifactPayload(BaseModel):
    project_id: Optional[str] = None
    result: Dict[str, Any] = Field(default_factory=dict)
    final_plan: Dict[str, Any] = Field(default_factory=dict)
    filename_stem: Optional[str] = None
    preview_quality: Optional[str] = None
    preview_style: Optional[str] = None
    label_density: Optional[str] = None
    render_labels: Optional[bool] = None
    preview_layers: Optional[List[str]] = None
    preview_mode: Optional[str] = None


class QueueArtifactExportPayload(ArtifactPayload):
    pass


class ChatDecisionPayload(BaseModel):
    message: str
    context: Dict[str, Any] = Field(default_factory=dict)


class ChatFeedbackPayload(BaseModel):
    project_id: Optional[str] = None
    message_id: Optional[str] = None
    feedback: str
    message: str
    assistant_message: str
    context: Dict[str, Any] = Field(default_factory=dict)


class UtilityPipeCatalogPayload(BaseModel):
    item_id: str
    network: str
    material: str
    sizes_in: List[float] = Field(default_factory=list)
    pressure_class: str = ""
    roughness_n: Optional[float] = None
    source: Dict[str, Any] = Field(default_factory=dict)
    review_status: str = "needs_review"
    limitations: List[str] = Field(default_factory=list)


class UtilityPartCatalogPayload(BaseModel):
    item_id: str
    network: str
    part_type: str
    name: str
    compatible_materials: List[str] = Field(default_factory=list)
    compatible_sizes_in: List[float] = Field(default_factory=list)
    source: Dict[str, Any] = Field(default_factory=dict)
    review_status: str = "needs_review"
    limitations: List[str] = Field(default_factory=list)


class UtilityCatalogValidationPayload(BaseModel):
    network: str = ""
    features: List[Dict[str, Any]] = Field(default_factory=list)


class CustomerTemplateImportPayload(BaseModel):
    template_id: str = ""
    name: str = ""
    firm_id: str = ""
    firm_name: str = ""
    company: str = ""
    version: str = ""
    review_status: str = "needs_review"
    accepted_by: str = ""
    accepted_date: str = ""
    source_reference: str = ""
    sections: Dict[str, Any] = Field(default_factory=dict)
    notes: List[str] = Field(default_factory=list)


class CustomerTemplateActivatePayload(BaseModel):
    template_id: str = ""


class SurveySlopePayload(BaseModel):
    filename: str


class ExistingConditionsOnlineSourcesPayload(BaseModel):
    address: str = ""
    bbox: Optional[Dict[str, Any]] = None
    parcel_service_url: str = ""
    provider_registry: Dict[str, Any] = Field(default_factory=dict)


class ExistingConditionsOnlineFetchPayload(BaseModel):
    address: str = ""
    bbox: Optional[Dict[str, Any]] = None
    parcel_service_url: str = ""
    parcel_layer_id: int = 0
    building_footprints_service_url: str = ""
    building_footprints_layer_id: int = 0
    roads_service_url: str = ""
    roads_layer_id: int = 0
    utilities_service_url: str = ""
    utilities_layer_id: int = 0
    contours_service_url: str = ""
    contours_layer_id: int = 0
    provider_registry: Dict[str, Any] = Field(default_factory=dict)
    include_floodplain: bool = True
    include_wetlands: bool = True
    include_parcels: bool = True
    include_building_footprints: bool = True
    include_roads: bool = True
    include_utilities: bool = True
    include_contours: bool = True
    include_elevation: bool = True
    include_imagery_detection: bool = True
    active_site_boundary: Dict[str, Any] = Field(default_factory=dict)


class LocalGisProviderRegistryPayload(BaseModel):
    providers: List[Dict[str, Any]] = Field(default_factory=list)


class StandardsDiscoveryPayload(BaseModel):
    city: str = ""
    county: str = ""
    state: str = ""
    utility_provider: str = ""
    extracted_rules: List[Dict[str, Any]] = Field(default_factory=list)


class StandardsAcceptancePayload(BaseModel):
    review_packet: Dict[str, Any] = Field(default_factory=dict)
    accepted_rule_ids: List[str] = Field(default_factory=list)
    edits: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    company_standards: Dict[str, Any] = Field(default_factory=dict)
    accepted_by: str = ""


class StandardsExtractPayload(BaseModel):
    source_url: str
    source_id: str = "official_source"


class StandardsLiveSourceFetchPayload(BaseModel):
    source_url: str
    source_id: str = "live_source"
    source_type: str = ""
    jurisdiction: Dict[str, Any] = Field(default_factory=dict)
    agency: str = ""
    document_title: str = ""
    effective_date: str = ""
    version: str = ""
    allow_network_fetch: bool = False
    source_owner: str = ""
    uploaded_by: str = ""
    allowlist_entries: List[Dict[str, Any]] = Field(default_factory=list)


class StandardsSingleSourceLookupPayload(BaseModel):
    source_url: str
    source_id: str = "single_source_lookup"
    jurisdiction: Dict[str, Any] = Field(default_factory=dict)
    agency: str = ""
    source_type: str = ""
    discipline: str = ""
    operator_authorized: bool = False
    document_title: str = ""
    effective_date: str = ""
    version: str = ""
    source_owner: str = ""
    uploaded_by: str = ""
    allowlist_entries: List[Dict[str, Any]] = Field(default_factory=list)


class GoldenScenarioRunPayload(BaseModel):
    scenario_ids: List[str] = Field(default_factory=list)


class UnitPriceBookPayload(BaseModel):
    unit_price_book: Dict[str, Any] = Field(default_factory=dict)


class UnitPriceBookCsvPayload(BaseModel):
    csv_text: str = ""
    source: str = ""
    location: str = ""
    effective_date: str = ""
    approved_by: str = ""
    approval_date: str = ""
    currency: str = "USD"
    contingency_pct: float = 15.0


class ProfessionalReleasePayload(BaseModel):
    engineer_name: str = ""
    license_number: str = ""
    status: str = ""
    review_date: str = ""
    sealed: bool = False
    jurisdiction: str = ""
    license_jurisdiction: str = ""
    discipline: str = "civil"
    review_scope: str = "civil_site_construction_documents"
    notes: str = ""


class ProfessionalReleaseValidationPayload(BaseModel):
    professional_review: Dict[str, Any] = Field(default_factory=dict)


class ImageAnalysisPayload(BaseModel):
    image_path: Optional[str] = None
    detections: List[Dict[str, Any]] = Field(default_factory=list)
    texts: List[Dict[str, Any]] = Field(default_factory=list)
    image_width: Optional[float] = None
    image_height: Optional[float] = None
    source_name: Optional[str] = None
    source_type: str = "image"
    meta: Dict[str, Any] = Field(default_factory=dict)


class ImageDetectPayload(BaseModel):
    image_path: Optional[str] = None
    source_type: str = "image"
    meta: Dict[str, Any] = Field(default_factory=dict)


class ReviseJobPayload(BaseModel):
    target_phase: Optional[str] = None


def _resolve_orchestration_project_id(
    outer_project_id: Optional[str],
    request_payload: OrchestratePayload,
) -> Optional[str]:
    return outer_project_id or request_payload.project_id


def _orchestration_request_payload(payload: OrchestratePayload) -> Dict[str, Any]:
    request_payload = _model_to_dict(payload)
    if not request_payload.get("prompt_text") and request_payload.get("prompt"):
        request_payload["prompt_text"] = request_payload["prompt"]
    return request_payload


def _queue_request_payload_with_project(
    payload: QueueOrchestratePayload,
) -> tuple[Optional[str], Dict[str, Any]]:
    project_id = _resolve_orchestration_project_id(payload.project_id, payload.request)
    request_payload = _orchestration_request_payload(payload.request)
    if project_id:
        request_payload["project_id"] = project_id
    return project_id, request_payload


app = FastAPI(
    title="Civora AI Backend",
    version=APP_VERSION,
    description="FastAPI backend for Civora AI orchestration.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_allow_origins(),
    # Bearer tokens are sent in headers, so cookies/credentialed CORS are not required.
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _load_orchestrator() -> tuple[Any, Any]:
    try:
        from backend.planning.orchestrator import PlannerOrchestratorRequest, orchestrate_plan
    except ImportError:
        from planner_orchestrator import PlannerOrchestratorRequest, orchestrate_plan
    return PlannerOrchestratorRequest, orchestrate_plan


def _model_to_dict(model: Any) -> Dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def _maybe_export_session(session_id: Optional[str]) -> Dict[str, Any]:
    return application_maybe_export_session(
        session_id,
        export_session_state=(session_state_mod.export_session_state if session_state_mod is not None else None),
    )


def _bearer_token(authorization: Optional[str]) -> str:
    text = str(authorization or "").strip()
    if not text.lower().startswith("bearer "):
        return ""
    return text[7:].strip()


def get_current_user(authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    token = _bearer_token(authorization)
    user = AUTH_STORE.authenticate_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return user


def _latest_project_final_plan_for_payload(
    current_user: Optional[Dict[str, Any]],
    payload_data: Dict[str, Any],
) -> Dict[str, Any]:
    if not current_user:
        return {}
    project_id = str(payload_data.get("project_id") or "").strip()
    if not project_id:
        return {}
    latest_result = PROJECT_STORE.get_project_latest_result(
        user_id=current_user["user_id"],
        project_id=project_id,
    )
    if not isinstance(latest_result, dict):
        return {}
    return dict(latest_result.get("final_plan") or {})


def _run_orchestration(
    payload_data: Dict[str, Any],
    *,
    current_user: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    payload_data = application_prepare_reactive_orchestration_payload(
        payload_data,
        checkpoint_final_plan=_latest_project_final_plan_for_payload(current_user, payload_data),
    )
    project_id = str(payload_data.get("project_id") or "")
    target = str(payload_data.get("meta", {}).get("generation_target") or payload_data.get("plan_type_hint") or "")
    log_memory("orchestration_start", project_id=project_id, target=target)
    try:
        return application_run_orchestration(
            payload_data,
            load_orchestrator=_load_orchestrator,
            assess_design_readiness=assess_design_readiness,
        )
    finally:
        log_memory("orchestration_end", project_id=project_id, target=target)

def _result_from_payload(current_user: Dict[str, Any], payload: ArtifactPayload) -> Dict[str, Any]:
    return application_result_from_payload(
        project_store=PROJECT_STORE,
        user_id=current_user["user_id"],
        project_id=payload.project_id,
        result=dict(payload.result or {}),
        final_plan=dict(payload.final_plan or {}),
    )


def _result_from_job_payload(
    *,
    user_id: str,
    project_id: Optional[str],
    result: Dict[str, Any],
    final_plan: Dict[str, Any],
) -> Dict[str, Any]:
    return application_result_from_payload(
        project_store=PROJECT_STORE,
        user_id=user_id,
        project_id=project_id,
        result=dict(result or {}),
        final_plan=dict(final_plan or {}),
    )


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return float(default)
        return float(value)
    except Exception:
        return float(default)


def _now_ts() -> float:
    return time.time()


def _new_workflow_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _count_unresolved_conflicts(final_plan: Dict[str, Any]) -> int:
    return application_count_unresolved_conflicts(final_plan)


def _build_run_summary(
    result_data: Dict[str, Any],
    *,
    source: str,
    project_id: Optional[str] = None,
    job_id: Optional[str] = None,
) -> Dict[str, Any]:
    return application_build_run_summary(
        result_data,
        source=source,
        project_id=project_id,
        job_id=job_id,
    )


def _merge_project_metadata(
    existing_metadata: Optional[Dict[str, Any]],
    *,
    run_summary: Optional[Dict[str, Any]] = None,
    artifact_summary: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return application_merge_project_metadata(
        existing_metadata,
        run_summary=run_summary,
        artifact_summary=artifact_summary,
    )


def _save_project_workflow_update(
    *,
    user_id: str,
    project_id: str,
    run_summary: Optional[Dict[str, Any]] = None,
    artifact_summary: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    return application_save_project_workflow_update(
        project_store=PROJECT_STORE,
        user_id=user_id,
        project_id=project_id,
        run_summary=run_summary,
        artifact_summary=artifact_summary,
    )


def _artifact_summary(
    *,
    path: Path,
    artifact_kind: str,
    project_id: Optional[str],
    result_data: Dict[str, Any],
) -> Dict[str, Any]:
    return application_artifact_summary(
        path=path,
        artifact_kind=artifact_kind,
        project_id=project_id,
        result_data=result_data,
    )


def _final_plan_from_result(result_data: Dict[str, Any]) -> Dict[str, Any]:
    return application_final_plan_from_result(result_data)


def _mapbox_token() -> tuple[Optional[str], str]:
    for source in ("MAPBOX_TOKEN", "NEXT_PUBLIC_MAPBOX_TOKEN"):
        token = (os.getenv(source) or "").strip()
        if token:
            return source, token
    return None, ""


def _log_mapbox_token_config() -> None:
    source, token = _mapbox_token()
    print(
        json.dumps(
            {
                "event": "mapbox_token_config",
                "present": bool(token),
                "source": source,
                "using_public_fallback": source == "NEXT_PUBLIC_MAPBOX_TOKEN",
            }
        ),
        flush=True,
    )


def _runtime_debug_payload() -> Dict[str, Any]:
    token_source, token = _mapbox_token()
    job_queue = JOB_QUEUE.runtime_stats()
    release_guard = {
        "product_mode": PRODUCT_MODE,
        "review_only": bool(ALPHA_REVIEW_ONLY),
        "construction_release_enabled": bool(CONSTRUCTION_RELEASES_ENABLED) and not bool(ALPHA_REVIEW_ONLY),
        "construction_release_blocked": bool(ALPHA_REVIEW_ONLY) or not bool(CONSTRUCTION_RELEASES_ENABLED),
        "truth_label": "Private alpha is review-only; construction release remains blocked.",
    }
    process_monitoring = runtime_process_monitoring_snapshot(
        state_dir=STORAGE_DIR,
        start_time=START_TIME,
        instance_id=RUNTIME_INSTANCE_ID,
    )
    monitoring = runtime_monitoring_snapshot(job_queue=job_queue, process=process_monitoring)
    alpha_monitoring_report = build_alpha_monitoring_report(monitoring)
    return {
        "status": "ok",
        "pid": os.getpid(),
        "uptime_seconds": round(time.time() - START_TIME, 3),
        "rss_mb": round(current_rss_mb(), 1),
        "peak_rss_mb": round(peak_rss_mb(), 1),
        "product_mode": PRODUCT_MODE,
        "launch_stage": "private_alpha" if ALPHA_REVIEW_ONLY else PRODUCT_MODE,
        "review_only": bool(ALPHA_REVIEW_ONLY),
        "construction_release_guard": release_guard,
        "monitoring": monitoring,
        "alpha_monitoring_report": alpha_monitoring_report,
        "storage_dir_exists": STORAGE_DIR.exists(),
        "storage_kind": DB.storage_kind,
        "mapbox_token_source": token_source,
        "mapbox_token_present": bool(token),
        "port": os.getenv("PORT"),
        "job_queue": job_queue,
    }


def _first_env_value(*names: str) -> str:
    for name in names:
        value = str(os.getenv(name) or "").strip()
        if value:
            return value
    return ""


def _public_api_base_url() -> str:
    configured = _first_env_value("CIVORA_PUBLIC_API_BASE_URL", "PUBLIC_API_BASE_URL", "NEXT_PUBLIC_API_BASE_URL")
    if configured:
        return configured.rstrip("/")
    railway_domain = _first_env_value("RAILWAY_PUBLIC_DOMAIN", "RAILWAY_STATIC_URL")
    if railway_domain:
        if railway_domain.startswith("http://") or railway_domain.startswith("https://"):
            return railway_domain.rstrip("/")
        return f"https://{railway_domain.rstrip('/')}"
    return "https://api.civoraai.com" if PRODUCT_MODE not in {"development", "local"} else ""


def _deployment_metadata() -> Dict[str, str]:
    commit_sha = _first_env_value("VERCEL_GIT_COMMIT_SHA", "RAILWAY_GIT_COMMIT_SHA", "RENDER_GIT_COMMIT", "GIT_COMMIT_SHA")
    return {
        "frontend_status": "unknown",
        "api_base_url": _public_api_base_url(),
        "build_version": _first_env_value("CIVORA_BUILD_VERSION", "VERCEL_GIT_COMMIT_SHA", "RAILWAY_GIT_COMMIT_SHA")[:12] or APP_VERSION,
        "commit_sha": commit_sha[:12] if commit_sha else "",
        "commit_ref": _first_env_value("VERCEL_GIT_COMMIT_REF", "RAILWAY_GIT_BRANCH", "RENDER_GIT_BRANCH", "GIT_BRANCH"),
        "environment": _first_env_value("VERCEL_ENV", "RAILWAY_ENVIRONMENT_NAME", "RENDER_SERVICE_TYPE", "CIVORA_ENVIRONMENT", "NODE_ENV"),
        "provider": "vercel" if os.getenv("VERCEL") else "railway" if os.getenv("RAILWAY_ENVIRONMENT") else "render" if os.getenv("RENDER") else "",
        "last_deploy_time": _first_env_value(
            "CIVORA_LAST_DEPLOY_TIME",
            "VERCEL_DEPLOYMENT_CREATED_AT",
            "RAILWAY_DEPLOYMENT_CREATED_AT",
            "RAILWAY_DEPLOYMENT_START_TIME",
            "RENDER_DEPLOYMENT_CREATED_AT",
        ),
    }


def _support_metadata() -> Dict[str, Any]:
    support_contact = _first_env_value("CIVORA_SUPPORT_CONTACT_URL", "CIVORA_SUPPORT_EMAIL", "CIVORA_SUPPORT_CONTACT")
    bug_report_url = _first_env_value("CIVORA_BUG_REPORT_URL", "CIVORA_BUG_REPORT_FORM_URL")
    escalation_contact = _first_env_value("CIVORA_ESCALATION_CONTACT")
    return {
        "support_contact_configured": bool(support_contact),
        "support_contact": support_contact or "support@civora.ai",
        "bug_report_configured": bool(bug_report_url),
        "bug_report_url": bug_report_url,
        "escalation_configured": bool(escalation_contact),
        "escalation_contact": escalation_contact,
        "user_safe_message": "Use the support contact or bug report path for pilot issues; stop relying on affected outputs when source, review, or export status is unclear.",
    }


def _log_runtime_event(event: str, **fields: Any) -> None:
    print(
        json.dumps(
            {
                "event": event,
                "pid": os.getpid(),
                "uptime_seconds": round(time.time() - START_TIME, 3),
                "rss_mb": round(current_rss_mb(), 1),
                **fields,
            }
        ),
        flush=True,
    )


@app.on_event("startup")
async def _register_job_handlers() -> None:
    try:
        thread_limit = int(os.getenv("CIVORA_ANYIO_THREAD_LIMIT") or "2")
        to_thread.current_default_thread_limiter().total_tokens = max(1, min(8, thread_limit))
    except Exception:
        pass
    log_memory("startup_begin")
    _log_runtime_event("startup_runtime", storage_dir=str(STORAGE_DIR), port=os.getenv("PORT"))
    _log_mapbox_token_config()
    JOB_QUEUE.register_handler(
        "orchestrate",
        application_build_orchestrate_job_runner(
            project_store=PROJECT_STORE,
            update_job_progress=JOB_QUEUE.update_job_progress,
            run_orchestration=_run_orchestration,
            build_run_summary=_build_run_summary,
            merge_project_metadata=_merge_project_metadata,
            final_plan_from_result=application_final_plan_from_result,
        ),
    )
    JOB_QUEUE.register_handler(
        "drainage_only",
        application_build_drainage_job_runner(
            project_store=PROJECT_STORE,
            update_job_progress=JOB_QUEUE.update_job_progress,
        ),
    )
    JOB_QUEUE.register_handler(
        "export_dxf",
        application_build_artifact_export_job_runner(
            artifact_service=ARTIFACTS,
            project_store=PROJECT_STORE,
            update_job_progress=JOB_QUEUE.update_job_progress,
            result_from_payload=_result_from_job_payload,
            export_dxf_artifact=application_export_dxf_artifact,
            export_report_artifact=application_export_report_artifact,
            export_kind="dxf",
        ),
    )
    JOB_QUEUE.register_handler(
        "export_report",
        application_build_artifact_export_job_runner(
            artifact_service=ARTIFACTS,
            project_store=PROJECT_STORE,
            update_job_progress=JOB_QUEUE.update_job_progress,
            result_from_payload=_result_from_job_payload,
            export_dxf_artifact=application_export_dxf_artifact,
            export_report_artifact=application_export_report_artifact,
            export_kind="report",
        ),
    )
    JOB_QUEUE.register_handler(
        "plan_pdf_analysis",
        application_build_plan_pdf_analysis_job_runner(
            upload_dir=UPLOAD_DIR,
            project_store=PROJECT_STORE,
            update_job_progress=JOB_QUEUE.update_job_progress,
        ),
    )
    log_memory("startup_complete")


@app.on_event("shutdown")
def _log_shutdown() -> None:
    _log_runtime_event("shutdown")


@app.get("/")
async def root() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/api/health")
async def health() -> Dict[str, Any]:
    commit_sha = _first_env_value("CIVORA_BUILD_VERSION", "VERCEL_GIT_COMMIT_SHA", "RAILWAY_GIT_COMMIT_SHA")[:12] or APP_VERSION
    api_base_url = _public_api_base_url()
    return {
        "success": True,
        "message": "Civora AI backend is running.",
        "app_name": APP_NAME,
        "version": APP_VERSION,
        "product_mode": PRODUCT_MODE,
        "launch_stage": "private_alpha" if str(PRODUCT_MODE).strip().lower() != "production" else PRODUCT_MODE,
        "review_only": str(PRODUCT_MODE).strip().lower() != "production",
        "auth_enabled": True,
        "storage": DB.storage_kind,
        "deployment": {
            "frontend_status": "unknown",
            "backend_status": "online",
            "api_status": "configured" if api_base_url else "missing_url",
            "api_base_url": api_base_url,
            "auth_status": "enabled",
            "queue_status": "not_checked_on_liveness",
            "build_status": "known" if commit_sha else "unknown",
            "build_version": commit_sha,
            "commit_sha": commit_sha,
            "commit_ref": _first_env_value("VERCEL_GIT_COMMIT_REF", "RAILWAY_GIT_BRANCH", "RENDER_GIT_BRANCH", "GIT_BRANCH"),
            "environment": _first_env_value("VERCEL_ENV", "RAILWAY_ENVIRONMENT_NAME", "RENDER_SERVICE_TYPE", "CIVORA_ENVIRONMENT", "NODE_ENV"),
            "provider": "vercel" if os.getenv("VERCEL") else "railway" if os.getenv("RAILWAY_ENVIRONMENT") else "render" if os.getenv("RENDER") else "",
            "user_safe_messages": [
                "Backend liveness is reachable. Detailed queue/runtime evidence is available from the authenticated runtime endpoint."
            ],
        },
        "support": {
            "support_contact_configured": bool(_first_env_value("CIVORA_SUPPORT_CONTACT_URL", "CIVORA_SUPPORT_EMAIL", "CIVORA_SUPPORT_CONTACT")),
            "support_contact": _first_env_value("CIVORA_SUPPORT_CONTACT_URL", "CIVORA_SUPPORT_EMAIL", "CIVORA_SUPPORT_CONTACT") or "support@civora.ai",
            "bug_report_configured": bool(_first_env_value("CIVORA_BUG_REPORT_URL", "CIVORA_BUG_REPORT_FORM_URL")),
            "bug_report_url": _first_env_value("CIVORA_BUG_REPORT_URL", "CIVORA_BUG_REPORT_FORM_URL"),
        },
        "alpha_review_guard": {
            "review_only": str(PRODUCT_MODE).strip().lower() != "production",
            "construction_release_enabled": False,
            "construction_release_blocked": True,
            "truth_label": "Civora outputs remain review-only unless separately released through professional review gates.",
        },
        "operational_summary": {
            "status": "healthy",
            "mode": PRODUCT_MODE,
            "review_only": str(PRODUCT_MODE).strip().lower() != "production",
            "auth_enabled": True,
            "storage": DB.storage_kind,
            "ready_for_ui": True,
            "runtime_details_endpoint": "/api/debug/runtime",
            "ready_for_public_launch": False,
            "public_beta_blocked": True,
        },
    }


@app.get("/api/debug/runtime")
def debug_runtime(
    current_user: Dict[str, Any] = Depends(get_current_user),
    _rate_limit: None = Depends(rate_limit("debug")),
) -> Dict[str, Any]:
    _ = current_user
    return _runtime_debug_payload()


@app.get("/api/debug/production-env")
def debug_production_env(
    current_user: Dict[str, Any] = Depends(get_current_user),
    _rate_limit: None = Depends(rate_limit("debug")),
) -> Dict[str, Any]:
    _ = current_user
    return validate_production_env_v1()


@app.get("/api/auth/status")
def auth_status(_rate_limit: None = Depends(rate_limit("auth"))) -> Dict[str, Any]:
    connection = DB.connect()
    try:
        user_count = int(connection.execute("SELECT COUNT(*) FROM users").fetchone()[0])
    finally:
        connection.close()
    return application_auth_status(user_count=user_count)


@app.post("/api/auth/register")
def register(payload: RegisterPayload, _rate_limit: None = Depends(rate_limit("auth"))) -> Dict[str, Any]:
    connection = DB.connect()
    try:
        user_count = int(connection.execute("SELECT COUNT(*) FROM users").fetchone()[0])
    finally:
        connection.close()
    if user_count > 0 and not _public_registration_allowed():
        raise HTTPException(status_code=403, detail="Public registration is disabled for private alpha.")
    return application_register_user(
        auth_store=AUTH_STORE,
        email=payload.email,
        password=payload.password,
        name=payload.name,
    )


@app.post("/api/auth/login")
def login(payload: LoginPayload, _rate_limit: None = Depends(rate_limit("auth"))) -> Dict[str, Any]:
    return application_login_user(
        auth_store=AUTH_STORE,
        email=payload.email,
        password=payload.password,
    )


@app.get("/api/auth/me")
def me(
    current_user: Dict[str, Any] = Depends(get_current_user),
    _rate_limit: None = Depends(rate_limit("auth")),
) -> Dict[str, Any]:
    response = application_current_user_response(current_user=current_user)
    response["billing_status_v1"] = build_billing_status(user=current_user)
    return response


@app.get("/api/billing/status")
def billing_status(
    current_user: Dict[str, Any] = Depends(get_current_user),
    _rate_limit: None = Depends(rate_limit("auth")),
) -> Dict[str, Any]:
    return build_billing_status(user=current_user)


@app.post("/api/auth/logout")
def logout(
    authorization: Optional[str] = Header(default=None),
    _rate_limit: None = Depends(rate_limit("auth")),
) -> Dict[str, Any]:
    return application_logout_user(
        auth_store=AUTH_STORE,
        token=_bearer_token(authorization),
    )


@app.post("/api/upload-image")
async def upload_image(
    file: UploadFile = File(...),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _rate_limit: None = Depends(rate_limit("upload")),
) -> Dict[str, Any]:
    return application_upload_image_file(
        upload_dir=UPLOAD_DIR,
        file=file,
        current_user=current_user,
    )


@app.post("/api/upload-survey")
async def upload_survey(
    file: UploadFile = File(...),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _rate_limit: None = Depends(rate_limit("upload")),
) -> Dict[str, Any]:
    return application_upload_survey_file(
        upload_dir=UPLOAD_DIR,
        file=file,
        current_user=current_user,
    )


@app.post("/api/upload-existing-conditions")
async def upload_existing_conditions(
    file: UploadFile = File(...),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _rate_limit: None = Depends(rate_limit("upload")),
) -> Dict[str, Any]:
    return application_upload_existing_conditions_file(
        upload_dir=UPLOAD_DIR,
        file=file,
        current_user=current_user,
    )


@app.post("/api/upload-plan-pdf")
async def upload_plan_pdf(
    file: UploadFile = File(...),
    project_id: str = Form(default=""),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _rate_limit: None = Depends(rate_limit("upload")),
) -> Dict[str, Any]:
    return application_upload_plan_pdf_file(
        upload_dir=UPLOAD_DIR,
        file=file,
        current_user=current_user,
        project_store=PROJECT_STORE,
        job_queue=JOB_QUEUE,
        project_id=project_id,
    )


@app.post("/api/existing-conditions/online-sources")
def existing_conditions_online_sources(
    payload: ExistingConditionsOnlineSourcesPayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
    _rate_limit: None = Depends(rate_limit("geocode")),
) -> Dict[str, Any]:
    _ = current_user
    return application_existing_conditions_online_sources(
        address=payload.address,
        bbox=payload.bbox,
        parcel_service_url=payload.parcel_service_url,
        provider_registry=payload.provider_registry,
    )


@app.post("/api/existing-conditions/fetch-online")
def fetch_existing_conditions_online(
    payload: ExistingConditionsOnlineFetchPayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
    _rate_limit: None = Depends(rate_limit("geocode")),
) -> Dict[str, Any]:
    _ = current_user
    return application_fetch_existing_conditions_online(
        address=payload.address,
        bbox=payload.bbox,
        parcel_service_url=payload.parcel_service_url,
        parcel_layer_id=payload.parcel_layer_id,
        building_footprints_service_url=payload.building_footprints_service_url,
        building_footprints_layer_id=payload.building_footprints_layer_id,
        roads_service_url=payload.roads_service_url,
        roads_layer_id=payload.roads_layer_id,
        utilities_service_url=payload.utilities_service_url,
        utilities_layer_id=payload.utilities_layer_id,
        contours_service_url=payload.contours_service_url,
        contours_layer_id=payload.contours_layer_id,
        provider_registry=payload.provider_registry,
        include_floodplain=payload.include_floodplain,
        include_wetlands=payload.include_wetlands,
        include_parcels=payload.include_parcels,
        include_building_footprints=payload.include_building_footprints,
        include_roads=payload.include_roads,
        include_utilities=payload.include_utilities,
        include_contours=payload.include_contours,
        include_elevation=payload.include_elevation,
        include_imagery_detection=payload.include_imagery_detection,
        active_site_boundary=payload.active_site_boundary,
    )


@app.post("/api/existing-conditions/provider-registry")
def local_gis_provider_registry(
    payload: LocalGisProviderRegistryPayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
    _rate_limit: None = Depends(rate_limit("geocode")),
) -> Dict[str, Any]:
    _ = current_user
    return application_build_local_gis_provider_registry(providers=payload.providers)


@app.post("/api/existing-conditions/provider-registry/check-health")
def local_gis_provider_registry_health(
    payload: LocalGisProviderRegistryPayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
    _rate_limit: None = Depends(rate_limit("geocode")),
) -> Dict[str, Any]:
    _ = current_user
    return application_check_local_gis_provider_registry(providers=payload.providers)


@app.post("/api/standards/discover")
def discover_standards(
    payload: StandardsDiscoveryPayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    _ = current_user
    return application_discover_standards_response(
        city=payload.city,
        county=payload.county,
        state=payload.state,
        utility_provider=payload.utility_provider,
    )


@app.post("/api/standards/review-packet")
def standards_review_packet(
    payload: StandardsDiscoveryPayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    _ = current_user
    return application_standards_review_packet_response(
        city=payload.city,
        county=payload.county,
        state=payload.state,
        utility_provider=payload.utility_provider,
        extracted_rules=payload.extracted_rules,
    )


@app.post("/api/standards/accept")
def accept_standards(
    payload: StandardsAcceptancePayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    accepted_by = payload.accepted_by or str(current_user.get("user_id") or current_user.get("email") or "")
    return application_accept_standards_response(
        review_packet=payload.review_packet,
        accepted_rule_ids=payload.accepted_rule_ids,
        edits=payload.edits,
        company_standards=payload.company_standards,
        accepted_by=accepted_by,
    )


@app.post("/api/standards/extract")
def extract_standards(
    payload: StandardsExtractPayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    _ = current_user
    return application_extract_standards_candidates_response(
        source_url=payload.source_url,
        source_id=payload.source_id,
    )


@app.get("/api/standards/live-source-policy")
def standards_live_source_policy(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    _ = current_user
    return application_standards_live_source_policy_response()


@app.post("/api/standards/live-source-candidate")
def fetch_live_standards_source_candidate(
    payload: StandardsLiveSourceFetchPayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    _ = current_user
    return application_fetch_live_standards_source_candidate_response(
        source_url=payload.source_url,
        source_id=payload.source_id,
        source_type=payload.source_type,
        jurisdiction=payload.jurisdiction,
        agency=payload.agency,
        document_title=payload.document_title,
        effective_date=payload.effective_date,
        version=payload.version,
        allow_network_fetch=payload.allow_network_fetch,
        source_owner=payload.source_owner,
        uploaded_by=payload.uploaded_by,
        allowlist_entries=payload.allowlist_entries,
    )


@app.post("/api/standards/single-source-lookup")
def controlled_single_source_lookup(
    payload: StandardsSingleSourceLookupPayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    _ = current_user
    return application_controlled_single_source_lookup_response(
        source_url=payload.source_url,
        source_id=payload.source_id,
        jurisdiction=payload.jurisdiction,
        agency=payload.agency,
        source_type=payload.source_type,
        discipline=payload.discipline,
        operator_authorized=payload.operator_authorized,
        document_title=payload.document_title,
        effective_date=payload.effective_date,
        version=payload.version,
        source_owner=payload.source_owner,
        uploaded_by=payload.uploaded_by,
        allowlist_entries=payload.allowlist_entries,
    )


@app.get("/api/utility-catalogs")
def utility_catalogs(
    current_user: Dict[str, Any] = Depends(get_current_user),
    _rate_limit: None = Depends(rate_limit("planner")),
) -> Dict[str, Any]:
    _ = current_user
    return GLOBAL_UTILITY_CATALOG_MANAGER.snapshot()


@app.get("/api/utility-catalogs/pipe-sizes")
def utility_catalog_pipe_sizes(
    network: str = "",
    material: str = "",
    accepted_only: bool = False,
    current_user: Dict[str, Any] = Depends(get_current_user),
    _rate_limit: None = Depends(rate_limit("planner")),
) -> Dict[str, Any]:
    _ = current_user
    return GLOBAL_UTILITY_CATALOG_MANAGER.available_pipe_sizes(
        network=network,
        material=material,
        accepted_only=accepted_only,
    )


@app.post("/api/utility-catalogs/pipes")
def utility_catalog_add_pipe(
    payload: UtilityPipeCatalogPayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
    _rate_limit: None = Depends(rate_limit("planner")),
) -> Dict[str, Any]:
    _ = current_user
    result = GLOBAL_UTILITY_CATALOG_MANAGER.add_pipe_catalog(_model_to_dict(payload))
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result)
    return result


@app.post("/api/utility-catalogs/parts")
def utility_catalog_add_part(
    payload: UtilityPartCatalogPayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
    _rate_limit: None = Depends(rate_limit("planner")),
) -> Dict[str, Any]:
    _ = current_user
    result = GLOBAL_UTILITY_CATALOG_MANAGER.add_part_catalog(_model_to_dict(payload))
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result)
    return result


@app.post("/api/utility-catalogs/validate-network")
def utility_catalog_validate_network(
    payload: UtilityCatalogValidationPayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
    _rate_limit: None = Depends(rate_limit("planner")),
) -> Dict[str, Any]:
    _ = current_user
    return GLOBAL_UTILITY_CATALOG_MANAGER.validate_network(_model_to_dict(payload))


@app.get("/api/customer-templates")
def customer_template_registry(
    current_user: Dict[str, Any] = Depends(get_current_user),
    _rate_limit: None = Depends(rate_limit("planner")),
) -> Dict[str, Any]:
    _ = current_user
    return application_customer_template_registry_response()


@app.get("/api/customer-templates/export")
def customer_template_export(
    current_user: Dict[str, Any] = Depends(get_current_user),
    _rate_limit: None = Depends(rate_limit("planner")),
) -> Dict[str, Any]:
    _ = current_user
    return application_export_customer_templates_response()


@app.get("/api/customer-templates/missing")
def customer_template_missing(
    template_id: str = "",
    current_user: Dict[str, Any] = Depends(get_current_user),
    _rate_limit: None = Depends(rate_limit("planner")),
) -> Dict[str, Any]:
    _ = current_user
    return application_explain_missing_customer_template_response(template_id)


@app.post("/api/customer-templates/import")
def customer_template_import(
    payload: CustomerTemplateImportPayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
    _rate_limit: None = Depends(rate_limit("planner")),
) -> Dict[str, Any]:
    _ = current_user
    result = application_import_customer_template_response(_model_to_dict(payload))
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result)
    return result


@app.post("/api/customer-templates/activate")
def customer_template_activate(
    payload: CustomerTemplateActivatePayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
    _rate_limit: None = Depends(rate_limit("planner")),
) -> Dict[str, Any]:
    _ = current_user
    result = application_activate_customer_template_response(payload.template_id)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result)
    return result


@app.post("/api/golden-scenarios/run")
def run_golden_scenarios(
    payload: GoldenScenarioRunPayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    _ = current_user
    return application_run_golden_scenarios_response(
        scenario_ids=payload.scenario_ids or None,
    )


@app.post("/api/cost/unit-price-book/normalize")
def normalize_unit_price_book(
    payload: UnitPriceBookPayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    _ = current_user
    return application_normalize_unit_price_book_response(payload.unit_price_book)


@app.post("/api/cost/unit-price-book/validate")
def validate_unit_price_book(
    payload: UnitPriceBookPayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    _ = current_user
    return application_validate_unit_price_book_response(payload.unit_price_book)


@app.post("/api/cost/unit-price-book/from-csv")
def unit_price_book_from_csv(
    payload: UnitPriceBookCsvPayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    _ = current_user
    return application_unit_price_book_from_csv_response(
        csv_text=payload.csv_text,
        source=payload.source,
        location=payload.location,
        effective_date=payload.effective_date,
        approved_by=payload.approved_by,
        approval_date=payload.approval_date,
        currency=payload.currency,
        contingency_pct=payload.contingency_pct,
    )


@app.post("/api/professional-release/build")
def build_professional_release(
    payload: ProfessionalReleasePayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    _ = current_user
    return application_professional_release_response(
        engineer_name=payload.engineer_name,
        license_number=payload.license_number,
        status=payload.status,
        review_date=payload.review_date,
        sealed=payload.sealed,
        jurisdiction=payload.jurisdiction,
        license_jurisdiction=payload.license_jurisdiction,
        discipline=payload.discipline,
        review_scope=payload.review_scope,
        notes=payload.notes,
    )


@app.post("/api/professional-release/validate")
def validate_professional_release(
    payload: ProfessionalReleaseValidationPayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    _ = current_user
    return application_validate_professional_release_response(payload.professional_review)


@app.post("/api/survey/estimate-slope")
def estimate_survey_slope(
    payload: SurveySlopePayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    return application_estimate_slope_from_survey(
        upload_dir=UPLOAD_DIR,
        current_user=current_user,
        filename=payload.filename,
    )


@app.post("/api/survey/points")
def get_survey_points(
    payload: SurveySlopePayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    return application_read_survey_points(
        upload_dir=UPLOAD_DIR,
        current_user=current_user,
        filename=payload.filename,
    )


@app.post("/api/image/analyze")
def analyze_image(
    payload: ImageAnalysisPayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    log_memory("image_analyze_start", image_path=payload.image_path)
    try:
        from vision.image_analysis_engine import ImageAnalysisEngine
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Image analysis unavailable: {exc}")

    engine = ImageAnalysisEngine()
    analysis_input = engine.from_detection_dict(
        {
            "detections": payload.detections,
            "texts": payload.texts,
            "image_width": payload.image_width,
            "image_height": payload.image_height,
            "source_name": payload.source_name or payload.image_path,
            "source_type": payload.source_type or "image",
            "meta": payload.meta,
        }
    )
    result = engine.analyze(analysis_input)
    try:
        return {
            "success": result.success,
            "message": result.message,
            "counts": result.counts,
            "warnings": result.warnings,
            "meta": result.meta,
        }
    finally:
        log_memory("image_analyze_end", image_path=payload.image_path)


@app.post("/api/image/detect-features")
def detect_image_features(
    payload: ImageDetectPayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    log_memory("image_detect_start", image_path=payload.image_path)
    try:
        from vision.feature_detection_engine import FeatureDetectionEngine
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Feature detection unavailable: {exc}")

    if not payload.image_path:
        raise HTTPException(status_code=400, detail="Image path is required for detection.")

    engine = FeatureDetectionEngine()
    result = engine.detect(payload.image_path)
    try:
        detections = [
            {
                "kind": det.kind,
                "bbox": det.bbox,
                "confidence": det.confidence,
                "geometry_type": det.geometry_type,
                "geometry": det.geometry,
                "image_path": payload.image_path,
            }
            for det in result.detections
        ]
        return {
            "success": result.success,
            "message": result.message,
            "image_width": result.image_width,
            "image_height": result.image_height,
            "detections": detections,
            "map_feature_detection_report_v1": build_map_feature_detection_report(image_detections=detections),
            "warnings": result.warnings,
            "meta": result.meta,
        }
    finally:
        log_memory("image_detect_end", image_path=payload.image_path)


def _blocked_geocode_response(
    *,
    address: str,
    provider: str,
    status: str,
    message: str,
    blocker_code: str,
) -> GeocodeResponse:
    geocode_record = {
        "success": False,
        "status": status,
        "display_name": address,
        "formatted_address": address,
        "matched_address": "",
        "normalized_address": "",
        "provider": provider,
        "source_type": "mapbox_geocoder",
        "crs": {"epsg": "EPSG:4326", "name": "WGS 84 geographic coordinates", "units": "degrees", "source": "mapbox_geocoder"},
        "warnings": [message],
        "blockers": [{"area": "geocode", "code": blocker_code, "message": message}],
    }
    return GeocodeResponse(
        success=False,
        status=status,
        blocked=True,
        display_name=address,
        provider=provider,
        message=message,
        warnings=[message],
        blockers=geocode_record["blockers"],
        crs=geocode_record["crs"],
        location_context=location_context_from_geocode(address=address, geocode=geocode_record),
    )


@app.post("/api/geocode", response_model=GeocodeResponse)
def geocode_address(
    payload: GeocodePayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
    _rate_limit: None = Depends(rate_limit("geocode")),
) -> GeocodeResponse:
    address = str(payload.address or "").strip()
    if not address:
        raise HTTPException(status_code=400, detail="Address is required.")
    _, token = _mapbox_token()
    if not token:
        return _blocked_geocode_response(
            address=address,
            provider="mapbox",
            status="provider_not_configured",
            message="Geocode provider is not configured for this environment.",
            blocker_code="provider_config_missing",
        )
    try:
        with httpx.Client(timeout=8.0) as client:
            resp = client.get(
                f"https://api.mapbox.com/geocoding/v5/mapbox.places/{urllib.parse.quote(address)}.json",
                params={"access_token": token, "limit": 1},
                headers={"User-Agent": "CivoraAI/0.1 (contact: support@civora.ai)"},
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code if exc.response is not None else "unknown"
        if status_code == 403:
            message = "Geocode provider rejected the configured credentials for this environment."
            blocker_code = "provider_credentials_rejected"
        else:
            message = "Geocode provider returned an unavailable response."
            blocker_code = "provider_unavailable"
        return _blocked_geocode_response(
            address=address,
            provider="mapbox",
            status="provider_unavailable",
            message=message,
            blocker_code=blocker_code,
        )
    except Exception:
        return _blocked_geocode_response(
            address=address,
            provider="mapbox",
            status="provider_failed",
            message="Geocode provider request failed before a valid response was parsed.",
            blocker_code="provider_request_failed",
        )
    features = data.get("features") if isinstance(data, dict) else None
    if not features:
        return _blocked_geocode_response(
            address=address,
            provider="mapbox",
            status="not_found",
            message="Address could not be geocoded by the configured provider.",
            blocker_code="address_not_found",
        )
    first = features[0] if isinstance(features, list) else None
    try:
        center = first.get("center") if isinstance(first, dict) else None
        if not center or len(center) < 2:
            raise ValueError("Missing center")
        lng = float(center[0])
        lat = float(center[1])
    except Exception:
        return _blocked_geocode_response(
            address=address,
            provider="mapbox",
            status="provider_invalid_response",
            message="Geocode provider returned an incomplete coordinate response.",
            blocker_code="provider_invalid_response",
        )
    display_name = str(first.get("place_name") or address) if isinstance(first, dict) else address
    geocode_record = {
        "success": True,
        "status": "ready",
        "lat": lat,
        "lng": lng,
        "display_name": display_name,
        "formatted_address": display_name,
        "matched_address": display_name,
        "normalized_address": display_name,
        "provider": "mapbox",
        "source_type": "mapbox_geocoder",
        "source": "https://api.mapbox.com/geocoding/v5/mapbox.places",
        "crs": {"epsg": "EPSG:4326", "name": "WGS 84 geographic coordinates", "units": "degrees", "source": "mapbox_geocoder"},
    }
    location_context = location_context_from_geocode(address=address, geocode=geocode_record)
    return GeocodeResponse(
        lat=lat,
        lng=lng,
        display_name=display_name,
        provider="mapbox",
        confidence=None,
        formatted_address=display_name,
        place_name=display_name,
        normalized_address=display_name,
        crs=geocode_record["crs"],
        location_context=location_context,
    )


@app.get("/api/uploads/{filename}")
def get_uploaded_image(
    filename: str,
    authorization: Optional[str] = Header(default=None),
    access_token: Optional[str] = Query(default=None),
    _rate_limit: None = Depends(rate_limit("export")),
) -> FileResponse:
    token = str(access_token or "").strip() or _bearer_token(authorization)
    return application_get_uploaded_image_response(
        upload_dir=UPLOAD_DIR,
        auth_store=AUTH_STORE,
        filename=filename,
        token=token,
    )


@app.post("/api/chat/decide")
def chat_decide(
    payload: ChatDecisionPayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
    _rate_limit: None = Depends(rate_limit("chat")),
) -> Dict[str, Any]:
    try:
        return application_decide_chat(
            _model_to_dict(payload),
            decide_chat_message=decide_chat_message,
            project_store=PROJECT_STORE,
            user_id=current_user["user_id"],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/chat/feedback")
def chat_feedback(
    payload: ChatFeedbackPayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
    _rate_limit: None = Depends(rate_limit("chat")),
) -> Dict[str, Any]:
    from backend.services.chat_learning_store import (
        append_chat_learning_event,
        append_chat_training_example,
    )

    data = _model_to_dict(payload)
    feedback = str(data.get("feedback") or "").strip().lower()
    if feedback not in {"up", "down"}:
        raise HTTPException(status_code=400, detail="Feedback must be 'up' or 'down'.")
    project_id = data.get("project_id")
    if project_id:
        record = PROJECT_STORE.get_project(user_id=current_user["user_id"], project_id=project_id)
        if record:
            project_input = dict(record.get("project_input") or {})
            meta = dict(project_input.get("meta") or {})
            history = list(meta.get("chat_feedback") or [])
            history.append(
                {
                    "message_id": data.get("message_id"),
                    "feedback": feedback,
                    "message": data.get("message"),
                    "assistant_message": data.get("assistant_message"),
                }
            )
            meta["chat_feedback"] = history[-50:]
            project_input["meta"] = meta
            PROJECT_STORE.save_project(
                user_id=current_user["user_id"],
                project_id=record.get("project_id"),
                name=record.get("name") or "Untitled Project",
                description=record.get("description") or "",
                session_id=record.get("session_id"),
                tags=record.get("tags") or [],
                project_input=project_input,
                latest_result=record.get("latest_result") or {},
                session_state=record.get("session_state") or {},
                metadata=record.get("metadata") or {},
            )

    append_chat_learning_event(
        {
            "event_type": "feedback",
            "user_id": current_user["user_id"],
            "project_id": project_id,
            "message_id": data.get("message_id"),
            "feedback": feedback,
            "message": data.get("message"),
            "assistant_message": data.get("assistant_message"),
        }
    )

    if feedback in {"up", "down"}:
        append_chat_training_example(
            {
                "user_id": current_user["user_id"],
                "project_id": project_id,
                "message_id": data.get("message_id"),
                "feedback": feedback,
                "input": data.get("message"),
                "output": data.get("assistant_message"),
            }
        )
    return {"success": True}


@app.post("/api/cron/chat-learning")
def chat_learning_cron(
    payload: ChatLearningCronPayload,
    x_cron_secret: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    token = str(x_cron_secret or "").strip()
    if not token and authorization:
        auth_value = str(authorization or "").strip()
        if auth_value.lower().startswith("bearer "):
            token = auth_value[7:].strip()
    if not CRON_SECRET:
        raise HTTPException(status_code=503, detail="Cron endpoint is disabled until CIVORA_CRON_SECRET is configured.")
    if CRON_SECRET and token != CRON_SECRET:
        raise HTTPException(status_code=401, detail="Invalid cron secret.")
    from backend.services.chat_learning_store import chat_learning_enabled

    if not chat_learning_enabled():
        return {"success": True, "disabled": True, "result": None}
    from backend.services.chat_learning_pipeline import run_chat_learning_pipeline

    result = run_chat_learning_pipeline(
        input_path=CHAT_LEARNING_PATH,
        output_path=CHAT_TRAINING_PATH,
        report_path=CHAT_LEARNING_REPORT_PATH,
        max_examples=payload.max_examples,
        max_synthetic=payload.max_synthetic,
        max_unrated=payload.max_unrated,
        exclude_unrated=payload.exclude_unrated,
    )
    return {"success": True, "result": result}


@app.get("/api/chat/learning-report")
def chat_learning_report(
    payload: ChatLearningReportPayload = Depends(),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    _ = current_user
    from backend.services.chat_learning_store import chat_learning_enabled

    if not chat_learning_enabled():
        return {"success": True, "disabled": True, "report": None}
    report_path = Path(payload.report_path or CHAT_LEARNING_REPORT_PATH).resolve()
    base = DATA_DIR.resolve()
    if base not in report_path.parents and report_path != base:
        raise HTTPException(status_code=403, detail="Invalid report path.")
    if not report_path.exists():
        return {"success": True, "report": None}
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception:
        report = None
    return {"success": True, "report": report}


@app.post("/api/orchestrate")
def orchestrate(
    payload: OrchestratePayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
    _rate_limit: None = Depends(rate_limit("planner")),
) -> Dict[str, Any]:
    result = _run_orchestration(_orchestration_request_payload(payload), current_user=current_user)
    metadata = dict(result.get("metadata") or {})
    metadata["billing_usage_gate_v1"] = usage_gate(action="orchestrate", user=current_user)
    result["metadata"] = metadata
    return result


@app.get("/api/projects")
def list_projects(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    return application_list_projects(
        project_store=PROJECT_STORE,
        user_id=current_user["user_id"],
    )


@app.post("/api/projects")
def save_project(payload: SaveProjectPayload, current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    return application_save_project_record(
        project_store=PROJECT_STORE,
        user_id=current_user["user_id"],
        payload_data=_model_to_dict(payload),
        export_session_state=_maybe_export_session,
        build_run_summary=_build_run_summary,
    )


@app.get("/api/projects/{project_id}")
def get_project(project_id: str, current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    return application_get_project_detail(
        project_store=PROJECT_STORE,
        user_id=current_user["user_id"],
        project_id=project_id,
    )


@app.get("/api/projects/{project_id}/result")
def get_project_result(project_id: str, current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    return application_get_project_result(
        project_store=PROJECT_STORE,
        user_id=current_user["user_id"],
        project_id=project_id,
    )


@app.get("/api/projects/{project_id}/admin")
def get_project_admin(project_id: str, current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    surface = PROJECT_STORE.project_admin_surface(user_id=current_user["user_id"], project_id=project_id)
    if surface is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return {"success": True, **surface}


@app.post("/api/projects/{project_id}/admin/invites")
def invite_project_member(
    project_id: str,
    payload: ProjectInvitePayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    try:
        invite = PROJECT_STORE.invite_project_member(
            actor_user_id=current_user["user_id"],
            project_id=project_id,
            email=payload.email,
            role=payload.role,
        )
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return {"success": True, "invite": invite}


@app.delete("/api/projects/{project_id}/admin/members/{member_user_id}")
def remove_project_member(
    project_id: str,
    member_user_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    try:
        removed = PROJECT_STORE.remove_project_member(
            actor_user_id=current_user["user_id"],
            project_id=project_id,
            user_id=member_user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if not removed:
        raise HTTPException(status_code=404, detail="Project member not found.")
    return {"success": True, "project_id": project_id, "removed_user_id": member_user_id}


@app.get("/api/projects/{project_id}/admin/audit")
def get_project_access_audit(project_id: str, current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    return {
        "success": True,
        "project_id": project_id,
        "audit_log": PROJECT_STORE.project_audit_log(user_id=current_user["user_id"], project_id=project_id, limit=100),
    }


@app.get("/api/projects/{project_id}/candidate-review-inbox")
def get_project_candidate_review_inbox(project_id: str, current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    return application_get_project_candidate_review_inbox(
        project_store=PROJECT_STORE,
        user_id=current_user["user_id"],
        project_id=project_id,
    )


@app.get("/api/projects/{project_id}/source-confidence")
def get_project_source_confidence_map(project_id: str, current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    return application_get_project_source_confidence_map(
        project_store=PROJECT_STORE,
        user_id=current_user["user_id"],
        project_id=project_id,
    )


@app.get("/api/projects/{project_id}/design-alternatives")
def get_project_design_alternatives(project_id: str, current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    return application_get_project_design_alternatives(
        project_store=PROJECT_STORE,
        user_id=current_user["user_id"],
        project_id=project_id,
    )


@app.post("/api/projects/{project_id}/design-alternatives")
def update_project_design_alternatives(
    project_id: str,
    payload: DesignAlternativesPayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    return application_update_project_design_alternatives(
        project_store=PROJECT_STORE,
        user_id=current_user["user_id"],
        project_id=project_id,
        action=payload.action,
        requested_count=payload.requested_count,
        option_number=payload.option_number,
        alternative_id=payload.alternative_id,
        reason=payload.reason,
        reviewer_id=str(current_user.get("user_id") or current_user.get("email") or ""),
    )


@app.post("/api/projects/{project_id}/candidate-review")
def review_project_candidates(
    project_id: str,
    payload: CandidateReviewPayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    return application_review_project_candidates(
        project_store=PROJECT_STORE,
        user_id=current_user["user_id"],
        project_id=project_id,
        candidate_ids=payload.candidate_ids,
        action=payload.action,
        reason=payload.reason,
        reviewer_id=str(current_user.get("user_id") or current_user.get("email") or ""),
    )


@app.get("/api/projects/{project_id}/plan-pdf/report")
def get_project_plan_pdf_report(project_id: str, current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    return application_get_project_plan_pdf_report(
        project_store=PROJECT_STORE,
        user_id=current_user["user_id"],
        project_id=project_id,
    )


@app.get("/api/projects/{project_id}/plan-pdf/report/download")
def download_project_plan_pdf_report(project_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    return application_download_project_plan_pdf_report(
        project_store=PROJECT_STORE,
        user_id=current_user["user_id"],
        project_id=project_id,
    )


@app.patch("/api/projects/{project_id}/plan-pdf/elements/{element_id}")
def update_project_plan_pdf_element(
    project_id: str,
    element_id: str,
    payload: PlanPdfElementUpdatePayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    return application_update_project_plan_pdf_element(
        project_store=PROJECT_STORE,
        user_id=current_user["user_id"],
        project_id=project_id,
        element_id=element_id,
        updates={key: value for key, value in _model_to_dict(payload).items() if value is not None},
    )


@app.delete("/api/projects/{project_id}")
def delete_project(project_id: str, current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    return application_delete_project_record(
        project_store=PROJECT_STORE,
        job_queue=JOB_QUEUE,
        artifact_service=ARTIFACTS,
        user_id=current_user["user_id"],
        project_id=project_id,
    )


@app.get("/api/jobs")
def list_jobs(
    current_user: Dict[str, Any] = Depends(get_current_user),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> Dict[str, Any]:
    page = JOB_QUEUE.list_jobs_page(user_id=current_user["user_id"], limit=limit, offset=offset)
    return {
        "success": True,
        "jobs": page["jobs"],
        "pagination": page["pagination"],
    }


@app.post("/api/jobs/orchestrate")
def queue_orchestrate_job(
    payload: QueueOrchestratePayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
    _rate_limit: None = Depends(rate_limit("planner")),
) -> Dict[str, Any]:
    project_id, request_payload = _queue_request_payload_with_project(payload)
    response = application_queue_orchestrate_job(
        project_store=PROJECT_STORE,
        job_queue=JOB_QUEUE,
        user_id=current_user["user_id"],
        project_id=project_id,
        request_payload=request_payload,
    )
    response["billing_usage_gate_v1"] = usage_gate(action="queue_orchestrate_job", user=current_user)
    return response


@app.post("/api/jobs/drainage")
def queue_drainage_job(
    payload: QueueDrainagePayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
    _rate_limit: None = Depends(rate_limit("planner")),
) -> Dict[str, Any]:
    project_id, request_payload = _queue_request_payload_with_project(payload)
    return application_queue_drainage_job(
        project_store=PROJECT_STORE,
        job_queue=JOB_QUEUE,
        user_id=current_user["user_id"],
        project_id=project_id,
        request_payload=request_payload,
    )


@app.post("/api/jobs/export/dxf")
def queue_export_dxf_job(
    payload: QueueArtifactExportPayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
    _rate_limit: None = Depends(rate_limit("export")),
) -> Dict[str, Any]:
    response = application_queue_artifact_export_job(
        project_store=PROJECT_STORE,
        job_queue=JOB_QUEUE,
        user_id=current_user["user_id"],
        project_id=payload.project_id,
        request_payload=_model_to_dict(payload),
        export_kind="dxf",
    )
    response["billing_usage_gate_v1"] = usage_gate(action="queue_export_dxf_job", user=current_user)
    return response


@app.post("/api/jobs/export/report")
def queue_export_report_job(
    payload: QueueArtifactExportPayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
    _rate_limit: None = Depends(rate_limit("export")),
) -> Dict[str, Any]:
    response = application_queue_artifact_export_job(
        project_store=PROJECT_STORE,
        job_queue=JOB_QUEUE,
        user_id=current_user["user_id"],
        project_id=payload.project_id,
        request_payload=_model_to_dict(payload),
        export_kind="report",
    )
    response["billing_usage_gate_v1"] = usage_gate(action="queue_export_report_job", user=current_user)
    return response


@app.post("/api/preview")
def build_preview(
    payload: ArtifactPayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
    _rate_limit: None = Depends(rate_limit("planner")),
) -> Dict[str, Any]:
    try:
        result_data = _result_from_payload(current_user, payload)
    except HTTPException as exc:
        detail = str(exc.detail or "").lower()
        if exc.status_code == 400 and "no saved planner result" in detail and payload.project_id:
            project = PROJECT_STORE.get_project(
                user_id=current_user["user_id"],
                project_id=payload.project_id,
            )
            project_input = dict(project.get("project_input") or {}) if isinstance(project, dict) else {}
            if not project_input:
                raise
            result_data = {"project_input": project_input, "request_metadata": {"project_input": project_input}}
        else:
            raise
    return application_build_preview_response(
        artifact_service=ARTIFACTS,
        result_data=result_data,
        project_store=PROJECT_STORE,
        user_id=current_user["user_id"],
        project_id=payload.project_id,
        preview_quality=payload.preview_quality,
        preview_style=payload.preview_style,
        label_density=payload.label_density,
        render_labels=payload.render_labels,
        preview_layers=payload.preview_layers,
        preview_mode=payload.preview_mode,
    )


@app.post("/api/export/dxf")
def export_dxf(
    payload: ArtifactPayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
    _rate_limit: None = Depends(rate_limit("export")),
) -> FileResponse:
    result_data = _result_from_payload(current_user, payload)
    path = application_export_dxf_artifact(
        artifact_service=ARTIFACTS,
        project_store=PROJECT_STORE,
        user_id=current_user["user_id"],
        project_id=payload.project_id,
        result_data=result_data,
        filename_stem=payload.filename_stem,
    )
    return FileResponse(
        path,
        media_type="application/dxf",
        filename=path.name,
    )


@app.post("/api/export/report")
def export_report(
    payload: ArtifactPayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
    _rate_limit: None = Depends(rate_limit("export")),
) -> FileResponse:
    result_data = _result_from_payload(current_user, payload)
    path = application_export_report_artifact(
        artifact_service=ARTIFACTS,
        project_store=PROJECT_STORE,
        user_id=current_user["user_id"],
        project_id=payload.project_id,
        result_data=result_data,
        filename_stem=payload.filename_stem,
    )
    return FileResponse(
        path,
        media_type="application/json",
        filename=path.name,
    )


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str, current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    job = JOB_QUEUE.get_job_detail(user_id=current_user["user_id"], job_id=job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return {"success": True, "job": job}


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(
    job_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    _rate_limit: None = Depends(rate_limit("planner")),
) -> Dict[str, Any]:
    return application_cancel_existing_job(
        job_queue=JOB_QUEUE,
        user_id=current_user["user_id"],
        job_id=job_id,
    )


@app.post("/api/jobs/{job_id}/continue")
def continue_job(
    job_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    _rate_limit: None = Depends(rate_limit("planner")),
) -> Dict[str, Any]:
    return application_continue_existing_job(
        job_queue=JOB_QUEUE,
        user_id=current_user["user_id"],
        job_id=job_id,
    )


@app.post("/api/jobs/{job_id}/retry")
def retry_job(
    job_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    _rate_limit: None = Depends(rate_limit("planner")),
) -> Dict[str, Any]:
    return application_retry_existing_job(
        job_queue=JOB_QUEUE,
        user_id=current_user["user_id"],
        job_id=job_id,
    )


@app.post("/api/jobs/{job_id}/revise")
def revise_job(
    job_id: str,
    payload: ReviseJobPayload = ReviseJobPayload(),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _rate_limit: None = Depends(rate_limit("planner")),
) -> Dict[str, Any]:
    return application_revise_existing_job(
        project_store=PROJECT_STORE,
        job_queue=JOB_QUEUE,
        user_id=current_user["user_id"],
        job_id=job_id,
        target_phase=payload.target_phase,
    )


@app.get("/api/artifacts/{filename}")
def download_artifact(
    filename: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    _rate_limit: None = Depends(rate_limit("export")),
) -> FileResponse:
    return application_download_artifact_response(
        artifact_dir=ARTIFACT_DIR,
        current_user=current_user,
        filename=filename,
    )
