# Worldwide Source Context

Apply Address uses the geocoder's coordinates and jurisdiction metadata to choose source coverage for the actual location. It no longer sends globally geocoded addresses back through a U.S.-only source path.

## Source order

1. Accepted project survey/control and record documents when the project has them.
2. Verified city, county, jurisdiction, or utility provider packs when Civora has one for the location.
3. Applicable national sources, such as USGS, FEMA, and USFWS in the United States.
4. Bounded OpenStreetMap/Overpass context for mapped buildings, roads, paths, parking, water, and limited mapped utility features worldwide.
5. Global point elevation through the configured elevation endpoint when a location is outside applicable U.S. coverage or the U.S. point query fails.
6. Configured imagery/object detection for visible candidates not supplied by mapped sources.

Higher-priority geometry wins over a lower-priority duplicate. Worldwide fallback does not replace a verified local building or road layer.

## Runtime settings

```text
CIVORA_OVERPASS_URL=https://overpass-api.de/api/interpreter,https://overpass.kumi.systems/api/interpreter
CIVORA_GLOBAL_ELEVATION_URL=https://api.open-meteo.com/v1/elevation
```

The default Overpass request is limited to a small site bounding box, balances its result budget across buildings, transportation, site context, and mapped utilities, caps output at 1,200 elements, caches results for 15 minutes in the web/worker process, and gives each configured endpoint a 30-second request timeout. Comma-separated endpoints are tried in order. Configure owned or appropriately provisioned provider capacity before sustained hosted traffic.

## Evidence boundaries

- OpenStreetMap is community-mapped context. Coverage, currency, tags, and positional accuracy vary.
- A mapped road is a centerline/context candidate, not a right-of-way boundary.
- Mapped utilities are incomplete context, not utility-owner records or a field locate.
- Global elevation is an approximate DEM point, not a topographic survey, terrain surface, benchmark, or datum.
- Parcels, easements, zoning, flood/environmental authority, subsurface utilities, survey/control, and adopted standards can remain missing depending on the location.
- Every returned feature remains individually reviewable and can be accepted or rejected as a draft candidate.
- Worldwide fallback is not a promise that every building, road, or utility is mapped. Empty and failed provider responses remain visibly empty/failed; Civora does not invent missing features.

The response includes `location_source_strategy_v1`, which records the selected verified provider packs, worldwide fallback status/count, source priority, and remaining authoritative gaps.
