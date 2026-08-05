# Civora End-State Validation

Run the repeatable local validation from the repository root:

```bash
python3 backend/scripts/run_end_state_capability_validation.py
```

The command checks source and terrain truth, semantic project lifecycle, civil calculation reference projects, reactive changes, deliverable interoperability, heavy-use reliability, frontend build quality, and human-style browser workflows. It writes a structured report to `reports/validation/end_state_capability_validation.json` by default.

The report also runs separate in-process reference equations for Rational Method flow, Manning full-pipe capacity, Hazen-Williams pressure loss, and canonical semantic area. `internal_software_assurance_complete` becomes true only when all eight required internal gates and all four cross-checks pass.

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

## Internal Assurance Bundle

After the validation report exists, build a hashed evidence bundle without sending artifacts to an external AI provider:

```bash
python3 backend/scripts/build_internal_assurance_bundle.py \
  --validation-report reports/validation/end_state_capability_validation.json \
  --artifact path/to/survey.csv \
  --artifact path/to/review.dxf
```

Optional JSON inputs can attach a survey-control package, internal DXF/LandXML verification results, the hosted gauntlet report, renderer status, and scoped external attestations. Credentials are never accepted by this command and are never written into the bundle.

The hosted gauntlet runs the authenticated workflow twice by default when `CIVORA_EMAIL` and `CIVORA_PASSWORD` are available in the process environment. It never embeds those values in source, command text, or reports.

Create artifact-level DXF/LandXML evidence internally with:

```bash
python3 backend/scripts/verify_internal_interoperability.py \
  --dxf path/to/review.dxf \
  --landxml path/to/review.xml
```

This command parses, roundtrips, and hashes the supplied files and DXF sidecars. It intentionally leaves external AutoCAD/Civil 3D verification false.
