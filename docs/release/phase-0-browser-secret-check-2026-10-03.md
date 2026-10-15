# Phase 0.5 browser-visible credential safeguard

The owner explicitly deferred the live storage-permission and file-backup checks. They remain unproven, not completed or waived. No production backend settings or paid resources were changed.

The environment validator now flags private credentials mistakenly assigned to browser-visible `NEXT_PUBLIC_*` settings, including unknown settings outside the documented contract. Findings contain setting names, never their credential values. Public Mapbox and Stripe publishable settings remain supported; recognizable private key values in those settings are rejected. Empty settings remain valid.

Verification: the validator suite passed 28 tests and six parameterized subtests, covering existing configuration behavior, public-key compatibility, server-only key redaction, private-key findings, and diagnostics-disabled operation. One existing Starlette/httpx deprecation warning remains.

The combined affected-area run passed 79 tests plus six subtests across environment validation, API release safety, release-candidate readiness, and data lifecycle/backup behavior. The patch whitespace check also passed.

This is local validation evidence. It does not establish that deployed browser assets are secret-free, automatically enforce a hosting promotion, or rotate previously exposed credentials. Production was unchanged.
