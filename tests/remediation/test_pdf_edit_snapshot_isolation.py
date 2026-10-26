"""C02: detached PDF edits and real CAS, never bypass revision protection."""
from copy import deepcopy
import hashlib
import importlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.application.project_snapshot import save_project_snapshot
from backend.planning.plan_pdf_understanding import (
    SOURCE_CONFIDENCE, analyze_plan_pdf, merge_plan_pdf_analysis_into_meta,
    update_editable_sheet_element,
)
from backend.services.auth_store import AuthStore
from backend.services.database import Database
from backend.services.canonical_project import COLLECTION_SECTIONS, MAPPING_SECTIONS
from backend.services.project_revision import result_revision
from backend.services.project_store import ProjectStore


def synthetic_meta():
    element = {"element_id": "synthetic-label", "type": "title_block_field", "editable": True,
               "text": "OWNER: ORIGINAL", "original_text": "OWNER: ORIGINAL", "review_status": "pending",
               "bbox": {"x0": 10, "y0": 20, "x1": 60, "y1": 40},
               "original_bbox": {"x0": 10, "y0": 20, "x1": 60, "y1": 40}}
    sheet = {"elements": [element], "change_log": [], "summary": {"fixture": "preserve"}}
    # The two views intentionally alias, as real PDF analysis metadata can.
    return {"plan_pdf_editable_sheet_v1": sheet,
            "plan_pdf_analysis_v1": {"editable_sheet": sheet, "source_hash": "synthetic-original-hash"},
            "unrelated": {"nested": [1, 2, 3]}}


UPDATES = [
    {"text": "OWNER: CHANGED"}, {"review_status": "accepted"}, {"review_status": "rejected"},
    {"move_target": {"x0": 120, "y0": 640}},
    {"bbox": {"x0": 5, "y0": 10, "x1": 45, "y1": 35}},
]


@pytest.mark.parametrize("updates", UPDATES)
def test_successful_edits_preserve_original_tree_and_input(updates):
    original = synthetic_meta()
    before, requested = deepcopy(original), deepcopy(updates)
    edited = update_editable_sheet_element(original, "synthetic-label", updates)
    assert original == before, "The source snapshot must remain valid for revision preconditions."
    assert updates == requested
    assert edited is not original
    assert edited["plan_pdf_editable_sheet_v1"] is not original["plan_pdf_editable_sheet_v1"]
    assert edited["plan_pdf_changed_elements_v1"]["changed_count"] == 1
    assert edited["plan_pdf_analysis_v1"]["source_hash"] == "synthetic-original-hash"
    edited["unrelated"]["nested"].append(4)
    assert original == before


@pytest.mark.parametrize("updates", [
    {"text": "MUST NOT LEAK", "review_status": "not-valid"},
    {"text": "MUST NOT LEAK", "move_target": {}},
])
def test_rejected_partial_edit_cannot_mutate_source(updates):
    original = synthetic_meta()
    before = deepcopy(original)
    with pytest.raises(ValueError):
        update_editable_sheet_element(original, "synthetic-label", updates)
    assert original == before


def test_protected_mark_and_history_remain_unchanged():
    original = synthetic_meta()
    original["plan_pdf_editable_sheet_v1"]["elements"][0]["type"] = "stamp_or_seal_source_imagery"
    before = deepcopy(original)
    with pytest.raises(ValueError, match="Protected professional mark"):
        update_editable_sheet_element(original, "synthetic-label", {"text": "forbidden"})
    assert original == before


class ObservedStore(ProjectStore):
    tracking = False
    loaded = None
    original = None
    before_save = None

    def get_project(self, **kwargs):
        record = super().get_project(**kwargs)
        if self.tracking:
            self.loaded, self.original = record, deepcopy(record)
        return record

    def save_project(self, **kwargs):
        if self.tracking:
            assert self.loaded == self.original, "Workflow mutated its original read before CAS."
            assert kwargs["expected_result_revision"] == result_revision(self.original)
            if self.before_save:
                callback, self.before_save = self.before_save, None
                callback()
        return super().save_project(**kwargs)


@pytest.fixture
def http_case(tmp_path, monkeypatch):
    # The external runner supplies an owned fresh API storage directory before
    # this import. No services/providers or production database are contacted.
    api = importlib.import_module("backend.api.app")
    db = Database(tmp_path / "pdf-edits.sqlite3", database_url="")
    auth, store = AuthStore(db), ObservedStore(db)
    account = auth.register_user(email="pdf-owner@synthetic.invalid", password="synthetic-pdf-test-password", name="PDF owner")
    user_id = account["user"]["user_id"]
    fixture = Path(__file__).resolve().parents[2] / "backend/fixtures/plan_pdfs/pool-geometric.pdf"
    analysis = analyze_plan_pdf(fixture, original_filename=fixture.name, stored_filename="synthetic-owned-source.pdf")
    meta = merge_plan_pdf_analysis_into_meta({}, analysis)
    record = store.save_project(user_id=user_id, project_id=None, name="Synthetic PDF edit",
        project_input={"address": "Synthetic offline test", "manual_fields": {"units": "ft", "site_objects": [
            {"id": "preserved-road", "type": "road", "x": 10, "y": 20, "w": 30, "d": 40}]}},
        latest_result={"success": True, "final_plan": {"actions": [], "meta": meta}})
    # Compare persistent reads with persistent reads, not the creation response
    # which legitimately omits lifecycle summary columns returned by get_project.
    record = store.get_project(user_id=user_id, project_id=record["project_id"])
    element = next(item for item in record["latest_result"]["final_plan"]["meta"]["plan_pdf_editable_sheet_v1"]["elements"]
                   if item.get("editable") and item.get("text") and item.get("bbox") and item["type"] != "stamp_or_seal_source_imagery")
    monkeypatch.setattr(api, "AUTH_STORE", auth)
    monkeypatch.setattr(api, "PROJECT_STORE", store)
    client = TestClient(api.app)
    yield client, store, db, account, record, element
    client.close()


def patch(client, account, record, element, updates):
    return client.patch(f"/api/projects/{record['project_id']}/plan-pdf/elements/{element['element_id']}",
                        json=updates, headers={"Authorization": f"Bearer {account['token']}"})


@pytest.mark.parametrize("updates", UPDATES)
def test_actual_authenticated_patch_saves_and_reopens_without_mutating_original(http_case, updates):
    client, store, _, account, record, original_element = http_case
    store.tracking = True
    response = patch(client, account, record, original_element, updates)
    store.tracking = False
    assert response.status_code == 200, response.text
    assert store.loaded == store.original
    reopened = store.get_project(user_id=account["user"]["user_id"], project_id=record["project_id"])
    meta = reopened["latest_result"]["final_plan"]["meta"]
    sheet = meta["plan_pdf_editable_sheet_v1"]
    edited = next(item for item in sheet["elements"] if item["element_id"] == original_element["element_id"])
    if "move_target" in updates:
        expected = updates["move_target"]
        assert edited["bbox"]["x0"] == expected["x0"] and edited["bbox"]["y0"] == expected["y0"]
        assert round(edited["bbox"]["x1"] - edited["bbox"]["x0"], 3) == round(original_element["bbox"]["x1"] - original_element["bbox"]["x0"], 3)
    else:
        for field, value in updates.items():
            assert edited[field] == value
    assert edited["source_confidence"] == SOURCE_CONFIDENCE
    assert edited["review_required"] is True and edited["construction_release_allowed"] is False
    assert sheet["change_log"][-1]["before"]["text"] == original_element["text"]
    assert sheet["change_log"][-1]["after"]["text"] == edited["text"]
    assert meta["plan_pdf_changed_elements_v1"]["changed_count"] == 1
    assert response.json()["plan_pdf_editable_sheet_v1"] == sheet
    # The canonical aggregate intentionally refreshes result/revision projections
    # after a saved PDF edit. User inputs and design geometry must not change.
    previous, current = record["project_input"], reopened["project_input"]
    assert {k: v for k, v in current.items() if k != "canonical_project_v1"} == {k: v for k, v in previous.items() if k != "canonical_project_v1"}
    before_doc, after_doc = previous["canonical_project_v1"], current["canonical_project_v1"]
    derived = {"calculation_results", "quantities", "revisions", "export_history", "extensions"}
    for section in set(COLLECTION_SECTIONS) | set(MAPPING_SECTIONS):
        if section in derived:
            continue
        before, after = before_doc[section], after_doc[section]
        if section in {"sources", "assumptions", "alternatives"}:
            before = [item for item in before if item.get("owner") != "project_record_v1"]
            after = [item for item in after if item.get("owner") != "project_record_v1"]
        assert after == before, section


@pytest.mark.parametrize("scope", ["design", "result", "metadata"])
def test_actual_intervening_writer_still_returns_conflict_and_keeps_winner(http_case, scope):
    client, store, db, account, record, element = http_case
    winner = {}
    def competing_writer():
        other = ProjectStore(db)
        current = other.get_project(user_id=account["user"]["user_id"], project_id=record["project_id"])
        fields = {key: deepcopy(current[key]) for key in ("name", "description", "session_id", "tags", "project_input", "latest_result", "session_state", "metadata")}
        if scope == "design":
            fields["name"] = "Concurrent design winner"
        elif scope == "result":
            fields["latest_result"]["final_plan"]["meta"]["concurrent_result"] = "winner"
        else:
            fields["metadata"]["concurrent_metadata"] = "winner"
        save_project_snapshot(other, current, user_id=account["user"]["user_id"], project_id=record["project_id"], **fields)
        winner.update(other.get_project(user_id=account["user"]["user_id"], project_id=record["project_id"]))
    store.before_save = competing_writer
    store.tracking = True
    response = patch(client, account, record, element, {"text": "STALE EDIT MUST NOT SAVE"})
    store.tracking = False
    assert response.status_code == 409, response.text
    assert winner, "A real competing store must have committed before the stale save."
    assert store.get_project(user_id=account["user"]["user_id"], project_id=record["project_id"]) == winner


def test_invalid_patch_leaves_database_unchanged(http_case):
    client, store, _, account, record, element = http_case
    response = patch(client, account, record, element, {"text": "not persisted", "review_status": "invalid"})
    assert response.status_code == 400
    assert store.get_project(user_id=account["user"]["user_id"], project_id=record["project_id"]) == record


def test_plain_real_store_patch_and_source_bytes_preserved(http_case, monkeypatch):
    client, _, db, account, record, element = http_case
    api = importlib.import_module("backend.api.app")
    plain = ProjectStore(db)
    monkeypatch.setattr(api, "PROJECT_STORE", plain)
    source = Path(__file__).resolve().parents[2] / "backend/fixtures/plan_pdfs/pool-geometric.pdf"
    before_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    response = patch(client, account, record, element, {"text": "PLAIN STORE VERIFIED SAVE"})
    assert response.status_code == 200, response.text
    reopened = plain.get_project(user_id=account["user"]["user_id"], project_id=record["project_id"])
    elements = reopened["latest_result"]["final_plan"]["meta"]["plan_pdf_editable_sheet_v1"]["elements"]
    assert next(item for item in elements if item["element_id"] == element["element_id"])["text"] == "PLAIN STORE VERIFIED SAVE"
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before_hash
