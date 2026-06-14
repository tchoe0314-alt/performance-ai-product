from backend.application.chat_workflows import decide_chat
from backend.planning.customer_templates import CustomerTemplateManager, template_behavior


def accepted_template_payload():
    return {
        "template_id": "acme_site_template",
        "name": "ACME site CAD template",
        "firm_name": "ACME Civil",
        "version": "2026.06",
        "review_status": "accepted_for_workspace",
        "accepted_by": "standards-admin",
        "accepted_date": "2026-06-07",
        "source_reference": "internal://company/templates/acme-site-template.json",
        "sections": {
            "layer_standards": {"layers": [{"name": "C-ROAD"}, {"name": "C-PIPE-STORM"}]},
            "title_block": {"sheet_size": "24x36", "fields": ["project_name", "revision"]},
            "label_style": {"styles": [{"key": "pipe", "format": "{diameter_in} in {material}"}]},
            "annotation_standards": {
                "dimension_styles": [
                    {"key": "linear", "kind": "linear", "precision": 2, "units": "ft", "suffix": "'"},
                    {"key": "aligned", "kind": "aligned", "precision": 2, "units": "ft", "suffix": "'"},
                    {"key": "angular", "kind": "angular", "precision": 1, "units": "deg", "suffix": " deg"},
                ],
                "text_styles": [{"key": "company_label", "family": "Inter", "size": 0.12, "alignment": "middle_center"}],
                "leader_callout_styles": [{"key": "object_callout", "connected_to_objects": True}],
                "hatch_fill_styles": [{"target": "pavement", "pattern": "ANSI31"}],
                "linetype_styles": [{"target": "utility", "linetype": "DASHED"}],
            },
            "symbol_library": {"blocks": [{"block_id": "inlet", "name": "Storm inlet"}]},
            "report_template": {"reports": [{"key": "review_summary", "sections": ["inputs", "open_items"]}]},
            "cost_book_link": {"links": [{"label": "ACME book", "cost_book_id": "acme_costs"}]},
            "pipe_template_hook": {"defaults": {"storm": {"layer": "C-PIPE-STORM"}}},
            "roadway_template_hook": {"defaults": {"roadway_layer": "C-ROAD"}},
        },
    }


def test_template_registry_import_activate_and_export_json():
    manager = CustomerTemplateManager({"templates": [], "active_template_id": ""})

    result = manager.import_template(accepted_template_payload())

    assert result["success"] is True
    assert result["template"]["accepted_for_workspace"] is True
    registry = manager.activate("acme_site_template")["registry"]
    assert registry["active_template_id"] == "acme_site_template"
    assert registry["behavior"]["status"] == "active_reviewed"
    assert registry["behavior"]["blockers"] == []
    assert registry["summaries"][0]["dimension_style_count"] == 3
    assert registry["summaries"][0]["hatch_style_count"] == 5
    exported = manager.export_json()
    assert exported["version"] == "customer_template_export_v1"
    assert exported["registry"]["active_template"]["template_id"] == "acme_site_template"


def test_template_behavior_lists_missing_sections_without_compliance_claim():
    manager = CustomerTemplateManager({"templates": [], "active_template_id": ""})
    partial = accepted_template_payload()
    partial["template_id"] = "partial_template"
    partial["sections"] = {"layer_standards": {"layers": [{"name": "C-ANNO"}]}}
    result = manager.import_template(partial)

    behavior = template_behavior(result["template"])

    assert "missing_title_block" in behavior["blockers"]
    assert behavior["policy"]["customer_standard_only"] is True
    assert behavior["policy"]["jurisdiction_compliance_claim"] is False
    assert "legal compliance" in behavior["policy"]["truth_label"]


def test_template_import_rejects_release_and_stamp_language():
    manager = CustomerTemplateManager({"templates": [], "active_template_id": ""})
    payload = accepted_template_payload()
    payload["template_id"] = "bad_template"
    payload["notes"] = ["Use for construction-ready stamped approval package."]

    result = manager.import_template(payload)

    assert result["success"] is False
    assert any("construction-ready" in issue for issue in result["issues"])


def test_chat_uses_active_company_template_without_planner_run():
    decision = decide_chat(
        {"message": "use my company template", "context": {}},
        decide_chat_message=lambda payload: {"intent": "generate", "run_mode": "run"},
    )

    assert decision["run_mode"] == "none"
    assert decision["response_metadata"]["action_taken"] == "activated_customer_template"
    assert decision["response_metadata"]["ui_navigation_target"] == "templates"
    assert "legal compliance" in decision["response_metadata"]["template_policy"]


def test_chat_answers_active_and_missing_template_questions():
    active = decide_chat(
        {"message": "what template is active?", "context": {}},
        decide_chat_message=lambda payload: {"intent": "generate", "run_mode": "run"},
    )
    missing = decide_chat(
        {"message": "why is template missing?", "context": {}},
        decide_chat_message=lambda payload: {"intent": "generate", "run_mode": "run"},
    )

    assert active["run_mode"] == "none"
    assert active["response_metadata"]["action_taken"] == "answered_active_template"
    assert missing["run_mode"] == "none"
    assert missing["response_metadata"]["action_taken"] == "answered_customer_template_missing_reason"


def test_chat_answers_annotation_standard_requests_without_release_claims():
    phrases = [
        "add dimensions",
        "make labels bigger",
        "use my company label style",
        "show proposed utilities dashed",
        "add hatch to parking",
    ]

    for phrase in phrases:
        decision = decide_chat(
            {"message": phrase, "context": {}},
            decide_chat_message=lambda payload: {"intent": "generate", "run_mode": "run"},
        )

        assert decision["run_mode"] == "none"
        assert decision["response_metadata"]["action_taken"].startswith("answered_annotation_")
        trace = decision["response_metadata"]["command_payload"]["annotation_standard_request_v1"]["trace"]
        assert trace["engineer_review_required"] is True
        assert trace["construction_release_allowed"] is False
        assert "linear" in trace["supported_annotation_styles"]["dimension_kinds"]
        assert "pavement" in trace["supported_annotation_styles"]["hatch_targets"]
        assert "utility" in trace["supported_annotation_styles"]["linetype_targets"]
        assert "construction-ready" not in decision["assistant_message"].lower()
