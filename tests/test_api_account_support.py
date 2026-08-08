from __future__ import annotations

from pathlib import Path
import importlib
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.api.app import app
from backend.services.auth_store import AuthStore
from backend.services.data_lifecycle import ACCOUNT_DELETE_CONFIRMATION, DataLifecycleService
from backend.services.database import Database
from backend.services.support_store import SupportStore


api_module = importlib.import_module("backend.api.app")


class AccountSupportApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        root = Path(self.tempdir.name)
        storage = root / "storage"
        uploads = storage / "uploads"
        artifacts = storage / "artifacts"
        uploads.mkdir(parents=True)
        artifacts.mkdir(parents=True)
        db = Database(storage / "api.db")
        self.auth = AuthStore(db)
        self.support = SupportStore(db)
        self.lifecycle = DataLifecycleService(
            db,
            storage_dir=storage,
            upload_dir=uploads,
            artifact_dir=artifacts,
        )
        registration = self.auth.register_user(
            email="api-owner@example.com",
            password="password123",
            name="API Owner",
        )
        self.token = registration["token"]
        self.client = TestClient(app)
        self.patches = (
            patch.object(api_module, "AUTH_STORE", self.auth),
            patch.object(api_module, "SUPPORT_STORE", self.support),
            patch.object(api_module, "DATA_LIFECYCLE", self.lifecycle),
        )
        for item in self.patches:
            item.start()
        api_module._RATE_LIMIT_EVENTS.clear()

    def tearDown(self) -> None:
        for item in reversed(self.patches):
            item.stop()
        self.tempdir.cleanup()

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    def test_support_request_and_account_export_routes(self) -> None:
        support = self.client.post(
            "/api/support/requests",
            headers=self.headers,
            json={
                "category": "workflow",
                "severity": "p2",
                "summary": "The drawing tool needs help",
                "details": "Finish was hard to find.",
                "client_context": {"password": "must-not-store", "browser": "chromium"},
            },
        )
        self.assertEqual(support.status_code, 200, support.text)
        self.assertEqual(support.json()["request"]["client_context"]["password"], "[redacted]")
        listed = self.client.get("/api/support/requests", headers=self.headers)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(len(listed.json()["requests"]), 1)

        exported = self.client.get("/api/account/export", headers=self.headers)
        self.assertEqual(exported.status_code, 200, exported.text)
        self.assertEqual(exported.headers["content-type"], "application/zip")
        self.assertTrue(exported.content.startswith(b"PK"))
        self.assertIn("attachment", exported.headers["content-disposition"])

    def test_account_deletion_requires_password_and_exact_confirmation(self) -> None:
        wrong_password = self.client.request(
            "DELETE",
            "/api/account",
            headers=self.headers,
            json={"current_password": "wrong-password", "confirmation": ACCOUNT_DELETE_CONFIRMATION},
        )
        self.assertEqual(wrong_password.status_code, 401)

        wrong_confirmation = self.client.request(
            "DELETE",
            "/api/account",
            headers=self.headers,
            json={"current_password": "password123", "confirmation": "delete"},
        )
        self.assertEqual(wrong_confirmation.status_code, 409)

        deleted = self.client.request(
            "DELETE",
            "/api/account",
            headers=self.headers,
            json={"current_password": "password123", "confirmation": ACCOUNT_DELETE_CONFIRMATION},
        )
        self.assertEqual(deleted.status_code, 200, deleted.text)
        self.assertTrue(deleted.json()["account_deleted"])
        self.assertEqual(self.client.get("/api/auth/me", headers=self.headers).status_code, 401)

    def test_account_routes_require_authentication(self) -> None:
        self.assertEqual(self.client.get("/api/account/export").status_code, 401)
        self.assertEqual(self.client.get("/api/account/deletion-readiness").status_code, 401)
        self.assertEqual(self.client.get("/api/support/requests").status_code, 401)


if __name__ == "__main__":
    unittest.main()
