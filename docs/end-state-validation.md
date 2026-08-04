# Civora End-State Validation

Run the repeatable local validation from the repository root:

```bash
python3 backend/scripts/run_end_state_capability_validation.py
```

The command checks source and terrain truth, semantic project lifecycle, civil calculation reference projects, reactive changes, deliverable interoperability, heavy-use reliability, frontend build quality, and human-style browser workflows. It writes a structured report to `reports/validation/end_state_capability_validation.json` by default.

Useful options:

```bash
python3 backend/scripts/run_end_state_capability_validation.py --list
python3 backend/scripts/run_end_state_capability_validation.py --gate semantic_project_lifecycle
python3 backend/scripts/run_end_state_capability_validation.py --skip-browser
python3 backend/scripts/run_end_state_capability_validation.py --hosted-url https://civoraai.com
```

Authenticated hosted checks read credentials from the existing Playwright environment. Do not put credentials in this document, commands, source code, or report artifacts.

## Evidence Boundary

Automated green gates do not prove all external evidence. The report intentionally keeps these requirements open until evidence is attached:

- Accepted project survey/control and independent registration check
- External DXF/LandXML target-tool workflow verification
- Independent civil engineer benchmark review
- Repeated authenticated hosted workflow proof
- Real, non-mock GPU visualization-provider proof

The external review should record the reviewer, date, input artifact hashes, expected values, tolerances, observed values, discrepancies, and disposition. Civora's automated report must not convert missing external evidence into a pass.

Use `docs/independent-engineer-validation-protocol.md` for the review packet and sign-off record. A completed packet is evidence for a named benchmark and software revision only; it is not a blanket construction-release authorization.
