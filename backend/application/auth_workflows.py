from __future__ import annotations

from typing import Any, Dict, Protocol

from fastapi import HTTPException


class AuthStoreProtocol(Protocol):
    def register_user(self, *, email: str, password: str, name: str) -> Dict[str, Any]:
        ...

    def login(self, *, email: str, password: str) -> Dict[str, Any]:
        ...

    def logout(self, token: str) -> None:
        ...


def auth_status(*, user_count: int = 0) -> Dict[str, Any]:
    return {
        "success": True,
        "auth_enabled": True,
        "account_setup": "configured" if int(user_count or 0) > 0 else "not_configured",
    }


def register_user(
    *,
    auth_store: AuthStoreProtocol,
    email: str,
    password: str,
    name: str,
) -> Dict[str, Any]:
    try:
        result = auth_store.register_user(email=email, password=password, name=name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, **result}


def login_user(
    *,
    auth_store: AuthStoreProtocol,
    email: str,
    password: str,
) -> Dict[str, Any]:
    try:
        result = auth_store.login(email=email, password=password)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return {"success": True, **result}


def current_user_response(*, current_user: Dict[str, Any]) -> Dict[str, Any]:
    return {"success": True, "user": current_user}


def logout_user(
    *,
    auth_store: AuthStoreProtocol,
    token: str,
) -> Dict[str, Any]:
    auth_store.logout(token)
    return {"success": True}
