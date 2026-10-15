# Phase 1: canvas result input association

Local, uncommitted checkpoint; not a deployment or completion of Phase 1.1.

New orchestration results carry a detached SHA-256 input binding covering resolved
canonical canvas/manual fields and legacy site-input source metadata. Project/file
labels are excluded; equivalent integer/float representations are normalized.
The result-read endpoint compares this binding with saved project inputs and
reports current, stale, or unverified. Legacy projects retain their previous
behavior. Existing results without bindings are not retroactively certified.

The website's saved-result loader refuses stale results and displays a short
recalculation message, even if a background job is active. It does not duplicate
the generated plan or invent quantity units.

Verification:

- 138 backend tests plus 5 subtests passed across result binding, canonical canvas,
  design workflows, project workflows, background jobs, and storage fast paths.
- 22 Chromium checks passed, including real local project editing/save/reopen and
  a website test with an intercepted stale-result response.
- TypeScript, scoped lint, production build, and whitespace checks passed.
- Website build ID: `i4IWfWY-z09pD8pShe747`, served locally on port 3050.
- Browser accounts/storage were disposable and local. The result-response test
  intentionally intercepts the endpoint; backend endpoint behavior is separately
  tested directly. No hosted writes, purchases, or production deployment.

Limitations and remaining work:

- This binding proves association with the stated input scope, not engineering
  correctness. Prompt/strategy changes and independent canonical source records
  are not covered by this narrowly named canvas binding.
- Quantity records, canonical result ownership, sources/assumptions, alternative
  histories, and export histories remain incomplete migrations.
- Late background-result writes and cross-session revision conflicts still need
  atomic write protection; read-time freshness detection does not provide that.
  The subsequent [calculation-history checkpoint](phase-1-calculation-history-2026-10-03.md)
  protects adopted canvas background-result writes; broader revision conflicts remain open.
- Direct/active-job result publication still uses existing UI safeguards; this
  new freshness gate specifically covers loading saved results.
- Unverified legacy results remain accessible rather than breaking older projects.
