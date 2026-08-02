import unittest

from backend.planning.existing_conditions_online import fetch_online_existing_conditions
from backend.planning.map_feature_detection import (
    accept_feature_candidate_as_draft_object,
    build_map_feature_detection_report,
    location_context_from_geocode,
    reject_feature_candidate,
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
        self.assertEqual(report["source_discovery"]["building_footprints"]["status"], "missing_source")

    def test_official_gis_building_candidate_is_high_confidence_but_review_required(self) -> None:
        report = build_map_feature_detection_report(
            location_context=location_context_from_geocode(address="1 Main St", geocode={"lat": 32.8, "lng": -96.8, "source_type": "census_geocoder"}),
            gis_layers={
                "building_footprints": [
                    {
                        "id": "BLDG-1",
                        "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [10, 0], [10, 10], [0, 0]]]},
                        "source_url": "https://county.example/gis/buildings",
                        "source_name": "county_building_footprints",
                    }
                ]
            },
        )

        candidate = report["feature_candidates"][0]

        self.assertEqual(candidate["feature_type"], "building_footprint")
        self.assertEqual(candidate["source_type"], "official_gis")
        self.assertEqual(candidate["source_url"], "https://county.example/gis/buildings")
        self.assertEqual(candidate["acceptance_status"], "pending")
        self.assertGreaterEqual(candidate["confidence"], 0.85)
        self.assertTrue(candidate["review_required"])
        self.assertIn("candidate evidence", candidate["blockers"][0])
        self.assertFalse(report["construction_release_allowed"])
        self.assertEqual(
            report["chat_panel_summary"]["message"],
            "I found 1 building footprint from GIS. Do you want to use it?",
        )

    def test_configured_gis_sources_create_source_backed_feature_candidates(self) -> None:
        report = build_map_feature_detection_report(
            gis_layers={
                "building_footprints": [
                    {"id": "BLDG-1", "geometry": {"type": "Polygon", "coordinates": []}, "source_name": "county_buildings"},
                ],
                "right_of_way": [
                    {"id": "ROW-1", "geometry": {"type": "LineString", "coordinates": []}, "source_name": "county_row"},
                ],
                "easements": [
                    {"id": "ESMT-1", "geometry": {"type": "Polygon", "coordinates": []}, "source_name": "county_easements"},
                ],
            }
        )

        candidates_by_id = {candidate["source_feature_id"]: candidate for candidate in report["feature_candidates"]}

        self.assertEqual(candidates_by_id["BLDG-1"]["feature_type"], "building_footprint")
        self.assertEqual(candidates_by_id["ROW-1"]["feature_type"], "road_or_drive")
        self.assertEqual(candidates_by_id["ESMT-1"]["feature_type"], "constraint_area")
        self.assertEqual({candidate["source_type"] for candidate in candidates_by_id.values()}, {"official_gis"})
        self.assertTrue(all(candidate["acceptance_status"] == "pending" for candidate in candidates_by_id.values()))

    def test_official_gis_parcel_source_creates_site_boundary_candidate(self) -> None:
        report = build_map_feature_detection_report(
            gis_layers={
                "parcels": [
                    {
                        "id": "PARCEL-1",
                        "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [20, 0], [20, 20], [0, 0]]]},
                        "source_name": "county_parcels",
                    }
                ]
            }
        )

        candidate = report["feature_candidates"][0]

        self.assertEqual(candidate["feature_type"], "parcel_or_site_boundary")
        self.assertEqual(candidate["source_type"], "official_gis")
        self.assertEqual(candidate["acceptance_status"], "pending")
        self.assertTrue(candidate["review_required"])

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
        self.assertEqual(candidate["acceptance_status"], "accepted")
        self.assertTrue(report["engineer_review_required"])
        self.assertFalse(report["construction_release_allowed"])

    def test_imagery_and_inferred_candidates_are_lower_confidence_and_need_confirmation(self) -> None:
        report = build_map_feature_detection_report(
            image_detections=[
                {"kind": "building", "bbox": [10, 20, 40, 50], "confidence": 0.92, "image_path": "/tmp/map.png"},
            ],
        )

        by_source = {candidate["source_type"]: candidate for candidate in report["feature_candidates"]}

        self.assertLessEqual(by_source["image_detected_candidate"]["confidence"], 0.7)
        self.assertEqual(by_source["image_detected_candidate"]["acceptance_status"], "pending")
        self.assertTrue(by_source["image_detected_candidate"]["needs_user_confirmation"])
        self.assertTrue(by_source["image_detected_candidate"]["review_required"])
        self.assertEqual(report["imagery_object_detection_report_v1"]["detection_count"], 1)
        self.assertEqual(
            len([candidate for candidate in report["feature_candidates"] if candidate["source_type"] == "image_detected_candidate"]),
            1,
        )

    def test_imagery_object_detection_report_adds_visual_building_road_and_tree_candidates(self) -> None:
        report = build_map_feature_detection_report(
            imagery_object_detection_report={
                "version": "imagery_object_detection_report_v1",
                "status": "detected",
                "provider": "test_segmentation_model",
                "detection_count": 3,
                "detections": [
                    {
                        "kind": "building",
                        "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [30, 0], [30, 20], [0, 0]]]},
                        "confidence": 0.86,
                        "source_url": "https://imagery.example/tile",
                    },
                    {"kind": "road", "bbox": [0, 40, 100, 12], "confidence": 0.74},
                    {"kind": "tree", "bbox": [80, 80, 10, 10], "confidence": 0.68},
                ],
            }
        )

        types = {candidate["feature_type"] for candidate in report["feature_candidates"]}

        self.assertEqual(report["source_discovery"]["imagery_object_detection"]["status"], "ready")
        self.assertIn("building_footprint", types)
        self.assertIn("road_or_drive", types)
        self.assertIn("vegetation/tree_area", types)
        self.assertTrue(all(candidate["source_type"] == "image_detected_candidate" for candidate in report["feature_candidates"]))
        self.assertTrue(all(candidate["review_required"] for candidate in report["feature_candidates"]))

    def test_unconfigured_imagery_detector_reports_missing_without_fake_candidates(self) -> None:
        report = build_map_feature_detection_report(
            imagery_object_detection_report={
                "version": "imagery_object_detection_report_v1",
                "status": "not_configured",
                "provider": "unconfigured",
                "detection_count": 0,
                "detections": [],
                "missing": ["imagery_object_detection_provider"],
            }
        )

        self.assertEqual(report["feature_candidates"], [])
        self.assertEqual(report["source_discovery"]["imagery_object_detection"]["status"], "missing_source")
        self.assertIn("imagery_object_detection_not_configured", {item["code"] for item in report["blockers"]})

    def test_pending_candidate_remains_pending_until_explicit_workflow_action(self) -> None:
        report = build_map_feature_detection_report(
            image_detections=[
                {"kind": "road", "bbox": [10, 20, 40, 50], "confidence": 0.6, "image_path": "/tmp/map.png"},
            ],
        )

        candidate = report["feature_candidates"][0]

        self.assertEqual(candidate["acceptance_status"], "pending")
        self.assertEqual(candidate.get("audit_trail", []), [])

    def test_missing_gis_and_imagery_returns_exact_blocker(self) -> None:
        report = build_map_feature_detection_report(
            location_context=location_context_from_geocode(address="1 Main St", geocode={"lat": 32.8, "lng": -96.8}),
        )

        self.assertEqual(report["status"], "blocked_no_feature_source")
        self.assertEqual(report["blockers"][0]["code"], "no_gis_or_imagery_feature_source")
        self.assertIn("Upload a map image", report["blockers"][0]["next_action"])
        blocker_codes = {item["code"] for item in report["blockers"]}
        self.assertIn("missing_building_footprints_source", blocker_codes)
        self.assertIn("missing_roads_row_source", blocker_codes)
        self.assertEqual(report["chat_panel_summary"]["message"], "No building footprint source is configured.")

    def test_confirmed_candidate_becomes_draft_review_required_object_only(self) -> None:
        report = build_map_feature_detection_report(
            image_detections=[
                {"kind": "building", "bbox": [10, 20, 40, 50], "confidence": 0.45, "image_path": "/tmp/map.png"},
            ]
        )

        draft = accept_feature_candidate_as_draft_object(report["feature_candidates"][0], accepted_by="user-1")

        self.assertEqual(draft["object_type"], "building")
        self.assertEqual(draft["status"], "draft_review_required")
        self.assertEqual(draft["acceptance_status"], "accepted")
        self.assertFalse(draft["trusted_canonical"])
        self.assertTrue(draft["needs_engineer_review"])
        self.assertFalse(draft["construction_release_allowed"])
        self.assertEqual(draft["audit_trail"][0]["action"], "accepted_candidate_as_draft")

    def test_rejected_candidate_is_preserved_with_audit_trail(self) -> None:
        report = build_map_feature_detection_report(
            gis_layers={
                "parcels": [
                    {
                        "id": "PARCEL-REJECT",
                        "geometry": {"type": "Polygon", "coordinates": []},
                        "source_name": "county_parcels",
                    }
                ]
            }
        )

        rejected = reject_feature_candidate(report["feature_candidates"][0], rejected_by="user-1", reason="Wrong parcel.")

        self.assertEqual(rejected["acceptance_status"], "rejected")
        self.assertEqual(rejected["audit_trail"][0]["action"], "rejected_candidate")
        self.assertEqual(rejected["audit_trail"][0]["reason"], "Wrong parcel.")

    def test_active_site_boundary_marks_outside_candidates(self) -> None:
        report = build_map_feature_detection_report(
            active_site_boundary={"west": -96.81, "south": 32.77, "east": -96.79, "north": 32.79},
            gis_layers={
                "building_footprints": [
                    {
                        "id": "inside-building",
                        "geometry": {"type": "Point", "coordinates": [-96.8, 32.78]},
                        "source_name": "city_buildings",
                    },
                    {
                        "id": "outside-building",
                        "geometry": {"type": "Point", "coordinates": [-96.7, 32.9]},
                        "source_name": "city_buildings",
                    },
                ]
            },
        )

        self.assertEqual(report["candidate_count"], 1)
        self.assertEqual(report["outside_site_candidate_count"], 1)
        self.assertEqual(report["feature_candidates"][0]["source_feature_id"], "inside-building")
        self.assertEqual(report["outside_site_candidates"][0]["source_feature_id"], "outside-building")
        self.assertTrue(report["outside_site_candidates"][0]["outside_site"])

    def test_site_intelligence_summarizes_frontage_driveway_and_grading_context(self) -> None:
        report = build_map_feature_detection_report(
            active_site_boundary={"west": -96.81, "south": 32.77, "east": -96.79, "north": 32.79},
            gis_layers={
                "roads": [
                    {
                        "id": "road-west",
                        "geometry": {"type": "LineString", "coordinates": [[-96.811, 32.77], [-96.811, 32.79]]},
                        "source_name": "city_roads",
                    }
                ],
                "building_footprints": [
                    {
                        "id": "inside-building",
                        "geometry": {"type": "Point", "coordinates": [-96.8, 32.78]},
                        "source_name": "city_buildings",
                    }
                ],
            },
            source_results={
                "elevation": {
                    "success": True,
                    "source_type": "usgs_3dep_epqs",
                    "source": "https://epqs.nationalmap.gov",
                    "lat": 32.78,
                    "lng": -96.8,
                    "elevation": 518.4,
                    "units": "feet",
                }
            },
        )

        summary = report["site_intelligence_summary_v1"]

        self.assertEqual(summary["version"], "site_intelligence_summary_v1")
        self.assertEqual(summary["road_frontage"]["likely_frontage_side"], "west")
        self.assertEqual(summary["driveway_suggestions"][0]["frontage_side"], "west")
        self.assertEqual(summary["grading_context"]["status"], "single_point_elevation")
        self.assertFalse(summary["survey_control_satisfied"])
        self.assertFalse(summary["construction_release_allowed"])
        self.assertIn("review-required", summary["one_sentence"])

    def test_elevation_source_creates_review_required_terrain_candidate(self) -> None:
        report = build_map_feature_detection_report(
            source_results={
                "elevation": {
                    "success": True,
                    "source_type": "usgs_3dep_epqs",
                    "source": "https://epqs.nationalmap.gov",
                    "lat": 32.78,
                    "lng": -96.8,
                    "elevation": 518.4,
                    "units": "feet",
                    "truth_label": "Public DEM/elevation context is not a topographic survey.",
                }
            }
        )

        self.assertEqual(report["feature_candidates"][0]["feature_type"], "terrain")
        self.assertTrue(report["feature_candidates"][0]["review_required"])
        self.assertIn("topographic survey", report["feature_candidates"][0]["blockers"][0])

    def test_detection_report_does_not_use_readiness_or_professional_responsibility_words(self) -> None:
        report = build_map_feature_detection_report(
            image_detections=[
                {"kind": "building", "bbox": [10, 20, 40, 50], "confidence": 0.45, "image_path": "/tmp/map.png"},
            ]
        )

        rendered_values = str(report).lower()

        for blocked_word in ["construction-ready", "stamp", "seal", "approval"]:
            self.assertNotIn(blocked_word, rendered_values)


if __name__ == "__main__":
    unittest.main()
