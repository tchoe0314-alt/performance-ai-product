import os
import unittest
import importlib
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.api.app import (
    ChatLearningCronPayload,
    ProfessionalReleasePayload,
    _cors_allow_origins,
    _runtime_debug_payload,
    app,
    chat_learning_cron,
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


if __name__ == "__main__":
    unittest.main()
