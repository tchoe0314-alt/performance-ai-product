from __future__ import annotations

from typing import Any, Dict

from backend.planning.alpha_monitoring import build_alpha_monitoring_report


REVIEW_ONLY_PRODUCT_MODES = {"development", "private_alpha", "public_beta", "alpha", "review", "review_only"}


def _normalize_product_mode(value: str) -> str:
    normalized = str(value or "private_alpha").strip().lower().replace("-", "_") or "private_alpha"
    aliases = {
        "alpha": "private_alpha",
        "review": "private_alpha",
        "review_only": "private_alpha",
        "beta": "public_beta",
    }
    return aliases.get(normalized, normalized)


def health_response(
    *,
    app_name: str,
    app_version: str,
    product_mode: str,
    user_count: int,
    storage: str = "sqlite",
    runtime_monitoring: Dict[str, Any] | None = None,
    release_guard: Dict[str, Any] | None = None,
) -> Dict[str, object]:
    normalized_mode = _normalize_product_mode(product_mode)
    normalized_storage = str(storage or "sqlite").strip().lower() or "sqlite"
    review_only = normalized_mode in REVIEW_ONLY_PRODUCT_MODES
    monitoring = runtime_monitoring or {}
    alpha_monitoring_report = build_alpha_monitoring_report(monitoring)
    release = release_guard or {}
    monitoring_status = str(monitoring.get("status") or "healthy").strip().lower() or "healthy"
    operational_status = "healthy" if monitoring_status in {"healthy", "ok"} else "degraded"
    return {
        "success": True,
        "message": "Civora AI backend is running.",
        "app_name": app_name,
        "version": app_version,
        "product_mode": normalized_mode,
        "launch_stage": "private_alpha" if review_only else normalized_mode,
        "review_only": review_only,
        "auth_enabled": True,
        "storage": normalized_storage,
        "user_count": int(user_count),
        "alpha_review_guard": {
            "review_only": review_only,
            "construction_release_enabled": bool(release.get("construction_release_enabled")) and not review_only,
            "construction_release_blocked": review_only or bool(release.get("construction_release_blocked")),
            "truth_label": (
                "Private alpha is review-only; construction release remains blocked."
                if review_only
                else "Production mode may release only through construction package and professional review gates."
            ),
        },
        "monitoring": monitoring,
        "alpha_monitoring_report": alpha_monitoring_report,
        "operational_summary": {
            "status": operational_status,
            "mode": normalized_mode,
            "launch_stage": "private_alpha" if review_only else normalized_mode,
            "review_only": review_only,
            "auth_enabled": True,
            "storage": normalized_storage,
            "user_count": int(user_count),
            "monitoring_status": monitoring_status,
            "alpha_monitoring_status": str(alpha_monitoring_report.get("readiness") or ""),
            "construction_release_enabled": bool(release.get("construction_release_enabled")) and not review_only,
            "construction_release_blocked": review_only or bool(release.get("construction_release_blocked")),
            "ready_for_ui": True,
            "ready_for_public_launch": False,
        },
    }
