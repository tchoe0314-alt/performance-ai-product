"""Private enrollment and recovery with fake mail and synthetic identities."""
import importlib

from fastapi.testclient import TestClient

from backend.services.auth_store import AuthStore
from backend.services.database import Database
from backend.services.email_delivery import FakeEmailSender
from backend.services.identity_proofs import IdentityProofStore
from backend.services.project_store import ProjectStore
from backend.services.rate_limit_store import RateLimitStore


def setup_api(tmp_path,monkeypatch):
    api=importlib.import_module("backend.api.app")
    db=Database(tmp_path/"enrollment.sqlite",database_url="sqlite-local-only")
    auth=AuthStore(db); projects=ProjectStore(db); sender=FakeEmailSender(); proofs=IdentityProofStore(db,sender=sender)
    for name,value in (("DB",db),("AUTH_STORE",auth),("PROJECT_STORE",projects),("IDENTITY_PROOFS",proofs),("RATE_LIMIT_STORE",RateLimitStore(db)),("PRODUCT_MODE","private_alpha")):
        monkeypatch.setattr(api,name,value)
    monkeypatch.setenv("CIVORA_ALLOW_PUBLIC_REGISTRATION","")
    return api,db,auth,projects,sender,proofs


def code(sender):return sender.messages[-1].text.splitlines()[0].split(": ",1)[1]


def test_empty_private_service_does_not_allow_first_visitor_bootstrap(tmp_path,monkeypatch):
    api,_,_,_,_,_=setup_api(tmp_path,monkeypatch)
    with TestClient(api.app) as client:
        assert client.get("/api/auth/status").json()["public_registration_enabled"] is False
        response=client.post("/api/auth/register",json={"email":"unknown@example.test","password":"Synthetic-only-123"})
        assert response.status_code == 403


def test_invitation_enrollment_validates_email_and_consumes_proof(tmp_path,monkeypatch):
    api,db,auth,projects,sender,proofs=setup_api(tmp_path,monkeypatch)
    owner=auth.register_user(email="owner@example.test",password="Synthetic-only-123",name="Owner")["user"]["user_id"]
    project=projects.save_project(user_id=owner,project_id=None,name="Synthetic")
    invite=projects.invite_project_member(actor_user_id=owner,project_id=project["project_id"],email="new@example.test")
    proofs.send_invitation(actor_user_id=owner,invite_id=invite["invite_id"]); invitation=code(sender)
    with TestClient(api.app) as client:
        wrong=client.post("/api/auth/register",json={"email":"wrong@example.test","password":"Synthetic-only-123","invitation_token":invitation})
        assert wrong.status_code == 400
        response=client.post("/api/auth/register",json={"email":"new@example.test","password":"Synthetic-only-123","invitation_token":invitation})
        assert response.status_code == 200,response.text
        user=response.json()["user"]["user_id"]
        assert proofs.is_verified(user)
        assert projects.project_role(user_id=user,project_id=project["project_id"]) == "viewer"
        assert auth.authenticate_token(response.json()["token"])["user_id"] == user
        assert client.post("/api/auth/register",json={"email":"new@example.test","password":"Synthetic-only-123","invitation_token":invitation}).status_code == 400


def test_mailbox_owner_can_recover_pre_registered_account_without_old_password(tmp_path,monkeypatch):
    api,_,auth,projects,sender,proofs=setup_api(tmp_path,monkeypatch)
    owner=auth.register_user(email="owner@example.test",password="Synthetic-only-123",name="Owner")["user"]["user_id"]
    attacker=auth.register_user(email="recipient@example.test",password="Pre-registration-password",name="Unverified")
    project=projects.save_project(user_id=owner,project_id=None,name="Synthetic")
    invite=projects.invite_project_member(actor_user_id=owner,project_id=project["project_id"],email="recipient@example.test")
    proofs.send_invitation(actor_user_id=owner,invite_id=invite["invite_id"]); invitation=code(sender)
    before=projects.get_project(user_id=owner,project_id=project["project_id"])
    with TestClient(api.app) as client:
        assert client.post("/api/auth/password-reset/request",json={"email":"recipient@example.test"}).status_code == 200
        reset=code(sender)
        invalid=client.post("/api/auth/password-reset/confirm",json={"email":"recipient@example.test","token":invitation,"new_password":"New-synthetic-password"})
        assert invalid.status_code == 400
        assert auth.authenticate_token(attacker["token"]) is not None
        changed=client.post("/api/auth/password-reset/confirm",json={"email":"recipient@example.test","token":reset,"new_password":"New-synthetic-password"})
        assert changed.status_code == 200
        assert auth.authenticate_token(attacker["token"]) is None
        assert client.post("/api/auth/login",json={"email":"recipient@example.test","password":"Pre-registration-password"}).status_code == 401
        signed_in=client.post("/api/auth/login",json={"email":"recipient@example.test","password":"New-synthetic-password"})
        assert signed_in.status_code == 200
        headers={"Authorization":"Bearer "+signed_in.json()["token"]}
        assert client.post("/api/invitations/accept",headers=headers,json={"token":invitation}).status_code == 200
        assert client.post("/api/auth/password-reset/confirm",json={"email":"recipient@example.test","token":reset,"new_password":"Another-synthetic-password"}).status_code == 400
    assert projects.get_project(user_id=owner,project_id=project["project_id"])["project_input"] == before["project_input"]


def test_reset_request_has_same_public_response_for_known_and_unknown_accounts(tmp_path,monkeypatch):
    api,db,auth,_,sender,_=setup_api(tmp_path,monkeypatch)
    auth.register_user(email="known@example.test",password="Synthetic-only-123",name="Known")
    with TestClient(api.app) as client:
        known=client.post("/api/auth/password-reset/request",json={"email":"known@example.test"})
        unknown=client.post("/api/auth/password-reset/request",json={"email":"unknown@example.test"})
        assert known.status_code == unknown.status_code == 200
        assert known.json() == unknown.json()
        assert len(sender.messages)==1
        monkeypatch.setattr(api,"IDENTITY_PROOFS",IdentityProofStore(db))
        assert client.post("/api/auth/password-reset/request",json={"email":"known@example.test"}).status_code == 503
        assert client.post("/api/auth/password-reset/request",json={"email":"unknown@example.test"}).status_code == 503
