from backend.application.chat_workflows import decide_chat
from backend.planning.utility_catalogs import UtilityCatalogManager


def reviewed_source():
    return {
        "source_name": "City utility catalog",
        "source_type": "jurisdiction_pdf",
        "source_reference": "https://example.invalid/catalog.pdf",
        "jurisdiction": "Example City",
        "reviewed_by": "reviewer@example.com",
        "review_date": "2026-06-07",
    }


def test_pipe_catalog_requires_source_and_review_metadata():
    manager = UtilityCatalogManager({"pipes": [], "parts": []})

    result = manager.add_pipe_catalog(
        {
            "item_id": "bad-water",
            "network": "water",
            "material": "DIP",
            "sizes_in": [6, 8],
            "source": {"source_name": "Partial"},
            "review_status": "accepted_for_workspace",
        }
    )

    assert result["success"] is False
    assert any("source.source_reference" in issue for issue in result["issues"])
    assert any("source.reviewed_by" in issue for issue in result["issues"])


def test_network_validation_flags_unlisted_size_and_review_state():
    manager = UtilityCatalogManager({"pipes": [], "parts": []})
    manager.add_pipe_catalog(
        {
            "item_id": "water-dip",
            "network": "water",
            "material": "DIP",
            "sizes_in": [6, 8, 12],
            "source": reviewed_source(),
            "review_status": "needs_review",
        }
    )

    invalid = manager.validate_network(
        {
            "network": "water",
            "features": [{"id": "W-1", "network": "water", "material": "DIP", "diameter_in": 10}],
        }
    )
    assert invalid["success"] is False
    assert invalid["issues"][0]["available_sizes_in"] == [6.0, 8.0, 12.0]

    review_required = manager.validate_network(
        {
            "network": "water",
            "features": [{"id": "W-2", "network": "water", "material": "DIP", "diameter_in": 8}],
        }
    )
    assert review_required["success"] is True
    assert review_required["status"] == "review_required"
    assert review_required["issues"][0]["severity"] == "warning"


def test_chat_answers_pipe_sizes_without_planner_run():
    decision = decide_chat(
        {"message": "what pipe sizes are available?", "context": {}},
        decide_chat_message=lambda payload: {"intent": "generate", "run_mode": "run"},
    )

    assert decision["run_mode"] == "none"
    assert decision["response_metadata"]["action_taken"] == "answered_catalog_pipe_sizes"
    assert "Available pipe sizes" in decision["assistant_message"]


def test_chat_blocks_hydrant_catalog_without_source_review():
    decision = decide_chat(
        {"message": "add hydrant catalog", "context": {}},
        decide_chat_message=lambda payload: {"intent": "generate", "run_mode": "run"},
    )

    assert decision["run_mode"] == "none"
    assert decision["response_metadata"]["action_taken"] == "blocked_catalog_missing_source_review"
    assert decision["response_metadata"]["state_changed"] is False
