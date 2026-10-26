"""Q01 source-fixture qualification, real ASGI boundaries and synthetic identity.

Not browser UAT, real email delivery, or engineering source certification.
"""
import hashlib
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from tests.remediation.test_enrollment_recovery_api import setup_api, code


FIXTURES = Path(__file__).resolve().parents[2] / "backend/fixtures/real_input_benchmarks"


@pytest.mark.parametrize("filename", [
    "survey_points.csv", "surface_grid.tif", "surface_points.las", "surface_pipe.landxml",
])
def test_owned_verified_account_imports_real_fixture_without_source_certification(tmp_path, monkeypatch, filename):
    api, db, auth, projects, sender, proofs = setup_api(tmp_path, monkeypatch)
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    monkeypatch.setattr(api, "UPLOAD_DIR", uploads)
    owner = auth.register_user(email="source-owner@example.test", password="Synthetic-only-123", name="Synthetic owner")
    other = auth.register_user(email="other@example.test", password="Synthetic-only-123", name="Other")
    owner_id = owner["user"]["user_id"]
    headers = {"Authorization": "Bearer " + owner["token"]}
    fixture = FIXTURES / filename
    original = fixture.read_bytes()
    with TestClient(api.app) as client:
        # Preserve private enrollment; do not turn public signup on for fixtures.
        denied = client.post("/api/auth/register", json={
            "email": "visitor@example.test", "password": "Synthetic-only-123",
        })
        assert denied.status_code == 403
        assert not proofs.is_verified(owner_id)
        assert client.post("/api/auth/email-verification/request", headers=headers).status_code == 200
        confirmation = code(sender)
        verified = client.post("/api/auth/email-verification/confirm", headers=headers, json={"token": confirmation})
        assert verified.status_code == 200
        assert proofs.is_verified(owner_id)
        assert client.post("/api/auth/email-verification/confirm", headers=headers,
                           json={"token": confirmation}).status_code == 400
        login = client.post("/api/auth/login", json={
            "email": "source-owner@example.test", "password": "Synthetic-only-123",
        })
        assert login.status_code == 200
        headers = {"Authorization": "Bearer " + login.json()["token"]}
        unauthenticated = client.post("/api/upload-existing-conditions", files={"file": (filename, original)})
        assert unauthenticated.status_code == 401
        uploaded = client.post("/api/upload-existing-conditions", headers=headers,
                               files={"file": (filename, original, "application/octet-stream")})
        assert uploaded.status_code == 200, uploaded.text
        payload = uploaded.json()
        assert payload["success"] is True, payload
        assert payload["source_sha256"] == hashlib.sha256(original).hexdigest()
        assert payload["filename"] == filename
        assert (uploads / payload["stored_filename"]).read_bytes() == original
        assert fixture.read_bytes() == original
        assert payload["imports"]
        assert payload["canonical_existing_conditions"]["sources"]
        # Tiny fixture metadata does not supply complete control/evidence.
        assert payload["import_validation"]["production_usable"] is False
        assert payload["blockers"]
        own_read = client.get(payload["file_url"], headers=headers)
        assert own_read.status_code == 200
        assert own_read.content == original
        other_read = client.get(payload["file_url"], headers={"Authorization": "Bearer " + other["token"]})
        assert other_read.status_code == 403
        assert original not in other_read.content
