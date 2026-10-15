# Raster and adapter contract follow-up

GeoTIFF import now preserves full pixel-corner extent, explicit cell sampling,
native CRS/unit metadata and row/column orientation. It no longer manufactures
mean elevations for NoData. Rotated/sheared/non-square or invalid domains fail
explicitly pending a supported reviewed reprojection. Source files remain intact.
Sampling/registration survive surface metadata projections.

Shared numeric integration can operate in native coordinate units, but APIs
whose fields explicitly say feet/cubic-feet now reject known non-foot inputs
instead of labeling metric values as feet. Missing legacy units still mean
unverified local arithmetic, not survey correctness. General unit conversion,
clipped/TIN domains and reviewed reprojection remain open capabilities.

The older civil-surface fixture counted four nodes as four100ft2 cells although
its bounds enclosed only100ft2. Its fixed-diagonal oracle is net250/3ft3,
cut25/9ft3 and fill775/9ft3. Test expectations now derive from those independent
triangle areas, matching the documented numerical convention rather than
capturing erroneous output.

CAN-01.C1: canonical model adapter version now requires integer1; Python bool,
float and string aliases reject consistently with strict frontend semantics.

Fresh isolated raster/import/civil-model/numerical/TIN/version run:54 PASS,
7 dependency warnings, no skips. Three tiny authored GeoTIFF tests include
NoData, metric units, sample centers, extent and orientation; six version cases
cover malformed/future aliases. Report:
`/tmp/civora-repair-verification.NBAOtD/results/raster-15.xml`.

No old files were reinterpreted or migrated. Rollback must not restore invented
NoData or silently label native metric volumes as cubic feet. Full release
regression, real survey controls and independent review remain unverified.
