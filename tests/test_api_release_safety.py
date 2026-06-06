import os
import unittest
import importlib
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.api.app import (
    ChatLearningCronPayload,
    ProfessionalReleasePayload,
    RegisterPayload,
    _RATE_LIMIT_DEFAULTS,
    _RATE_LIMIT_EVENTS,
    _cors_allow_origins,
    _runtime_debug_payload,
    app,
    chat_learning_cron,
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
        with patch.dict(os.environ, {"CORS_ALLOW_ORIGINS": "*"}):
            origins = _cors_allow_origins()

        self.assertNotEqual(origins, ["*"])
        self.assertIn("https://www.civoraai.com", origins)
        self.assertIn("http://localhost:3000", origins)

    def test_professional_release_payload_defaults_do_not_claim_release(self) -> None:
        payload = ProfessionalReleasePayload()

        self.assertEqual(payload.status, "")
        self.assertFalse(payload.sealed)

    def test_private_alpha_registration_blocks_public_signup_after_bootstrap(self) -> None:
        class FakeConnection:
            def execute(self, _sql: str) -> "FakeConnection":
                return self

            def fetchone(self) -> tuple[int]:
                return (1,)

            def close(self) -> None:
                pass

        class FakeDatabase:
            def connect(self) -> FakeConnection:
                return FakeConnection()

        with patch.object(api_app_module, "DB", FakeDatabase()):
            with patch.dict(os.environ, {"CIVORA_ALLOW_PUBLIC_REGISTRATION": ""}, clear=False):
                with self.assertRaises(HTTPException) as ctx:
                    register(RegisterPayload(email="new@example.com", password="long-enough", name="New User"))

        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("Public registration is disabled", str(ctx.exception.detail))

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
        self.assertEqual(second.json()["detail"], "Rate limit exceeded. Try again later.")


if __name__ == "__main__":
    unittest.main()
