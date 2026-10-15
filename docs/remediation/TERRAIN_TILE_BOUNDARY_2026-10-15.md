# Terrain tile transport and image boundary

Parent: `779af92f`. SEC-01/production input validation follow-up.

Terrain-RGB tile fetching used direct requests with unbounded body buffering;
Pillow decode errors escaped and image dimensions/mode were unchecked before
pixel sampling. It now uses bounded public-HTTPS transport in explicit binary
mode, retaining the shared DNS pinning/redirect/deadline/2MiB constraints.
The fixed @2x Terrain-RGB endpoint is accepted only as512x512 PNG RGB or opaque
RGBA; dimensions are inspected before decode. Malformed, unexpected or
transparent tiles return None and are never cached. Valid tiles cache as RGB.
No rescaling or invented elevation values are introduced.

Fresh isolated evidence:
`/tmp/civora-repair-verification.NBAOtD/results/terrain-47.xml`:
84 tests+13 subtests passed. Covers synthetic valid/invalid/dimension/alpha tiles,
binary byte preservation/size rejection, common transport security, standards
and worldwide source behavior. No Mapbox requests, token lookup, production,
customer data, paid services or deployment used.

This changes input safety, not engineering validation. Terrain sampling units,
datum, coordinate controls, missing-cell policy, caller tile_size variations and
surface interpretation still require qualification. In particular,
_elevation_from_rgb returns the Terrain-RGB decoded value while build_terrain_surface
uses foot-named horizontal inputs and no explicit vertical-unit metadata; inspect
all consumers before claiming unit-correct engineering terrain or making a
numerical conversion. Survey accuracy is not established by valid image decode.
Other imagery fetches and total per-request tile budgets remain open.

Rollback is an isolated commit revert; no schema/data migration. Reverting
reopens unbounded/unchecked image handling. Keep equivalent transport and image
limits rather than enabling arbitrary image sizes as a compatibility shortcut.
