# Civora RC1 Release Checklist

Use this checklist for a controlled, invite-only, review-focused release. A technical pass does not approve legal terms, billing, professional engineering use, provider contracts, or a public release.

## Decision Rules

- **Technical RC ready** requires every automated evidence item below to pass on the exact release revision.
- **Controlled invite-only release allowed** additionally requires named support, escalation, monitoring, rollback, hosted backup/restore, engineer UAT, pilot terms, privacy terms, and retention-policy evidence.
- **Paid release allowed** additionally requires counsel-approved billing documents, a configured billing provider, and explicit charging enablement.
- **Public beta allowed** additionally requires public production configuration and owner-approved public release gates.
- Civora does not self-approve any human, legal, provider, or professional gate.

## Required Automated Evidence

| Evidence key | Minimum proof | Result |
| --- | --- | --- |
| `backend_regression` | Full `pytest` suite on release revision | Pending |
| `frontend_quality` | Clean install, lint, strict typecheck, production build | Pending |
| `security_dependency` | Dependency audits plus medium/high static Python security analysis | Pending |
| `data_lifecycle` | Authenticated account export/deletion and support intake tests | Pending |
| `backup_restore_local` | SQLite backup, restore, row-count and content-hash comparison | Pending |
| `engineering_real_files` | Golden scenarios, real-file fixtures, expected-vs-actual checks | Pending |
| `browser_core` | Full supported Chromium workflow suite | Pending |
| `browser_cross_device_accessibility` | Chromium, Firefox, WebKit, desktop/mobile and WCAG checks | Pending |
| `long_session_concurrency` | Long interaction session and two-user isolation/concurrency | Pending |
| `hosted_end_to_end` | Authenticated hosted run on exact deployed revision | Pending |

Run the engineering comparison separately:

```bash
PYTHONPATH=. python3 backend/scripts/run_rc1_engineering_validation.py
```

Install the pinned release-audit utilities outside the runtime dependency set before recording security evidence:

```bash
python3 -m pip install -r requirements_audit.txt
```

The RC1 evidence runner audits npm, every pinned Python requirements set, and medium/high Bandit findings across `backend` and `scripts`. Missing audit tooling is a failed evidence item, not a silent skip.

On macOS, Firefox rendering is verified by the `RC1 Firefox accessibility` GitHub Actions workflow. After that workflow succeeds on the exact RC1 commit, provide its HTTPS run URL, revision, and status when recording the cross-browser section:

```bash
export CIVORA_FIREFOX_CI_EVIDENCE_URL="https://github.com/.../actions/runs/..."
export CIVORA_FIREFOX_CI_REVISION="$(git rev-parse HEAD)"
export CIVORA_FIREFOX_CI_STATUS="success"
```

The runner still executes WebKit, mobile Chromium, and mobile WebKit locally. A stale or mismatched Firefox CI revision fails the evidence section.

Run the release decision after an evidence manifest has been created:

```bash
PYTHONPATH=. python3 backend/scripts/run_rc1_readiness.py \
  --evidence-manifest reports/release/rc1-evidence-manifest.json \
  --output reports/release/rc1-readiness.json
```

## Required Operational Evidence

- [ ] User-visible support contact configured.
- [ ] Bug intake URL configured.
- [ ] Named escalation owner recorded.
- [ ] Named monitoring owner recorded.
- [ ] Named rollback owner recorded.
- [ ] Hosted database provider backups enabled.
- [ ] Backup-retention evidence link recorded.
- [ ] Hosted restore drill completed and dated.
- [ ] Incident response tabletop completed.
- [ ] Exact deployment revision recorded.
- [ ] Rollback to the last known-good revision proven.

## Required Human Evidence

- [ ] Independent engineer UAT completed using [rc1-engineer-uat-packet.md](rc1-engineer-uat-packet.md).
- [ ] Engineer UAT owner and evidence link recorded.
- [ ] Pilot terms accepted by the responsible business/counsel owner.
- [ ] Terms and privacy posture accepted by the responsible business/counsel owner.
- [ ] Data retention and deletion policy accepted by the responsible owner.
- [ ] External provider rights and permitted uses reviewed.

## Paid Release Gates

- [ ] Paid pilot order form and billing language approved by counsel.
- [ ] Billing provider configured and tested in its safe test mode.
- [ ] Refund, cancellation, invoice, tax, and support ownership documented.
- [ ] Real charging remains disabled until the preceding items are complete.

## Final Release Record

| Field | Value |
| --- | --- |
| Git revision | Pending |
| Frontend deployment ID | Pending |
| Backend deployment ID | Pending |
| Technical evidence manifest | Pending |
| Hosted evidence report | Pending |
| Engineer UAT evidence | Pending |
| Release owner | Pending |
| Release decision | Pending |
| Decision date/time/timezone | Pending |

Do not replace any `Pending` value with `Pass` unless the linked evidence exists for the exact release revision.
