from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Mapping, Optional
from urllib.parse import urlparse


VALID_PRODUCT_MODES = {"development", "local", "private_alpha", "public_beta", "production"}
PRODUCTION_MODES = {"public_beta", "production"}
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}
SECRET_MARKERS = ("KEY", "SECRET", "TOKEN", "PASSWORD", "DATABASE_URL", "POSTGRES", "REDIS_URL")
RECOGNIZED_BILLING_PROVIDERS = {"none", "disabled", "off", "stripe"}


@dataclass(frozen=True)
class EnvVarSpec:
    name: str
    category: str
    required_modes: tuple[str, ...] = ()
    optional: bool = False
    secret: bool = False
    description: str = ""


ENV_VAR_SPECS: tuple[EnvVarSpec, ...] = (
    EnvVarSpec("CIVORA_PRODUCT_MODE", "mode", ("private_alpha", "public_beta", "production"), description="Runtime product stage."),
    EnvVarSpec("CIVORA_DEPLOYMENT_TARGET", "mode", (), optional=True, description="Expected platform: local, vercel, railway, or split."),
    EnvVarSpec("CIVORA_FRONTEND_PUBLIC_URL", "frontend", (), optional=True, description="Browser app origin used to cross-check CORS."),
    EnvVarSpec("NEXT_PUBLIC_API_BASE_URL", "frontend", ("public_beta", "production"), description="Browser-facing backend base URL."),
    EnvVarSpec("CIVORA_PUBLIC_API_BASE_URL", "backend", ("public_beta", "production"), description="Public backend URL."),
    EnvVarSpec("CORS_ALLOW_ORIGINS", "cors", ("private_alpha", "public_beta", "production"), description="Comma-separated browser origins."),
    EnvVarSpec("CIVORA_SESSION_SECRET", "auth", ("public_beta", "production"), secret=True, description="Shared app secret for session-capable deployments."),
    EnvVarSpec("CIVORA_CRON_SECRET", "auth", (), optional=True, secret=True, description="Secret for scheduled backend maintenance routes."),
    EnvVarSpec("DATABASE_URL", "storage", (), optional=True, secret=True, description="Postgres URL. SQLite is allowed for private alpha."),
    EnvVarSpec("PERFORMANCE_AI_STORAGE_DIR", "storage", ("private_alpha", "public_beta", "production"), description="Persistent upload/artifact directory."),
    EnvVarSpec("CIVORA_PROCESS_ROLE", "queue", (), optional=True, description="Runtime process role: combined, web, or worker."),
    EnvVarSpec("CIVORA_DEDICATED_WORKER_ENABLED", "queue", (), optional=True, description="Confirms that a separately deployed worker consumes queued jobs."),
    EnvVarSpec("CIVORA_ENABLED_JOB_TYPES", "queue", (), optional=True, description="Comma-separated allowlist of job handlers for this service."),
    EnvVarSpec("CIVORA_DISABLED_JOB_TYPES", "queue", (), optional=True, description="Comma-separated denylist of job handlers for this service."),
    EnvVarSpec("PERFORMANCE_AI_JOB_WORKERS", "queue", (), optional=True, description="In-process job worker count. Use 0 for a web-only service."),
    EnvVarSpec("PERFORMANCE_AI_RESUME_PENDING_JOBS", "queue", (), optional=True, description="Enables database polling for queued jobs."),
    EnvVarSpec("PERFORMANCE_AI_RESUME_POLL_SECONDS", "queue", (), optional=True, description="Database queue polling interval."),
    EnvVarSpec("MAPBOX_TOKEN", "mapbox", (), optional=True, secret=True, description="Backend Mapbox token for geocode and terrain lookups."),
    EnvVarSpec("NEXT_PUBLIC_MAPBOX_TOKEN", "mapbox", (), optional=True, description="Frontend Mapbox token for map rendering."),
    EnvVarSpec("CIVORA_AI_PROVIDER", "ai", ("public_beta", "production"), description="AI provider: none, openai, ollama, or local."),
    EnvVarSpec("OPENAI_API_KEY", "ai", (), optional=True, secret=True, description="Required when CIVORA_AI_PROVIDER=openai."),
    EnvVarSpec("CIVORA_OLLAMA_BASE_URL", "ai", (), optional=True, description="Required when CIVORA_AI_PROVIDER is ollama/local."),
    EnvVarSpec("CIVORA_JOB_TIMEOUT_SECONDS", "queue", (), optional=True, description="Maximum in-process job runtime."),
    EnvVarSpec("CIVORA_MEMORY_WARN_MB", "monitoring", (), optional=True, description="Runtime memory warning threshold."),
    EnvVarSpec("CIVORA_RUNTIME_DEBUG_BEARER_TOKEN", "monitoring", (), optional=True, secret=True, description="Audit token for runtime sampling tools."),
    EnvVarSpec("CIVORA_MAX_IMAGE_UPLOAD_BYTES", "uploads", (), optional=True, description="Image/map snapshot upload limit."),
    EnvVarSpec("CIVORA_MAX_SURVEY_UPLOAD_BYTES", "uploads", (), optional=True, description="Survey CSV upload limit."),
    EnvVarSpec("CIVORA_MAX_EXISTING_CONDITIONS_UPLOAD_BYTES", "uploads", (), optional=True, description="Existing-condition and plan PDF upload limit."),
    EnvVarSpec("CIVORA_SUPPORT_CONTACT_URL", "support", (), optional=True, description="User-visible support contact or support page."),
    EnvVarSpec("CIVORA_SUPPORT_EMAIL", "support", (), optional=True, description="Fallback user-visible support email."),
    EnvVarSpec("CIVORA_BUG_REPORT_URL", "support", (), optional=True, description="User-visible bug report intake URL."),
    EnvVarSpec("CIVORA_ESCALATION_CONTACT", "support", (), optional=True, description="Internal escalation contact for source-trust, safety, privacy, billing, and export incidents."),
    EnvVarSpec("CIVORA_MONITORING_OWNER", "operations", (), optional=True, description="Named owner for deployment health, queue, auth, upload, and error monitoring."),
    EnvVarSpec("CIVORA_ROLLBACK_OWNER", "operations", (), optional=True, description="Named owner authorized to roll back or disable Vercel/Railway services."),
    EnvVarSpec("CIVORA_PUBLIC_BETA_RELEASE_GATES_GREEN", "safety", (), optional=True, description="Explicit owner gate. Public beta remains blocked unless this is true and operational gates are configured."),
    EnvVarSpec("CIVORA_ALLOW_LOCAL_PILOT_CORS", "cors", (), optional=True, description="Temporary QA-only flag for local frontend to live backend."),
    EnvVarSpec("CIVORA_LOCAL_PILOT_CORS_ORIGINS", "cors", (), optional=True, description="Explicit local origins allowed only when CIVORA_ALLOW_LOCAL_PILOT_CORS=true."),
    EnvVarSpec("CIVORA_BILLING_PROVIDER", "billing", (), optional=True, description="Billing provider name. Defaults to none."),
    EnvVarSpec("CIVORA_ENABLE_REAL_CHARGING", "billing", (), optional=True, description="Must remain explicit; validator never enables it."),
    EnvVarSpec("CIVORA_BILLING_LEGAL_DOCS_READY", "billing", (), optional=True, description="Business-doc gate for paid pilot."),
    EnvVarSpec("STRIPE_PUBLISHABLE_KEY", "billing", (), optional=True, description="Stripe browser key when billing provider is stripe."),
    EnvVarSpec("STRIPE_SECRET_KEY", "billing", (), optional=True, secret=True, description="Stripe API key when billing provider is stripe."),
    EnvVarSpec("STRIPE_PILOT_PRICE_ID", "billing", (), optional=True, description="Stripe price id when billing provider is stripe."),
    EnvVarSpec("STRIPE_WEBHOOK_SECRET", "billing", (), optional=True, secret=True, description="Stripe webhook secret when billing provider is stripe."),
    EnvVarSpec("CIVORA_OCR_ENGINE", "ocr_pdf", (), optional=True, description="OCR engine for plan PDF parsing."),
    EnvVarSpec("CIVORA_OCR_LANG", "ocr_pdf", (), optional=True, description="OCR language."),
    EnvVarSpec("CIVORA_PDF_RENDERER", "ocr_pdf", (), optional=True, description="PDF preview renderer hint."),
    EnvVarSpec("CIVORA_GIS_PROVIDER_REGISTRY_URL", "gis", (), optional=True, description="Source registry for GIS providers."),
    EnvVarSpec("CIVORA_REQUIRE_GIS_PROVIDERS", "gis", (), optional=True, description="Promote missing GIS providers to blockers in stricter modes."),
    EnvVarSpec("CIVORA_IMAGERY_DETECTION_PROVIDER", "imagery_detection", (), optional=True, description="Name of imagery/object detection provider."),
    EnvVarSpec("CIVORA_IMAGERY_DETECTION_URL", "imagery_detection", (), optional=True, description="Backend endpoint for address/site imagery object detection."),
    EnvVarSpec("CIVORA_IMAGERY_DETECTION_TOKEN", "imagery_detection", (), optional=True, secret=True, description="Bearer token for imagery/object detection provider."),
    EnvVarSpec("PORT", "railway", (), optional=True, description="Railway-provided port. Backend must bind to it."),
    EnvVarSpec("RAILWAY_PUBLIC_DOMAIN", "railway", (), optional=True, description="Railway public domain."),
    EnvVarSpec("VERCEL", "vercel", (), optional=True, description="Set by Vercel builds."),
    EnvVarSpec("VERCEL_ENV", "vercel", (), optional=True, description="Vercel environment."),
    EnvVarSpec("CIVORA_ALPHA_REVIEW_ONLY", "safety", (), optional=True, description="Keeps alpha modes review-only."),
    EnvVarSpec("CIVORA_ENABLE_PUBLIC_ACCESS", "safety", (), optional=True, description="Explicit public access flag."),
)


def _normalize_mode(value: str) -> str:
    normalized = str(value or "").strip().lower().replace("-", "_")
    aliases = {"alpha": "private_alpha", "beta": "public_beta", "prod": "production"}
    return aliases.get(normalized, normalized or "private_alpha")


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _clean_url(value: str) -> str:
    return str(value or "").strip().rstrip("/")


def _parse_origins(value: str) -> list[str]:
    return [_clean_url(item) for item in str(value or "").split(",") if _clean_url(item)]


def _is_url(value: str) -> bool:
    parsed = urlparse(_clean_url(value))
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _hostname(value: str) -> str:
    return str(urlparse(_clean_url(value)).hostname or "").lower()


def _is_local_url(value: str) -> bool:
    return _hostname(value) in LOCAL_HOSTS


def _is_public_prod_url(value: str) -> bool:
    return _is_url(value) and not _is_local_url(value)


def _secret_like(name: str) -> bool:
    upper = name.upper()
    return any(marker in upper for marker in SECRET_MARKERS)


def _redacted_value(name: str, value: str) -> Dict[str, Any]:
    raw = str(value or "")
    if not raw:
        return {"present": False}
    if _secret_like(name):
        return {"present": True, "redacted": True, "length": len(raw)}
    if _is_url(raw):
        parsed = urlparse(_clean_url(raw))
        return {"present": True, "scheme": parsed.scheme, "host": parsed.hostname or "", "path_present": bool(parsed.path and parsed.path != "/")}
    return {"present": True, "value": raw if len(raw) <= 80 else f"{raw[:32]}...{raw[-8:]}", "redacted": False}


def _first_env(env: Mapping[str, str], names: Iterable[str]) -> str:
    for name in names:
        value = str(env.get(name) or "").strip()
        if value:
            return value
    return ""


def _issue(severity: str, code: str, message: str, *, env_vars: Optional[list[str]] = None) -> Dict[str, Any]:
    return {"severity": severity, "code": code, "message": message, "env_vars": env_vars or []}


def build_env_contract() -> Dict[str, list[Dict[str, Any]]]:
    required: list[Dict[str, Any]] = []
    optional: list[Dict[str, Any]] = []
    for spec in ENV_VAR_SPECS:
        target = optional if spec.optional or not spec.required_modes else required
        target.append(
            {
                "name": spec.name,
                "category": spec.category,
                "required_modes": list(spec.required_modes),
                "secret": spec.secret,
                "description": spec.description,
            }
        )
    return {"required": required, "optional": optional}


def validate_production_env_v1(
    env: Optional[Mapping[str, str]] = None,
    *,
    deployment_target: str = "",
    include_diagnostics: bool = True,
) -> Dict[str, Any]:
    env = dict(os.environ if env is None else env)
    mode = _normalize_mode(env.get("CIVORA_PRODUCT_MODE") or env.get("PERFORMANCE_AI_PRODUCT_MODE") or "private_alpha")
    target = str(deployment_target or env.get("CIVORA_DEPLOYMENT_TARGET") or "").strip().lower()
    if not target:
        if env.get("VERCEL"):
            target = "vercel"
        elif env.get("RAILWAY_ENVIRONMENT") or env.get("RAILWAY_PUBLIC_DOMAIN"):
            target = "railway"
        else:
            target = "local"

    blockers: list[Dict[str, Any]] = []
    warnings: list[Dict[str, Any]] = []
    info: list[Dict[str, Any]] = []

    if mode not in VALID_PRODUCT_MODES:
        blockers.append(_issue("blocker", "invalid_product_mode", f"CIVORA_PRODUCT_MODE must be one of {sorted(VALID_PRODUCT_MODES)}.", env_vars=["CIVORA_PRODUCT_MODE"]))
    if target not in {"local", "vercel", "railway", "split", "render"}:
        warnings.append(_issue("warning", "unknown_deployment_target", "Deployment target is not recognized; platform checks will be conservative.", env_vars=["CIVORA_DEPLOYMENT_TARGET"]))

    for spec in ENV_VAR_SPECS:
        if mode in spec.required_modes and not str(env.get(spec.name) or "").strip():
            blockers.append(_issue("blocker", "missing_required_env", f"{spec.name} is required for {mode}.", env_vars=[spec.name]))

    frontend_url = _clean_url(env.get("NEXT_PUBLIC_API_BASE_URL", ""))
    frontend_origin = _clean_url(env.get("CIVORA_FRONTEND_PUBLIC_URL", ""))
    if not frontend_origin and env.get("VERCEL_URL"):
        frontend_origin = _clean_url(str(env.get("VERCEL_URL") or ""))
        if frontend_origin and not frontend_origin.startswith(("http://", "https://")):
            frontend_origin = f"https://{frontend_origin}"
    backend_url = _clean_url(_first_env(env, ("CIVORA_PUBLIC_API_BASE_URL", "PUBLIC_API_BASE_URL", "RAILWAY_STATIC_URL", "RAILWAY_PUBLIC_DOMAIN")))
    if backend_url and not backend_url.startswith(("http://", "https://")):
        backend_url = f"https://{backend_url}"

    if mode in PRODUCTION_MODES and not frontend_url:
        blockers.append(_issue("blocker", "public_api_base_url_missing", "NEXT_PUBLIC_API_BASE_URL is required in public_beta and production.", env_vars=["NEXT_PUBLIC_API_BASE_URL"]))
    if frontend_url:
        if not _is_url(frontend_url):
            blockers.append(_issue("blocker", "invalid_frontend_api_base_url", "NEXT_PUBLIC_API_BASE_URL must be an absolute http(s) URL.", env_vars=["NEXT_PUBLIC_API_BASE_URL"]))
        elif mode in PRODUCTION_MODES and _is_local_url(frontend_url):
            blockers.append(_issue("blocker", "frontend_api_base_url_localhost", "NEXT_PUBLIC_API_BASE_URL cannot point at localhost in public_beta or production.", env_vars=["NEXT_PUBLIC_API_BASE_URL"]))
        elif mode in PRODUCTION_MODES and urlparse(frontend_url).scheme != "https":
            blockers.append(_issue("blocker", "frontend_api_base_url_not_https", "NEXT_PUBLIC_API_BASE_URL must use https in public_beta or production.", env_vars=["NEXT_PUBLIC_API_BASE_URL"]))
    if mode in PRODUCTION_MODES and not backend_url:
        blockers.append(_issue("blocker", "backend_public_url_missing", "CIVORA_PUBLIC_API_BASE_URL is required in public_beta and production.", env_vars=["CIVORA_PUBLIC_API_BASE_URL"]))
    if backend_url:
        if not _is_url(backend_url):
            blockers.append(_issue("blocker", "invalid_backend_public_url", "Backend public URL must be an absolute http(s) URL.", env_vars=["CIVORA_PUBLIC_API_BASE_URL", "RAILWAY_PUBLIC_DOMAIN"]))
        elif mode in PRODUCTION_MODES and _is_local_url(backend_url):
            blockers.append(_issue("blocker", "backend_public_url_localhost", "Backend public URL cannot point at localhost in public_beta or production.", env_vars=["CIVORA_PUBLIC_API_BASE_URL"]))
        elif mode in PRODUCTION_MODES and urlparse(backend_url).scheme != "https":
            blockers.append(_issue("blocker", "backend_public_url_not_https", "CIVORA_PUBLIC_API_BASE_URL must use https in public_beta or production.", env_vars=["CIVORA_PUBLIC_API_BASE_URL"]))

    cors_raw = str(env.get("CORS_ALLOW_ORIGINS") or "").strip()
    cors_origins = _parse_origins(cors_raw)
    if "*" in cors_origins and mode not in {"development", "local"}:
        blockers.append(_issue("blocker", "wildcard_cors_not_allowed", "Wildcard CORS is only allowed in local/development mode.", env_vars=["CORS_ALLOW_ORIGINS"]))
    elif mode in PRODUCTION_MODES and not cors_origins:
        blockers.append(_issue("blocker", "missing_cors_origins", "CORS_ALLOW_ORIGINS must list deployed frontend origins.", env_vars=["CORS_ALLOW_ORIGINS"]))
    if frontend_origin:
        if not _is_url(frontend_origin):
            blockers.append(_issue("blocker", "invalid_frontend_public_url", "CIVORA_FRONTEND_PUBLIC_URL must be an absolute http(s) URL.", env_vars=["CIVORA_FRONTEND_PUBLIC_URL"]))
        elif cors_origins and frontend_origin not in cors_origins:
            blockers.append(_issue("blocker", "frontend_origin_not_in_cors", "Frontend public origin is not listed in CORS_ALLOW_ORIGINS.", env_vars=["CIVORA_FRONTEND_PUBLIC_URL", "CORS_ALLOW_ORIGINS"]))
    if mode == "private_alpha" and target == "local":
        local_browser_origins = {"http://localhost:3000", "http://127.0.0.1:3000"}
        missing_local_origins = sorted(local_browser_origins.difference(cors_origins))
        if missing_local_origins:
            warnings.append(
                _issue(
                    "warning",
                    "local_private_alpha_cors_origins_incomplete",
                    "Local private-alpha browser QA should allow both http://localhost:3000 and http://127.0.0.1:3000 in CORS_ALLOW_ORIGINS.",
                    env_vars=["CORS_ALLOW_ORIGINS"],
                )
            )
        else:
            info.append(
                _issue(
                    "info",
                    "local_private_alpha_cors_origins_ready",
                    "Local private-alpha CORS includes localhost:3000 and 127.0.0.1:3000 for browser QA.",
                    env_vars=["CORS_ALLOW_ORIGINS"],
                )
            )
    if mode in PRODUCTION_MODES and _truthy(env.get("CIVORA_ALLOW_LOCAL_PILOT_CORS")):
        warnings.append(_issue("warning", "temporary_local_cors_enabled", "Local pilot CORS is enabled; remove it after the live QA window.", env_vars=["CIVORA_ALLOW_LOCAL_PILOT_CORS", "CIVORA_LOCAL_PILOT_CORS_ORIGINS"]))

    storage_dir = str(env.get("PERFORMANCE_AI_STORAGE_DIR") or env.get("PERFORMANCE_AI_DATA_DIR") or "").strip()
    database_url = str(env.get("DATABASE_URL") or "").strip()
    if mode == "production" and not database_url:
        warnings.append(_issue("warning", "production_sqlite_storage", "DATABASE_URL is missing; backend will use SQLite/local storage.", env_vars=["DATABASE_URL"]))
    if mode in PRODUCTION_MODES and storage_dir and storage_dir.startswith("./"):
        warnings.append(_issue("warning", "relative_storage_dir", "Persistent storage should use an absolute mounted path on deploy platforms.", env_vars=["PERFORMANCE_AI_STORAGE_DIR"]))

    process_role = str(env.get("CIVORA_PROCESS_ROLE") or "combined").strip().lower()
    dedicated_worker_enabled = _truthy(env.get("CIVORA_DEDICATED_WORKER_ENABLED"))
    enabled_job_types = {
        item.strip()
        for item in str(env.get("CIVORA_ENABLED_JOB_TYPES") or "").split(",")
        if item.strip()
    }
    disabled_job_types = {
        item.strip()
        for item in str(env.get("CIVORA_DISABLED_JOB_TYPES") or "").split(",")
        if item.strip()
    }
    source_context_externalized = dedicated_worker_enabled and "source_context" in disabled_job_types
    raw_worker_count = str(env.get("PERFORMANCE_AI_JOB_WORKERS") or ("0" if process_role == "web" else "1")).strip()
    try:
        worker_count = int(raw_worker_count)
    except ValueError:
        worker_count = -1
        blockers.append(
            _issue(
                "blocker",
                "invalid_job_worker_count",
                "PERFORMANCE_AI_JOB_WORKERS must be a non-negative integer.",
                env_vars=["PERFORMANCE_AI_JOB_WORKERS"],
            )
        )
    if process_role not in {"combined", "web", "worker"}:
        blockers.append(
            _issue(
                "blocker",
                "invalid_process_role",
                "CIVORA_PROCESS_ROLE must be combined, web, or worker.",
                env_vars=["CIVORA_PROCESS_ROLE"],
            )
        )
    elif worker_count >= 0:
        if process_role == "web" and worker_count != 0:
            blockers.append(
                _issue(
                    "blocker",
                    "web_process_has_local_workers",
                    "A web-only process must set PERFORMANCE_AI_JOB_WORKERS=0.",
                    env_vars=["CIVORA_PROCESS_ROLE", "PERFORMANCE_AI_JOB_WORKERS"],
                )
            )
        if process_role == "worker" and worker_count < 1:
            blockers.append(
                _issue(
                    "blocker",
                    "worker_process_has_no_workers",
                    "A worker process must set PERFORMANCE_AI_JOB_WORKERS to at least 1.",
                    env_vars=["CIVORA_PROCESS_ROLE", "PERFORMANCE_AI_JOB_WORKERS"],
                )
            )
    if target in {"railway", "render", "split"} and process_role in {"web", "worker"} and not database_url:
        blockers.append(
            _issue(
                "blocker",
                "split_queue_requires_postgres",
                "Separate web and worker services require a shared Postgres DATABASE_URL; local SQLite cannot coordinate across services.",
                env_vars=["CIVORA_PROCESS_ROLE", "DATABASE_URL"],
            )
        )
    if target in {"railway", "render", "split"} and process_role == "web" and not dedicated_worker_enabled:
        blockers.append(
            _issue(
                "blocker",
                "dedicated_worker_not_confirmed",
                "The web service queues source-context jobs but no dedicated worker deployment is confirmed.",
                env_vars=["CIVORA_PROCESS_ROLE", "CIVORA_DEDICATED_WORKER_ENABLED"],
            )
        )
    if process_role == "worker" and enabled_job_types and "source_context" not in enabled_job_types:
        warnings.append(
            _issue(
                "warning",
                "worker_does_not_handle_source_context",
                "The dedicated worker allowlist does not include source_context; hosted source detection may remain unavailable.",
                env_vars=["CIVORA_ENABLED_JOB_TYPES"],
            )
        )
    if target in {"railway", "render", "split"} and process_role == "combined" and not source_context_externalized:
        warnings.append(
            _issue(
                "warning",
                "combined_web_worker_process",
                "Long source-context jobs share the request service. Use separate web and worker services with shared Postgres for reliable hosted discovery.",
                env_vars=["CIVORA_PROCESS_ROLE", "CIVORA_DEDICATED_WORKER_ENABLED", "DATABASE_URL"],
            )
        )

    ai_provider = str(env.get("CIVORA_AI_PROVIDER") or env.get("CIVORA_LLM_PROVIDER") or "none").strip().lower()
    if ai_provider == "openai" and not str(env.get("OPENAI_API_KEY") or "").strip():
        blockers.append(_issue("blocker", "openai_key_missing", "OPENAI_API_KEY is required when CIVORA_AI_PROVIDER=openai.", env_vars=["CIVORA_AI_PROVIDER", "OPENAI_API_KEY"]))
    elif ai_provider in {"ollama", "local"} and not str(env.get("CIVORA_OLLAMA_BASE_URL") or "").strip():
        blockers.append(_issue("blocker", "ollama_url_missing", "CIVORA_OLLAMA_BASE_URL is required for local/ollama provider mode.", env_vars=["CIVORA_AI_PROVIDER", "CIVORA_OLLAMA_BASE_URL"]))
    elif ai_provider in {"none", "disabled", "off"} and mode == "production":
        warnings.append(_issue("warning", "ai_provider_disabled", "AI provider is disabled in production; deterministic fallbacks only.", env_vars=["CIVORA_AI_PROVIDER"]))

    if mode in PRODUCTION_MODES and not (env.get("MAPBOX_TOKEN") or env.get("NEXT_PUBLIC_MAPBOX_TOKEN")):
        warnings.append(_issue("warning", "mapbox_missing", "Mapbox/geocode config is missing; address lookup should return blocked responses.", env_vars=["MAPBOX_TOKEN", "NEXT_PUBLIC_MAPBOX_TOKEN"]))

    if _truthy(env.get("CIVORA_REQUIRE_GIS_PROVIDERS")) and not str(env.get("CIVORA_GIS_PROVIDER_REGISTRY_URL") or "").strip():
        blockers.append(_issue("blocker", "gis_registry_missing", "GIS provider registry is required by CIVORA_REQUIRE_GIS_PROVIDERS.", env_vars=["CIVORA_GIS_PROVIDER_REGISTRY_URL"]))
    elif mode == "production" and not str(env.get("CIVORA_GIS_PROVIDER_REGISTRY_URL") or "").strip():
        warnings.append(_issue("warning", "gis_registry_missing", "GIS provider registry is not configured; GIS features remain manual/import-only.", env_vars=["CIVORA_GIS_PROVIDER_REGISTRY_URL"]))

    billing_provider = str(env.get("CIVORA_BILLING_PROVIDER") or "none").strip().lower()
    charging_requested = _truthy(env.get("CIVORA_ENABLE_REAL_CHARGING"))
    if charging_requested:
        if billing_provider == "none":
            blockers.append(_issue("blocker", "charging_requested_without_provider", "Charging was requested but no billing provider is configured.", env_vars=["CIVORA_ENABLE_REAL_CHARGING", "CIVORA_BILLING_PROVIDER"]))
        if not _truthy(env.get("CIVORA_BILLING_LEGAL_DOCS_READY")):
            blockers.append(_issue("blocker", "charging_requested_without_business_docs", "Charging was requested but billing business-document readiness is false.", env_vars=["CIVORA_ENABLE_REAL_CHARGING", "CIVORA_BILLING_LEGAL_DOCS_READY"]))
    if billing_provider not in RECOGNIZED_BILLING_PROVIDERS:
        blockers.append(_issue("blocker", "unknown_billing_provider", "Billing provider must be none/disabled/off or a configured supported provider.", env_vars=["CIVORA_BILLING_PROVIDER"]))
    billing_legal_ready = _truthy(env.get("CIVORA_BILLING_LEGAL_DOCS_READY"))
    if billing_provider in {"stripe"} and not billing_legal_ready:
        blockers.append(_issue("blocker", "billing_provider_without_legal_docs", "A real billing provider cannot be selected until billing/legal gates are ready.", env_vars=["CIVORA_BILLING_PROVIDER", "CIVORA_BILLING_LEGAL_DOCS_READY"]))
    if billing_provider == "stripe":
        missing_stripe = [name for name in ("STRIPE_PUBLISHABLE_KEY", "STRIPE_SECRET_KEY", "STRIPE_PILOT_PRICE_ID", "STRIPE_WEBHOOK_SECRET") if not str(env.get(name) or "").strip()]
        if missing_stripe:
            blockers.append(_issue("blocker", "stripe_config_incomplete", "Stripe billing provider is selected but required Stripe config is missing.", env_vars=missing_stripe))
    if charging_requested and billing_provider == "stripe":
        missing_charge_gates = [
            name
            for name in ("CIVORA_BILLING_PROVIDER", "CIVORA_BILLING_LEGAL_DOCS_READY", "STRIPE_PUBLISHABLE_KEY", "STRIPE_SECRET_KEY", "STRIPE_PILOT_PRICE_ID", "STRIPE_WEBHOOK_SECRET")
            if not str(env.get(name) or "").strip()
        ]
        if missing_charge_gates:
            blockers.append(_issue("blocker", "real_charging_gates_incomplete", "Real charging remains blocked until every explicit legal, billing, and provider flag is configured.", env_vars=missing_charge_gates))

    if target == "railway":
        if not env.get("PORT"):
            warnings.append(_issue("warning", "railway_port_unset_locally", "PORT is usually injected by Railway; local validation can only check that the Docker CMD uses it.", env_vars=["PORT"]))
        if str(env.get("CIVORA_RAILWAY_HEALTHCHECK_PATH") or "/api/health").strip() != "/api/health":
            blockers.append(_issue("blocker", "railway_healthcheck_path_mismatch", "Railway healthcheck path must be /api/health.", env_vars=["CIVORA_RAILWAY_HEALTHCHECK_PATH"]))
    if target == "vercel":
        if mode in PRODUCTION_MODES and not frontend_url:
            blockers.append(_issue("blocker", "vercel_api_base_missing", "Vercel builds need NEXT_PUBLIC_API_BASE_URL.", env_vars=["NEXT_PUBLIC_API_BASE_URL"]))
        if str(env.get("CIVORA_VERCEL_ROOT") or "apps/web").strip() != "apps/web":
            warnings.append(_issue("warning", "vercel_root_expected_apps_web", "Vercel project root should be apps/web.", env_vars=["CIVORA_VERCEL_ROOT"]))

    if mode == "production" and _truthy(env.get("CIVORA_ALPHA_REVIEW_ONLY")):
        blockers.append(_issue("blocker", "production_review_only_flag_enabled", "Production mode conflicts with CIVORA_ALPHA_REVIEW_ONLY=true.", env_vars=["CIVORA_PRODUCT_MODE", "CIVORA_ALPHA_REVIEW_ONLY"]))
    if mode in {"private_alpha", "development", "local"} and _truthy(env.get("CIVORA_ENABLE_PUBLIC_ACCESS")):
        blockers.append(_issue("blocker", "public_access_enabled_in_restricted_mode", "Public access flag cannot be enabled in local/development/private_alpha.", env_vars=["CIVORA_ENABLE_PUBLIC_ACCESS"]))

    if mode in PRODUCTION_MODES:
        support_contact = _first_env(env, ("CIVORA_SUPPORT_CONTACT_URL", "CIVORA_SUPPORT_EMAIL", "CIVORA_SUPPORT_CONTACT"))
        public_beta_gates = {
            "support_contact_missing": (not support_contact, ["CIVORA_SUPPORT_CONTACT_URL", "CIVORA_SUPPORT_EMAIL"]),
            "bug_report_url_missing": (not str(env.get("CIVORA_BUG_REPORT_URL") or env.get("CIVORA_BUG_REPORT_FORM_URL") or "").strip(), ["CIVORA_BUG_REPORT_URL"]),
            "escalation_contact_missing": (not str(env.get("CIVORA_ESCALATION_CONTACT") or "").strip(), ["CIVORA_ESCALATION_CONTACT"]),
            "monitoring_owner_missing": (not str(env.get("CIVORA_MONITORING_OWNER") or "").strip(), ["CIVORA_MONITORING_OWNER"]),
            "rollback_owner_missing": (not str(env.get("CIVORA_ROLLBACK_OWNER") or "").strip(), ["CIVORA_ROLLBACK_OWNER"]),
            "billing_legal_docs_not_ready": (not billing_legal_ready, ["CIVORA_BILLING_LEGAL_DOCS_READY"]),
            "public_beta_release_gates_not_green": (not _truthy(env.get("CIVORA_PUBLIC_BETA_RELEASE_GATES_GREEN")), ["CIVORA_PUBLIC_BETA_RELEASE_GATES_GREEN"]),
        }
        for code, (blocked, env_vars) in public_beta_gates.items():
            if blocked:
                blockers.append(
                    _issue(
                        "blocker",
                        code,
                        "Public beta/production remains blocked until support, bug intake, monitoring, rollback, billing/legal, production queue/storage, and release gates are owner-approved.",
                        env_vars=env_vars,
                    )
                )

    if not env.get("CIVORA_OCR_ENGINE"):
        warnings.append(_issue("warning", "ocr_engine_missing", "OCR/PDF extraction provider is not configured; PDF workflows should degrade gracefully.", env_vars=["CIVORA_OCR_ENGINE"]))
    if not env.get("CIVORA_IMAGERY_DETECTION_URL"):
        warnings.append(_issue("warning", "imagery_detection_missing", "Imagery/object detection provider is not configured; Apply Address will use GIS/provider candidates and uploaded-image detection only.", env_vars=["CIVORA_IMAGERY_DETECTION_URL", "CIVORA_IMAGERY_DETECTION_PROVIDER"]))

    status = "blocked" if blockers else "warning" if warnings else "ready"
    diagnostics = {
        spec.name: _redacted_value(spec.name, str(env.get(spec.name) or ""))
        for spec in ENV_VAR_SPECS
        if include_diagnostics
    }
    info.append(_issue("info", "billing_not_auto_enabled", "Validator reports billing config only; it does not enable billing or charging."))
    if mode == "private_alpha" and target == "local":
        info.append(
            _issue(
                "info",
                "local_private_alpha_env_defaults",
                "Documented local defaults: CIVORA_PRODUCT_MODE=private_alpha, CORS_ALLOW_ORIGINS=http://localhost:3000,http://127.0.0.1:3000, PERFORMANCE_AI_STORAGE_DIR=./data. Queue monitoring still requires a live authenticated runtime sample.",
                env_vars=["CIVORA_PRODUCT_MODE", "CORS_ALLOW_ORIGINS", "PERFORMANCE_AI_STORAGE_DIR", "CIVORA_RUNTIME_DEBUG_BEARER_TOKEN"],
            )
        )
    return {
        "version": "production_env_validator_v1",
        "status": status,
        "release_blocked": bool(blockers),
        "product_mode": mode,
        "deployment_target": target,
        "blockers": blockers,
        "warnings": warnings,
        "info": info,
        "diagnostics": diagnostics,
        "required_env_vars": build_env_contract()["required"],
        "optional_env_vars": build_env_contract()["optional"],
        "checks": {
            "vercel": {"root": "apps/web", "api_base_url_present": bool(frontend_url), "api_base_url_public": _is_public_prod_url(frontend_url), "frontend_origin_present": bool(frontend_origin), "localhost_blocked_in_prod": mode in PRODUCTION_MODES},
            "railway": {"port_env": "${PORT:-8002}", "healthcheck_path": "/api/health", "public_url_present": bool(backend_url), "public_url_public": _is_public_prod_url(backend_url)},
        },
    }


__all__ = ["ENV_VAR_SPECS", "build_env_contract", "validate_production_env_v1"]
