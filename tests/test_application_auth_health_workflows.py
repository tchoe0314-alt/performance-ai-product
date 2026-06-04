import unittest

from fastapi import HTTPException

from backend.application.auth_workflows import (
    auth_status,
    current_user_response,
    login_user,
    logout_user,
    register_user,
)
from backend.application.health_workflows import health_response


class FakeAuthStore:
    def register_user(self, *, email: str, password: str, name: str):
        if email == "taken@example.com":
            raise ValueError("That email is already registered.")
        return {"user": {"email": email, "name": name}, "token": "tok"}

    def login(self, *, email: str, password: str):
        if password != "good-password":
            raise ValueError("Invalid email or password.")
        return {"user": {"email": email}, "token": "tok"}

    def logout(self, token: str):
        self.token = token


class ApplicationAuthHealthWorkflowsTest(unittest.TestCase):
    def test_health_response(self):
        data = health_response(
            app_name="Civora AI",
            app_version="1.0",
            product_mode="development",
            user_count=3,
        )
        self.assertTrue(data["success"])
        self.assertEqual(data["user_count"], 3)
        self.assertEqual(data["operational_summary"]["status"], "healthy")
        self.assertEqual(data["operational_summary"]["mode"], "development")
        self.assertTrue(data["operational_summary"]["ready_for_ui"])
        self.assertTrue(data["operational_summary"]["review_only"])
        self.assertFalse(data["operational_summary"]["construction_release_enabled"])

    def test_health_response_reports_private_alpha_review_only_guard(self):
        data = health_response(
            app_name="Civora AI",
            app_version="1.0",
            product_mode="private_alpha",
            user_count=3,
            storage="postgres",
            runtime_monitoring={"status": "healthy", "rss_mb": 128.0},
            release_guard={"construction_release_enabled": False, "construction_release_blocked": True},
        )

        self.assertEqual(data["product_mode"], "private_alpha")
        self.assertEqual(data["launch_stage"], "private_alpha")
        self.assertTrue(data["review_only"])
        self.assertTrue(data["alpha_review_guard"]["construction_release_blocked"])
        self.assertFalse(data["alpha_review_guard"]["construction_release_enabled"])
        self.assertEqual(data["monitoring"]["rss_mb"], 128.0)

    def test_auth_status(self):
        data = auth_status(user_count=5)
        self.assertTrue(data["auth_enabled"])
        self.assertEqual(data["user_count"], 5)

    def test_register_user_wraps_success(self):
        data = register_user(
            auth_store=FakeAuthStore(),
            email="a@example.com",
            password="long-enough",
            name="Alice",
        )
        self.assertTrue(data["success"])
        self.assertEqual(data["user"]["email"], "a@example.com")

    def test_register_user_wraps_error(self):
        with self.assertRaises(HTTPException) as ctx:
            register_user(
                auth_store=FakeAuthStore(),
                email="taken@example.com",
                password="long-enough",
                name="Alice",
            )
        self.assertEqual(ctx.exception.status_code, 400)

    def test_login_user_wraps_error(self):
        with self.assertRaises(HTTPException) as ctx:
            login_user(
                auth_store=FakeAuthStore(),
                email="a@example.com",
                password="bad",
            )
        self.assertEqual(ctx.exception.status_code, 401)

    def test_current_user_response_and_logout(self):
        store = FakeAuthStore()
        current = current_user_response(current_user={"user_id": "u1"})
        self.assertTrue(current["success"])
        result = logout_user(auth_store=store, token="tok")
        self.assertTrue(result["success"])
        self.assertEqual(store.token, "tok")


if __name__ == "__main__":
    unittest.main()
