# Unavailable terrain fallback provenance

Parent: `c9f04ed0`. Missing-data/source distinction follow-up.

When terrain retrieval returned None, grading retained its inferred source type
but did not state that terrain had been attempted and failed. It now records
terrain_attempted, terrain_used=false and terrain_unavailable=true, and adds an
explicit unavailable/incomplete/not-surveyed explanation to source_detail.
The existing grading summary source_detail projection carries this explanation;
the summary also exposes terrain_unavailable. No synthetic fallback formulas or
numerical units changed, and fallback is not relabeled as provider terrain.

Isolated report: `/tmp/civora-repair-verification.NBAOtD/results/provenance-49.xml`.
Tests cover explicit unavailable-provider provenance, synthetic tile safety and
existing TIN tests. No real providers, production/customer data, paid services or
deployments used. This is metadata/contract verification, not independent browser
warning visibility or export/release gate acceptance. Units/datum and inferred
fallback gating remain open. Rollback is a commit revert with no data migration.
