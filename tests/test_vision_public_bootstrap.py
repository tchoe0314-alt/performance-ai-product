from __future__ import annotations

import unittest

from backend.planning.vision_public_bootstrap import (
    WEAK_SUPERVISION_STATUS,
    build_geographic_tile_grid,
    build_weak_supervision_package,
    clip_ring_to_bbox,
    merge_weak_supervision_packages,
    normalize_microsoft_partition_url,
    quadkey_for_point,
    quadkeys_for_bbox,
)


class VisionPublicBootstrapTests(unittest.TestCase):
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
        package = build_weak_supervision_package(
            tiles=[tile],
            footprint_features=[feature],
            imagery_source={"name": "USGS", "license": "public-domain", "source_rights": {}},
            label_source={"name": "Microsoft", "license": "CDLA-Permissive-2.0", "source_rights": {}},
        )

        self.assertEqual(package["supervision_status"], WEAK_SUPERVISION_STATUS)
        self.assertFalse(package["promotion_eligible"])
        self.assertEqual(package["eligible_image_count"], 1)
        self.assertEqual(package["annotation_count"], 1)
        self.assertEqual(package["annotations"][0]["review_status"], "pending")
        self.assertTrue(package["dataset_fingerprint"])

        second = {
            **package,
            "images": [{**package["images"][0], "file_name": "second.png"}],
            "dataset_fingerprint": "b" * 64,
        }
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


if __name__ == "__main__":
    unittest.main()
