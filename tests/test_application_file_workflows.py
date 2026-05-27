import tempfile
import unittest
from io import BytesIO
from pathlib import Path

from fastapi import UploadFile

from backend.application.file_workflows import (
    download_artifact_response,
    existing_conditions_online_sources,
    fetch_existing_conditions_online,
    get_uploaded_image_response,
    upload_existing_conditions_file,
    upload_image_file,
)


class FakeAuthStore:
    def __init__(self, user=None):
        self.user = user

    def authenticate_token(self, token: str):
        if token == "good-token":
            return dict(self.user or {"user_id": "u1"})
        return None


class ApplicationFileWorkflowsTest(unittest.TestCase):
    def test_upload_image_file_stores_prefixed_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            upload = UploadFile(filename="site.png", file=BytesIO(b"abc"))
            result = upload_image_file(
                upload_dir=Path(tmpdir),
                file=upload,
                current_user={"user_id": "u1"},
            )
            self.assertTrue(result["stored_filename"].startswith("u1_"))
            self.assertTrue((Path(tmpdir) / result["stored_filename"]).exists())

    def test_get_uploaded_image_response_validates_token_and_owner(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "u1_site.png"
            target.write_bytes(b"abc")
            response = get_uploaded_image_response(
                upload_dir=Path(tmpdir),
                auth_store=FakeAuthStore({"user_id": "u1"}),
                filename="u1_site.png",
                token="good-token",
            )
            self.assertEqual(Path(response.path).name, "u1_site.png")

    def test_download_artifact_response_returns_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            user_dir = Path(tmpdir) / "u1"
            user_dir.mkdir()
            artifact = user_dir / "plan.dxf"
            artifact.write_text("dxf")
            response = download_artifact_response(
                artifact_dir=Path(tmpdir),
                current_user={"user_id": "u1"},
                filename="plan.dxf",
            )
            self.assertEqual(Path(response.path).name, "plan.dxf")

    def test_upload_existing_conditions_imports_survey_csv(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            upload = UploadFile(
                filename="survey.csv",
                file=BytesIO(b"x,y,z\n0,0,100\n10,0,101\n0,10,99\n"),
            )
            result = upload_existing_conditions_file(
                upload_dir=Path(tmpdir),
                file=upload,
                current_user={"user_id": "u1"},
            )

            self.assertTrue(result["success"])
            self.assertEqual(result["canonical_existing_conditions"]["survey"]["point_count"], 3)
            self.assertTrue(result["existing_conditions_summary"]["survey"]["ready"])

    def test_online_sources_returns_truth_labeled_registry(self):
        result = existing_conditions_online_sources(address="1 Main St", bbox={"west": -97, "south": 32, "east": -96, "north": 33})

        self.assertTrue(result["success"])
        self.assertIn("census_geocoder", result["sources"])
        self.assertIn("Production truth", result["truth_label"])

    def test_fetch_online_existing_conditions_blocks_without_location(self):
        result = fetch_existing_conditions_online()

        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "blocked")
        self.assertIn("existing_conditions_summary", result)


if __name__ == "__main__":
    unittest.main()
