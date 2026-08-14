from __future__ import annotations

from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request
from unittest.mock import MagicMock, patch
from PIL import Image

from backend.planning.vision_ground_truth_flywheel import (
    DATASET_VERSION,
    LEDGER_VERSION,
    verify_ground_truth_ledger,
)
from backend.planning.vision_evidence_integrity import (
    build_frozen_split_manifest,
    build_held_out_test_commitment,
    coco_dataset_fingerprint,
)
from backend.planning.vision_public_bootstrap import (
    build_geographic_tile_grid,
    build_public_review_sprint,
    build_scoped_weak_supervision_package,
    build_weak_supervision_package,
    merge_weak_supervision_packages,
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
from backend.scripts.bootstrap_public_vision_dataset import (
    _buffer_line_feature,
    _collect_additional_label_sets,
    _open_source_request,
    _restore_verified_imagery_tile,
    _select_usgs_records,
    _usgs_export_url,
    _write_imagery_tile_checkpoint,
)
from backend.scripts.bootstrap_public_vision_collection import verify_resumable_region
from backend.scripts.merge_public_vision_datasets import merge_public_vision_packages


REGISTRY_FINGERPRINT = "f" * 64


def _png_bytes(*, size: tuple[int, int]) -> bytes:
    output = io.BytesIO()
    Image.new("RGB", size, (90, 120, 80)).save(output, format="PNG")
    return output.getvalue()


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
    def test_split_scoped_packages_physically_separate_training_and_frozen_test(self) -> None:
        first, _ = _review_sprint()
        first["images"][0]["split"] = "train"
        first["images"][0]["geography_id"] = "train-city"
        first["splits"] = {"train": [1], "validation": [], "test": []}
        first["dataset_fingerprint"] = weak_supervision_package_fingerprint(first)
        second = deepcopy(first)
        second["images"][0].update({
            "imagery_frame_id": "test-frame",
            "source_sha256": "b" * 64,
            "split": "test",
            "geography_id": "test-city",
        })
        second["splits"] = {"train": [], "validation": [], "test": [1]}
        second["dataset_fingerprint"] = weak_supervision_package_fingerprint(second)
        merged = merge_weak_supervision_packages(
            [first, second],
            source_names=["train-city", "test-city"],
            split_policy={
                "strategy": "geography_disjoint",
                "grouping_field": "geography_id",
                "required_splits": ["train", "test"],
                "test_split_frozen": True,
            },
        )
        merged["images"][0]["hidden_test_labels"] = [{"category_id": 1}]
        merged["annotations"][0]["hidden_test_geography"] = "test-city"
        merged["categories"][0]["hidden_test_count"] = 12
        merged["source_datasets"][0]["hidden_test_summary"] = "test-city"
        merged["label_source_status"].append(
            {
                "source_dataset": "train-city",
                "source_id": "fixture-source",
                "status": "ready",
                "fallback_used": False,
                "feature_count": 1,
                "hidden_test_status": "test-city",
            }
        )
        merged["review_candidates"]["features"][0]["properties"]["hidden_test_status"] = "test-city"
        merged["split_policy"]["hidden_test_labels"] = [1, 2, 3]
        merged["licenses"][0]["hidden_test_location"] = "test-city"
        merged["dataset_fingerprint"] = weak_supervision_package_fingerprint(merged)
        merged["coco_evidence_fingerprint"] = coco_dataset_fingerprint(merged)
        merged["frozen_split_manifest"] = build_frozen_split_manifest(merged)

        training = build_scoped_weak_supervision_package(
            merged,
            included_splits=("train",),
            dataset_role="training_and_validation",
        )
        test = build_scoped_weak_supervision_package(
            merged,
            included_splits=("test",),
            dataset_role="frozen_test",
        )

        self.assertEqual({item["split"] for item in training["images"]}, {"train"})
        self.assertEqual(training["splits"]["test"], [])
        self.assertFalse(training["test_records_in_package"])
        encoded_training = json.dumps(training)
        self.assertNotIn("hidden_test_labels", encoded_training)
        self.assertNotIn("hidden_test_geography", encoded_training)
        self.assertNotIn("hidden_test_count", encoded_training)
        self.assertNotIn("hidden_test_summary", encoded_training)
        self.assertNotIn("hidden_test_status", encoded_training)
        self.assertNotIn("hidden_test_location", encoded_training)
        self.assertEqual(
            training["held_out_test_manifest"]["test_image_membership_sha256"],
            build_held_out_test_commitment(merged["frozen_split_manifest"])[
                "test_image_membership_sha256"
            ],
        )
        self.assertNotIn("test_annotation_count", training["held_out_test_manifest"])
        self.assertEqual({item["split"] for item in test["images"]}, {"test"})
        self.assertEqual(test["splits"]["train"], [])
        self.assertFalse(test["training_records_in_package"])
        self.assertTrue(verify_weak_supervision_package(training)["valid"])
        self.assertTrue(verify_weak_supervision_package(test)["valid"])

    def test_optional_label_source_outage_is_recorded_without_fabricating_fallback(self) -> None:
        source_id = "usgs_nhd_surface_water"
        source_registry = {
            source_id: {
                "source_role": "weak_label_proposals_only",
                "name": "USGS National Hydrography Dataset",
                "source_url": "https://www.usgs.gov/national-hydrography",
                "service_url": "https://hydro.nationalmap.gov/arcgis/rest/services/nhd/MapServer",
                "service_layers": [{"layer_id": 9}, {"layer_id": 12}],
                "license": "public-domain",
                "license_url": "https://www.usgs.gov/license",
                "rights": {
                    "training_use_allowed": True,
                    "storage_allowed": True,
                    "derivative_labels_allowed": True,
                    "redistribution_allowed": True,
                },
            }
        }
        with patch(
            "backend.scripts.bootstrap_public_vision_dataset._query_arcgis_geojson_features",
            side_effect=SystemExit("Approved source returned HTTP 500; no fallback source was used."),
        ) as query:
            label_sets, statuses = _collect_additional_label_sets(
                source_configs=[{
                    "source_id": source_id,
                    "category_id": 3,
                    "category_name": "surface_water",
                    "feature_type": "water/pond/basin",
                }],
                source_registry=source_registry,
                registry_fingerprint=REGISTRY_FINGERPRINT,
                bbox={"west": -123, "south": 47, "east": -122, "north": 48},
            )

        self.assertEqual(query.call_count, 2)
        self.assertEqual(label_sets[0]["features"], [])
        self.assertEqual(statuses[0]["status"], "unavailable")
        self.assertEqual(statuses[0]["feature_count"], 0)
        self.assertFalse(statuses[0]["fallback_used"])
        self.assertEqual(len(statuses[0]["blockers"]), 2)

    def test_buffered_road_centerline_becomes_one_closed_review_corridor(self) -> None:
        buffered = _buffer_line_feature(
            {
                "type": "Feature",
                "properties": {"NAME": "Review Road"},
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[-96.24, 41.18], [-96.235, 41.182], [-96.23, 41.181]],
                },
            },
            half_width_meters=8,
        )

        self.assertEqual(len(buffered), 1)
        ring = buffered[0]["geometry"]["coordinates"][0]
        self.assertEqual(ring[0], ring[-1])
        self.assertEqual(len(ring), 7)
        self.assertEqual(buffered[0]["properties"]["weak_geometry_method"], "buffered_centerline_corridor")

    def test_multiclass_weak_package_preserves_annotation_feature_types(self) -> None:
        package, _ = _review_sprint()
        bbox = package["images"][0]["bbox_wgs84"]
        road = {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [bbox["west"], bbox["south"]],
                    [bbox["east"], bbox["south"]],
                    [bbox["east"], bbox["south"] + (bbox["north"] - bbox["south"]) * 0.1],
                    [bbox["west"], bbox["south"] + (bbox["north"] - bbox["south"]) * 0.1],
                    [bbox["west"], bbox["south"]],
                ]],
            },
        }
        imagery_source = package["licenses"][0]
        building_source = package["licenses"][1]
        rebuilt = build_weak_supervision_package(
            tiles=[
                {
                    **package["images"][0],
                    "frame_id": package["images"][0]["imagery_frame_id"],
                    "sha256": package["images"][0]["source_sha256"],
                }
            ],
            footprint_features=[],
            imagery_source=imagery_source,
            label_source=building_source,
            additional_label_sets=[
                {
                    "category_id": 2,
                    "category_name": "road",
                    "feature_type": "road_or_drive",
                    "features": [road],
                    "label_source": _source_record(
                        source_id="us_census_tigerweb_roads",
                        source_role="weak_label_proposals_only",
                        license_name="public-domain",
                    ),
                }
            ],
        )

        self.assertTrue(verify_weak_supervision_package(rebuilt)["valid"])
        self.assertEqual(rebuilt["annotations"][0]["category_id"], 2)
        self.assertEqual(rebuilt["annotations"][0]["feature_type"], "road_or_drive")
        sprint = build_public_review_sprint(rebuilt)
        candidate = sprint["meta"]["candidate_review_inbox_v1"]["candidates"][0]
        self.assertEqual(candidate["label"], "road or drive")
        self.assertEqual(candidate["source_record"]["feature_type"], "road_or_drive")

    def test_source_request_retries_transient_failure_without_using_fallback(self) -> None:
        request = Request("https://imagery.nationalmap.gov/approved")
        response = MagicMock()
        with patch(
            "backend.scripts.bootstrap_public_vision_dataset.urlopen",
            side_effect=[
                HTTPError(request.full_url, 502, "Bad Gateway", {}, None),
                response,
            ],
        ) as open_url, patch("backend.scripts.bootstrap_public_vision_dataset.time.sleep") as sleep:
            result = _open_source_request(request, timeout=5, attempts=3)

        self.assertIs(result, response)
        self.assertEqual(open_url.call_count, 2)
        sleep.assert_called_once()

    def test_source_request_stops_after_bounded_transient_failures(self) -> None:
        request = Request("https://imagery.nationalmap.gov/approved")
        failure = HTTPError(request.full_url, 502, "Bad Gateway", {}, None)
        with patch(
            "backend.scripts.bootstrap_public_vision_dataset.urlopen",
            side_effect=[failure, failure, failure],
        ), patch("backend.scripts.bootstrap_public_vision_dataset.time.sleep"):
            with self.assertRaisesRegex(SystemExit, "after 3 attempts; no fallback source was used"):
                _open_source_request(request, timeout=5, attempts=3)

    def test_source_request_honors_bounded_retry_after(self) -> None:
        request = Request("https://imagery.nationalmap.gov/approved")
        failure = HTTPError(request.full_url, 429, "Too Many Requests", {"Retry-After": "60"}, None)
        response = MagicMock()
        with patch(
            "backend.scripts.bootstrap_public_vision_dataset.urlopen",
            side_effect=[failure, response],
        ), patch("backend.scripts.bootstrap_public_vision_dataset.time.sleep") as sleep:
            result = _open_source_request(request, timeout=5, attempts=2)

        self.assertIs(result, response)
        sleep.assert_called_once_with(15.0)

    def test_interrupted_region_reuses_only_checksum_verified_imagery_tile(self) -> None:
        tile = build_geographic_tile_grid(
            center_longitude=-96.237,
            center_latitude=41.185,
            rows=1,
            columns=1,
            tile_meters=320,
            image_pixels=32,
            permanent_split="train",
        )[0]
        tile.update(
            {
                "sha256": "",
                "source_url": (
                    "https://imagery.nationalmap.gov/arcgis/rest/services/USGSNAIPPlus/"
                    "ImageServer/exportImage?mosaicRule=locked"
                ),
                "source_item_ids": [123],
                "source_item_names": ["NAIP fixture"],
                "geography_id": "gretna_ne",
            }
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / tile["file_name"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(_png_bytes(size=(32, 32)))
            tile["sha256"] = hashlib.sha256(destination.read_bytes()).hexdigest()
            checkpoint = root / "tile.json"
            _write_imagery_tile_checkpoint(tile, checkpoint)
            expected = dict(tile)
            restored = {
                key: value
                for key, value in tile.items()
                if key not in {"sha256", "source_url", "source_item_ids", "source_item_names", "geography_id"}
            }

            self.assertTrue(
                _restore_verified_imagery_tile(
                    restored,
                    destination=destination,
                    checkpoint_path=checkpoint,
                    image_pixels=32,
                )
            )
            self.assertEqual(restored, expected)

            destination.write_bytes(b"tampered")
            self.assertFalse(
                _restore_verified_imagery_tile(
                    dict(restored),
                    destination=destination,
                    checkpoint_path=checkpoint,
                    image_pixels=32,
                )
            )

    def test_gallery_renders_registered_frames_and_truthful_review_controls(self) -> None:
        _, sprint = _review_sprint()

        html = build_public_review_gallery_html(sprint, image_prefix="images")

        self.assertIn("Nothing starts as ground truth", html)
        self.assertIn("images/naip-r00-c00.png", html)
        self.assertIn("Review ${candidate.label}", html)
        self.assertIn("decisions_fingerprint", html)
        self.assertIn("crypto.subtle.digest('SHA-256'", html)
        self.assertIn("Exported ${reviewed.length} decisions", html)
        self.assertIn('data-testid="vision-review-queue"', html)
        self.assertIn("Needs redraw", html)
        self.assertIn("civora-vision-review:${data.review_sprint_fingerprint}", html)
        self.assertIn("frame.permanent_split", html)
        self.assertIn("state === 'redraw'", html)
        self.assertIn("corrected geometry must be redrawn in Civora Draw", html)
        self.assertIn("candidate?.label || 'visible feature'", html)
        self.assertNotIn("accepted the visible building outline", html)
        self.assertIn("height: 100vh", html)
        self.assertIn("grid-template-columns: minmax(0, 1fr)", html)
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
            self.assertEqual(
                merged["coco_evidence_fingerprint"],
                coco_dataset_fingerprint(merged),
            )
            self.assertEqual(
                merged["frozen_split_manifest"],
                build_frozen_split_manifest(merged),
            )
            self.assertEqual(merged["images"][0]["file_name"], "gretna/naip-r00-c00.png")
            self.assertEqual(
                (Path(result["image_root"]) / merged["images"][0]["file_name"]).read_bytes(),
                image_bytes,
            )

    def test_resume_region_requires_verified_package_manifest_split_and_image(self) -> None:
        package, _ = _review_sprint()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image_root = root / "images"
            image_root.mkdir()
            image_path = image_root / package["images"][0]["file_name"]
            image_path.write_bytes(b"resume-image")
            package["images"][0]["source_sha256"] = hashlib.sha256(image_path.read_bytes()).hexdigest()
            package["images"][0]["split"] = "train"
            package["splits"] = {"train": [package["images"][0]["id"]], "validation": [], "test": []}
            package["geography_id"] = "gretna_ne"
            package["image_root"] = str(image_root)
            package["label_source_status"] = [
                {
                    "source_id": item["source_id"],
                    "status": "ready",
                    "feature_count": 1,
                    "blockers": [],
                    "fallback_used": False,
                }
                for item in package["licenses"]
                if item.get("source_role") == "weak_label_proposals_only"
            ]
            package["dataset_fingerprint"] = weak_supervision_package_fingerprint(package)
            (root / "weak-coco-package.json").write_text(json.dumps(package), encoding="utf-8")
            (root / "source-manifest.json").write_text(
                json.dumps({"dataset_fingerprint": package["dataset_fingerprint"]}),
                encoding="utf-8",
            )

            verified = verify_resumable_region(root, geography_id="gretna_ne", expected_split="train")
            self.assertTrue(verified["valid"])

            image_path.unlink()
            rejected = verify_resumable_region(root, geography_id="gretna_ne", expected_split="train")
            self.assertFalse(rejected["valid"])
            self.assertIn("completed_region_image_file_missing", rejected["blockers"])

    def test_resume_region_rejects_legacy_package_without_source_status_evidence(self) -> None:
        package, _ = _review_sprint()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image_root = root / "images"
            image_root.mkdir()
            image_path = image_root / package["images"][0]["file_name"]
            image_path.write_bytes(b"resume-image")
            package["images"][0]["source_sha256"] = hashlib.sha256(image_path.read_bytes()).hexdigest()
            package["images"][0]["split"] = "train"
            package["splits"] = {"train": [package["images"][0]["id"]], "validation": [], "test": []}
            package["geography_id"] = "gretna_ne"
            package["image_root"] = str(image_root)
            package.pop("label_source_status", None)
            package["dataset_fingerprint"] = weak_supervision_package_fingerprint(package)
            (root / "weak-coco-package.json").write_text(json.dumps(package), encoding="utf-8")
            (root / "source-manifest.json").write_text(
                json.dumps({"dataset_fingerprint": package["dataset_fingerprint"]}),
                encoding="utf-8",
            )

            rejected = verify_resumable_region(root, geography_id="gretna_ne", expected_split="train")

            self.assertFalse(rejected["valid"])
            self.assertTrue(
                any(item.startswith("completed_region_label_source_status_missing:") for item in rejected["blockers"])
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
        core_plan = json.loads(
            (root / "vision/datasets/us-conus-core-segmentation-seed-v1.json").read_text(encoding="utf-8")
        )
        diagnostic = json.loads(
            (root / "vision/datasets/us-conus-core-segmentation-diagnostic-v2-report.json").read_text(encoding="utf-8")
        )

        self.assertEqual(registry["version"], "civora_vision_public_source_registry_v1")
        self.assertEqual(len(plan["geographies"]), 5)
        self.assertEqual(len({item["geography_id"] for item in plan["geographies"]}), 5)
        self.assertEqual(plan["split_policy"]["strategy"], "geography_disjoint")
        self.assertEqual(plan["split_policy"]["grouping_field"], "geography_id")
        self.assertEqual(
            {item["split"] for item in plan["geographies"]},
            {"train", "validation", "test"},
        )
        split_groups = {
            split: {item["geography_id"] for item in plan["geographies"] if item["split"] == split}
            for split in ("train", "validation", "test")
        }
        self.assertFalse(split_groups["train"] & split_groups["validation"])
        self.assertFalse(split_groups["train"] & split_groups["test"])
        self.assertFalse(split_groups["validation"] & split_groups["test"])
        self.assertFalse(plan["output_policy"]["ground_truth_at_collection_time"])
        self.assertFalse(plan["output_policy"]["promotion_eligible"])
        self.assertEqual(
            {item["category_name"] for item in core_plan["additional_label_sources"]},
            {"road", "surface_water"},
        )
        self.assertEqual(core_plan["tile_defaults"]["rows"], 3)
        self.assertEqual(core_plan["tile_defaults"]["columns"], 3)
        self.assertEqual(
            core_plan["coverage_policy"]["minimum_proposals_per_class_per_split"],
            {"building": 5, "road": 5, "surface_water": 1},
        )
        self.assertFalse(diagnostic["decision"]["promotion_eligible"])
        self.assertFalse(diagnostic["decision"]["deployed_as_primary"])
        self.assertFalse(diagnostic["decision"]["deployed_as_shadow"])
        self.assertEqual(diagnostic["decision"]["decision"], "rejected_before_deployment")
        self.assertEqual(diagnostic["dataset"]["ground_truth_annotation_count"], 0)
        for source in registry["sources"].values():
            self.assertTrue(source["rights"]["training_use_allowed"])
            self.assertTrue(source["rights"]["storage_allowed"])
            self.assertTrue(source["rights"]["derivative_labels_allowed"])
            self.assertTrue(source["license"])
            self.assertTrue(source["license_url"].startswith("https://"))


if __name__ == "__main__":
    unittest.main()
