import unittest

from backend.planning.existing_conditions_online import (
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
        self.assertIn("not a stamped", result["truth_label"])

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

    def test_fetch_online_existing_conditions_blocks_without_location(self) -> None:
        result = fetch_online_existing_conditions(session=_RoutingSession())

        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
