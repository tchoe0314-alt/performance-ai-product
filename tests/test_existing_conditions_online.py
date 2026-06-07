import unittest

from backend.planning.existing_conditions_online import (
    ONLINE_DISCOVERY_VERSION,
    fetch_configured_parcels,
    fetch_online_existing_conditions,
    fetch_fema_floodplain,
    fetch_usfws_wetlands,
    fetch_usgs_elevation_point,
    geocode_address_census,
    online_import_to_gis_layers,
)


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class _Session:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append({"url": url, "params": params, "timeout": timeout})
        return _Response(self.payload)


class _RoutingSession:
    def __init__(self):
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append({"url": url, "params": params, "timeout": timeout})
        if "geocoder" in url:
            return _Response(
                {
                    "result": {
                        "addressMatches": [
                            {"matchedAddress": "1 MAIN ST", "coordinates": {"x": -96.8, "y": 32.8}},
                        ]
                    }
                }
            )
        if "epqs" in url:
            return _Response({"value": {"elevation": 512.25}})
        return _Response({"type": "FeatureCollection", "features": [{"id": "A", "properties": {}, "geometry": {"type": "Polygon", "coordinates": []}}]})


class _AddressRoutingSession:
    def get(self, url, params=None, timeout=None):
        address = (params or {}).get("address", "")
        if "geocoder" in url and address == "1 Main St":
            return _Response(
                {
                    "result": {
                        "addressMatches": [
                            {"matchedAddress": "1 MAIN ST", "coordinates": {"x": -96.8, "y": 32.8}},
                        ]
                    }
                }
            )
        if "geocoder" in url and address == "2 Main St":
            return _Response(
                {
                    "result": {
                        "addressMatches": [
                            {"matchedAddress": "2 MAIN ST", "coordinates": {"x": -97.4, "y": 33.1}},
                        ]
                    }
                }
            )
        return _Response({})


class _FailingSession:
    def get(self, url, params=None, timeout=None):
        raise TimeoutError(f"timeout fetching {url}")


class ExistingConditionsOnlineTests(unittest.TestCase):
    def test_census_geocoder_normalizes_first_match(self) -> None:
        session = _Session(
            {
                "result": {
                    "addressMatches": [
                        {"matchedAddress": "1 MAIN ST", "coordinates": {"x": -96.8, "y": 32.8}},
                    ]
                }
            }
        )

        result = geocode_address_census("1 Main St", session=session)

        self.assertTrue(result["success"])
        self.assertEqual(result["lat"], 32.8)
        self.assertEqual(result["lng"], -96.8)

    def test_different_addresses_produce_different_location_context_coordinates(self) -> None:
        session = _AddressRoutingSession()

        first = fetch_online_existing_conditions(
            address="1 Main St",
            include_elevation=False,
            include_floodplain=False,
            include_wetlands=False,
            include_parcels=False,
            include_building_footprints=False,
            include_roads=False,
            include_easements=False,
            include_zoning=False,
            include_utilities=False,
            session=session,
        )
        second = fetch_online_existing_conditions(
            address="2 Main St",
            include_elevation=False,
            include_floodplain=False,
            include_wetlands=False,
            include_parcels=False,
            include_building_footprints=False,
            include_roads=False,
            include_easements=False,
            include_zoning=False,
            include_utilities=False,
            session=session,
        )

        self.assertNotEqual(first["location_context"]["coordinates"], second["location_context"]["coordinates"])
        self.assertEqual(first["source_results"]["geocode"]["matched_address"], "1 MAIN ST")
        self.assertEqual(second["source_results"]["geocode"]["matched_address"], "2 MAIN ST")
        self.assertEqual(first["map_feature_detection_report_v1"]["feature_candidates"], [])
        self.assertEqual(second["map_feature_detection_report_v1"]["feature_candidates"], [])

    def test_usgs_elevation_point_returns_truth_labeled_context(self) -> None:
        session = _Session({"value": {"elevation": 512.25}})

        result = fetch_usgs_elevation_point(32.8, -96.8, session=session)

        self.assertTrue(result["success"])
        self.assertEqual(result["elevation"], 512.25)
        self.assertIn("not a topographic survey", result["truth_label"])

    def test_fema_and_wetlands_arcgis_queries_become_gis_layers(self) -> None:
        payload = {"type": "FeatureCollection", "features": [{"id": "A", "properties": {}, "geometry": {"type": "Polygon", "coordinates": []}}]}
        fema = fetch_fema_floodplain({"west": -97, "south": 32, "east": -96, "north": 33}, session=_Session(payload))
        wetlands = fetch_usfws_wetlands({"west": -97, "south": 32, "east": -96, "north": 33}, session=_Session(payload))

        merged = online_import_to_gis_layers(fema, wetlands)

        self.assertTrue(merged["success"])
        self.assertEqual(len(merged["gis_layers"]["floodplain"]), 1)
        self.assertEqual(len(merged["gis_layers"]["wetlands"]), 1)

    def test_parcels_are_unconfigured_without_local_service(self) -> None:
        result = fetch_configured_parcels({"west": -97, "south": 32, "east": -96, "north": 33})

        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "unconfigured")

    def test_fetch_online_existing_conditions_orchestrates_sources(self) -> None:
        result = fetch_online_existing_conditions(
            address="1 Main St",
            parcel_service_url="https://county.example/arcgis/rest/services/Parcels/MapServer",
            session=_RoutingSession(),
        )

        canonical = result["canonical_existing_conditions"]

        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "ready_with_context")
        self.assertEqual(canonical["coordinate_system"]["epsg"], "EPSG:4326")
        self.assertEqual(len(canonical["gis_layers"]["floodplain"]), 1)
        self.assertEqual(len(canonical["gis_layers"]["wetlands"]), 1)
        self.assertEqual(len(canonical["gis_layers"]["parcels"]), 1)
        self.assertTrue(canonical["dem_lidar"]["ready"])
        self.assertIn("does not replace", result["truth_label"])

    def test_online_discovery_reports_parcel_building_road_and_constraint_candidates(self) -> None:
        result = fetch_online_existing_conditions(
            address="1 Main St",
            parcel_service_url="https://county.example/arcgis/rest/services/Parcels/MapServer",
            building_footprints_service_url="https://county.example/arcgis/rest/services/Buildings/MapServer",
            roads_service_url="https://county.example/arcgis/rest/services/Roads/MapServer",
            session=_RoutingSession(),
        )

        report = result[ONLINE_DISCOVERY_VERSION]
        sources = {item["key"]: item for item in report["sources"]}

        self.assertEqual(report["version"], ONLINE_DISCOVERY_VERSION)
        self.assertEqual(report["status"], "candidates_found")
        self.assertTrue(report["supported_live_providers"])
        self.assertTrue(report["fixture_provider_only_sources"])
        self.assertGreaterEqual(sources["parcel_site_boundary"]["candidate_count"], 1)
        self.assertGreaterEqual(sources["building_footprints"]["candidate_count"], 1)
        self.assertGreaterEqual(sources["road_row"]["candidate_count"], 1)
        self.assertGreaterEqual(sources["gis_constraints"]["candidate_count"], 1)
        self.assertEqual(sources["parcel_site_boundary"]["acceptance_status"], "candidate")
        self.assertTrue(all(item["review_required"] for item in report["sources"]))

    def test_online_discovery_reports_no_sources_found_without_fake_address_detection(self) -> None:
        result = fetch_online_existing_conditions(
            address="1 Main St",
            include_elevation=False,
            include_floodplain=False,
            include_wetlands=False,
            include_parcels=False,
            include_building_footprints=False,
            include_roads=False,
            include_easements=False,
            include_zoning=False,
            include_utilities=False,
            session=_RoutingSession(),
        )

        report = result[ONLINE_DISCOVERY_VERSION]

        self.assertEqual(report["status"], "no_sources_found")
        self.assertEqual(report["candidate_count"], 0)
        self.assertEqual(result["map_feature_detection_report_v1"]["feature_candidates"], [])
        self.assertIn("parcel_site_boundary", {item["key"] for item in report["missing_sources"]})

    def test_online_discovery_reports_source_failure_timeout(self) -> None:
        result = fetch_online_existing_conditions(
            bbox={"west": -97, "south": 32, "east": -96, "north": 33},
            include_parcels=False,
            include_building_footprints=False,
            include_roads=False,
            include_easements=False,
            include_zoning=False,
            include_utilities=False,
            session=_FailingSession(),
        )

        report = result[ONLINE_DISCOVERY_VERSION]

        self.assertEqual(report["status"], "fetch_failed")
        self.assertTrue(report["failed_sources"])
        self.assertIn("timeout fetching", " ".join(report["blockers"]))

    def test_online_candidates_stay_review_required(self) -> None:
        result = fetch_online_existing_conditions(
            address="1 Main St",
            parcel_service_url="https://county.example/arcgis/rest/services/Parcels/MapServer",
            building_footprints_service_url="https://county.example/arcgis/rest/services/Buildings/MapServer",
            roads_service_url="https://county.example/arcgis/rest/services/Roads/MapServer",
            session=_RoutingSession(),
        )

        discovery = result[ONLINE_DISCOVERY_VERSION]
        feature_report = result["map_feature_detection_report_v1"]

        self.assertTrue(discovery["review_required"])
        self.assertEqual(discovery["acceptance_status"], "candidate")
        self.assertTrue(all(item["review_required"] for item in feature_report["feature_candidates"]))
        self.assertTrue(all(item["acceptance_status"] == "pending" for item in feature_report["feature_candidates"]))
        self.assertFalse(any(item["canonical_object_allowed"] for item in feature_report["feature_candidates"]))

    def test_online_discovery_does_not_satisfy_survey_or_control(self) -> None:
        result = fetch_online_existing_conditions(
            address="1 Main St",
            parcel_service_url="https://county.example/arcgis/rest/services/Parcels/MapServer",
            session=_RoutingSession(),
        )

        report = result[ONLINE_DISCOVERY_VERSION]
        canonical = result["canonical_existing_conditions"]

        self.assertFalse(report["survey_control"]["survey_control_satisfied"])
        self.assertEqual(report["survey_control"]["status"], "not_satisfied")
        self.assertEqual(canonical["survey"]["source"], "missing")
        self.assertEqual(canonical["survey"]["point_count"], 0)

    def test_fetch_online_existing_conditions_blocks_without_location(self) -> None:
        result = fetch_online_existing_conditions(session=_RoutingSession())

        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
