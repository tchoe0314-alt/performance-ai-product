from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from urllib.parse import parse_qs, urlsplit

from backend.planning.vision_ground_truth_flywheel import (
    DATASET_VERSION,
    LEDGER_VERSION,
    verify_ground_truth_ledger,
)
from backend.planning.vision_public_bootstrap import (
    build_geographic_tile_grid,
    build_public_review_sprint,
    build_weak_supervision_package,
    verify_public_review_sprint,
    verify_weak_supervision_package,
    weak_supervision_package_fingerprint,
)
from backend.planning.vision_review_gallery import build_public_review_gallery_html
from backend.scripts.apply_public_vision_review_decisions import (
    DECISIONS_VERSION,
    apply_review_decisions,
    review_decisions_fingerprint,
)
from backend.scripts.bootstrap_public_vision_dataset import _select_usgs_records, _usgs_export_url
from backend.scripts.merge_public_vision_datasets import merge_public_vision_packages


REGISTRY_FINGERPRINT = "f" * 64


def _source_record(*, source_id: str, source_role: str, license_name: str):
    license_url = f"https://licenses.example/{source_id}"
    return {
        "source_id": source_id,
        "source_role": source_role,
        "name": source_id,
        "url": f"https://sources.example/{source_id}",
        "license": license_name,
        "license_url": license_url,
        "source_rights": {
            "license": license_name,
            "license_url": license_url,
            "training_use_allowed": True,
            "storage_allowed": True,
            "derivative_labels_allowed": True,
            "redistribution_allowed": True,
            "rights_registry_fingerprint": REGISTRY_FINGERPRINT,
        },
    }


def _review_sprint():
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
            "source_url": (
                "https://imagery.nationalmap.gov/arcgis/rest/services/USGSNAIPPlus/"
                "ImageServer/exportImage?mosaicRule=locked"
            ),
            "geography_id": "gretna_ne",
            "capture_date": "2022-08-02",
            "capture_year": 2022,
            "season": "summer",
            "imagery_quality_band": "medium_resolution_0_31m_to_0_60m",
            "resolution_meters": 0.6,
            "source_agency": "USDA",
            "source_item_ids": [120902],
            "source_item_names": ["NAIP fixture"],
        }
    )
    bbox = tile["bbox_wgs84"]
    width = bbox["east"] - bbox["west"]
    height = bbox["north"] - bbox["south"]

    def feature(x0: float, y0: float, x1: float, y1: float):
        return {
            "type": "Feature",
            "properties": {"confidence": 0.71},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [bbox["west"] + width * x0, bbox["south"] + height * y0],
                    [bbox["west"] + width * x1, bbox["south"] + height * y0],
                    [bbox["west"] + width * x1, bbox["south"] + height * y1],
                    [bbox["west"] + width * x0, bbox["south"] + height * y1],
                    [bbox["west"] + width * x0, bbox["south"] + height * y0],
                ]],
            },
        }

    package = build_weak_supervision_package(
        tiles=[tile],
        footprint_features=[feature(0.1, 0.1, 0.3, 0.3), feature(0.6, 0.6, 0.85, 0.85)],
        imagery_source=_source_record(
            source_id="usgs_naip_conus",
            source_role="training_imagery",
            license_name="public-domain",
        ),
        label_source=_source_record(
            source_id="microsoft_global_building_footprints",
            source_role="weak_label_proposals_only",
            license_name="CDLA-Permissive-2.0",
        ),
    )
    return package, build_public_review_sprint(package)


def _decisions(sprint, rows):
    value = {
        "version": DECISIONS_VERSION,
        "review_sprint_fingerprint": sprint["review_sprint_fingerprint"],
        "reviewer_id": "reviewer-é",
        "source_frame_review_attested": True,
        "exported_at": "2026-08-02T18:00:00.000Z",
        "decisions": rows,
    }
    value["decisions_fingerprint"] = review_decisions_fingerprint(value)
    return value


class PublicVisionReviewSprintTests(unittest.TestCase):
    def test_gallery_renders_registered_frames_and_truthful_review_controls(self) -> None:
        _, sprint = _review_sprint()

        html = build_public_review_gallery_html(sprint, image_prefix="images")

        self.assertIn("Nothing starts as ground truth", html)
        self.assertIn("images/naip-r00-c00.png", html)
        self.assertIn("Review ${candidate.label}", html)
        self.assertIn("decisions_fingerprint", html)
        self.assertIn("crypto.subtle.digest('SHA-256'", html)
        self.assertIn("Exported ${reviewed.length} decisions", html)
        self.assertNotIn("construction-ready", html.lower())

    def test_attested_accept_and_reject_append_verified_ledger_events(self) -> None:
        _, sprint = _review_sprint()
        candidates = sprint["meta"]["candidate_review_inbox_v1"]["candidates"]
        decisions = _decisions(
            sprint,
            [
                {
                    "candidate_id": candidates[0]["candidate_id"],
                    "action": "accept",
                    "reason": "Visible roof outline matches the proposal.",
                },
                {
                    "candidate_id": candidates[1]["candidate_id"],
                    "action": "reject",
                    "reason": "No matching roof is visible in the source frame.",
                },
            ],
        )

        result = apply_review_decisions(review_sprint=sprint, decisions=decisions)

        self.assertEqual(result["reviewed_decision_count"], 2)
        self.assertEqual(result["accepted_count"], 1)
        self.assertEqual(result["rejected_count"], 1)
        self.assertEqual(result["source_decisions_fingerprint"], decisions["decisions_fingerprint"])
        self.assertTrue(verify_ground_truth_ledger(result[LEDGER_VERSION])["valid"])
        self.assertEqual(len(result[LEDGER_VERSION]["events"]), 2)
        self.assertEqual(result[DATASET_VERSION]["annotation_count"], 1)
        self.assertFalse(result["promotion_eligible"])

    def test_review_handoff_rejects_missing_attestation_and_content_tampering(self) -> None:
        _, sprint = _review_sprint()
        candidate_id = sprint["meta"]["candidate_review_inbox_v1"]["candidates"][0]["candidate_id"]
        decisions = _decisions(
            sprint,
            [{"candidate_id": candidate_id, "action": "accept", "reason": "Matches visible roof."}],
        )
        unattested = deepcopy(decisions)
        unattested["source_frame_review_attested"] = False
        unattested["decisions_fingerprint"] = review_decisions_fingerprint(unattested)
        with self.assertRaisesRegex(ValueError, "must attest"):
            apply_review_decisions(review_sprint=sprint, decisions=unattested)

        tampered = deepcopy(decisions)
        tampered["decisions"][0]["reason"] = "Changed after export."
        with self.assertRaisesRegex(ValueError, "fingerprint mismatch"):
            apply_review_decisions(review_sprint=sprint, decisions=tampered)

        unknown = deepcopy(decisions)
        unknown["decisions"][0]["candidate_id"] = "outside-this-sprint"
        unknown["decisions_fingerprint"] = review_decisions_fingerprint(unknown)
        with self.assertRaisesRegex(ValueError, "outside this sprint"):
            apply_review_decisions(review_sprint=sprint, decisions=unknown)

        invalid_timestamp = deepcopy(decisions)
        invalid_timestamp["exported_at"] = "not-a-timestamp"
        invalid_timestamp["decisions_fingerprint"] = review_decisions_fingerprint(invalid_timestamp)
        with self.assertRaisesRegex(ValueError, "timestamp is invalid"):
            apply_review_decisions(review_sprint=sprint, decisions=invalid_timestamp)

        tampered_sprint = deepcopy(sprint)
        tampered_sprint["meta"]["candidate_review_inbox_v1"]["candidates"][0]["label"] = "altered"
        validation = verify_public_review_sprint(tampered_sprint)
        self.assertFalse(validation["valid"])
        self.assertIn("review_sprint_fingerprint_mismatch", validation["blockers"])

    def test_package_fingerprint_covers_license_and_rights_records(self) -> None:
        package, _ = _review_sprint()
        self.assertTrue(verify_weak_supervision_package(package)["valid"])

        tampered = deepcopy(package)
        tampered["licenses"][1]["license"] = "unknown-license"
        validation = verify_weak_supervision_package(tampered)
        self.assertFalse(validation["valid"])
        self.assertIn("source_rights_license_mismatch", validation["blockers"])
        self.assertIn("weak_dataset_fingerprint_mismatch", validation["blockers"])

    def test_merge_verifies_original_images_then_refingerprints_copied_paths(self) -> None:
        package, _ = _review_sprint()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "gretna" / "images"
            source_root.mkdir(parents=True)
            image_bytes = b"registered-image-fixture"
            image_path = source_root / package["images"][0]["file_name"]
            image_path.write_bytes(image_bytes)
            package["images"][0]["source_sha256"] = hashlib.sha256(image_bytes).hexdigest()
            package["image_root"] = str(source_root)
            package["dataset_fingerprint"] = weak_supervision_package_fingerprint(package)
            package_path = root / "gretna" / "weak-coco-package.json"
            package_path.write_text(json.dumps(package), encoding="utf-8")

            result = merge_public_vision_packages(
                package_paths=[package_path],
                output_root=root / "merged",
            )
            merged = json.loads(Path(result["package"]).read_text(encoding="utf-8"))

            self.assertTrue(verify_weak_supervision_package(merged)["valid"])
            self.assertEqual(merged["source_datasets"][0]["dataset_fingerprint"], package["dataset_fingerprint"])
            self.assertEqual(merged["images"][0]["file_name"], "gretna/naip-r00-c00.png")
            self.assertEqual(
                (Path(result["image_root"]) / merged["images"][0]["file_name"]).read_bytes(),
                image_bytes,
            )

    def test_usgs_selection_requires_exact_latest_usda_naip_records_and_locks_export(self) -> None:
        records = [
            {"OBJECTID": 8, "Category": 1, "agency": "USDA", "acquisition_date": 1000},
            {"OBJECTID": 9, "Category": 1, "agency": "USDA", "acquisition_date": 2000},
            {"OBJECTID": 10, "Category": 1, "agency": "USDA", "acquisition_date": 2000},
            {"OBJECTID": 11, "Category": 2, "agency": "USDA", "acquisition_date": 3000},
            {"OBJECTID": 12, "Category": 1, "agency": "commercial", "acquisition_date": 4000},
        ]

        selected = _select_usgs_records(records)
        self.assertEqual([item["OBJECTID"] for item in selected], [9, 10])
        url = _usgs_export_url(
            "https://imagery.nationalmap.gov/arcgis/rest/services/USGSNAIPPlus/ImageServer",
            {"west": -96.3, "south": 41.1, "east": -96.2, "north": 41.2},
            512,
            raster_ids=[item["OBJECTID"] for item in selected],
        )
        mosaic_rule = json.loads(parse_qs(urlsplit(url).query)["mosaicRule"][0])
        self.assertEqual(mosaic_rule["mosaicMethod"], "esriMosaicLockRaster")
        self.assertEqual(mosaic_rule["lockRasterIds"], [9, 10])
        with self.assertRaisesRegex(SystemExit, "rights-cleared USGS raster record"):
            _usgs_export_url(
                "https://imagery.nationalmap.gov/arcgis/rest/services/USGSNAIPPlus/ImageServer",
                {"west": -96.3, "south": 41.1, "east": -96.2, "north": 41.2},
                512,
            )

    def test_committed_collection_plan_is_multi_geography_and_never_ground_truth_by_default(self) -> None:
        root = Path(__file__).resolve().parents[1]
        registry = json.loads((root / "vision/datasets/public-source-registry-v1.json").read_text(encoding="utf-8"))
        plan = json.loads((root / "vision/datasets/us-conus-building-seed-v1.json").read_text(encoding="utf-8"))

        self.assertEqual(registry["version"], "civora_vision_public_source_registry_v1")
        self.assertEqual(len(plan["geographies"]), 5)
        self.assertEqual(len({item["geography_id"] for item in plan["geographies"]}), 5)
        self.assertFalse(plan["output_policy"]["ground_truth_at_collection_time"])
        self.assertFalse(plan["output_policy"]["promotion_eligible"])
        for source in registry["sources"].values():
            self.assertTrue(source["rights"]["training_use_allowed"])
            self.assertTrue(source["rights"]["storage_allowed"])
            self.assertTrue(source["rights"]["derivative_labels_allowed"])
            self.assertTrue(source["license"])
            self.assertTrue(source["license_url"].startswith("https://"))


if __name__ == "__main__":
    unittest.main()
