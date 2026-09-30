# Commercial Pad Benchmark 001

## Current status

This is Civora's first reviewer-ready commercial-site benchmark package. Its
automated portion uses repository-owned synthetic survey and constraint files.
It is not yet a real customer project or an independently engineered reference.

The automated report must remain `pending_human_review` until a qualified,
independent reviewer completes the calculation table and provides attributable
evidence for the exact tested software revision.

## Automated scope

The benchmark records:

- SHA-256 hashes for every input artifact;
- coordinate-system and datum declarations;
- source ownership and limitations;
- expected-versus-observed comparisons with explicit tolerances;
- canonical storm, sanitary, utility, and quantity evidence;
- fail-closed civil and construction readiness state; and
- the exact Civora revision used for the run.

Run it from the repository root:

```bash
python3 backend/scripts/run_commercial_site_benchmark.py
```

The report is written to `reports/validation/commercial-pad-001.json` by default.

## Human evidence still required

Use `docs/independent-engineer-validation-protocol.md` to replace the synthetic
reference with a rights-cleared project and independently prepared calculations.
The reviewer must be identified, qualified, independent from benchmark
preparation, and must evaluate values before inspecting Civora's answers.

At minimum, the first human-reviewed commercial project should cover:

- property and developable area;
- building and parking program;
- accessible route and roadway connection;
- existing and proposed grades;
- peak runoff and detention assumptions;
- storm pipe capacity;
- sanitary service and cover;
- water/fire-flow assumptions;
- utility conflicts;
- quantities and exported geometry; and
- one building move followed by affected-system regeneration.

Passing automated checks does not authorize permitting, construction, stamping,
sealing, or professional release.
