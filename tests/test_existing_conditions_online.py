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
from backend.planning.gis_provider_registry import build_arcgis_provider_record, build_provider_registry
from backend.planning.gis_provider_registry import build_known_provider_record


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


class _GretnaRoutingSession:
    def __init__(self):
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append({"url": url, "params": params, "timeout": timeout})
        if "geocoder" in url:
            return _Response(
                {
                    "result": {
                        "addressMatches": [
                            {
                                "matchedAddress": "20525 MARGO ST, GRETNA, NE, 68028",
                                "coordinates": {"x": -96.237022515225, "y": 41.185240483552},
                            }
                        ]
                    }
                }
            )
        if "epqs" in url:
            return _Response({"value": 1291.9334764960693, "attributes": {"AcquisitionDate": "2/4/2017"}})
        if "Sarpy_Parcels_WFL1" in url:
            return _Response({"type": "FeatureCollection", "features": [{"id": "parcel-1", "properties": {"SITEADDRESS": "20525 MARGO ST"}, "geometry": {"type": "Polygon", "coordinates": []}}]})
        if "LandRecordsDynamic/MapServer/3/query" in url:
            return _Response({"type": "FeatureCollection", "features": [{"id": "road-1", "properties": {"FULLNAME": "Margo St"}, "geometry": {"type": "LineString", "coordinates": []}}]})
        if "NFHL/MapServer/28/query" in url:
            return _Response({"type": "FeatureCollection", "features": [{"id": "flood-1", "properties": {"FLD_ZONE": "X"}, "geometry": {"type": "Polygon", "coordinates": []}}]})
        return _Response({"type": "FeatureCollection", "features": []})


class _MultiMarketRoutingSession:
    def __init__(self, address):
        self.address = address
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append({"url": url, "params": params, "timeout": timeout})
        if "geocoder" in url:
            if "Austin" in self.address:
                return _Response({"result": {"addressMatches": [{"matchedAddress": "301 W 2ND ST, AUSTIN, TX, 78701", "coordinates": {"x": -97.747, "y": 30.265}}]}})
            if "Atlanta" in self.address:
                return _Response({"result": {"addressMatches": [{"matchedAddress": "55 TRINITY AVE SW, ATLANTA, GA, 30303", "coordinates": {"x": -84.3903, "y": 33.7488}}]}})
            if "Dallas" in self.address:
                return _Response({"result": {"addressMatches": [{"matchedAddress": "1500 MARILLA ST, DALLAS, TX, 75201", "coordinates": {"x": -96.7970, "y": 32.7767}}]}})
            if "Houston" in self.address:
                return _Response({"result": {"addressMatches": [{"matchedAddress": "1001 PRESTON ST, HOUSTON, TX, 77002", "coordinates": {"x": -95.3698, "y": 29.7604}}]}})
            if "Denver" in self.address:
                return _Response({"result": {"addressMatches": [{"matchedAddress": "201 W COLFAX AVE, DENVER, CO, 80202", "coordinates": {"x": -104.9903, "y": 39.7392}}]}})
            if "Phoenix" in self.address:
                return _Response({"result": {"addressMatches": [{"matchedAddress": "301 W JEFFERSON ST, PHOENIX, AZ, 85003", "coordinates": {"x": -112.0740, "y": 33.4484}}]}})
            if "Charlotte" in self.address:
                return _Response({"result": {"addressMatches": [{"matchedAddress": "600 E 4TH ST, CHARLOTTE, NC, 28202", "coordinates": {"x": -80.8431, "y": 35.2271}}]}})
            return _Response({"result": {"addressMatches": [{"matchedAddress": "100 MAIN ST, MADISON, WI, 53703", "coordinates": {"x": -89.384, "y": 43.074}}]}})
        if "epqs" in url:
            return _Response({"value": {"elevation": 700.0}})
        return _Response({"type": "FeatureCollection", "features": [{"id": "feature-1", "properties": {}, "geometry": {"type": "Polygon", "coordinates": []}}]})


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

    def test_online_fetch_carries_site_intelligence_summary(self) -> None:
        result = fetch_online_existing_conditions(
            address="1 Main St",
            active_site_boundary={"west": -96.81, "south": 32.77, "east": -96.79, "north": 32.79},
            include_easements=False,
            include_zoning=False,
            include_utilities=False,
            include_contours=False,
            session=_RoutingSession(),
        )

        discovery_summary = result[ONLINE_DISCOVERY_VERSION]["site_intelligence_summary_v1"]
        feature_summary = result["map_feature_detection_report_v1"]["site_intelligence_summary_v1"]

        self.assertEqual(discovery_summary["version"], "site_intelligence_summary_v1")
        self.assertEqual(discovery_summary, feature_summary)
        self.assertIn("road_frontage", discovery_summary)
        self.assertIn("grading_context", discovery_summary)
        self.assertFalse(discovery_summary["survey_control_satisfied"])
        self.assertFalse(discovery_summary["construction_release_allowed"])

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

    def test_provider_registry_configures_local_arcgis_sources(self) -> None:
        registry = build_provider_registry(
            include_builtin=False,
            providers=[
                build_arcgis_provider_record(
                    source_type="buildings",
                    service_url="https://city.example/arcgis/rest/services/Buildings/MapServer",
                    layer_id=3,
                    jurisdiction={"city": "Example City"},
                    jurisdiction_level="city",
                ),
                build_arcgis_provider_record(
                    source_type="contours",
                    service_url="https://county.example/arcgis/rest/services/Contours/MapServer",
                    layer_id=4,
                    jurisdiction={"county": "Example County"},
                    jurisdiction_level="county",
                ),
            ],
        )

        session = _RoutingSession()
        result = fetch_online_existing_conditions(
            bbox={"west": -97, "south": 32, "east": -96, "north": 33},
            include_parcels=False,
            include_roads=False,
            include_easements=False,
            include_zoning=False,
            include_utilities=False,
            include_floodplain=False,
            include_wetlands=False,
            include_elevation=False,
            provider_registry=registry,
            session=session,
        )

        report = result[ONLINE_DISCOVERY_VERSION]
        sources = {item["key"]: item for item in report["sources"]}
        urls = [call["url"] for call in session.calls]

        self.assertGreaterEqual(sources["building_footprints"]["candidate_count"], 1)
        self.assertGreaterEqual(sources["contours"]["candidate_count"], 1)
        self.assertIn("https://city.example/arcgis/rest/services/Buildings/MapServer/3/query", urls)
        self.assertIn("https://county.example/arcgis/rest/services/Contours/MapServer/4/query", urls)
        self.assertEqual(report["configured_provider_count"], 2)

    def test_gretna_target_market_address_uses_real_configured_provider_records(self) -> None:
        session = _GretnaRoutingSession()
        result = fetch_online_existing_conditions(address="20525 Margo St, Gretna, NE", session=session)

        report = result[ONLINE_DISCOVERY_VERSION]
        sources = {item["key"]: item for item in report["sources"]}
        urls = [call["url"] for call in session.calls]

        self.assertEqual(result["source_results"]["geocode"]["matched_address"], "20525 MARGO ST, GRETNA, NE, 68028")
        self.assertGreaterEqual(sources["parcel_site_boundary"]["candidate_count"], 1)
        self.assertGreaterEqual(sources["road_row"]["candidate_count"], 1)
        self.assertGreaterEqual(sources["gis_constraints"]["candidate_count"], 1)
        self.assertEqual(sources["building_footprints"]["candidate_count"], 0)
        self.assertIn("provider responded but returned no features", " ".join(sources["building_footprints"]["blockers"]))
        self.assertEqual(sources["public_utilities"]["candidate_count"], 0)
        self.assertIn("provider responded but returned no features", " ".join(sources["public_utilities"]["blockers"]))
        self.assertEqual(sources["contours"]["candidate_count"], 0)
        self.assertIn("VectorTileServer", " ".join(sources["contours"]["blockers"]))
        self.assertIn("https://services.arcgis.com/OiG7dbwhQEWoy77N/arcgis/rest/services/Sarpy_Parcels_WFL1/FeatureServer/0/query", urls)
        self.assertIn("https://geodata.sarpy.gov/arcgis/rest/services/Cadastral/LandRecordsDynamic/MapServer/42/query", urls)
        self.assertIn("https://geodata.sarpy.gov/arcgis/rest/services/Cadastral/LandRecordsDynamic/MapServer/3/query", urls)
        self.assertIn("https://geodata.sarpy.gov/arcgis/rest/services/PublicWorks/SanitarySewerNetwork/MapServer/10/query", urls)
        self.assertIn("https://geodata.sarpy.gov/arcgis/rest/services/PublicWorks/StormwaterNetwork/MapServer/7/query", urls)
        self.assertIn("https://geodata.sarpy.gov/arcgis/rest/services/PublicWorks/StormwaterNetwork/MapServer/3/query", urls)
        self.assertIn("https://geodata.sarpy.gov/arcgis/rest/services/PublicWorks/StormwaterNetwork/MapServer/4/query", urls)
        self.assertIn("https://geodata.sarpy.gov/arcgis/rest/services/Cadastral/LandRecordsDynamic/MapServer/46/query", urls)
        utility_children = result["source_results"]["existing_utilities"]["child_sources"]
        self.assertEqual(len(utility_children), 5)
        self.assertTrue(any(item["provider"] == "Sarpy County stormwater gravity mains" for item in utility_children))
        self.assertTrue(any(item["provider"] == "Sarpy County waterlines" for item in utility_children))
        self.assertEqual(report["configured_provider_count"], 12)
        self.assertTrue(all(item["review_required"] for item in report["sources"]))

    def test_austin_provider_pack_selects_local_queryable_sources(self) -> None:
        session = _MultiMarketRoutingSession("301 W 2nd St, Austin, TX")
        result = fetch_online_existing_conditions(address="301 W 2nd St, Austin, TX", session=session)

        report = result[ONLINE_DISCOVERY_VERSION]
        sources = {item["key"]: item for item in report["sources"]}
        urls = [call["url"] for call in session.calls]

        self.assertEqual(report["provider_packs"][0]["pack_id"], "austin_tx_city")
        self.assertGreaterEqual(sources["parcel_site_boundary"]["candidate_count"], 1)
        self.assertGreaterEqual(sources["building_footprints"]["candidate_count"], 1)
        self.assertGreaterEqual(sources["road_row"]["candidate_count"], 1)
        self.assertGreaterEqual(sources["contours"]["candidate_count"], 1)
        self.assertIn("https://maps.austintexas.gov/gis/rest/Shared/AppraisalDistricts/MapServer/0/query", urls)
        self.assertIn("https://maps.austintexas.gov/gis/rest/Shared/PlanimetricsSurvey_1/MapServer/0/query", urls)

    def test_atlanta_pack_reports_explicit_missing_local_buildings_and_utilities(self) -> None:
        session = _MultiMarketRoutingSession("55 Trinity Ave SW, Atlanta, GA")
        result = fetch_online_existing_conditions(address="55 Trinity Ave SW, Atlanta, GA", session=session)

        report = result[ONLINE_DISCOVERY_VERSION]
        sources = {item["key"]: item for item in report["sources"]}

        self.assertEqual(report["provider_packs"][0]["pack_id"], "atlanta_fulton_ga")
        self.assertGreaterEqual(sources["parcel_site_boundary"]["candidate_count"], 1)
        self.assertEqual(sources["building_footprints"]["candidate_count"], 0)
        self.assertIn("no verified queryable local provider", " ".join(sources["building_footprints"]["blockers"]).lower())
        self.assertEqual(sources["public_utilities"]["candidate_count"], 0)
        self.assertIn("No verified queryable Fulton/Atlanta utility", " ".join(sources["public_utilities"]["blockers"]))

    def test_denver_provider_pack_fetches_source_traced_candidates(self) -> None:
        session = _MultiMarketRoutingSession("201 W Colfax Ave, Denver, CO")
        result = fetch_online_existing_conditions(address="201 W Colfax Ave, Denver, CO", session=session)

        report = result[ONLINE_DISCOVERY_VERSION]
        sources = {item["key"]: item for item in report["sources"]}
        urls = [call["url"] for call in session.calls]

        self.assertEqual(report["provider_packs"][0]["pack_id"], "denver_co_city_county")
        self.assertGreaterEqual(sources["parcel_site_boundary"]["candidate_count"], 1)
        self.assertGreaterEqual(sources["building_footprints"]["candidate_count"], 1)
        self.assertGreaterEqual(sources["road_row"]["candidate_count"], 1)
        self.assertIn("https://services1.arcgis.com/zdB7qR0BtYrg0Xpl/ArcGIS/rest/services/ODC_PROP_PARCELS_A/FeatureServer/245/query", urls)
        self.assertIn("https://services1.arcgis.com/zdB7qR0BtYrg0Xpl/ArcGIS/rest/services/ODC_PROP_BUILDINGOUTLINES_A/FeatureServer/111/query", urls)
        self.assertIn("https://services1.arcgis.com/zdB7qR0BtYrg0Xpl/ArcGIS/rest/services/ODC_TRANS_STREET_L/FeatureServer/145/query", urls)
        self.assertTrue(all(item["review_required"] for item in report["sources"]))
        self.assertFalse(report["survey_control"]["survey_control_satisfied"])

    def test_houston_pack_reports_missing_buildings_without_fabricating(self) -> None:
        session = _MultiMarketRoutingSession("1001 Preston St, Houston, TX")
        result = fetch_online_existing_conditions(address="1001 Preston St, Houston, TX", session=session)

        report = result[ONLINE_DISCOVERY_VERSION]
        sources = {item["key"]: item for item in report["sources"]}
        urls = [call["url"] for call in session.calls]

        self.assertEqual(report["provider_packs"][0]["pack_id"], "houston_harris_tx")
        self.assertGreaterEqual(sources["parcel_site_boundary"]["candidate_count"], 1)
        self.assertGreaterEqual(sources["road_row"]["candidate_count"], 1)
        self.assertEqual(sources["building_footprints"]["candidate_count"], 0)
        self.assertIn("No verified queryable Houston/Harris building-footprint provider", " ".join(sources["building_footprints"]["blockers"]))
        self.assertIn("https://www.gis.hctx.net/arcgis/rest/services/HCAD/Parcels/MapServer/0/query", urls)
        self.assertNotIn("building", " ".join(urls).lower())

    def test_federal_fallback_sources_work_without_local_pack(self) -> None:
        session = _MultiMarketRoutingSession("100 Main St, Madison, WI")
        result = fetch_online_existing_conditions(
            address="100 Main St, Madison, WI",
            include_parcels=True,
            include_building_footprints=True,
            include_roads=True,
            include_utilities=True,
            include_contours=True,
            session=session,
        )

        report = result[ONLINE_DISCOVERY_VERSION]
        sources = {item["key"]: item for item in report["sources"]}

        self.assertEqual(report["provider_packs"], [])
        self.assertGreaterEqual(sources["terrain_dem_lidar"]["candidate_count"], 1)
        self.assertGreaterEqual(sources["gis_constraints"]["candidate_count"], 1)
        self.assertEqual(sources["parcel_site_boundary"]["status"], "unconfigured")
        self.assertEqual(sources["building_footprints"]["status"], "unconfigured")
        self.assertIn("No building footprint GIS source is configured.", sources["building_footprints"]["blockers"])

    def test_non_queryable_vector_tile_contours_are_reported_not_queryable(self) -> None:
        registry = build_provider_registry(
            include_builtin=False,
            providers=[
                build_known_provider_record(
                    source_type="contours",
                    service_url="https://tiles.example/arcgis/rest/services/Contours/VectorTileServer",
                    name="County contour vector tiles",
                    provider_kind="vector_tile",
                )
            ],
        )
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
            provider_registry=registry,
            session=_RoutingSession(),
        )

        sources = {item["key"]: item for item in result[ONLINE_DISCOVERY_VERSION]["sources"]}
        self.assertEqual(sources["contours"]["status"], "known_not_queryable")
        self.assertIn("not queryable", " ".join(sources["contours"]["blockers"]))

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
