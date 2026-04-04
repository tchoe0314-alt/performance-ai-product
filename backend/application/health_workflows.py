from __future__ import annotations

from typing import Dict


def health_response(
    *,
    app_name: str,
    app_version: str,
    product_mode: str,
    user_count: int,
) -> Dict[str, object]:
    return {
        "success": True,
        "message": "Civora AI backend is running.",
        "app_name": app_name,
        "version": app_version,
        "product_mode": product_mode,
        "auth_enabled": True,
        "storage": "sqlite",
        "user_count": int(user_count),
    }
