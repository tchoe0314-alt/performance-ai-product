from __future__ import annotations

import json
import os
from pathlib import Path
import time
import uuid
import urllib.parse
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
import httpx

from parsers.chat_intent_parser import assess_design_readiness, decide_chat_message
from backend.application.design_workflows import (
    build_run_summary as application_build_run_summary,
    count_unresolved_conflicts as application_count_unresolved_conflicts,
    final_plan_from_result as application_final_plan_from_result,
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
from backend.application.file_workflows import (
    download_artifact_response as application_download_artifact_response,
    get_uploaded_image_response as application_get_uploaded_image_response,
    estimate_slope_from_survey as application_estimate_slope_from_survey,
    read_survey_points as application_read_survey_points,
    upload_image_file as application_upload_image_file,
    upload_survey_file as application_upload_survey_file,
)
from backend.application.health_workflows import health_response as application_health_response
from backend.application.memory_logging import log_memory
from backend.application.job_workflows import (
    build_drainage_job_runner as application_build_drainage_job_runner,
    build_orchestrate_job_runner as application_build_orchestrate_job_runner,
    cancel_existing_job as application_cancel_existing_job,
    continue_existing_job as application_continue_existing_job,
    queue_drainage_job as application_queue_drainage_job,
    queue_orchestrate_job as application_queue_orchestrate_job,
    revise_existing_job as application_revise_existing_job,
)
from backend.application.project_workflows import (
    artifact_summary as application_artifact_summary,
    delete_project_record as application_delete_project_record,
    get_project_detail as application_get_project_detail,
    get_project_result as application_get_project_result,
    list_projects as application_list_projects,
    merge_project_metadata as application_merge_project_metadata,
    result_from_payload as application_result_from_payload,
    save_project_record as application_save_project_record,
    save_project_workflow_update as application_save_project_workflow_update,
)
from backend.application.session_workflows import maybe_export_session as application_maybe_export_session
from backend.services.artifact_service import ArtifactService
from backend.services.auth_store import AuthStore
from backend.services.database import Database
from backend.services.job_queue import JobQueueService
from backend.services.project_store import ProjectStore

try:
    from core.config import APP_NAME, APP_VERSION, PRODUCT_MODE
except Exception:
    APP_NAME = "Civora AI"
    APP_VERSION = "0.1.0"
    PRODUCT_MODE = "development"


BASE_DIR = Path(__file__).resolve().parents[2]
STORAGE_DIR = Path(
    os.getenv("PERFORMANCE_AI_STORAGE_DIR")
    or os.getenv("PERFORMANCE_AI_DATA_DIR")
    or (BASE_DIR / "data")
).resolve()
UPLOAD_DIR = STORAGE_DIR / "uploads"
DATA_DIR = STORAGE_DIR
DB_PATH = DATA_DIR / "performance_ai.db"
ARTIFACT_DIR = DATA_DIR / "artifacts"
CHAT_LEARNING_PATH = DATA_DIR / "chat_learning.jsonl"
CHAT_TRAINING_PATH = DATA_DIR / "chat_training.jsonl"
CHAT_LEARNING_REPORT_PATH = DATA_DIR / "chat_learning_report.json"
CRON_SECRET = str(os.getenv("CIVORA_CRON_SECRET") or "").strip()
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)


def _cors_allow_origins() -> list[str]:
    raw = str(os.getenv("CORS_ALLOW_ORIGINS") or "*").strip()
    if not raw or raw == "*":
        return ["*"]
    cleaned: list[str] = []
    for item in raw.split(","):
        value = item.strip().rstrip("/")
        if value and value not in cleaned:
            cleaned.append(value)
    return cleaned

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
    lat: float
    lng: float
    display_name: str
    provider: str
    confidence: Optional[float] = None
    name: str = ""


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
    name: str
    description: str = ""
    session_id: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    project_input: Dict[str, Any] = Field(default_factory=dict)
    latest_result: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


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


class SurveySlopePayload(BaseModel):
    filename: str


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


def _run_orchestration(payload_data: Dict[str, Any]) -> Dict[str, Any]:
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


@app.on_event("startup")
def _register_job_handlers() -> None:
    log_memory("startup_begin")
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
    log_memory("startup_complete")


@app.get("/api/health")
def health() -> Dict[str, Any]:
    connection = DB.connect()
    try:
        user_count = int(connection.execute("SELECT COUNT(*) FROM users").fetchone()[0])
    finally:
        connection.close()
    return application_health_response(
        app_name=APP_NAME,
        app_version=APP_VERSION,
        product_mode=PRODUCT_MODE,
        user_count=user_count,
        storage=DB.storage_kind,
    )


@app.get("/api/auth/status")
def auth_status() -> Dict[str, Any]:
    connection = DB.connect()
    try:
        user_count = int(connection.execute("SELECT COUNT(*) FROM users").fetchone()[0])
    finally:
        connection.close()
    return application_auth_status(user_count=user_count)


@app.post("/api/auth/register")
def register(payload: RegisterPayload) -> Dict[str, Any]:
    return application_register_user(
        auth_store=AUTH_STORE,
        email=payload.email,
        password=payload.password,
        name=payload.name,
    )


@app.post("/api/auth/login")
def login(payload: LoginPayload) -> Dict[str, Any]:
    return application_login_user(
        auth_store=AUTH_STORE,
        email=payload.email,
        password=payload.password,
    )


@app.get("/api/auth/me")
def me(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    return application_current_user_response(current_user=current_user)


@app.post("/api/auth/logout")
def logout(authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    return application_logout_user(
        auth_store=AUTH_STORE,
        token=_bearer_token(authorization),
    )


@app.post("/api/upload-image")
async def upload_image(
    file: UploadFile = File(...),
    current_user: Dict[str, Any] = Depends(get_current_user),
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
) -> Dict[str, Any]:
    return application_upload_survey_file(
        upload_dir=UPLOAD_DIR,
        file=file,
        current_user=current_user,
    )


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
        return {
            "success": result.success,
            "message": result.message,
            "image_width": result.image_width,
            "image_height": result.image_height,
            "detections": [
                {
                    "kind": det.kind,
                    "bbox": det.bbox,
                    "confidence": det.confidence,
                    "geometry_type": det.geometry_type,
                    "geometry": det.geometry,
                }
                for det in result.detections
            ],
            "warnings": result.warnings,
            "meta": result.meta,
        }
    finally:
        log_memory("image_detect_end", image_path=payload.image_path)


@app.post("/api/geocode", response_model=GeocodeResponse)
def geocode_address(
    payload: GeocodePayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> GeocodeResponse:
    address = str(payload.address or "").strip()
    if not address:
        raise HTTPException(status_code=400, detail="Address is required.")
    token = os.getenv("MAPBOX_TOKEN") or os.getenv("NEXT_PUBLIC_MAPBOX_TOKEN")
    if not token:
        raise HTTPException(status_code=500, detail="Mapbox token is not configured.")
    try:
        with httpx.Client(timeout=8.0) as client:
            resp = client.get(
                f"https://api.mapbox.com/geocoding/v5/mapbox.places/{urllib.parse.quote(address)}.json",
                params={"access_token": token, "limit": 1},
                headers={"User-Agent": "CivoraAI/0.1 (contact: support@civora.ai)"},
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Geocoding failed: {exc}") from exc
    features = data.get("features") if isinstance(data, dict) else None
    if not features:
        raise HTTPException(status_code=404, detail="Address could not be geocoded.")
    first = features[0] if isinstance(features, list) else None
    try:
        center = first.get("center") if isinstance(first, dict) else None
        if not center or len(center) < 2:
            raise ValueError("Missing center")
        lng = float(center[0])
        lat = float(center[1])
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Invalid geocode response: {exc}") from exc
    display_name = str(first.get("place_name") or address) if isinstance(first, dict) else address
    return GeocodeResponse(
        lat=lat,
        lng=lng,
        display_name=display_name,
        provider="mapbox",
        confidence=None,
    )


@app.get("/api/uploads/{filename}")
def get_uploaded_image(
    filename: str,
    authorization: Optional[str] = Header(default=None),
    access_token: Optional[str] = Query(default=None),
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
    if CRON_SECRET and token != CRON_SECRET:
        raise HTTPException(status_code=401, detail="Invalid cron secret.")
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
) -> Dict[str, Any]:
    _ = current_user
    return _run_orchestration(_orchestration_request_payload(payload))


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
def list_jobs(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    return {
        "success": True,
        "jobs": JOB_QUEUE.list_jobs(user_id=current_user["user_id"]),
    }


@app.post("/api/jobs/orchestrate")
def queue_orchestrate_job(payload: QueueOrchestratePayload, current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    project_id, request_payload = _queue_request_payload_with_project(payload)
    return application_queue_orchestrate_job(
        project_store=PROJECT_STORE,
        job_queue=JOB_QUEUE,
        user_id=current_user["user_id"],
        project_id=project_id,
        request_payload=request_payload,
    )


@app.post("/api/jobs/drainage")
def queue_drainage_job(payload: QueueDrainagePayload, current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    project_id, request_payload = _queue_request_payload_with_project(payload)
    return application_queue_drainage_job(
        project_store=PROJECT_STORE,
        job_queue=JOB_QUEUE,
        user_id=current_user["user_id"],
        project_id=project_id,
        request_payload=request_payload,
    )


@app.post("/api/preview")
def build_preview(
    payload: ArtifactPayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
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
def cancel_job(job_id: str, current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    return application_cancel_existing_job(
        job_queue=JOB_QUEUE,
        user_id=current_user["user_id"],
        job_id=job_id,
    )


@app.post("/api/jobs/{job_id}/continue")
def continue_job(job_id: str, current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    return application_continue_existing_job(
        job_queue=JOB_QUEUE,
        user_id=current_user["user_id"],
        job_id=job_id,
    )


@app.post("/api/jobs/{job_id}/revise")
def revise_job(
    job_id: str,
    payload: ReviseJobPayload = ReviseJobPayload(),
    current_user: Dict[str, Any] = Depends(get_current_user),
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
) -> FileResponse:
    return application_download_artifact_response(
        artifact_dir=ARTIFACT_DIR,
        current_user=current_user,
        filename=filename,
    )
