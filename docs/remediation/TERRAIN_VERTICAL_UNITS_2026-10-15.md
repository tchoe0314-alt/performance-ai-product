# Terrain surface vertical units

Parent: `d90f2385`. Engineering units mismatch confirmed in caller/provider code.

Source inspected2026-10-15:
https://docs.mapbox.com/data/tilesets/reference/mapbox-terrain-rgb-v1/
Provider documentation states decoded heights are metres, using the implemented
RGB formula. It also states sources use different vertical datum references.

build_terrain_surface receives foot-labelled lot dimensions and a foot-coordinate
grid from grading_support, but previously inserted raw metre heights directly.
The surface adapter now converts decoded metres to international feet by dividing
by exact0.3048. The raw decoder and standalone sample_elevation remain metres,
explicitly documented, so their compatibility contract does not silently change.
The grid records horizontal/vertical ft, unknown CRS/datum, provider identity and
unverified control. Sample metadata records source metres and the conversion.
This corrects unit magnitude, not geoid/datum/survey accuracy. No saved surfaces
or results were rewritten. Prior terrain results need rerun and review; this
commit does not recertify them or stamp a global engine qualification.

Fresh isolated evidence:
`/tmp/civora-repair-verification.NBAOtD/results/units-53.xml`.
25 tests passed across independent RGB100metre/328.0839895013123ft oracle, tile
safety, budgets, missing-data provenance and GeoTIFF spatial contracts. Expected
conversion is independently specified, not copied from provider output. No live
tiles, actual tokens, production/customer data, paid API or deployment used.

Remaining: engine-version qualification/invalidation for previous terrain runs,
survey datum alignment, downstream registered-surface compatibility, professional
control benchmarks and complete unit workflows. Unknown datum must not be
relabeled NAVD88 or verified. Rollback reopens the magnitude defect; do not mix
old/new terrain quantities without explicit version and review. No schema/data
rollback required, but preserve historical results as unverified evidence.
