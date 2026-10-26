"""C06: status-only tests; synthetic strings, no provider client or payment calls."""
from itertools import product
import unittest

from backend.services.billing import (
    BillingConfig, DisabledBillingProvider, StripeBillingProvider,
    build_billing_status,
)


class BillingEffectiveCapabilityTests(unittest.TestCase):
    def test_disabled_providers_never_report_effective_charging(self):
        providers = (
            DisabledBillingProvider(),
            StripeBillingProvider("synthetic-public", "", "", ""),
            StripeBillingProvider("synthetic-public", "synthetic-secret", "synthetic-price", "synthetic-webhook"),
        )
        for provider, paid, requested, legal, enrolled in product(providers, (False, True), (False, True), (False, True), (False, True)):
            with self.subTest(provider=provider.provider_name, configured=provider.configured(), paid=paid,
                              requested=requested, legal=legal, enrolled=enrolled):
                config = BillingConfig(
                    paid_pilot_mode=paid, charging_enabled=requested, legal_docs_ready=legal,
                    terms_url="", privacy_url="", order_form_url="", provider_name=provider.provider_name,
                    plan_code="synthetic", plan_label="Synthetic status only", monthly_project_limit=5,
                    monthly_export_limit=20, monthly_job_limit=40, pilot_user_ids=["enrolled"], pilot_emails=[],
                )
                status = build_billing_status(
                    user={"user_id": "enrolled" if enrolled else "other"}, config=config, provider=provider,
                )
                self.assertFalse(provider.status()["charging_enabled"])
                self.assertEqual(status["charging_config_requested"], requested)
                self.assertFalse(status["real_charging_enabled"])
                self.assertFalse(status["charging_guard"]["real_charging_allowed"])
                self.assertNotEqual(status["operational_state"], "enabled")
                self.assertEqual(status["payment"]["status"], "disabled")


if __name__ == "__main__":
    unittest.main()
