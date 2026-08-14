from __future__ import annotations

from copy import deepcopy
import unittest

from backend.planning.vision_public_bootstrap import (
    WEAK_SUPERVISION_STATUS,
    build_geographic_tile_grid,
    build_split_integrity,
    build_public_review_sprint,
    build_weak_supervision_package,
    capture_date_from_epoch_ms,
    capture_season,
    clip_ring_to_bbox,
    imagery_quality_band,
    merge_weak_supervision_packages,
    normalize_microsoft_partition_url,
    quadkey_for_point,
    quadkeys_for_bbox,
    verify_weak_supervision_package,
    weak_supervision_package_fingerprint,
)


REGISTRY_FINGERPRINT = "f" * 64


def _source_record(*, source_id: str, source_role: str, name: str, license_name: str):
    license_url = f"https://licenses.example/{source_id}"
    return {
        "source_id": source_id,
        "source_role": source_role,
        "name": name,
        "url": f"https://sources.example/{source_id}",
        "license": license_name,
        "license_url": license_url,
        "source_rights": {
            "license": license_name,
            "license_url": license_url,
            "training_use_allowed": True,
            "storage_allowed": True,
            "derivative_labels_allowed": True,
            "rights_registry_fingerprint": REGISTRY_FINGERPRINT,
        },
    }


def _registered_sources():
    return (
        _source_record(
            source_id="usgs_naip_conus",
            source_role="training_imagery",
            name="USGS NAIP",
            license_name="public-domain",
        ),
        _source_record(
            source_id="microsoft_global_building_footprints",
            source_role="weak_label_proposals_only",
            name="Microsoft Global ML Building Footprints",
            license_name="CDLA-Permissive-2.0",
        ),
    )


class VisionPublicBootstrapTests(unittest.TestCase):
    def test_label_source_availability_is_sealed_and_region_scoped_when_merged(self) -> None:
        imagery_source, label_source = _registered_sources()

        def package_for(frame_id: str, geography_id: str, split: str):
            tile = build_geographic_tile_grid(
                center_longitude=-96.237,
                center_latitude=41.185,
                rows=1,
                columns=1,
                tile_meters=320,
                image_pixels=512,
                permanent_split=split,
            )[0]
            tile.update({
                "frame_id": frame_id,
                "file_name": f"{frame_id}.png",
                "sha256": ("a" if geography_id == "gretna_ne" else "b") * 64,
                "geography_id": geography_id,
            })
            bbox = tile["bbox_wgs84"]
            feature = {
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [[
                    [bbox["west"], bbox["south"]],
                    [bbox["east"], bbox["south"]],
                    [bbox["east"], bbox["north"]],
                    [bbox["west"], bbox["north"]],
                    [bbox["west"], bbox["south"]],
                ]]},
            }
            package = build_weak_supervision_package(
                tiles=[tile],
                footprint_features=[feature],
                imagery_source=imagery_source,
                label_source=label_source,
            )
            package["label_source_status"] = [{
                "source_id": "usgs_nhd_surface_water",
                "status": "unavailable",
                "feature_count": 0,
                "blockers": ["layer_9:HTTP 500"],
                "fallback_used": False,
            }]
            package["dataset_fingerprint"] = weak_supervision_package_fingerprint(package)
            return package

        first = package_for("frame-gretna", "gretna_ne", "train")
        second = package_for("frame-seattle", "seattle_wa", "test")
        self.assertTrue(verify_weak_supervision_package(first)["valid"])

        tampered = deepcopy(first)
        tampered["label_source_status"][0]["status"] = "ready"
        self.assertIn(
            "weak_dataset_fingerprint_mismatch",
            verify_weak_supervision_package(tampered)["blockers"],
        )
        fallback = deepcopy(first)
        fallback["label_source_status"][0]["fallback_used"] = True
        fallback["dataset_fingerprint"] = weak_supervision_package_fingerprint(fallback)
        self.assertIn(
            "label_source_status_fallback_boundary_invalid",
            verify_weak_supervision_package(fallback)["blockers"],
        )

        merged = merge_weak_supervision_packages(
            [first, second],
            source_names=["gretna_ne", "seattle_wa"],
        )
        self.assertTrue(verify_weak_supervision_package(merged)["valid"])
        self.assertEqual(len(merged["label_source_status"]), 2)
        self.assertEqual(
            {item["source_dataset"] for item in merged["label_source_status"]},
            {"gretna_ne", "seattle_wa"},
        )
        self.assertIn(
            "weak_label_source_unavailable:gretna_ne:usgs_nhd_surface_water",
            merged["promotion_blockers"],
        )

    def test_capture_metadata_is_normalized_without_guessing(self) -> None:
        self.assertEqual(capture_date_from_epoch_ms(1659398400000), "2022-08-02")
        self.assertEqual(capture_season("2022-08-02"), "summer")
        self.assertEqual(capture_season("2022-10-14"), "autumn")
        self.assertEqual(capture_season("unknown"), "")
        self.assertEqual(imagery_quality_band(0.3), "high_resolution_0_30m_or_better")
        self.assertEqual(imagery_quality_band(0.6), "medium_resolution_0_31m_to_0_60m")
        self.assertEqual(imagery_quality_band(1.0), "standard_resolution_0_61m_to_1_00m")

    def test_gretna_quadkey_matches_public_partition_index(self) -> None:
        self.assertEqual(quadkey_for_point(-96.2370225, 41.1852405, level=9), "021332333")

    def test_legacy_microsoft_static_host_is_rewritten_to_blob_storage(self) -> None:
        self.assertEqual(
            normalize_microsoft_partition_url(
                "https://bfppub.z5.web.core.windows.net/2026-07-24/data/part.csv.gz"
            ),
            "https://bfppub.blob.core.windows.net/%24web/2026-07-24/data/part.csv.gz",
        )

    def test_bbox_partition_lookup_covers_every_intersecting_quadkey(self) -> None:
        quadkeys = quadkeys_for_bbox(
            {"west": -100.0, "south": 40.0, "east": -90.0, "north": 45.0},
            level=9,
        )

        self.assertGreater(len(quadkeys), 5)
        self.assertIn(quadkey_for_point(-100.0, 45.0, level=9), quadkeys)
        self.assertIn(quadkey_for_point(-90.0, 40.0, level=9), quadkeys)

    def test_tile_grid_has_balanced_train_validation_and_test_splits(self) -> None:
        tiles = build_geographic_tile_grid(
            center_longitude=-96.237,
            center_latitude=41.185,
            rows=4,
            columns=4,
            tile_meters=320,
            image_pixels=512,
        )

        self.assertEqual(len(tiles), 16)
        self.assertEqual(sum(tile["split"] == "train" for tile in tiles), 12)
        self.assertEqual(sum(tile["split"] == "validation" for tile in tiles), 2)
        self.assertEqual(sum(tile["split"] == "test" for tile in tiles), 2)

    def test_permanent_geography_splits_are_disjoint_and_leakage_is_reported(self) -> None:
        images = []
        for image_id, (geography_id, split) in enumerate(
            (("gretna_ne", "train"), ("denver_co", "validation"), ("charlotte_nc", "test")),
            start=1,
        ):
            tile = build_geographic_tile_grid(
                center_longitude=-96.237,
                center_latitude=41.185,
                rows=1,
                columns=1,
                tile_meters=320,
                image_pixels=512,
                permanent_split=split,
            )[0]
            images.append({"id": image_id, "geography_id": geography_id, "split": tile["split"]})

        integrity = build_split_integrity(
            images,
            required_splits=("train", "validation", "test"),
        )
        self.assertTrue(integrity["valid"])
        self.assertEqual(integrity["groups_by_split"]["validation"], ["denver_co"])

        images.append({"id": 4, "geography_id": "gretna_ne", "split": "test"})
        leaked = build_split_integrity(images, required_splits=("train", "validation", "test"))
        self.assertFalse(leaked["valid"])
        self.assertEqual(leaked["leaked_groups"], ["gretna_ne"])
        self.assertIn("split_group_leakage_detected", leaked["blockers"])

    def test_polygon_clipping_keeps_geometry_inside_tile(self) -> None:
        clipped = clip_ring_to_bbox(
            [[-1, -1], [2, -1], [2, 2], [-1, 2], [-1, -1]],
            {"west": 0, "south": 0, "east": 1, "north": 1},
        )

        self.assertGreaterEqual(len(clipped), 4)
        self.assertEqual(clipped[0], clipped[-1])
        self.assertTrue(all(0 <= point[0] <= 1 and 0 <= point[1] <= 1 for point in clipped))

    def test_bootstrap_package_is_trainable_but_cannot_be_promoted(self) -> None:
        tile = build_geographic_tile_grid(
            center_longitude=-96.237,
            center_latitude=41.185,
            rows=1,
            columns=1,
            tile_meters=320,
            image_pixels=512,
        )[0]
        tile["sha256"] = "a" * 64
        bbox = tile["bbox_wgs84"]
        inset_x = (bbox["east"] - bbox["west"]) * 0.2
        inset_y = (bbox["north"] - bbox["south"]) * 0.2
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [bbox["west"] + inset_x, bbox["south"] + inset_y],
                    [bbox["east"] - inset_x, bbox["south"] + inset_y],
                    [bbox["east"] - inset_x, bbox["north"] - inset_y],
                    [bbox["west"] + inset_x, bbox["north"] - inset_y],
                    [bbox["west"] + inset_x, bbox["south"] + inset_y],
                ]],
            },
        }
        imagery_source, label_source = _registered_sources()
        package = build_weak_supervision_package(
            tiles=[tile],
            footprint_features=[feature],
            imagery_source=imagery_source,
            label_source=label_source,
        )

        self.assertEqual(package["supervision_status"], WEAK_SUPERVISION_STATUS)
        self.assertFalse(package["promotion_eligible"])
        self.assertEqual(package["eligible_image_count"], 1)
        self.assertEqual(package["annotation_count"], 1)
        self.assertEqual(package["annotations"][0]["review_status"], "pending")
        self.assertTrue(package["dataset_fingerprint"])

        second_tile = deepcopy(tile)
        second_tile.update({"frame_id": "public_naip_second", "file_name": "second.png", "sha256": "b" * 64})
        second = build_weak_supervision_package(
            tiles=[second_tile],
            footprint_features=[feature],
            imagery_source=imagery_source,
            label_source=label_source,
        )
        merged = merge_weak_supervision_packages(
            [package, second],
            source_names=["gretna", "dallas"],
        )

        self.assertEqual(merged["eligible_image_count"], 2)
        self.assertEqual(merged["annotation_count"], 2)
        self.assertEqual([item["id"] for item in merged["images"]], [1, 2])
        self.assertEqual([item["image_id"] for item in merged["annotations"]], [1, 2])
        self.assertEqual({item["source_dataset"] for item in merged["images"]}, {"gretna", "dallas"})
        self.assertFalse(merged["promotion_eligible"])
        self.assertIn("multi_geography_generalization_not_measured", merged["promotion_blockers"])

    def test_review_sprint_starts_with_zero_ground_truth_and_verified_frames(self) -> None:
        tile = build_geographic_tile_grid(
            center_longitude=-96.237,
            center_latitude=41.185,
            rows=1,
            columns=1,
            tile_meters=320,
            image_pixels=512,
        )[0]
        tile.update(
            {
                "sha256": "a" * 64,
                "source_url": "https://imagery.nationalmap.gov/arcgis/rest/services/USGSNAIPPlus/ImageServer/exportImage",
                "geography_id": "gretna_ne",
                "capture_date": "2022-08-02",
                "season": "summer",
                "imagery_quality_band": "medium_resolution_0_31m_to_0_60m",
                "resolution_meters": 0.6,
                "source_agency": "USDA",
                "source_item_ids": [120902],
            }
        )
        bbox = tile["bbox_wgs84"]
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [bbox["west"], bbox["south"]],
                    [bbox["east"], bbox["south"]],
                    [bbox["east"], bbox["north"]],
                    [bbox["west"], bbox["north"]],
                    [bbox["west"], bbox["south"]],
                ]],
            },
        }
        imagery_source, label_source = _registered_sources()
        package = build_weak_supervision_package(
            tiles=[tile],
            footprint_features=[feature],
            imagery_source=imagery_source,
            label_source=label_source,
        )

        validation = verify_weak_supervision_package(package)
        sprint = build_public_review_sprint(package)

        self.assertTrue(validation["valid"])
        self.assertEqual(sprint["imagery_frame_count"], 1)
        self.assertEqual(sprint["pending_candidate_count"], 1)
        self.assertEqual(sprint["ground_truth_annotation_count"], 0)
        self.assertFalse(sprint["promotion_eligible"])
        meta = sprint["meta"]
        self.assertEqual(meta["candidate_review_inbox_v1"]["counts"]["pending"], 1)
        self.assertEqual(meta["civora_vision_ground_truth_ledger_v1"]["events"], [])
        frame = meta["civora_vision_detection_report_v2"]["imagery_frames"][0]
        self.assertEqual(frame["frame_id"], tile["frame_id"])
        self.assertEqual(frame["geography_id"], "gretna_ne")
        self.assertEqual(frame["season"], "summer")

        package["images"][0]["source_sha256"] = "b" * 64
        with self.assertRaisesRegex(ValueError, "weak_dataset_fingerprint_mismatch"):
            build_public_review_sprint(package)


if __name__ == "__main__":
    unittest.main()
