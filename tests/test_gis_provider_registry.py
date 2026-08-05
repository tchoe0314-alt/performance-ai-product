import unittest

from backend.planning.gis_provider_registry import (
    build_arcgis_provider_record,
    build_known_provider_record,
    build_provider_registry,
    check_registry_health,
    provider_freshness_status,
    provider_packs_for_location,
    providers_for_source_type,
    target_market_known_gaps,
    target_market_provider_records,
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


class GisProviderRegistryTests(unittest.TestCase):
    def test_arcgis_provider_record_keeps_source_review_required(self) -> None:
        provider = build_arcgis_provider_record(
            source_type="parcel",
            service_url="https://county.example/arcgis/rest/services/Parcels/MapServer",
            layer_id=2,
            jurisdiction={"county": "Example County", "state": "TX"},
            jurisdiction_level="county",
        )

        self.assertEqual(provider["source_type"], "parcels")
        self.assertEqual(provider["jurisdiction_level"], "county")
        self.assertEqual(provider["arcgis"]["query_url"], "https://county.example/arcgis/rest/services/Parcels/MapServer/2/query")
        self.assertTrue(provider["review_required"])
        self.assertFalse(provider["survey_backed"])

    def test_registry_supports_jurisdiction_city_county_source_types(self) -> None:
        registry = build_provider_registry(
            include_builtin=False,
            providers=[
                build_arcgis_provider_record(
                    source_type="buildings",
                    service_url="https://city.example/arcgis/rest/services/Buildings/FeatureServer",
                    jurisdiction={"city": "Example City"},
                    jurisdiction_level="city",
                ),
                build_arcgis_provider_record(
                    source_type="roads_row",
                    service_url="https://county.example/arcgis/rest/services/Roads/MapServer",
                    jurisdiction={"county": "Example County"},
                    jurisdiction_level="county",
                ),
            ],
        )

        self.assertEqual(registry["configured_provider_count"], 2)
        self.assertEqual(providers_for_source_type(registry, "building")[0]["jurisdiction_level"], "city")
        self.assertEqual(providers_for_source_type(registry, "road/ROW")[0]["jurisdiction_level"], "county")

    def test_provider_health_and_freshness_are_separate_from_success(self) -> None:
        provider = build_arcgis_provider_record(
            source_type="utilities",
            service_url="https://utility.example/arcgis/rest/services/Water/MapServer",
            layer_id=4,
            freshness_date="2020-01-01T00:00:00Z",
            stale_after_days=30,
        )
        registry = build_provider_registry(include_builtin=False, providers=[provider])
        health = check_registry_health(registry, session=_Session({"layers": [{"id": 4}], "name": "Water"}))

        self.assertEqual(health["healthy_provider_count"], 1)
        self.assertEqual(health["stale_provider_count"], 1)
        self.assertEqual(provider_freshness_status(provider)["status"], "stale")

    def test_gretna_target_market_records_are_real_review_required_providers(self) -> None:
        providers = target_market_provider_records(address="20525 Margo St, Gretna, NE", lat=41.185240483552, lng=-96.237022515225)
        registry = build_provider_registry(include_builtin=False, providers=providers)
        gaps = target_market_known_gaps(address="20525 Margo St, Gretna, NE", lat=41.185240483552, lng=-96.237022515225)

        self.assertEqual(registry["configured_provider_count"], 7)
        self.assertEqual(providers_for_source_type(registry, "parcels")[0]["arcgis"]["layer_id"], 0)
        self.assertEqual(providers_for_source_type(registry, "buildings")[0]["arcgis"]["layer_id"], 42)
        self.assertEqual(providers_for_source_type(registry, "roads_row")[0]["arcgis"]["layer_id"], 3)
        utility_names = {item["name"] for item in providers_for_source_type(registry, "utilities")}
        utility_layers = {item["arcgis"]["layer_id"] for item in providers_for_source_type(registry, "utilities")}
        self.assertIn("Sarpy County sanitary gravity mains", utility_names)
        self.assertIn("Sarpy County stormwater gravity mains", utility_names)
        self.assertIn("Sarpy County stormwater inlets", utility_names)
        self.assertIn("Sarpy County stormwater discharge points", utility_names)
        self.assertNotIn("Sarpy County waterlines", utility_names)
        self.assertTrue({3, 4, 7, 10}.issubset(utility_layers))
        self.assertTrue(all(item["review_required"] and not item["survey_backed"] for item in registry["providers"]))
        self.assertTrue(any("VectorTileServer" in item.get("source_url", "") for item in gaps))
        self.assertTrue(any("raster/tile elevation pipeline" in item.get("message", "") for item in gaps))
        self.assertTrue(any("hydrography" in item.get("message", "") for item in gaps))

    def test_provider_pack_selection_supports_multiple_markets(self) -> None:
        gretna = provider_packs_for_location(address="20525 Margo St, Gretna, NE", lat=41.185240483552, lng=-96.237022515225)
        austin = provider_packs_for_location(address="301 W 2nd St, Austin, TX", lat=30.265, lng=-97.747)
        atlanta = provider_packs_for_location(address="55 Trinity Ave SW, Atlanta, GA", lat=33.7488, lng=-84.3903)
        dallas = provider_packs_for_location(address="1500 Marilla St, Dallas, TX", lat=32.7767, lng=-96.7970)
        houston = provider_packs_for_location(address="1001 Preston St, Houston, TX", lat=29.7604, lng=-95.3698)
        denver = provider_packs_for_location(address="201 W Colfax Ave, Denver, CO", lat=39.7392, lng=-104.9903)
        phoenix = provider_packs_for_location(address="301 W Jefferson St, Phoenix, AZ", lat=33.4484, lng=-112.0740)
        charlotte = provider_packs_for_location(address="600 E 4th St, Charlotte, NC", lat=35.2271, lng=-80.8431)
        omaha = provider_packs_for_location(address="1600 Dodge St, Omaha, NE", lat=41.2598, lng=-95.9372)

        self.assertEqual(gretna[0]["pack_id"], "gretna_ne_sarpy_county")
        self.assertEqual(austin[0]["pack_id"], "austin_tx_city")
        self.assertEqual(atlanta[0]["pack_id"], "atlanta_fulton_ga")
        self.assertEqual(dallas[0]["pack_id"], "dallas_tx_city")
        self.assertEqual(houston[0]["pack_id"], "houston_harris_tx")
        self.assertEqual(denver[0]["pack_id"], "denver_co_city_county")
        self.assertEqual(phoenix[0]["pack_id"], "phoenix_maricopa_az")
        self.assertEqual(charlotte[0]["pack_id"], "charlotte_mecklenburg_nc")
        self.assertEqual(omaha[0]["pack_id"], "omaha_douglas_ne")
        self.assertTrue(any(item["source_type"] == "buildings" for item in austin[0]["providers"]))
        self.assertTrue(any(item["source_type"] == "parcels" for item in atlanta[0]["providers"]))
        self.assertTrue(any(item["source_type"] == "buildings" for item in atlanta[0]["known_gaps"]))
        self.assertTrue(any(item["source_type"] == "roads_row" for item in dallas[0]["providers"]))
        self.assertTrue(any(item["source_type"] == "buildings" for item in houston[0]["known_gaps"]))
        self.assertTrue(any(item["source_type"] == "buildings" for item in denver[0]["providers"]))
        self.assertTrue(any(item["source_type"] == "floodplain" for item in phoenix[0]["providers"]))
        self.assertTrue(any(item["source_type"] == "roads_row" for item in charlotte[0]["known_gaps"]))
        self.assertTrue(any(item["source_type"] == "terrain_breaklines" for item in omaha[0]["providers"]))
        self.assertTrue(any(item["source_type"] == "lidar_index" for item in omaha[0]["providers"]))
        self.assertTrue(any(item["source_type"] == "contours" and not item["queryable"] for item in omaha[0]["providers"]))

    def test_new_market_provider_packs_are_review_required_source_traced(self) -> None:
        cases = [
            ("1500 Marilla St, Dallas, TX", 32.7767, -96.7970, "https://gis.dallascityhall.com/arcgis/rest/services/Basemap/DallasTaxParcels/FeatureServer"),
            ("1001 Preston St, Houston, TX", 29.7604, -95.3698, "https://www.gis.hctx.net/arcgis/rest/services/HCAD/Parcels/MapServer"),
            ("201 W Colfax Ave, Denver, CO", 39.7392, -104.9903, "https://services1.arcgis.com/zdB7qR0BtYrg0Xpl/ArcGIS/rest/services/ODC_PROP_PARCELS_A/FeatureServer"),
            ("301 W Jefferson St, Phoenix, AZ", 33.4484, -112.0740, "https://gis.mcassessor.maricopa.gov/arcgis/rest/services/Parcels/MapServer"),
            ("600 E 4th St, Charlotte, NC", 35.2271, -80.8431, "https://meckgis.mecklenburgcountync.gov/server/rest/services/TaxParcelBoundaries/FeatureServer"),
            ("1600 Dodge St, Omaha, NE", 41.2598, -95.9372, "https://dcgis.org/server/rest/services/vector/Parcels_public/FeatureServer"),
        ]

        for address, lat, lng, expected_url in cases:
            with self.subTest(address=address):
                providers = target_market_provider_records(address=address, lat=lat, lng=lng)
                registry = build_provider_registry(include_builtin=False, providers=providers)
                urls = {item["service_url"] for item in registry["providers"]}

                self.assertIn(expected_url, urls)
                self.assertTrue(all(item["review_required"] and not item["survey_backed"] for item in registry["providers"]))
                self.assertTrue(
                    all(
                        item["arcgis"]["service_kind"] in {"FeatureServer", "MapServer"}
                        for item in registry["providers"]
                        if item["queryable"]
                    )
                )
                self.assertGreaterEqual(registry["queryable_provider_count"], 2)

    def test_non_queryable_vector_tile_source_is_known_but_not_selected(self) -> None:
        vector = build_known_provider_record(
            source_type="contours",
            service_url="https://tiles.example/arcgis/rest/services/Contours/VectorTileServer",
            name="County contour vector tiles",
            jurisdiction={"county": "Example County", "state": "NE"},
            jurisdiction_level="county",
            provider_kind="vector_tile",
        )
        registry = build_provider_registry(include_builtin=False, providers=[vector])

        self.assertEqual(registry["configured_provider_count"], 1)
        self.assertEqual(registry["queryable_provider_count"], 0)
        self.assertEqual(providers_for_source_type(registry, "contours"), [])
        self.assertFalse(registry["providers"][0]["queryable"])
        self.assertEqual(registry["providers"][0]["arcgis"]["service_kind"], "VectorTileServer")


if __name__ == "__main__":
    unittest.main()
