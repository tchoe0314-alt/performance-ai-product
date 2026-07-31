from backend.api.app import _job_handler_is_enabled


def test_job_handler_routing_defaults_to_all_handlers() -> None:
    assert _job_handler_is_enabled("source_context", {}) is True
    assert _job_handler_is_enabled("export_report", {}) is True


def test_api_can_externalize_only_source_context() -> None:
    env = {"CIVORA_DISABLED_JOB_TYPES": "source_context"}
    assert _job_handler_is_enabled("source_context", env) is False
    assert _job_handler_is_enabled("orchestrate", env) is True
    assert _job_handler_is_enabled("plan_pdf_analysis", env) is True
    assert _job_handler_is_enabled("export_report", env) is True


def test_worker_can_allow_only_source_context() -> None:
    env = {"CIVORA_ENABLED_JOB_TYPES": "source_context"}
    assert _job_handler_is_enabled("source_context", env) is True
    assert _job_handler_is_enabled("orchestrate", env) is False
    assert _job_handler_is_enabled("plan_pdf_analysis", env) is False
    assert _job_handler_is_enabled("export_report", env) is False


def test_disabled_job_type_wins_over_allowlist() -> None:
    env = {
        "CIVORA_ENABLED_JOB_TYPES": "source_context,export_report",
        "CIVORA_DISABLED_JOB_TYPES": "source_context",
    }
    assert _job_handler_is_enabled("source_context", env) is False
    assert _job_handler_is_enabled("export_report", env) is True
