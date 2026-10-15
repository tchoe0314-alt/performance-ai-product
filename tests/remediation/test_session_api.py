"""ASGI-only session flows with a disposable database; no HTTP sockets."""
import importlib

from fastapi.testclient import TestClient

from backend.services.auth_store import AuthStore
from backend.services.database import Database
from backend.services.rate_limit_store import RateLimitStore


def test_rotate_and_revoke_routes_require_identity_and_password(tmp_path, monkeypatch):
    api = importlib.import_module("backend.api.app")
    auth = AuthStore(Database(tmp_path/"session-api.sqlite", database_url="sqlite-local-only"))
    account = auth.register_user(email="session@example.test", password="Synthetic-password-123", name="Test")
    second = auth.login(email="session@example.test", password="Synthetic-password-123")["token"]
    monkeypatch.setattr(api, "AUTH_STORE", auth)
    # Independent test state; does not change configured abuse limits.
    monkeypatch.setattr(api, "RATE_LIMIT_STORE", RateLimitStore(auth.db))
    with TestClient(api.app) as client:
        assert client.post("/api/auth/rotate-session").status_code == 401
        headers = {"Authorization":"Bearer "+account["token"]}
        response = client.post("/api/auth/rotate-session", headers=headers)
        assert response.status_code == 200
        replacement = response.json()["token"]
        assert auth.authenticate_token(account["token"]) is None
        assert auth.authenticate_token(replacement)["user_id"] == account["user"]["user_id"]
        headers = {"Authorization":"Bearer "+replacement}
        assert client.post("/api/auth/logout-all", headers=headers, json={"current_password":"wrong"}).status_code == 403
        assert auth.authenticate_token(second) is not None
        assert client.post("/api/auth/logout-all", headers=headers, json={"current_password":"Synthetic-password-123"}).status_code == 200
        assert auth.authenticate_token(second) is None
        assert auth.authenticate_token(replacement) is None
        assert client.post("/api/auth/rotate-session", headers=headers).status_code == 401
