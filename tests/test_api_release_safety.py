import os
import unittest
import importlib
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from fastapi import UploadFile
from fastapi.testclient import TestClient
from starlette.datastructures import Headers

from backend.application.file_workflows import _copy_upload_with_limit, _validate_upload_metadata
from backend.api.app import (
    ChatLearningCronPayload,
    GeocodePayload,
    ProfessionalReleasePayload,
    RegisterPayload,
    _RATE_LIMIT_DEFAULTS,
    _RATE_LIMIT_EVENTS,
    _cors_allow_origins,
    _runtime_debug_payload,
    app,
    chat_learning_cron,
    geocode_address,
    register,
)

api_app_module = importlib.import_module("backend.api.app")


class ApiReleaseSafetyTest(unittest.TestCase):
    def test_debug_runtime_requires_authentication(self) -> None:
        client = TestClient(app)
        response = client.get("/api/debug/runtime")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "Authentication required.")

    def test_runtime_debug_payload_does_not_expose_paths_or_token_prefixes(self) -> None:
        payload = _runtime_debug_payload()

        self.assertNotIn("storage_dir", payload)
        self.assertNotIn("mapbox_token_prefix", payload)
        self.assertIn("storage_kind", payload)
        self.assertIn("mapbox_token_present", payload)

    def test_cron_endpoint_is_disabled_without_configured_secret(self) -> None:
        with patch.object(api_app_module, "CRON_SECRET", ""):
            with self.assertRaises(HTTPException) as ctx:
                chat_learning_cron(ChatLearningCronPayload())

        self.assertEqual(ctx.exception.status_code, 503)
        self.assertIn("CIVORA_CRON_SECRET", str(ctx.exception.detail))

    def test_cors_default_is_not_wildcard_for_private_alpha(self) -> None:
        with patch.dict(os.environ, {"CORS_ALLOW_ORIGINS": "*", "CIVORA_ALLOW_LOCAL_PILOT_CORS": ""}):
            origins = _cors_allow_origins()

        self.assertNotEqual(origins, ["*"])
        self.assertIn("https://www.civoraai.com", origins)
        self.assertIn("https://civoraai.com", origins)
        self.assertNotIn("http://localhost:3000", origins)

    def test_cors_allows_deployed_frontend_origin(self) -> None:
        client = TestClient(app)
        response = client.options(
            "/api/health",
            headers={
                "Origin": "https://civoraai.com",
                "Access-Control-Request-Method": "GET",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("access-control-allow-origin"), "https://civoraai.com")

    def test_cors_blocks_unlisted_origin(self) -> None:
        client = TestClient(app)
        response = client.options(
            "/api/health",
            headers={
                "Origin": "https://example.invalid",
                "Access-Control-Request-Method": "GET",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIsNone(response.headers.get("access-control-allow-origin"))

    def test_local_pilot_cors_origins_require_explicit_flag(self) -> None:
        with patch.dict(os.environ, {"CORS_ALLOW_ORIGINS": "", "CIVORA_ALLOW_LOCAL_PILOT_CORS": ""}, clear=False):
            self.assertNotIn("http://localhost:3000", _cors_allow_origins())

        with patch.dict(os.environ, {"CORS_ALLOW_ORIGINS": "", "CIVORA_ALLOW_LOCAL_PILOT_CORS": "true"}, clear=False):
            origins = _cors_allow_origins()

        self.assertIn("http://localhost:3000", origins)
        self.assertIn("http://127.0.0.1:3000", origins)

    def test_local_pilot_cors_can_be_limited_to_explicit_origin(self) -> None:
        with patch.dict(
            os.environ,
            {
                "CORS_ALLOW_ORIGINS": "",
                "CIVORA_ALLOW_LOCAL_PILOT_CORS": "true",
                "CIVORA_LOCAL_PILOT_CORS_ORIGINS": "http://localhost:4173",
            },
            clear=False,
        ):
            origins = _cors_allow_origins()

        self.assertIn("https://civoraai.com", origins)
        self.assertIn("http://localhost:4173", origins)
        self.assertNotIn("http://localhost:3000", origins)

    def test_geocode_returns_ready_response_for_provider_success(self) -> None:
        testcase = self

        class FakeResponse:
            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict:
                return {"features": [{"center": [-96.8, 32.78], "place_name": "Dallas, Texas"}]}

        class FakeClient:
            def __init__(self, *args, **kwargs) -> None:
                pass

            def __enter__(self) -> "FakeClient":
                return self

            def __exit__(self, *args) -> None:
                return None

            def get(self, *args, **kwargs) -> FakeResponse:
                testcase.assertNotIn("access_token", args[0])
                return FakeResponse()

        with patch.object(api_app_module, "_mapbox_token", return_value=("MAPBOX_TOKEN", "token-value")):
            with patch.object(api_app_module.httpx, "Client", FakeClient):
                response = geocode_address(GeocodePayload(address="Dallas, TX"), current_user={"id": "user-1"})

        self.assertTrue(response.success)
        self.assertFalse(response.blocked)
        self.assertEqual(response.status, "ready")
        self.assertEqual(response.provider, "mapbox")
        self.assertEqual(response.lat, 32.78)
        self.assertEqual(response.lng, -96.8)

    def test_geocode_returns_blocked_response_when_provider_is_missing(self) -> None:
        with patch.object(api_app_module, "_mapbox_token", return_value=(None, "")):
            response = geocode_address(GeocodePayload(address="Dallas, TX"), current_user={"id": "user-1"})

        self.assertFalse(response.success)
        self.assertTrue(response.blocked)
        self.assertEqual(response.status, "provider_not_configured")
        self.assertIsNone(response.lat)
        self.assertIsNone(response.lng)
        self.assertIn("not configured", response.message)
        self.assertNotIn("token", str(response.blockers).lower())

    def test_geocode_returns_blocked_response_for_provider_failure(self) -> None:
        request = api_app_module.httpx.Request("GET", "https://api.mapbox.com/geocoding/v5/mapbox.places/test.json")
        failed_response = api_app_module.httpx.Response(403, request=request)

        class FakeResponse:
            def raise_for_status(self) -> None:
                raise api_app_module.httpx.HTTPStatusError("forbidden", request=request, response=failed_response)

        class FakeClient:
            def __init__(self, *args, **kwargs) -> None:
                pass

            def __enter__(self) -> "FakeClient":
                return self

            def __exit__(self, *args) -> None:
                return None

            def get(self, *args, **kwargs) -> FakeResponse:
                return FakeResponse()

        with patch.object(api_app_module, "_mapbox_token", return_value=("MAPBOX_TOKEN", "token-value")):
            with patch.object(api_app_module.httpx, "Client", FakeClient):
                response = geocode_address(GeocodePayload(address="Dallas, TX"), current_user={"id": "user-1"})

        self.assertFalse(response.success)
        self.assertTrue(response.blocked)
        self.assertEqual(response.status, "provider_unavailable")
        self.assertIsNone(response.lat)
        self.assertIsNone(response.lng)
        self.assertNotIn("token-value", response.message)

    def test_professional_release_payload_defaults_do_not_claim_release(self) -> None:
        payload = ProfessionalReleasePayload()

        self.assertEqual(payload.status, "")
        self.assertFalse(payload.sealed)

    def test_private_alpha_registration_allows_temporary_public_signup(self) -> None:
        class FakeConnection:
            def execute(self, _sql: str, _params: object = ()) -> "FakeConnection":
                return self

            def fetchone(self) -> tuple[int]:
                return (1,)

            def close(self) -> None:
                pass

        class FakeDatabase:
            def connect(self) -> FakeConnection:
                return FakeConnection()

        class FakeAuthStore:
            def register_user(self, *, email: str, password: str, name: str):
                return {"user": {"email": email, "name": name}, "token": "tok"}

        with patch.object(api_app_module, "DB", FakeDatabase()):
            with patch.object(api_app_module, "AUTH_STORE", FakeAuthStore()):
                data = register(RegisterPayload(email="new@example.com", password="long-enough", name="New User"))

        self.assertTrue(data["success"])
        self.assertEqual(data["user"]["email"], "new@example.com")

    def test_production_registration_blocks_public_signup_without_flag(self) -> None:
        class FakeConnection:
            def execute(self, _sql: str, _params: object = ()) -> "FakeConnection":
                return self

            def fetchone(self) -> tuple[int]:
                return (1,)

            def close(self) -> None:
                pass

        class FakeDatabase:
            def connect(self) -> FakeConnection:
                return FakeConnection()

        with patch.object(api_app_module, "DB", FakeDatabase()):
            with patch.object(api_app_module, "PRODUCT_MODE", "production"):
                with patch.dict(os.environ, {"CIVORA_ALLOW_PUBLIC_REGISTRATION": ""}, clear=False):
                    api_app_module._RATE_LIMIT_EVENTS.clear()
                    with self.assertRaises(HTTPException) as ctx:
                        register(RegisterPayload(email="new@example.com", password="long-enough", name="New User"))

        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("Public registration is disabled", str(ctx.exception.detail))

    def test_production_registration_allows_signup_with_flag(self) -> None:
        class FakeConnection:
            def execute(self, _sql: str, _params: object = ()) -> "FakeConnection":
                return self

            def fetchone(self) -> tuple[int]:
                return (1,)

            def close(self) -> None:
                pass

        class FakeDatabase:
            def connect(self) -> FakeConnection:
                return FakeConnection()

        class FakeAuthStore:
            def register_user(self, *, email: str, password: str, name: str):
                return {"user": {"email": email, "name": name}, "token": "tok"}

        with patch.object(api_app_module, "DB", FakeDatabase()):
            with patch.object(api_app_module, "AUTH_STORE", FakeAuthStore()):
                with patch.object(api_app_module, "PRODUCT_MODE", "production"):
                    with patch.dict(os.environ, {"CIVORA_ALLOW_PUBLIC_REGISTRATION": "1"}, clear=False):
                        api_app_module._RATE_LIMIT_EVENTS.clear()
                        data = register(RegisterPayload(email="new@example.com", password="long-enough", name="New User"))

        self.assertTrue(data["success"])
        self.assertEqual(data["user"]["email"], "new@example.com")

    def test_auth_status_route_is_rate_limited(self) -> None:
        client = TestClient(app)
        previous = _RATE_LIMIT_DEFAULTS["auth"]
        _RATE_LIMIT_EVENTS.clear()
        _RATE_LIMIT_DEFAULTS["auth"] = (1, 60)
        try:
            first = client.get("/api/auth/status")
            second = client.get("/api/auth/status")
        finally:
            _RATE_LIMIT_DEFAULTS["auth"] = previous
            _RATE_LIMIT_EVENTS.clear()

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)
        self.assertEqual(second.json()["detail"], "Rate limit exceeded for auth. Wait about 60 seconds, then try again.")

    def test_preview_has_a_separate_bounded_rate_limit(self) -> None:
        preview_limit, preview_window = _RATE_LIMIT_DEFAULTS["preview"]
        planner_limit, planner_window = _RATE_LIMIT_DEFAULTS["planner"]

        self.assertEqual((preview_limit, preview_window), (120, 60))
        self.assertEqual((planner_limit, planner_window), (40, 60))
        self.assertGreater(preview_limit, planner_limit)
        self.assertLess(preview_limit, 1000)

    def test_upload_type_error_names_allowed_extensions(self) -> None:
        upload = UploadFile(filename="site.bmp", file=BytesIO(b"not-an-image"), headers=Headers({"content-type": "image/bmp"}))

        with self.assertRaises(HTTPException) as ctx:
            _validate_upload_metadata(
                file=upload,
                safe_name="site.bmp",
                allowed_extensions={".png", ".jpg", ".jpeg", ".webp"},
                allowed_content_types={"image/png", "image/jpeg", "image/webp"},
            )

        self.assertEqual(ctx.exception.status_code, 415)
        self.assertIn("Unsupported upload file type", str(ctx.exception.detail))
        self.assertIn(".png", str(ctx.exception.detail))

    def test_upload_size_error_names_limit(self) -> None:
        target = Path(os.getcwd()) / "_tmp_upload_limit_test.bin"
        upload = UploadFile(filename="site.png", file=BytesIO(b"x" * 8))
        try:
            with self.assertRaises(HTTPException) as ctx:
                _copy_upload_with_limit(file=upload, target=target, max_bytes=4)
        finally:
            target.unlink(missing_ok=True)

        self.assertEqual(ctx.exception.status_code, 413)
        self.assertIn("Maximum allowed size", str(ctx.exception.detail))


if __name__ == "__main__":
    unittest.main()
