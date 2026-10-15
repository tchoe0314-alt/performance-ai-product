# P02 execution scope and product rules

Date: October 15, 2026. Application baseline `ab7db888e85fb9b6125551ecff769d08e0ca7322`; P01 delivery `ef22d42c4647e15cd0d6815b9d3816702cf9dbb4`.

The founder subsequently authorized an **internal P01 review and P02 decision/compatibility preparation only**, acknowledging that self-review is not independent professional validation. This addendum records that narrower authority without editing the eight original planning documents or old audit evidence. It does not grant implementation authority for P03 or any security workstream.

## Product rule, as clarified by the founder

Civora does not sign or seal engineering deliverables or provide professional approval. The engineer using the software performs their own review and signs/seals their own work where applicable. This is a product boundary, not a legal opinion or a transfer of responsibility for software defects.

Civora still must calculate correctly within its stated supported scope, preserve inputs/units/sources, reject invalid inputs, identify estimates and missing information, and keep edits/results/exports consistent. A disclaimer or end-user review is not a substitute for those duties.

Internal diagnosis, analytical tests, software verification, decision preparation and separately authorized repairs do not require Civora to stamp a project. Independent method/benchmark review remains valuable evidence; Codex cannot impersonate a licensed reviewer or self-certify independence. The original independent-review release gates remain pending unless explicitly revised by an authorized release decision. Preparing a draft is not satisfying those gates.

## Authorized file boundary

New files only in `docs/remediation/p02/`, `tests/remediation/test_p02.py`, `tests/remediation/run_p02.py` and `tests/remediation/fixtures/p02_*.json`. No change to existing application, frontend, dependencies, configuration, schema, calculation output, security, billing, source evidence or the eight pre-existing plan files. No customer data, production, paid provider, external network, migration or deployment access. Local synthetic tests and unique evidence files only.

Dedicated branch: `codex/remediation-p02-contract-decisions`, based on the P01 commit. No commit/push is implied by this preparation authorization. Pre-existing `docs/remediation/CIVORA_*.md` files remain untracked and untouched.

## Acceptance states

- P01: internal mechanical review may accept evidence for **limited internal preparation**, with missing original-source and external-review gaps retained. No independent QA/release approval is invented.
- P02 preparation: draft owner/method/migration decisions, selected synthetic compatibility fixtures, and executable tests can be completed now.
- P02 formal decisions: architecture/numerical/geospatial approval and any required independent method review remain recorded as **PENDING**. No algorithm, array interpretation, unit conversion or schema migration takes effect from these documents.
- P03 and later packages: require separate founder authorization and applicable decision acceptance. No automatic continuation.

If the founder wants a different review requirement for a release gate, record that explicit change separately; do not silently relabel the original gate PASS. No engineering-grade or launch-readiness claim follows from P02 preparation.
