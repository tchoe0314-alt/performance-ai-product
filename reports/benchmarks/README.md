# Benchmark artifact policy

This directory keeps intentional benchmark evidence, not every local run output.

## Classifications

- Canonical evidence artifacts: commit stable, named evidence files when they support a roadmap, release gate, or regression claim. Prefer chat- or date-scoped names such as `chat50_dense_utility_benchmark.json`.
- Historical artifacts: move older named evidence into `reports/benchmarks/archive/` when superseded but still useful for audit history.
- Local runtime noise: do not commit ad hoc outputs, especially files using default runner names or machine-specific timing and memory updates.
- Test fixtures: place deterministic input or expected-output fixtures under `tests/fixtures/` when tests need to load them directly.

## Hygiene

- Do not commit secrets, tokens, private URLs, or local filesystem paths.
- Keep generated evidence JSON sorted and deterministic where practical.
- Treat runtime and RSS-only diffs as local noise unless the change is the evidence being intentionally refreshed.
