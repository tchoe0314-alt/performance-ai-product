import unittest

from backend.planning.gis_provider_registry import (
    build_arcgis_provider_record,
    build_provider_registry,
    check_registry_health,
    provider_freshness_status,
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

        self.assertEqual(registry["configured_provider_count"], 4)
        self.assertEqual(providers_for_source_type(registry, "parcels")[0]["arcgis"]["layer_id"], 0)
        self.assertEqual(providers_for_source_type(registry, "buildings")[0]["arcgis"]["layer_id"], 42)
        self.assertEqual(providers_for_source_type(registry, "roads_row")[0]["arcgis"]["layer_id"], 3)
        self.assertEqual(providers_for_source_type(registry, "utilities")[0]["arcgis"]["layer_id"], 10)
        self.assertTrue(all(item["review_required"] and not item["survey_backed"] for item in registry["providers"]))
        self.assertIn("VectorTileServer", gaps[0]["source_url"])
        self.assertIn("queryable", gaps[0]["message"])


if __name__ == "__main__":
    unittest.main()
