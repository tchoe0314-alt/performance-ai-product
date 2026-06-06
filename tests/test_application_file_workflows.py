import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException, UploadFile

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

    def test_upload_image_file_rejects_oversized_file_and_removes_partial(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            upload = UploadFile(filename="site.png", file=BytesIO(b"abc"))
            with patch.dict("os.environ", {"CIVORA_MAX_IMAGE_UPLOAD_BYTES": "2"}):
                with self.assertRaises(HTTPException) as ctx:
                    upload_image_file(
                        upload_dir=Path(tmpdir),
                        file=upload,
                        current_user={"user_id": "u1"},
                    )

            self.assertEqual(ctx.exception.status_code, 413)
            self.assertFalse((Path(tmpdir) / "u1_site.png").exists())

    def test_upload_image_file_rejects_unsupported_extension(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            upload = UploadFile(filename="site.exe", file=BytesIO(b"abc"))
            with self.assertRaises(HTTPException) as ctx:
                upload_image_file(
                    upload_dir=Path(tmpdir),
                    file=upload,
                    current_user={"user_id": "u1"},
                )

            self.assertEqual(ctx.exception.status_code, 415)
            self.assertFalse((Path(tmpdir) / "u1_site.exe").exists())

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
            self.assertIn("existing_conditions_package", result)
            self.assertEqual(result["existing_conditions_package"]["status"], "blocked")
            self.assertIn("import_validation", result["existing_conditions_package"])

    def test_upload_existing_conditions_rejects_unsupported_extension_before_storage(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            upload = UploadFile(filename="notes.txt", file=BytesIO(b"not source data"))
            with self.assertRaises(HTTPException) as ctx:
                upload_existing_conditions_file(
                    upload_dir=Path(tmpdir),
                    file=upload,
                    current_user={"user_id": "u1"},
                )

            self.assertEqual(ctx.exception.status_code, 415)
            self.assertFalse((Path(tmpdir) / "u1_notes.txt").exists())

    def test_upload_existing_conditions_reports_dependency_blocked_file_as_failed_source(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            upload = UploadFile(filename="constraints.shp", file=BytesIO(b"not a shapefile"))
            with patch(
                "backend.application.file_workflows.classify_existing_conditions_file",
                return_value={
                    "supported": False,
                    "format": "shp",
                    "mode": "geospatial_vector",
                    "required_dependency": "Shapefile import requires fiona/geopandas or GDAL.",
                },
            ):
                result = upload_existing_conditions_file(
                    upload_dir=Path(tmpdir),
                    file=upload,
                    current_user={"user_id": "u1"},
                )

            self.assertFalse(result["success"])
            self.assertTrue(result["imports"][0]["dependency_blocked"])
            self.assertEqual(result["imports"][0]["required_dependency"], "Shapefile import requires fiona/geopandas or GDAL.")
            source = result["existing_conditions_package"]["canonical_existing_conditions"]["sources"][0]
            self.assertTrue(source["dependency_blocked"])
            self.assertIn("sources", {item["field"] for item in result["existing_conditions_package"]["blockers"]})

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
        self.assertIn("existing_conditions_package", result)
        self.assertEqual(result["existing_conditions_package"]["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
