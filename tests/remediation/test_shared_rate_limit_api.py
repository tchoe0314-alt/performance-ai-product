"""ASGI-only abuse tests with synthetic target identities and source addresses."""
import importlib

from fastapi.testclient import TestClient

from backend.services.database import Database
from backend.services.rate_limit_store import RateLimitStore,RateLimitUnavailable


class DenyLogin:
    def __init__(self):self.calls=0
    def login(self,**kwargs):
        self.calls+=1
        raise ValueError("Invalid email or password.")


def setup_api(tmp_path,monkeypatch,*,source_limit,target_limit):
    api=importlib.import_module("backend.api.app")
    db=Database(tmp_path/"rate-api.sqlite",database_url="sqlite-local-only")
    auth=DenyLogin()
    monkeypatch.setattr(api,"AUTH_STORE",auth)
    monkeypatch.setattr(api,"RATE_LIMIT_STORE",RateLimitStore(db))
    monkeypatch.setattr(api,"_RATE_LIMIT_DEFAULTS",{"auth":(source_limit,60),"auth_target":(target_limit,60)})
    return api,db,auth


def test_account_target_limit_survives_source_replica_and_header_changes(tmp_path,monkeypatch):
    api,db,auth=setup_api(tmp_path,monkeypatch,source_limit=30,target_limit=2)
    statuses=[]
    for index,email in enumerate(("user@example.test"," USER@example.test ","User@Example.Test")):
        # Different instances sharing the DB, rather than resetting protection.
        monkeypatch.setattr(api,"RATE_LIMIT_STORE",RateLimitStore(Database(db.db_path,database_url="sqlite-local-only")))
        with TestClient(api.app,client=(f"198.51.100.{index+1}",50000)) as client:
            response=client.post("/api/auth/login",json={"email":email,"password":"synthetic-invalid"},headers={"Authorization":f"Bearer arbitrary-{index}","X-Forwarded-For":f"203.0.113.{index}"})
            statuses.append(response.status_code)
    assert statuses == [401,401,429]
    assert "auth_target" in response.json()["detail"]
    assert 1<=int(response.headers["retry-after"])<=60
    assert auth.calls == 2


def test_bearer_and_forwarded_headers_do_not_reset_source_limit(tmp_path,monkeypatch):
    api,_,auth=setup_api(tmp_path,monkeypatch,source_limit=2,target_limit=30)
    with TestClient(api.app,client=("198.51.100.1",50000)) as client:
        responses=[client.post("/api/auth/login",json={"email":f"target-{index}@example.test","password":"synthetic-invalid"},headers={"Authorization":f"Bearer different-{index}","X-Forwarded-For":f"203.0.113.{index}"}) for index in range(3)]
    assert [response.status_code for response in responses] == [401,401,429]
    assert "for auth." in responses[-1].json()["detail"]
    assert auth.calls == 2


def test_unavailable_shared_storage_blocks_request_without_local_fallback(tmp_path,monkeypatch):
    api,_,auth=setup_api(tmp_path,monkeypatch,source_limit=30,target_limit=2)
    class Broken:
        def consume(self,*args,**kwargs):raise RateLimitUnavailable("synthetic outage")
    monkeypatch.setattr(api,"RATE_LIMIT_STORE",Broken())
    with TestClient(api.app) as client:
        response=client.post("/api/auth/login",json={"email":"user@example.test","password":"synthetic-invalid"})
    assert response.status_code == 503
    assert auth.calls == 0
    assert response.headers["retry-after"] == "60"
    assert "synthetic outage" not in response.text
