import unittest

from fastapi.testclient import TestClient

from backend.api.app import app
from backend.application.production_env_validator_v1 import validate_production_env_v1


class ProductionEnvValidatorV1Test(unittest.TestCase):
    def test_blocks_missing_required_production_config(self) -> None:
        report = validate_production_env_v1({"CIVORA_PRODUCT_MODE": "production"}, deployment_target="vercel")

        self.assertTrue(report["release_blocked"])
        codes = {item["code"] for item in report["blockers"]}
        self.assertIn("missing_required_env", codes)
        self.assertIn("public_api_base_url_missing", codes)
        self.assertIn("backend_public_url_missing", codes)
        self.assertIn("vercel_api_base_missing", codes)

    def test_redacts_secret_diagnostics(self) -> None:
        report = validate_production_env_v1(
            {
                "CIVORA_PRODUCT_MODE": "production",
                "NEXT_PUBLIC_API_BASE_URL": "https://api.example.com",
                "CIVORA_PUBLIC_API_BASE_URL": "https://api.example.com",
                "CORS_ALLOW_ORIGINS": "https://app.example.com",
                "CIVORA_SESSION_SECRET": "super-secret-session-value",
                "PERFORMANCE_AI_STORAGE_DIR": "/data",
                "CIVORA_AI_PROVIDER": "openai",
                "OPENAI_API_KEY": "sk-test-secret",
            },
            deployment_target="railway",
        )

        diagnostics = report["diagnostics"]
        self.assertEqual(diagnostics["OPENAI_API_KEY"]["present"], True)
        self.assertEqual(diagnostics["OPENAI_API_KEY"]["redacted"], True)
        self.assertNotIn("sk-test-secret", str(report))
        self.assertNotIn("super-secret-session-value", str(report))

    def test_openai_provider_requires_key(self) -> None:
        report = validate_production_env_v1(
            {
                "CIVORA_PRODUCT_MODE": "production",
                "NEXT_PUBLIC_API_BASE_URL": "https://api.example.com",
                "CIVORA_PUBLIC_API_BASE_URL": "https://api.example.com",
                "CORS_ALLOW_ORIGINS": "https://app.example.com",
                "CIVORA_SESSION_SECRET": "session-secret",
                "PERFORMANCE_AI_STORAGE_DIR": "/data",
                "CIVORA_AI_PROVIDER": "openai",
            }
        )

        self.assertIn("openai_key_missing", {item["code"] for item in report["blockers"]})

    def test_private_alpha_warns_for_optional_provider_gaps(self) -> None:
        report = validate_production_env_v1(
            {
                "CIVORA_PRODUCT_MODE": "private_alpha",
                "CORS_ALLOW_ORIGINS": "https://civoraai.com",
                "PERFORMANCE_AI_STORAGE_DIR": "/data",
                "CIVORA_AI_PROVIDER": "none",
            }
        )

        self.assertFalse(report["release_blocked"])
        self.assertEqual(report["status"], "warning")
        self.assertIn("ocr_engine_missing", {item["code"] for item in report["warnings"]})

    def test_production_blocks_wildcard_cors_and_localhost_api(self) -> None:
        report = validate_production_env_v1(
            {
                "CIVORA_PRODUCT_MODE": "production",
                "NEXT_PUBLIC_API_BASE_URL": "http://localhost:8002",
                "CIVORA_PUBLIC_API_BASE_URL": "https://api.example.com",
                "CORS_ALLOW_ORIGINS": "*",
                "CIVORA_SESSION_SECRET": "session-secret",
                "PERFORMANCE_AI_STORAGE_DIR": "/data",
                "CIVORA_AI_PROVIDER": "none",
            }
        )

        codes = {item["code"] for item in report["blockers"]}
        self.assertIn("frontend_api_base_url_localhost", codes)
        self.assertIn("wildcard_cors_not_allowed", codes)

    def test_production_blocks_mixed_wildcard_cors_and_insecure_public_urls(self) -> None:
        report = validate_production_env_v1(
            {
                "CIVORA_PRODUCT_MODE": "production",
                "NEXT_PUBLIC_API_BASE_URL": "http://api.example.com",
                "CIVORA_PUBLIC_API_BASE_URL": "http://api.example.com",
                "CORS_ALLOW_ORIGINS": "https://app.example.com,*",
                "CIVORA_FRONTEND_PUBLIC_URL": "https://app.example.com",
                "CIVORA_SESSION_SECRET": "session-secret",
                "PERFORMANCE_AI_STORAGE_DIR": "/data",
                "CIVORA_AI_PROVIDER": "none",
            }
        )

        codes = {item["code"] for item in report["blockers"]}
        self.assertIn("wildcard_cors_not_allowed", codes)
        self.assertIn("frontend_api_base_url_not_https", codes)
        self.assertIn("backend_public_url_not_https", codes)

    def test_gis_requirement_promotes_missing_registry_to_blocker(self) -> None:
        report = validate_production_env_v1(
            {
                "CIVORA_PRODUCT_MODE": "private_alpha",
                "CORS_ALLOW_ORIGINS": "https://civoraai.com",
                "PERFORMANCE_AI_STORAGE_DIR": "/data",
                "CIVORA_REQUIRE_GIS_PROVIDERS": "true",
            }
        )

        self.assertIn("gis_registry_missing", {item["code"] for item in report["blockers"]})

    def test_public_beta_warns_when_temporary_local_cors_is_enabled(self) -> None:
        report = validate_production_env_v1(
            {
                "CIVORA_PRODUCT_MODE": "public_beta",
                "NEXT_PUBLIC_API_BASE_URL": "https://api.example.com",
                "CIVORA_PUBLIC_API_BASE_URL": "https://api.example.com",
                "CORS_ALLOW_ORIGINS": "https://app.example.com",
                "CIVORA_FRONTEND_PUBLIC_URL": "https://app.example.com",
                "CIVORA_SESSION_SECRET": "session-secret",
                "PERFORMANCE_AI_STORAGE_DIR": "/data",
                "CIVORA_AI_PROVIDER": "none",
                "CIVORA_ALLOW_LOCAL_PILOT_CORS": "true",
            }
        )

        self.assertIn("temporary_local_cors_enabled", {item["code"] for item in report["warnings"]})
        self.assertIn("public_beta_release_gates_not_green", {item["code"] for item in report["blockers"]})

    def test_public_beta_blocks_until_ops_gates_are_configured(self) -> None:
        report = validate_production_env_v1(
            {
                "CIVORA_PRODUCT_MODE": "public_beta",
                "NEXT_PUBLIC_API_BASE_URL": "https://api.example.com",
                "CIVORA_PUBLIC_API_BASE_URL": "https://api.example.com",
                "CORS_ALLOW_ORIGINS": "https://app.example.com",
                "CIVORA_FRONTEND_PUBLIC_URL": "https://app.example.com",
                "CIVORA_SESSION_SECRET": "session-secret",
                "PERFORMANCE_AI_STORAGE_DIR": "/data",
                "CIVORA_AI_PROVIDER": "none",
                "CIVORA_BILLING_LEGAL_DOCS_READY": "true",
            }
        )

        codes = {item["code"] for item in report["blockers"]}
        self.assertIn("support_contact_missing", codes)
        self.assertIn("bug_report_url_missing", codes)
        self.assertIn("monitoring_owner_missing", codes)
        self.assertIn("rollback_owner_missing", codes)
        self.assertIn("public_beta_release_gates_not_green", codes)

    def test_real_charging_requires_legal_and_provider_gates(self) -> None:
        report = validate_production_env_v1(
            {
                "CIVORA_PRODUCT_MODE": "production",
                "NEXT_PUBLIC_API_BASE_URL": "https://api.example.com",
                "CIVORA_PUBLIC_API_BASE_URL": "https://api.example.com",
                "CORS_ALLOW_ORIGINS": "https://app.example.com",
                "CIVORA_FRONTEND_PUBLIC_URL": "https://app.example.com",
                "CIVORA_SESSION_SECRET": "session-secret",
                "PERFORMANCE_AI_STORAGE_DIR": "/data",
                "CIVORA_AI_PROVIDER": "none",
                "CIVORA_ENABLE_REAL_CHARGING": "true",
                "CIVORA_BILLING_PROVIDER": "stripe",
                "CIVORA_SUPPORT_CONTACT_URL": "https://support.example.com",
                "CIVORA_BUG_REPORT_URL": "https://support.example.com/bugs",
                "CIVORA_ESCALATION_CONTACT": "ops@example.com",
                "CIVORA_MONITORING_OWNER": "ops@example.com",
                "CIVORA_ROLLBACK_OWNER": "release@example.com",
                "CIVORA_PUBLIC_BETA_RELEASE_GATES_GREEN": "true",
            }
        )

        codes = {item["code"] for item in report["blockers"]}
        self.assertIn("billing_provider_without_legal_docs", codes)
        self.assertIn("stripe_config_incomplete", codes)
        self.assertIn("real_charging_gates_incomplete", codes)

    def test_public_beta_env_contract_can_be_ready_when_ops_gates_are_green(self) -> None:
        report = validate_production_env_v1(
            {
                "CIVORA_PRODUCT_MODE": "public_beta",
                "NEXT_PUBLIC_API_BASE_URL": "https://api.example.com",
                "CIVORA_PUBLIC_API_BASE_URL": "https://api.example.com",
                "CORS_ALLOW_ORIGINS": "https://app.example.com",
                "CIVORA_FRONTEND_PUBLIC_URL": "https://app.example.com",
                "CIVORA_SESSION_SECRET": "session-secret",
                "PERFORMANCE_AI_STORAGE_DIR": "/data",
                "CIVORA_AI_PROVIDER": "none",
                "CIVORA_SUPPORT_CONTACT_URL": "https://support.example.com",
                "CIVORA_BUG_REPORT_URL": "https://support.example.com/bugs",
                "CIVORA_ESCALATION_CONTACT": "ops@example.com",
                "CIVORA_MONITORING_OWNER": "ops@example.com",
                "CIVORA_ROLLBACK_OWNER": "release@example.com",
                "CIVORA_PUBLIC_BETA_RELEASE_GATES_GREEN": "true",
                "CIVORA_BILLING_LEGAL_DOCS_READY": "true",
                "CIVORA_OCR_ENGINE": "manual",
            }
        )

        self.assertFalse(report["release_blocked"])
        self.assertEqual(report["status"], "warning")

    def test_debug_endpoint_requires_authentication(self) -> None:
        response = TestClient(app).get("/api/debug/production-env")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "Authentication required.")


if __name__ == "__main__":
    unittest.main()
