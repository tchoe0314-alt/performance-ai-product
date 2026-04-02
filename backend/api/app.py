from __future__ import annotations

import os
from pathlib import Path
from base64 import b64encode
import mimetypes
import shutil
import time
import uuid
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

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


class LoginPayload(BaseModel):
    email: str
    password: str


class OrchestratePayload(BaseModel):
    input_mode: str = "assisted"
    strict_mode: bool = False
    prompt_text: Optional[str] = None
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


class SaveProjectPayload(BaseModel):
    project_id: Optional[str] = None
    name: str
    description: str = ""
    session_id: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    project_input: Dict[str, Any] = Field(default_factory=dict)
    latest_result: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class QueueOrchestratePayload(BaseModel):
    project_id: Optional[str] = None
    request: OrchestratePayload


class ArtifactPayload(BaseModel):
    project_id: Optional[str] = None
    result: Dict[str, Any] = Field(default_factory=dict)
    final_plan: Dict[str, Any] = Field(default_factory=dict)
    filename_stem: Optional[str] = None


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
    if not session_id or session_state_mod is None:
        return {}
    try:
        exported = session_state_mod.export_session_state(session_id)
        return exported if isinstance(exported, dict) else {}
    except Exception:
        return {}


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
    PlannerOrchestratorRequest, orchestrate_plan = _load_orchestrator()

    req = PlannerOrchestratorRequest(
        input_mode=payload_data.get("input_mode", "assisted"),
        strict_mode=bool(payload_data.get("strict_mode", False)),
        prompt_text=payload_data.get("prompt_text"),
        image_path=payload_data.get("image_path"),
        manual_fields=dict(payload_data.get("manual_fields") or {}),
        image_width_px=payload_data.get("image_width_px"),
        image_height_px=payload_data.get("image_height_px"),
        pixels_per_unit=payload_data.get("pixels_per_unit"),
        plan_type_hint=payload_data.get("plan_type_hint"),
        units=payload_data.get("units", "ft"),
        allow_ai_fill_for_blanks=bool(payload_data.get("allow_ai_fill_for_blanks", True)),
        persist_trace_metadata=bool(payload_data.get("persist_trace_metadata", True)),
        meta=dict(payload_data.get("meta") or {}),
    )

    result = orchestrate_plan(req)
    result_payload = {
        "success": result.success,
        "message": result.message,
        "parsed_payload": result.parsed_payload,
        "final_plan": result.final_plan,
        "warnings": result.warnings,
        "errors": result.errors,
        "issues": [
            {
                "code": issue.code,
                "severity": issue.severity,
                "message": issue.message,
                "context": issue.context,
            }
            for issue in result.issues
        ],
        "assumptions": [
            {
                "field_name": assumption.field_name,
                "assumed_value": assumption.assumed_value,
                "reason": assumption.reason,
            }
            for assumption in result.assumptions
        ],
        "metadata": dict(result.metadata or {}),
    }
    result_payload["metadata"].setdefault("_workflow_run_id", _new_workflow_id("run"))
    result_payload["metadata"].setdefault("input_mode", payload_data.get("input_mode", "assisted"))
    return result_payload


def _result_from_payload(current_user: Dict[str, Any], payload: ArtifactPayload) -> Dict[str, Any]:
    if payload.project_id:
        project = PROJECT_STORE.get_project(
            user_id=current_user["user_id"],
            project_id=payload.project_id,
        )
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found.")
        result_data = dict(project.get("latest_result") or {})
        if not result_data:
            raise HTTPException(status_code=400, detail="Selected project has no saved planner result.")
        return result_data

    if payload.result:
        return dict(payload.result)

    if payload.final_plan:
        return {"final_plan": dict(payload.final_plan)}

    raise HTTPException(status_code=400, detail="No plan or result payload was provided.")


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
    meta = dict(final_plan.get("meta") or {})
    coordination = dict(meta.get("coordination") or {})
    unresolved = coordination.get("unresolved_conflicts") or []
    if isinstance(unresolved, int):
        return int(unresolved)
    return len(unresolved)


def _build_run_summary(
    result_data: Dict[str, Any],
    *,
    source: str,
    project_id: Optional[str] = None,
    job_id: Optional[str] = None,
) -> Dict[str, Any]:
    metadata = dict(result_data.get("metadata") or {})
    final_plan = dict(result_data.get("final_plan") or {})
    plan_meta = dict(final_plan.get("meta") or {})
    deliverables = dict(plan_meta.get("deliverables") or {})
    engineering = dict(plan_meta.get("engineering_status") or {})
    truth = dict(plan_meta.get("truth_audit") or {})
    manual_validation = dict(plan_meta.get("manual_validation") or {})
    stage_completeness = dict(plan_meta.get("stage_completeness") or {})
    coordination = dict(plan_meta.get("coordination") or {})

    return {
        "run_id": metadata.get("_workflow_run_id") or _new_workflow_id("run"),
        "project_id": project_id,
        "job_id": job_id,
        "source": source,
        "created_at": _now_ts(),
        "input_mode": metadata.get("input_mode") or dict(result_data.get("parsed_payload") or {}).get("input_mode"),
        "strict_mode": bool(dict(result_data.get("parsed_payload") or {}).get("strict_mode", False)),
        "success": bool(result_data.get("success")),
        "message": str(result_data.get("message") or ""),
        "engineering_status": {
            "success": bool(engineering.get("success")),
            "status": str(engineering.get("status") or ""),
            "trust_score": float(engineering.get("engineering_trust_score") or truth.get("engineering_trust_score") or 0.0),
        },
        "truth_success": bool(truth.get("success")),
        "all_required_complete": bool(stage_completeness.get("all_required_complete")),
        "requested_deliverables": list(deliverables.get("requested") or []),
        "produced_deliverables": list(deliverables.get("produced") or []),
        "failed_deliverables": list(deliverables.get("failed") or []),
        "manual_failures": [
            {
                "code": item.get("code"),
                "message": item.get("message"),
                "system": item.get("system"),
                "rule": item.get("rule"),
                "location": item.get("location"),
                "reason": item.get("reason"),
            }
            for item in list(manual_validation.get("failures") or [])
        ],
        "stage_summary": {
            "all_required_complete": bool(stage_completeness.get("all_required_complete")),
            "required_stage_count": int(stage_completeness.get("required_stage_count") or 0),
            "complete_stage_count": int(stage_completeness.get("complete_stage_count") or 0),
            "statuses": dict(stage_completeness.get("statuses") or {}),
        },
        "coordination_summary": {
            "unresolved_conflicts": _count_unresolved_conflicts(final_plan),
            "selected_strategy": coordination.get("selected_group_strategy") or "none",
        },
        "warning_count": len(list(result_data.get("warnings") or [])),
        "error_count": len(list(result_data.get("errors") or [])),
    }


def _merge_project_metadata(
    existing_metadata: Optional[Dict[str, Any]],
    *,
    run_summary: Optional[Dict[str, Any]] = None,
    artifact_summary: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    metadata = dict(existing_metadata or {})
    workflow = dict(metadata.get("workflow") or {})
    runs = [dict(item) for item in list(workflow.get("runs") or []) if isinstance(item, dict)]
    artifacts = [dict(item) for item in list(workflow.get("artifacts") or []) if isinstance(item, dict)]

    if run_summary:
        run_id = str(run_summary.get("run_id") or "")
        runs = [item for item in runs if str(item.get("run_id") or "") != run_id]
        runs.insert(0, dict(run_summary))
        runs = runs[:20]

    if artifact_summary:
        artifact_id = str(artifact_summary.get("artifact_id") or "")
        artifacts = [item for item in artifacts if str(item.get("artifact_id") or "") != artifact_id]
        artifacts.insert(0, dict(artifact_summary))
        artifacts = artifacts[:40]

    workflow["runs"] = runs
    workflow["artifacts"] = artifacts
    metadata["workflow"] = workflow
    return metadata


def _save_project_workflow_update(
    *,
    user_id: str,
    project_id: str,
    run_summary: Optional[Dict[str, Any]] = None,
    artifact_summary: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    existing = PROJECT_STORE.get_project(user_id=user_id, project_id=project_id)
    if existing is None:
        return None
    metadata = _merge_project_metadata(
        dict(existing.get("metadata") or {}),
        run_summary=run_summary,
        artifact_summary=artifact_summary,
    )
    return PROJECT_STORE.save_project(
        user_id=user_id,
        project_id=project_id,
        name=existing.get("name", "Untitled Project"),
        description=existing.get("description", ""),
        session_id=existing.get("session_id"),
        tags=existing.get("tags", []),
        project_input=existing.get("project_input", {}),
        latest_result=existing.get("latest_result", {}),
        session_state=existing.get("session_state", {}),
        metadata=metadata,
    )


def _artifact_summary(
    *,
    path: Path,
    artifact_kind: str,
    project_id: Optional[str],
    result_data: Dict[str, Any],
) -> Dict[str, Any]:
    final_plan = dict(result_data.get("final_plan") or {})
    return {
        "artifact_id": _new_workflow_id("artifact"),
        "kind": artifact_kind,
        "project_id": project_id,
        "filename": path.name,
        "created_at": _now_ts(),
        "project_name": str(final_plan.get("project_name") or "Generated Plan"),
        "download_path": f"/api/artifacts/{path.name}",
    }


def _build_drawable_fallback_plan(result_data: Dict[str, Any]) -> Dict[str, Any]:
    parsed_payload = dict(result_data.get("parsed_payload") or {})
    manual_fields = dict(parsed_payload.get("manual_fields") or {})
    site_plan = dict(manual_fields.get("site_plan") or {})
    lot = dict(manual_fields.get("lot") or parsed_payload.get("lot") or {})

    lot_x = _safe_float(lot.get("x"), 0.0)
    lot_y = _safe_float(lot.get("y"), 0.0)
    lot_w = _safe_float(lot.get("w"), 0.0)
    lot_h = _safe_float(lot.get("h"), 0.0)
    setback = max(_safe_float(manual_fields.get("setback"), 10.0), 0.0)

    actions: List[Dict[str, Any]] = []

    if lot_w > 0 and lot_h > 0:
        actions.append(
            {
                "task": "rectangle",
                "origin": (lot_x, lot_y),
                "width": lot_w,
                "height": lot_h,
                "label": "LOT",
                "layer": "SITE",
            }
        )

        building_w = min(
            max(_safe_float(manual_fields.get("building_width"), 48.0), 12.0),
            max(lot_w - setback * 2, 12.0),
        )
        building_h = min(
            max(_safe_float(manual_fields.get("building_depth"), 34.0), 12.0),
            max(lot_h - setback * 2, 12.0),
        )
        building_x = lot_x + max((lot_w - building_w) / 2.0, setback)
        building_y = lot_y + max((lot_h - building_h) / 2.0, setback)
        actions.append(
            {
                "task": "rectangle",
                "origin": (building_x, building_y),
                "width": building_w,
                "height": building_h,
                "label": "BLDG",
                "layer": "BUILDING",
            }
        )

        parking_count = max(_safe_float(site_plan.get("parking_count"), 0.0), 0.0)
        if parking_count > 0:
            stall_area = parking_count * 162.0
            parking_w = min(max(lot_w - setback * 2, 18.0), max(building_w * 1.2, 24.0))
            parking_h = min(max(stall_area / max(parking_w, 1.0), 18.0), max(lot_h * 0.28, 18.0))
            actions.append(
                {
                    "task": "rectangle",
                    "origin": (lot_x + setback, lot_y + setback),
                    "width": parking_w,
                    "height": parking_h,
                    "label": f"PARK {int(parking_count)}",
                    "layer": "PAVEMENT",
                }
            )

        actions.append(
            {
                "task": "text_note",
                "origin": (lot_x, lot_y + lot_h + max(setback * 0.5, 4.0)),
                "text": "Fallback preview generated from structured inputs.",
                "text_height": 1.0,
                "layer": "ANNO",
            }
        )

    return {
        "project_name": manual_fields.get("project_name")
        or parsed_payload.get("project_name")
        or "Generated Plan",
        "units": manual_fields.get("units") or parsed_payload.get("units") or "ft",
        "actions": actions,
        "assumptions": [
            "Preview/export used fallback geometry because the planner result did not include drawable actions."
        ],
    }


def _final_plan_from_result(result_data: Dict[str, Any]) -> Dict[str, Any]:
    final_plan = dict(result_data.get("final_plan") or result_data)
    actions = final_plan.get("actions")
    if isinstance(actions, list) and actions:
        return final_plan

    fallback_plan = _build_drawable_fallback_plan(result_data)
    fallback_actions = fallback_plan.get("actions")
    if isinstance(fallback_actions, list) and fallback_actions:
        return fallback_plan

    raise HTTPException(
        status_code=400,
        detail="No drawable plan actions are available yet. Run the planner first.",
    )
    return final_plan


@app.on_event("startup")
def _register_job_handlers() -> None:
    def orchestrate_runner(job: Dict[str, Any]) -> Dict[str, Any]:
        payload = dict(job.get("payload") or {})
        result = _run_orchestration(payload)
        project_id = job.get("project_id")
        user_id = job.get("user_id")
        if project_id and user_id:
            existing = PROJECT_STORE.get_project(user_id=user_id, project_id=project_id)
            if existing is not None:
                PROJECT_STORE.save_project(
                    user_id=user_id,
                    project_id=project_id,
                    name=existing.get("name", "Untitled Project"),
                    description=existing.get("description", ""),
                    session_id=existing.get("session_id"),
                    tags=existing.get("tags", []),
                    project_input=payload,
                    latest_result=result,
                    session_state=existing.get("session_state", {}),
                    metadata=_merge_project_metadata(
                        dict(existing.get("metadata") or {}),
                        run_summary=_build_run_summary(
                            result,
                            source="queued_job",
                            project_id=project_id,
                            job_id=job.get("job_id"),
                        ),
                    ),
                )
        return result

    JOB_QUEUE.register_handler("orchestrate", orchestrate_runner)


@app.get("/api/health")
def health() -> Dict[str, Any]:
    connection = DB.connect()
    try:
        user_count = int(connection.execute("SELECT COUNT(*) FROM users").fetchone()[0])
    finally:
        connection.close()
    return {
        "success": True,
        "message": "Civora AI backend is running.",
        "app_name": APP_NAME,
        "version": APP_VERSION,
        "product_mode": PRODUCT_MODE,
        "auth_enabled": True,
        "storage": "sqlite",
        "user_count": user_count,
    }


@app.get("/api/auth/status")
def auth_status() -> Dict[str, Any]:
    connection = DB.connect()
    try:
        user_count = int(connection.execute("SELECT COUNT(*) FROM users").fetchone()[0])
    finally:
        connection.close()
    return {
        "success": True,
        "auth_enabled": True,
        "user_count": user_count,
    }


@app.post("/api/auth/register")
def register(payload: RegisterPayload) -> Dict[str, Any]:
    try:
        result = AUTH_STORE.register_user(email=payload.email, password=payload.password, name=payload.name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, **result}


@app.post("/api/auth/login")
def login(payload: LoginPayload) -> Dict[str, Any]:
    try:
        result = AUTH_STORE.login(email=payload.email, password=payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return {"success": True, **result}


@app.get("/api/auth/me")
def me(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    return {"success": True, "user": current_user}


@app.post("/api/auth/logout")
def logout(authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    AUTH_STORE.logout(_bearer_token(authorization))
    return {"success": True}


@app.post("/api/upload-image")
async def upload_image(
    file: UploadFile = File(...),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    filename = file.filename or "uploaded_image"
    safe_prefix = str(current_user["user_id"]).replace("/", "_")
    safe_name = Path(filename).name
    stored_name = f"{safe_prefix}_{safe_name}"
    target = UPLOAD_DIR / stored_name

    with target.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return {
        "success": True,
        "message": "Image uploaded.",
        "image_path": str(target),
        "filename": safe_name,
        "stored_filename": stored_name,
        "image_url": f"/api/uploads/{stored_name}",
    }


@app.get("/api/uploads/{filename}")
def get_uploaded_image(
    filename: str,
    authorization: Optional[str] = Header(default=None),
    access_token: Optional[str] = Query(default=None),
) -> FileResponse:
    token = str(access_token or "").strip() or _bearer_token(authorization)
    current_user = AUTH_STORE.authenticate_token(token)
    if current_user is None:
        raise HTTPException(status_code=401, detail="Authentication required.")

    safe_name = Path(filename).name
    expected_prefix = f"{current_user['user_id']}_"
    if not safe_name.startswith(expected_prefix):
        raise HTTPException(status_code=403, detail="That image does not belong to this user.")

    target = UPLOAD_DIR / safe_name
    if not target.exists():
        raise HTTPException(status_code=404, detail="Uploaded image not found.")

    media_type, _ = mimetypes.guess_type(str(target))
    return FileResponse(target, media_type=media_type or "application/octet-stream")


@app.post("/api/orchestrate")
def orchestrate(
    payload: OrchestratePayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    _ = current_user
    return _run_orchestration(_model_to_dict(payload))


@app.get("/api/projects")
def list_projects(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    return {
        "success": True,
        "projects": PROJECT_STORE.list_projects(user_id=current_user["user_id"]),
    }


@app.post("/api/projects")
def save_project(payload: SaveProjectPayload, current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    session_export = _maybe_export_session(payload.session_id)
    existing = None
    if payload.project_id:
        existing = PROJECT_STORE.get_project(user_id=current_user["user_id"], project_id=payload.project_id)
    metadata = dict(existing.get("metadata") or {}) if existing else {}
    metadata.update(dict(payload.metadata or {}))
    if payload.latest_result:
        metadata = _merge_project_metadata(
            metadata,
            run_summary=_build_run_summary(
                dict(payload.latest_result),
                source="project_save",
                project_id=payload.project_id,
            ),
        )
    try:
        record = PROJECT_STORE.save_project(
            user_id=current_user["user_id"],
            project_id=payload.project_id,
            name=payload.name,
            description=payload.description,
            session_id=payload.session_id,
            tags=payload.tags,
            project_input=payload.project_input,
            latest_result=payload.latest_result,
            session_state=session_export,
            metadata=metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return {"success": True, "project": record}


@app.get("/api/projects/{project_id}")
def get_project(project_id: str, current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    record = PROJECT_STORE.get_project(user_id=current_user["user_id"], project_id=project_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return {"success": True, "project": record}


@app.delete("/api/projects/{project_id}")
def delete_project(project_id: str, current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    deleted = PROJECT_STORE.delete_project(user_id=current_user["user_id"], project_id=project_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Project not found.")
    return {"success": True, "project_id": project_id}


@app.get("/api/jobs")
def list_jobs(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    return {
        "success": True,
        "jobs": JOB_QUEUE.list_jobs(user_id=current_user["user_id"]),
    }


@app.post("/api/jobs/orchestrate")
def queue_orchestrate_job(payload: QueueOrchestratePayload, current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    if payload.project_id:
        existing = PROJECT_STORE.get_project(user_id=current_user["user_id"], project_id=payload.project_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="Project not found.")

    job = JOB_QUEUE.submit_job(
        user_id=current_user["user_id"],
        job_type="orchestrate",
        payload=_model_to_dict(payload.request),
        project_id=payload.project_id,
    )
    return {"success": True, "job": job}


@app.post("/api/preview")
def build_preview(
    payload: ArtifactPayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    result_data = _result_from_payload(current_user, payload)
    final_plan = _final_plan_from_result(result_data)
    png_bytes = ARTIFACTS.build_preview_png(final_plan)
    return {
        "success": True,
        "preview_image_data_url": f"data:image/png;base64,{b64encode(png_bytes).decode('ascii')}",
        "summary": {
            "project_name": final_plan.get("project_name", "Generated Plan"),
            "units": final_plan.get("units", "ft"),
            "action_count": len(final_plan.get("actions") or []),
        },
    }


@app.post("/api/export/dxf")
def export_dxf(
    payload: ArtifactPayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> FileResponse:
    result_data = _result_from_payload(current_user, payload)
    final_plan = _final_plan_from_result(result_data)
    filename_stem = payload.filename_stem or str(final_plan.get("project_name") or "civora-ai-plan")
    path = ARTIFACTS.export_dxf(
        user_id=current_user["user_id"],
        final_plan=final_plan,
        stem=filename_stem,
    )
    if payload.project_id:
        _save_project_workflow_update(
            user_id=current_user["user_id"],
            project_id=payload.project_id,
            artifact_summary=_artifact_summary(
                path=path,
                artifact_kind="dxf",
                project_id=payload.project_id,
                result_data=result_data,
            ),
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
    final_plan = _final_plan_from_result(result_data)
    filename_stem = payload.filename_stem or str(final_plan.get("project_name") or "civora-ai-report")
    path = ARTIFACTS.export_report_json(
        user_id=current_user["user_id"],
        result_data=result_data,
        stem=filename_stem,
    )
    if payload.project_id:
        _save_project_workflow_update(
            user_id=current_user["user_id"],
            project_id=payload.project_id,
            artifact_summary=_artifact_summary(
                path=path,
                artifact_kind="report",
                project_id=payload.project_id,
                result_data=result_data,
            ),
        )
    return FileResponse(
        path,
        media_type="application/json",
        filename=path.name,
    )


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str, current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    job = JOB_QUEUE.get_job(user_id=current_user["user_id"], job_id=job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return {"success": True, "job": job}


@app.get("/api/artifacts/{filename}")
def download_artifact(
    filename: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> FileResponse:
    path = ARTIFACT_DIR / current_user["user_id"] / Path(filename).name
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Artifact not found.")
    return FileResponse(
        path,
        media_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream",
        filename=path.name,
    )
