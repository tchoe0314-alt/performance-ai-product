from __future__ import annotations

from backend.application.full_launch_readiness import (
    REQUIRED_CONFIRMATION_ACTIONS,
    REQUIRED_EXTERNAL_GATES,
    REQUIRED_TECHNICAL_EVIDENCE,
    build_full_launch_readiness,
)


REVISION = "abc123"


def _engineering() -> dict:
    return {"success": True, "scenario_count": 10, "real_file_fixture_count": 8, "failed_comparison_count": 0, "automated_expected_actual_comparison_count": 12}


def _sources() -> dict:
    return {
        "source_traceability_verified": True,
        "missing_source_behavior_verified": True,
        "queryable_source_count": 12,
        "market_count": 8,
        "rights_review": {"status": "accepted", "owner": "data counsel", "evidence_date": "2026-09-20", "evidence_url": "https://evidence.example/source-rights"},
    }


def _confirmation() -> dict:
    actions = sorted(REQUIRED_CONFIRMATION_ACTIONS)
    return {"preview_required": True, "explicit_confirmation_required": True, "reversible": True, "history_preserved": True, "tests_passed": True, "covered_actions": actions, "integrated_actions": actions, "browser_verified_actions": actions}


def _reliability() -> dict:
    return {"revision": REVISION, "evidence": {key: {"success": True} for key in REQUIRED_TECHNICAL_EVIDENCE}}


def _hosted() -> dict:
    return {"revision": REVISION, "authenticated_smoke": {"status": "passed", "repeat_count": 2, "passed_runs": 2}}


def _external() -> dict:
    return {gate: {"status": "completed", "owner": f"owner-{gate}", "evidence_date": "2026-09-20", "evidence_url": f"https://evidence.example/{gate}"} for gate in REQUIRED_EXTERNAL_GATES}


def _real_projects() -> list[dict]:
    disciplines = ["grading", "drainage", "storm", "sanitary", "water", "roadway", "earthwork", "quantities"]
    return [
        {
            "project_id": f"real-{index}",
            "project_type": "commercial_site_development",
            "software_revision": REVISION,
            "input_artifact_hashes": [f"hash-{index}"],
            "reviewer": f"engineer-{index}",
            "reviewer_qualification": "licensed civil engineer",
            "review_date": "2026-09-20",
            "disposition": "passed",
            "disciplines": disciplines if index == 0 else ["grading", "drainage"],
            "comparisons": [{"metric": "test", "expected": 1.0, "observed": 1.0, "tolerance": 0.01, "passed": True}],
        }
        for index in range(3)
    ]


def _report(**overrides: object) -> dict:
    values = {
        "revision": REVISION,
        "engineering_validation": _engineering(),
        "source_infrastructure": _sources(),
        "confirmation_evidence": _confirmation(),
        "reliability_manifest": _reliability(),
        "hosted_evidence": _hosted(),
        "external_evidence": _external(),
        "real_project_records": _real_projects(),
    }
    values.update(overrides)
    return build_full_launch_readiness(**values)


def test_complete_evidence_can_clear_full_launch_gate_without_claiming_construction_release() -> None:
    report = _report()
    assert report["technical_program_ready"] is True
    assert report["full_launch_ready"] is True
    assert report["status"] == "full_launch_ready"
    assert report["blockers"] == []
    assert report["construction_ready"] is False
    assert report["construction_release_allowed"] is False
    assert len(report["report_sha256"]) == 64


def test_missing_external_evidence_fails_closed() -> None:
    report = _report(external_evidence={})
    assert report["technical_program_ready"] is True
    assert report["full_launch_ready"] is False
    assert report["domains"]["external_readiness"]["ready"] is False
    assert {item["code"] for item in report["blockers"]} >= {f"{gate}_missing" for gate in REQUIRED_EXTERNAL_GATES}


def test_revision_mismatch_and_incomplete_confirmation_block_technical_program() -> None:
    reliability = _reliability()
    reliability["revision"] = "different"
    confirmation = _confirmation()
    confirmation["covered_actions"] = ["create_review_package"]
    report = _report(reliability_manifest=reliability, confirmation_evidence=confirmation)
    assert report["technical_program_ready"] is False
    assert report["full_launch_ready"] is False
    assert "revision_bound_reliability_incomplete" in {item["code"] for item in report["blockers"]}
    assert "major_change_confirmation_incomplete" in {item["code"] for item in report["blockers"]}


def test_real_project_records_require_three_complete_projects_and_all_disciplines() -> None:
    report = _report(real_project_records=_real_projects()[:2])
    assert report["domains"]["real_project_validation"]["ready"] is False
    assert "real_project_validation_incomplete" in {item["code"] for item in report["blockers"]}


def test_real_project_records_reject_duplicate_ids_and_false_pass_flags() -> None:
    projects = _real_projects()
    projects[1]["project_id"] = projects[0]["project_id"]
    projects[2]["comparisons"][0].update({"expected": 1.0, "observed": 2.0, "tolerance": 0.01, "passed": True})
    report = _report(real_project_records=projects)
    assert report["domains"]["real_project_validation"]["ready"] is False
    assert report["domains"]["real_project_validation"]["unique_complete_project_count"] == 1


def test_report_redacts_secrets_and_rejects_stale_external_evidence() -> None:
    external = _external()
    external["security_assessment"]["api_token"] = "do-not-write-me"
    external["security_assessment"]["evidence_date"] = "2020-01-01"
    report = _report(external_evidence=external)
    assert report["full_launch_ready"] is False
    assert "do-not-write-me" not in str(report)
    security = next(row for row in report["domains"]["external_readiness"]["gates"] if row["gate_id"] == "security_assessment")
    assert security["record"]["api_token"] == "[redacted]"
