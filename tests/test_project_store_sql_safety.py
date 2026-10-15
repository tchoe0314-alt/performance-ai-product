import pytest

from backend.services.project_store import _project_by_id_sql, _project_shell_sql


@pytest.mark.parametrize("storage", ["sqlite", "postgres"])
def test_project_queries_keep_parameters_permissions_and_backend_specific_locks(storage: str) -> None:
    lookup = _project_by_id_sql(storage)
    shell = " ".join(_project_shell_sql(storage).split())
    assert lookup.count("?") == 1
    assert shell.count("?") == 5
    assert "p.deleted_at IS NULL AND (p.user_id = ? OR pm.user_id = ?)" in shell
    assert "LEFT JOIN project_members pm ON pm.project_id = p.project_id AND pm.user_id = ?" in shell
    if storage == "postgres":
        assert lookup.endswith(" FOR UPDATE")
        assert shell.endswith(" FOR UPDATE OF p")
    else:
        assert "FOR UPDATE" not in lookup
        assert "FOR UPDATE" not in shell


def test_storage_selector_cannot_splice_sql_into_project_queries() -> None:
    hostile = "postgres; DROP TABLE projects; --"
    assert _project_by_id_sql(hostile) == _project_by_id_sql("sqlite")
    assert _project_shell_sql(hostile) == _project_shell_sql("sqlite")
