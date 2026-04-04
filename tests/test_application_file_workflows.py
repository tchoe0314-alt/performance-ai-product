import tempfile
import unittest
from io import BytesIO
from pathlib import Path

from fastapi import UploadFile

from backend.application.file_workflows import (
    download_artifact_response,
    get_uploaded_image_response,
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


if __name__ == "__main__":
    unittest.main()
