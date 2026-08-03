from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from PIL import Image, ImageDraw

from backend.planning.vision_ai_review_assist import (
    AI_RECOMMENDATIONS,
    AI_TRIAGE_OVERRIDE_VERSION,
    AI_TRIAGE_VERSION,
    build_ai_assisted_vision_triage,
    render_ai_triage_contact_sheets,
    verify_ai_assisted_vision_triage,
)
from backend.planning.vision_public_bootstrap import (
    build_geographic_tile_grid,
    build_public_review_sprint,
    build_weak_supervision_package,
)
from backend.scripts.apply_public_vision_review_decisions import apply_review_decisions


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


def _feature(bbox, x0: float, y0: float, x1: float, y1: float, confidence: float):
    width = bbox["east"] - bbox["west"]
    height = bbox["north"] - bbox["south"]
    return {
        "type": "Feature",
        "properties": {"confidence": confidence},
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


def _review_sprint(root: Path):
    image_root = root / "images"
    image_root.mkdir(parents=True)
    tile = build_geographic_tile_grid(
        center_longitude=-96.237,
        center_latitude=41.185,
        rows=1,
        columns=1,
        tile_meters=320,
        image_pixels=256,
    )[0]
    image_path = image_root / tile["file_name"]
    image = Image.new("RGB", (256, 256), "#5d7d51")
    draw = ImageDraw.Draw(image)
    draw.rectangle((48, 48, 111, 111), fill="#d5d4cc", outline="#20262a", width=3)
    draw.rectangle((155, 155, 218, 218), fill="#406844", outline="#36553b", width=2)
    draw.line((0, 130, 256, 130), fill="#9b9388", width=18)
    image.save(image_path)
    tile.update(
        {
            "sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
            "source_url": "https://imagery.nationalmap.gov/arcgis/rest/services/USGSNAIPPlus/ImageServer/exportImage",
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
    package = build_weak_supervision_package(
        tiles=[tile],
        footprint_features=[
            _feature(bbox, 0.18, 0.56, 0.44, 0.82, 0.7),
            _feature(bbox, 0.60, 0.14, 0.86, 0.40, 0.08),
        ],
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
    return build_public_review_sprint(package), image_root


class VisionAiReviewAssistTests(unittest.TestCase):
    def test_builds_verified_recommendations_crops_and_contact_sheets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sprint, image_root = _review_sprint(root)
            crop_root = root / "triage" / "crops"

            triage = build_ai_assisted_vision_triage(
                sprint,
                image_root=image_root,
                crop_root=crop_root,
            )
            validation = verify_ai_assisted_vision_triage(triage, review_sprint=sprint)
            sheets = render_ai_triage_contact_sheets(
                triage,
                crop_root=crop_root,
                output_root=root / "triage" / "contact-sheets",
                columns=2,
                rows=1,
            )

            self.assertTrue(validation["valid"], validation["blockers"])
            self.assertEqual(triage["version"], AI_TRIAGE_VERSION)
            self.assertEqual(triage["candidate_count"], 2)
            self.assertEqual(triage["override_count"], 0)
            self.assertEqual(len(triage["recommendations"]), 2)
            self.assertTrue(all(item["recommended_action"] in AI_RECOMMENDATIONS for item in triage["recommendations"]))
            self.assertTrue(all(item["human_review_required"] is True for item in triage["recommendations"]))
            self.assertTrue(all(item["ground_truth_eligible"] is False for item in triage["recommendations"]))
            self.assertFalse(triage["human_attestation_present"])
            self.assertFalse(triage["ledger_append_allowed"])
            self.assertFalse(triage["promotion_eligible"])
            self.assertTrue(all((crop_root / item["evidence_crop"]["file_name"]).is_file() for item in triage["recommendations"]))
            self.assertEqual(len(sheets), 1)
            self.assertTrue(Path(sheets[0]).is_file())

    def test_tampering_and_source_asset_mismatch_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sprint, image_root = _review_sprint(root)
            triage = build_ai_assisted_vision_triage(
                sprint,
                image_root=image_root,
                crop_root=root / "crops",
            )
            tampered = deepcopy(triage)
            tampered["recommendations"][0]["recommended_action"] = "likely_reject"
            validation = verify_ai_assisted_vision_triage(tampered, review_sprint=sprint)
            self.assertFalse(validation["valid"])
            self.assertIn("ai_triage_fingerprint_mismatch", validation["blockers"])
            self.assertIn("ai_triage_recommendation_counts_mismatch", validation["blockers"])

            image_path = next(image_root.glob("*.png"))
            image_path.write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError, "fingerprint mismatch"):
                build_ai_assisted_vision_triage(
                    sprint,
                    image_root=image_root,
                    crop_root=root / "tampered-crops",
                )

    def test_overrides_remain_non_human_and_cannot_enter_ground_truth_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sprint, image_root = _review_sprint(root)
            candidate_id = sprint["meta"]["candidate_review_inbox_v1"]["candidates"][0]["candidate_id"]
            overrides = {
                "version": AI_TRIAGE_OVERRIDE_VERSION,
                "reviewer_type": "ai_assisted_non_human",
                "overrides": [
                    {
                        "candidate_id": candidate_id,
                        "recommended_action": "redraw_or_human_review",
                        "confidence": 0.9,
                        "review_priority": "high",
                        "reason_codes": ["ai_visual_inspection_override"],
                    }
                ],
            }
            triage = build_ai_assisted_vision_triage(
                sprint,
                image_root=image_root,
                crop_root=root / "crops",
                overrides=overrides,
            )

            self.assertTrue(triage["recommendations"][0]["override_applied"])
            self.assertEqual(triage["override_count"], 1)
            self.assertFalse(triage["ground_truth_eligible"])
            with self.assertRaisesRegex(ValueError, "Unsupported public vision review decision version"):
                apply_review_decisions(review_sprint=sprint, decisions=triage)

            human_claim = deepcopy(overrides)
            human_claim["reviewer_type"] = "human"
            with self.assertRaisesRegex(ValueError, "cannot claim human review"):
                build_ai_assisted_vision_triage(
                    sprint,
                    image_root=image_root,
                    crop_root=root / "human-claim-crops",
                    overrides=human_claim,
                )

            ground_truth_claim = deepcopy(overrides)
            ground_truth_claim["ground_truth_eligible"] = True
            with self.assertRaisesRegex(ValueError, "ground-truth eligibility"):
                build_ai_assisted_vision_triage(
                    sprint,
                    image_root=image_root,
                    crop_root=root / "ground-truth-claim-crops",
                    overrides=ground_truth_claim,
                )

            unknown = deepcopy(overrides)
            unknown["overrides"][0]["candidate_id"] = "outside-sprint"
            with self.assertRaisesRegex(ValueError, "outside this sprint"):
                build_ai_assisted_vision_triage(
                    sprint,
                    image_root=image_root,
                    crop_root=root / "unknown-crops",
                    overrides=unknown,
                )

    def test_cli_writes_verified_artifacts_and_cleans_stale_generated_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sprint, image_root = _review_sprint(root)
            sprint_path = root / "review-sprint.json"
            sprint_path.write_text(json.dumps(sprint), encoding="utf-8")
            output_root = root / "triage-output"
            stale_crop = output_root / "crops" / "stale.png"
            stale_sheet = output_root / "contact-sheets" / "triage-contact-sheet-99.jpg"
            stale_crop.parent.mkdir(parents=True)
            stale_sheet.parent.mkdir(parents=True)
            stale_crop.write_bytes(b"stale")
            stale_sheet.write_bytes(b"stale")
            repository_root = Path(__file__).resolve().parents[1]
            environment = os.environ.copy()
            environment["PYTHONPATH"] = str(repository_root)

            completed = subprocess.run(
                [
                    sys.executable,
                    "backend/scripts/triage_public_vision_review_sprint.py",
                    "--review-sprint",
                    str(sprint_path),
                    "--image-root",
                    str(image_root),
                    "--output-root",
                    str(output_root),
                ],
                cwd=repository_root,
                env=environment,
                check=True,
                capture_output=True,
                text=True,
            )

            summary = json.loads(completed.stdout)
            triage = json.loads((output_root / "ai-assisted-triage.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["candidate_count"], 2)
            self.assertEqual(summary["contact_sheet_count"], 1)
            self.assertTrue(verify_ai_assisted_vision_triage(triage, review_sprint=sprint)["valid"])
            self.assertFalse(stale_crop.exists())
            self.assertFalse(stale_sheet.exists())
            self.assertEqual(len(list((output_root / "crops").glob("*.png"))), 2)
            self.assertEqual(len(list((output_root / "contact-sheets").glob("*.jpg"))), 1)


if __name__ == "__main__":
    unittest.main()
