import unittest

from backend.planning.existing_conditions_online import fetch_online_existing_conditions
from backend.planning.gis_provider_registry import build_arcgis_provider_record, build_provider_registry
from backend.planning.worldwide_source_discovery import (
    fetch_global_elevation_point,
    fetch_openstreetmap_site_context,
)


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def _osm_payload():
    return {
        "elements": [
            {
                "type": "way",
                "id": 101,
                "tags": {"building": "office", "name": "Example House"},
                "geometry": [
                    {"lat": 51.5000, "lon": -0.1250},
                    {"lat": 51.5000, "lon": -0.1248},
                    {"lat": 51.5002, "lon": -0.1248},
                    {"lat": 51.5002, "lon": -0.1250},
                    {"lat": 51.5000, "lon": -0.1250},
                ],
            },
            {
                "type": "way",
                "id": 102,
                "tags": {"highway": "residential", "name": "Example Road"},
                "geometry": [
                    {"lat": 51.4998, "lon": -0.1252},
                    {"lat": 51.5004, "lon": -0.1246},
                ],
            },
            {
                "type": "way",
                "id": 103,
                "tags": {"amenity": "parking"},
                "geometry": [
                    {"lat": 51.5001, "lon": -0.1247},
                    {"lat": 51.5001, "lon": -0.1246},
                    {"lat": 51.5002, "lon": -0.1246},
                    {"lat": 51.5001, "lon": -0.1247},
                ],
            },
            {
                "type": "way",
                "id": 104,
                "tags": {"highway": "footway"},
                "geometry": [
                    {"lat": 51.4999, "lon": -0.1250},
                    {"lat": 51.5003, "lon": -0.1249},
                ],
            },
            {
                "type": "way",
                "id": 105,
                "tags": {"natural": "water"},
                "geometry": [
                    {"lat": 51.5003, "lon": -0.1247},
                    {"lat": 51.5003, "lon": -0.1246},
                    {"lat": 51.5004, "lon": -0.1246},
                    {"lat": 51.5003, "lon": -0.1247},
                ],
            },
            {
                "type": "node",
                "id": 106,
                "lat": 51.5001,
                "lon": -0.1249,
                "tags": {"emergency": "fire_hydrant"},
            },
        ]
    }


class _WorldwideSession:
    def __init__(self):
        self.calls = []

    def get(self, url, params=None, timeout=None, headers=None):
        self.calls.append({"url": url, "params": params or {}, "timeout": timeout, "headers": headers or {}})
        if "open-meteo.com" in url:
            return _Response({"elevation": [18.0]})
        if "overpass" in url:
            return _Response(_osm_payload())
        raise AssertionError(f"Unexpected non-worldwide source request: {url}")


class _OfficialAndWorldwideSession(_WorldwideSession):
    def get(self, url, params=None, timeout=None, headers=None):
        if "county.example" in url:
            self.calls.append({"url": url, "params": params or {}, "timeout": timeout, "headers": headers or {}})
            return _Response(
                {
                    "type": "FeatureCollection",
                    "features": [
                        {
                            "type": "Feature",
                            "id": "official-building",
                            "properties": {},
                            "geometry": {
                                "type": "Polygon",
                                "coordinates": [[[-0.125, 51.5], [-0.1248, 51.5], [-0.125, 51.5]]],
                            },
                        }
                    ],
                }
            )
        return super().get(url, params=params, timeout=timeout, headers=headers)


class _FallbackWorldwideSession(_WorldwideSession):
    def get(self, url, params=None, timeout=None, headers=None):
        if "overpass-api.de" in url:
            self.calls.append({"url": url, "params": params or {}, "timeout": timeout, "headers": headers or {}})
            raise TimeoutError("primary endpoint timeout")
        return super().get(url, params=params, timeout=timeout, headers=headers)


class _UsAddressAndWorldwideSession(_WorldwideSession):
    def get(self, url, params=None, timeout=None, headers=None):
        self.calls.append({"url": url, "params": params or {}, "timeout": timeout, "headers": headers or {}})
        if "geocoder" in url:
            return _Response(
                {
                    "result": {
                        "addressMatches": [
                            {
                                "matchedAddress": "20525 MARGO ST, GRETNA, NE, 68028",
                                "coordinates": {"x": -96.2370, "y": 41.1852},
                            }
                        ]
                    }
                }
            )
        if "overpass" in url:
            return _Response(_osm_payload())
        raise AssertionError(f"Unexpected source request: {url}")


class _EmptyWorldwideSession(_WorldwideSession):
    def get(self, url, params=None, timeout=None, headers=None):
        self.calls.append({"url": url, "params": params or {}, "timeout": timeout, "headers": headers or {}})
        if "overpass" in url:
            return _Response({"elements": []})
        if "open-meteo.com" in url:
            return _Response({"elevation": []})
        raise AssertionError(f"Unexpected source request: {url}")


class _FailedWorldwideSession(_WorldwideSession):
    def get(self, url, params=None, timeout=None, headers=None):
        self.calls.append({"url": url, "params": params or {}, "timeout": timeout, "headers": headers or {}})
        raise TimeoutError("provider unavailable")


class WorldwideSourceDiscoveryTests(unittest.TestCase):
    def test_openstreetmap_fetch_classifies_bounded_site_features(self) -> None:
        session = _WorldwideSession()

        result = fetch_openstreetmap_site_context(
            {"west": -0.126, "south": 51.499, "east": -0.124, "north": 51.501},
            session=session,
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["source_tier"], "community_global")
        self.assertEqual(result["feature_count"], 6)
        self.assertEqual(result["layer_results"]["building_footprints"]["feature_count"], 1)
        self.assertEqual(result["layer_results"]["roads"]["feature_count"], 1)
        self.assertEqual(result["layer_results"]["parking"]["feature_count"], 1)
        self.assertEqual(result["layer_results"]["sidewalks"]["feature_count"], 1)
        self.assertEqual(result["layer_results"]["water"]["feature_count"], 1)
        self.assertEqual(result["layer_results"]["existing_utilities"]["feature_count"], 1)
        self.assertIn("[bbox:51.4990000,-0.1260000,51.5010000,-0.1240000]", session.calls[0]["params"]["data"])
        self.assertTrue(result["review_required"])
        self.assertFalse(result["survey_backed"])

    def test_openstreetmap_fetch_blocks_unbounded_area(self) -> None:
        session = _WorldwideSession()

        result = fetch_openstreetmap_site_context(
            {"west": -10, "south": 40, "east": 10, "north": 60},
            session=session,
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(session.calls, [])

    def test_openstreetmap_fetch_uses_configured_fallback_endpoint(self) -> None:
        session = _FallbackWorldwideSession()

        result = fetch_openstreetmap_site_context(
            {"west": -0.126, "south": 51.499, "east": -0.124, "north": 51.501},
            session=session,
        )

        self.assertTrue(result["success"])
        self.assertIn("overpass.kumi.systems", result["source"])
        self.assertEqual(len(session.calls), 2)
        self.assertIn("Primary mapped-context endpoint failed", " ".join(result["warnings"]))

    def test_openstreetmap_fetch_honors_bounded_request_timeout(self) -> None:
        session = _WorldwideSession()

        result = fetch_openstreetmap_site_context(
            {"west": -0.126, "south": 51.499, "east": -0.124, "north": 51.501},
            request_timeout_seconds=4.5,
            session=session,
        )

        self.assertTrue(result["success"])
        self.assertEqual(session.calls[0]["timeout"], 4.5)
        self.assertIn("[timeout:3]", session.calls[0]["params"]["data"])

    def test_openstreetmap_empty_result_stays_empty_without_invented_features(self) -> None:
        result = fetch_openstreetmap_site_context(
            {"west": 36.80, "south": -1.30, "east": 36.81, "north": -1.29},
            session=_EmptyWorldwideSession(),
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "ready_empty")
        self.assertEqual(result["feature_count"], 0)
        self.assertTrue(all(layer["feature_count"] == 0 for layer in result["layer_results"].values()))

    def test_openstreetmap_provider_outage_is_reported_without_candidates(self) -> None:
        session = _FailedWorldwideSession()
        result = fetch_openstreetmap_site_context(
            {"west": 139.75, "south": 35.67, "east": 139.76, "north": 35.68},
            session=session,
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "fetch_failed")
        self.assertEqual(result["layer_results"], {})
        self.assertEqual([call["timeout"] for call in session.calls], [5.0, 5.0])
        self.assertIn("no features were inferred", result["truth_label"])

    def test_global_elevation_keeps_dem_truth(self) -> None:
        result = fetch_global_elevation_point(51.5, -0.125, session=_WorldwideSession())

        self.assertTrue(result["success"])
        self.assertEqual(result["elevation"], 18.0)
        self.assertEqual(result["units"], "meters")
        self.assertFalse(result["survey_backed"])
        self.assertIn("not a topographic survey", result["truth_label"])

    def test_global_elevation_empty_result_stays_missing(self) -> None:
        result = fetch_global_elevation_point(-1.29, 36.81, session=_EmptyWorldwideSession())

        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "no_elevation")
        self.assertNotIn("elevation", result)

    def test_international_geocode_uses_worldwide_context_without_us_only_calls(self) -> None:
        session = _WorldwideSession()
        geocode_context = {
            "lat": 51.5,
            "lng": -0.125,
            "display_name": "10 Downing Street, London, England, United Kingdom",
            "provider": "mapbox",
            "location_context": {
                "coordinates": {"lat": 51.5, "lng": -0.125},
                "jurisdiction": {
                    "country": "United Kingdom",
                    "country_code": "GB",
                    "region": "England",
                    "place": "London",
                    "postcode": "SW1A 2AA",
                },
            },
        }

        result = fetch_online_existing_conditions(
            address="10 Downing Street, London",
            bbox={"west": -0.126, "south": 51.499, "east": -0.124, "north": 51.501},
            geocode_context=geocode_context,
            include_imagery_detection=False,
            session=session,
        )

        urls = [call["url"] for call in session.calls]
        layers = result["canonical_existing_conditions"]["gis_layers"]
        candidates = result["map_feature_detection_report_v1"]["feature_candidates"]
        strategy = result["location_source_strategy_v1"]
        self.assertFalse(any("census" in url or "fema" in url or "wetlands" in url for url in urls))
        self.assertTrue(any("overpass" in url for url in urls))
        self.assertTrue(any("open-meteo" in url for url in urls))
        self.assertEqual(result["location_context"]["country_code"], "GB")
        self.assertEqual(len(layers["building_footprints"]), 1)
        self.assertEqual(len(layers["roads"]), 1)
        self.assertEqual(len(layers["parking"]), 1)
        self.assertIn("community_mapped", {candidate["source_type"] for candidate in candidates})
        self.assertIn("public_dem", {candidate["source_type"] for candidate in candidates})
        self.assertTrue(strategy["worldwide_fallback_used"])
        self.assertEqual(strategy["source_priority"][0], "accepted project survey/control and record documents")
        self.assertIn("authoritative parcel/boundary record", strategy["remaining_authoritative_gaps"])
        self.assertEqual(result["source_results"]["floodplain"]["status"], "outside_provider_scope")
        self.assertEqual(result["canonical_existing_conditions"]["dem_lidar"]["source_tier"], "global_public_context")
        self.assertIn("Open-Meteo", result["canonical_existing_conditions"]["dem_lidar"]["attribution"])
        canonical_sources = {source["key"]: source for source in result["canonical_existing_conditions"]["sources"]}
        self.assertEqual(canonical_sources["worldwide_mapped_context"]["source_tier"], "community_global")
        self.assertIn("OpenStreetMap contributors", canonical_sources["worldwide_mapped_context"]["attribution"])
        providers = {provider["key"]: provider for provider in result["online_existing_conditions_discovery_v1"]["supported_live_providers"]}
        self.assertIn("supplied_geocode", providers)
        self.assertEqual(providers["global_dem_point_elevation"]["status"], "ready")
        self.assertEqual(providers["usgs_3dep_epqs"]["status"], "available_in_us")

    def test_direct_us_address_uses_worldwide_context_without_frontend_geocode_context(self) -> None:
        session = _UsAddressAndWorldwideSession()

        result = fetch_online_existing_conditions(
            address="20525 Margo St, Gretna, NE",
            bbox={"west": -96.238, "south": 41.184, "east": -96.236, "north": 41.186},
            include_floodplain=False,
            include_wetlands=False,
            include_parcels=False,
            include_easements=False,
            include_zoning=False,
            include_contours=False,
            include_elevation=False,
            include_imagery_detection=False,
            session=session,
        )

        types = {candidate["feature_type"] for candidate in result["map_feature_detection_report_v1"]["feature_candidates"]}
        self.assertTrue(any("overpass" in call["url"] for call in session.calls))
        self.assertIn("building_footprint", types)
        self.assertIn("road_or_drive", types)
        self.assertTrue(result["location_source_strategy_v1"]["worldwide_fallback_used"])

    def test_worldwide_fallback_respects_disabled_primary_layer_flags(self) -> None:
        result = fetch_online_existing_conditions(
            address="20525 Margo St, Gretna, NE",
            bbox={"west": -96.238, "south": 41.184, "east": -96.236, "north": 41.186},
            include_floodplain=False,
            include_wetlands=False,
            include_parcels=False,
            include_building_footprints=False,
            include_roads=False,
            include_easements=False,
            include_zoning=False,
            include_utilities=False,
            include_contours=False,
            include_elevation=False,
            include_imagery_detection=False,
            session=_UsAddressAndWorldwideSession(),
        )

        layers = result["canonical_existing_conditions"]["gis_layers"]
        self.assertEqual(layers["building_footprints"], [])
        self.assertEqual(layers["roads"], [])
        self.assertEqual(layers["existing_utilities"], [])
        self.assertEqual(len(layers["parking"]), 1)
        self.assertEqual(len(layers["sidewalks"]), 1)
        self.assertEqual(len(layers["water"]), 1)

    def test_international_address_with_empty_sources_is_not_called_ready_with_context(self) -> None:
        result = fetch_online_existing_conditions(
            address="Example address, Nairobi",
            bbox={"west": 36.80, "south": -1.30, "east": 36.81, "north": -1.29},
            geocode_context={
                "lat": -1.295,
                "lng": 36.805,
                "provider": "mapbox",
                "location_context": {"jurisdiction": {"country_code": "KE", "place": "Nairobi"}},
            },
            include_imagery_detection=False,
            session=_EmptyWorldwideSession(),
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "address_located_no_context")
        self.assertEqual(result["map_feature_detection_report_v1"]["candidate_count"], 0)

    def test_supplied_global_geocode_without_country_does_not_call_us_only_sources(self) -> None:
        session = _WorldwideSession()
        result = fetch_online_existing_conditions(
            address="Globally geocoded site",
            bbox={"west": 2.34, "south": 48.85, "east": 2.35, "north": 48.86},
            geocode_context={
                "lat": 48.855,
                "lng": 2.345,
                "provider": "mapbox",
                "location_context": {"jurisdiction": {"place": "Unknown-country test"}},
            },
            include_imagery_detection=False,
            session=session,
        )

        urls = [call["url"] for call in session.calls]
        self.assertFalse(any("epqs" in url or "fema" in url or "wetlands" in url for url in urls))
        self.assertTrue(any("open-meteo" in url for url in urls))
        self.assertEqual(result["source_results"]["floodplain"]["status"], "outside_provider_scope")

    def test_verified_provider_geometry_wins_over_worldwide_duplicate(self) -> None:
        registry = build_provider_registry(
            include_builtin=False,
            providers=[
                build_arcgis_provider_record(
                    source_type="buildings",
                    service_url="https://county.example/arcgis/rest/services/Buildings/FeatureServer",
                    layer_id=0,
                    name="Verified county buildings",
                    jurisdiction_level="county",
                )
            ],
        )
        result = fetch_online_existing_conditions(
            address="Example site, London",
            bbox={"west": -0.126, "south": 51.499, "east": -0.124, "north": 51.501},
            geocode_context={
                "lat": 51.5,
                "lng": -0.125,
                "provider": "mapbox",
                "location_context": {"jurisdiction": {"country_code": "GB", "place": "London"}},
            },
            provider_registry=registry,
            include_floodplain=False,
            include_wetlands=False,
            include_parcels=False,
            include_roads=False,
            include_easements=False,
            include_zoning=False,
            include_utilities=False,
            include_contours=False,
            include_elevation=False,
            include_imagery_detection=False,
            session=_OfficialAndWorldwideSession(),
        )

        buildings = result["canonical_existing_conditions"]["gis_layers"]["building_footprints"]
        self.assertEqual(len(buildings), 1)
        self.assertEqual(buildings[0]["id"], "official-building")
        self.assertEqual(buildings[0]["source_name"], "Verified county buildings")
        self.assertNotEqual(buildings[0]["source_tier"], "community_global")


if __name__ == "__main__":
    unittest.main()
