import os
import tempfile
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
from backend.application.memory_logging import (
    record_process_shutdown,
    record_process_start,
    runtime_monitoring_snapshot,
)


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
        self.assertEqual(data["alpha_monitoring_report"]["readiness"], "blocked")

    def test_health_response_reports_private_alpha_review_only_guard(self):
        data = health_response(
            app_name="Civora AI",
            app_version="1.0",
            product_mode="private_alpha",
            user_count=3,
            storage="postgres",
            runtime_monitoring={
                "status": "healthy",
                "rss_mb": 128.0,
                "peak_rss_mb": 180.0,
                "job_queue": {
                    "status": "healthy",
                    "monitored_job_types": ["orchestrate", "drainage_only"],
                    "queued_count": 0,
                    "failed_recent_count": 0,
                    "stale_job_count": 0,
                    "oldest_active_age_sec": 0.0,
                },
                "process": {"status": "healthy", "recent_start_count": 1},
            },
            release_guard={"construction_release_enabled": False, "construction_release_blocked": True},
        )

        self.assertEqual(data["product_mode"], "private_alpha")
        self.assertEqual(data["launch_stage"], "private_alpha")
        self.assertTrue(data["review_only"])
        self.assertTrue(data["alpha_review_guard"]["construction_release_blocked"])
        self.assertFalse(data["alpha_review_guard"]["construction_release_enabled"])
        self.assertEqual(data["monitoring"]["rss_mb"], 128.0)
        self.assertEqual(data["alpha_monitoring_report"]["readiness"], "ready")
        self.assertEqual(data["operational_summary"]["alpha_monitoring_status"], "ready")

    def test_runtime_monitoring_reports_process_restart_risk(self):
        previous = {
            key: os.environ.get(key)
            for key in (
                "CIVORA_RESTART_WINDOW_SECONDS",
                "CIVORA_RESTART_WARNING_COUNT",
                "CIVORA_RESTART_CRITICAL_COUNT",
            )
        }
        os.environ["CIVORA_RESTART_WINDOW_SECONDS"] = "60"
        os.environ["CIVORA_RESTART_WARNING_COUNT"] = "2"
        os.environ["CIVORA_RESTART_CRITICAL_COUNT"] = "3"
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                record_process_start(state_dir=tmpdir, start_time=1000.0, instance_id="one")
                record_process_start(state_dir=tmpdir, start_time=1010.0, instance_id="two")
                process = record_process_start(state_dir=tmpdir, start_time=1020.0, instance_id="three")
                combined = runtime_monitoring_snapshot(
                    job_queue={
                        "registered_handlers": ["orchestrate"],
                        "monitoring": {
                            "status": "healthy",
                            "queued_count": 0,
                            "failed_recent_count": 0,
                            "stale_job_count": 0,
                        },
                    },
                    process=process,
                )

                self.assertEqual(process["status"], "critical")
                self.assertEqual(process["recent_start_count"], 3)
                self.assertFalse(process["previous_shutdown_clean"])
                self.assertIn("process_restart_critical_threshold_exceeded", process["warnings"])
                self.assertEqual(combined["status"], "critical")
                self.assertIn("process_monitoring_not_healthy", combined["warnings"])

                record_process_shutdown(state_dir=tmpdir, instance_id="three", now=1030.0)
                clean = record_process_start(state_dir=tmpdir, start_time=1040.0, instance_id="four")
                self.assertTrue(clean["previous_shutdown_clean"])
                self.assertNotIn("previous_process_did_not_shutdown_cleanly", clean["warnings"])
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

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
