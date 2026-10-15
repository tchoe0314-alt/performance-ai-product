"""Actual ASGI routes with fake delivery and a disposable identity database."""
import importlib

from fastapi.testclient import TestClient

from backend.services.auth_store import AuthStore
from backend.services.database import Database
from backend.services.email_delivery import FakeEmailSender
from backend.services.identity_proofs import IdentityProofStore
from backend.services.project_store import ProjectStore


def test_fake_delivered_proof_required_for_existing_account_invitation(tmp_path, monkeypatch):
    api=importlib.import_module("backend.api.app")
    db=Database(tmp_path/"identity-api.sqlite",database_url="sqlite-local-only")
    auth=AuthStore(db); store=ProjectStore(db); sender=FakeEmailSender(); proofs=IdentityProofStore(db,sender=sender)
    owner=auth.register_user(email="owner@example.test",password="Synthetic-only-123",name="Owner")
    recipient=auth.register_user(email="recipient@example.test",password="Synthetic-only-123",name="Recipient")
    project=store.save_project(user_id=owner["user"]["user_id"],project_id=None,name="Synthetic")
    monkeypatch.setattr(api,"AUTH_STORE",auth); monkeypatch.setattr(api,"PROJECT_STORE",store)
    monkeypatch.setattr(api,"IDENTITY_PROOFS",proofs); monkeypatch.setattr(api,"_RATE_LIMIT_EVENTS",{})
    owner_headers={"Authorization":"Bearer "+owner["token"]}
    recipient_headers={"Authorization":"Bearer "+recipient["token"]}
    with TestClient(api.app) as client:
        response=client.post(f"/api/projects/{project['project_id']}/admin/invites",headers=owner_headers,json={"email":"recipient@example.test"})
        assert response.status_code == 200
        assert response.json()["invite"]["status"] == "pending"
        assert store.project_role(user_id=recipient["user"]["user_id"],project_id=project["project_id"]) is None
        code=sender.messages[-1].text.splitlines()[0].split(": ",1)[1]
        assert code not in response.text
        assert client.post("/api/invitations/accept",json={"token":code}).status_code == 401
        assert client.post("/api/invitations/accept",headers=recipient_headers,json={"token":code}).status_code == 200
        assert store.project_role(user_id=recipient["user"]["user_id"],project_id=project["project_id"]) == "viewer"
        assert client.post("/api/invitations/accept",headers=recipient_headers,json={"token":code}).status_code == 400
        assert proofs.is_verified(recipient["user"]["user_id"])
        pending=client.post(f"/api/projects/{project['project_id']}/admin/invites",headers=owner_headers,json={"email":"recipient@example.test","role":"editor"}).json()["invite"]
        base=f"/api/projects/{project['project_id']}/admin/invites/{pending['invite_id']}"
        assert client.post(base+"/resend",headers=recipient_headers).status_code == 403
        assert client.post(base+"/resend",headers=owner_headers).status_code == 200
        revoked_code=sender.messages[-1].text.splitlines()[0].split(": ",1)[1]
        assert client.delete(base,headers=owner_headers).status_code == 200
        assert client.post("/api/invitations/accept",headers=recipient_headers,json={"token":revoked_code}).status_code == 400
        assert store.project_role(user_id=recipient["user"]["user_id"],project_id=project["project_id"]) == "viewer"
        assert client.post("/api/auth/email-verification/request",headers=owner_headers).status_code == 200
        code=sender.messages[-1].text.splitlines()[0].split(": ",1)[1]
        assert client.post("/api/auth/email-verification/confirm",headers=owner_headers,json={"token":code}).status_code == 200
        assert proofs.is_verified(owner["user"]["user_id"])
