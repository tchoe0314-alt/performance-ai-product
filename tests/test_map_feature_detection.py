import unittest

from backend.planning.existing_conditions_online import fetch_online_existing_conditions
from backend.planning.map_feature_detection import (
    accept_feature_candidate_as_draft_object,
    build_map_feature_detection_report,
    location_context_from_geocode,
)


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class _GeocodeOnlySession:
    def get(self, url, params=None, timeout=None):
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
        return _Response({})


class MapFeatureDetectionTests(unittest.TestCase):
    def test_address_only_produces_location_evidence_without_fake_objects(self) -> None:
        result = fetch_online_existing_conditions(
            address="1 Main St",
            include_elevation=False,
            include_floodplain=False,
            include_wetlands=False,
            include_parcels=False,
            session=_GeocodeOnlySession(),
        )

        report = result["map_feature_detection_report_v1"]

        self.assertTrue(result["success"])
        self.assertEqual(report["location_context"]["matched_address"], "1 MAIN ST")
        self.assertEqual(report["feature_candidates"], [])
        self.assertEqual(report["trusted_canonical_object_count"], 0)
        self.assertNotIn("site_boundary", result["canonical_existing_conditions"])
        self.assertFalse(report["construction_release_allowed"])

    def test_official_gis_building_candidate_is_high_confidence_but_review_required(self) -> None:
        report = build_map_feature_detection_report(
            location_context=location_context_from_geocode(address="1 Main St", geocode={"lat": 32.8, "lng": -96.8, "source_type": "census_geocoder"}),
            gis_layers={
                "building_footprints": [
                    {
                        "id": "BLDG-1",
                        "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [10, 0], [10, 10], [0, 0]]]},
                        "source": "county_building_footprints",
                    }
                ]
            },
        )

        candidate = report["feature_candidates"][0]

        self.assertEqual(candidate["feature_type"], "building_footprint")
        self.assertEqual(candidate["source_type"], "official_gis")
        self.assertGreaterEqual(candidate["confidence"], 0.85)
        self.assertTrue(candidate["needs_user_confirmation"])
        self.assertIn("candidate evidence", candidate["blockers"][0])
        self.assertFalse(report["construction_release_allowed"])

    def test_accepted_official_source_can_clear_user_confirmation_but_not_engineer_review(self) -> None:
        report = build_map_feature_detection_report(
            gis_layers={
                "building_footprints": [
                    {
                        "id": "BLDG-2",
                        "geometry": {"type": "Polygon", "coordinates": []},
                        "source": "accepted_county_gis",
                        "accepted_for_project": True,
                    }
                ]
            }
        )

        candidate = report["feature_candidates"][0]

        self.assertFalse(candidate["needs_user_confirmation"])
        self.assertEqual(candidate["blockers"], [])
        self.assertTrue(report["engineer_review_required"])
        self.assertFalse(report["construction_release_allowed"])

    def test_imagery_and_inferred_candidates_are_lower_confidence_and_need_confirmation(self) -> None:
        report = build_map_feature_detection_report(
            image_detections=[
                {"kind": "building", "bbox": [10, 20, 40, 50], "confidence": 0.92, "image_path": "/tmp/map.png"},
            ],
            inferred_candidates=[
                {"feature_type": "road_or_drive", "geometry": {"type": "LineString", "coordinates": []}, "confidence": 0.62},
            ],
        )

        by_source = {candidate["source_type"]: candidate for candidate in report["feature_candidates"]}

        self.assertLessEqual(by_source["map_imagery_detected"]["confidence"], 0.7)
        self.assertTrue(by_source["map_imagery_detected"]["needs_user_confirmation"])
        self.assertLessEqual(by_source["inferred"]["confidence"], 0.55)
        self.assertTrue(by_source["inferred"]["needs_user_confirmation"])

    def test_missing_gis_and_imagery_returns_exact_blocker(self) -> None:
        report = build_map_feature_detection_report(
            location_context=location_context_from_geocode(address="1 Main St", geocode={"lat": 32.8, "lng": -96.8}),
        )

        self.assertEqual(report["status"], "blocked_no_feature_source")
        self.assertEqual(report["blockers"][0]["code"], "no_gis_or_imagery_feature_source")
        self.assertIn("Upload a map image", report["blockers"][0]["next_action"])

    def test_confirmed_candidate_becomes_draft_review_required_object_only(self) -> None:
        report = build_map_feature_detection_report(
            image_detections=[
                {"kind": "building", "bbox": [10, 20, 40, 50], "confidence": 0.45, "image_path": "/tmp/map.png"},
            ]
        )

        draft = accept_feature_candidate_as_draft_object(report["feature_candidates"][0], accepted_by="user-1")

        self.assertEqual(draft["object_type"], "building")
        self.assertEqual(draft["status"], "draft_review_required")
        self.assertFalse(draft["trusted_canonical"])
        self.assertTrue(draft["needs_engineer_review"])
        self.assertFalse(draft["construction_release_allowed"])


if __name__ == "__main__":
    unittest.main()
