"""Offline safety checks. These do NOT qualify PostgreSQL storage semantics."""
from unittest.mock import MagicMock, patch
import re
from urllib.parse import parse_qs, urlsplit

import pytest

from c01a_postgres_support import APPROVAL, approved_target, disposable_postgres


def settings(uri="postgresql://tester:synthetic@127.0.0.1:55439/civora_c01a_test_abcdef123456", **overrides):
    return {"CIVORA_C01A_POSTGRES_APPROVAL": APPROVAL, "CIVORA_C01A_POSTGRES_DSN": uri, **overrides}


@pytest.mark.parametrize("uri", [
    "", "sqlite:///local.db", "host=127.0.0.1 dbname=civora_c01a_test_abcdef123456",
    "postgresql://tester@localhost:55439/civora_c01a_test_abcdef123456",
    "postgresql://tester@db.example.invalid:5432/civora_c01a_test_abcdef123456",
    "postgresql://tester@127.0.0.1:55439/production",
    "postgresql://tester@127.0.0.1/civora_c01a_test_abcdef123456",
    "postgresql://tester@127.0.0.1:99999/civora_c01a_test_abcdef123456",
    "postgresql://tester@127.0.0.1:55439/civora_c01a_test_abcdef123456?host=another-host",
    "postgresql://tester@127.0.0.1:55439/civora_c01a_test_abcdef123456?options=-csearch_path=public",
    "postgresql://tester@127.0.0.1:55439/civora_c01a_test_abcdef123456?sslmode=disable&sslmode=require",
    "postgresql://tester@127.0.0.1:55439/civora_c01a_test_abcdef123456#secret",
])
def test_unsafe_target_rejected_before_connection(uri, tmp_path):
    with patch("psycopg.connect") as connect:
        with pytest.raises(ValueError):
            with disposable_postgres(tmp_path, settings(uri)):
                raise AssertionError("Unsafe target reached body")
        connect.assert_not_called()


@pytest.mark.parametrize("override", [
    {"CIVORA_C01A_POSTGRES_APPROVAL": ""},
    {"CIVORA_C01A_POSTGRES_APPROVAL": "yes"},
    {"DATABASE_URL": "postgresql://not-to-be-used.invalid/production"},
])
def test_missing_approval_or_ordinary_database_url_never_connects(override, tmp_path):
    with patch("psycopg.connect") as connect:
        with pytest.raises(ValueError):
            with disposable_postgres(tmp_path, settings(**override)):
                raise AssertionError("Unapproved target reached body")
        connect.assert_not_called()


@pytest.mark.parametrize("key", ["PGHOSTADDR", "PGHOST", "PGPORT", "PGDATABASE", "PGSERVICE", "PGSERVICEFILE", "PGPASSFILE", "PGPASSWORD"])
def test_inherited_driver_routing_or_credentials_never_connect(key, tmp_path):
    with patch("psycopg.connect") as connect:
        with pytest.raises(ValueError, match="inherited PostgreSQL"):
            with disposable_postgres(tmp_path, settings(**{key: "unrelated-settings"})):
                raise AssertionError("Inherited PostgreSQL setting reached body")
        connect.assert_not_called()


def test_valid_local_explicit_target_validation_is_pure():
    approved = settings()
    assert approved_target(approved) == approved["CIVORA_C01A_POSTGRES_DSN"]
    ipv6 = settings("postgresql://tester@[::1]:55439/civora_c01a_test_abcdef123456?sslmode=require")
    assert approved_target(ipv6) == ipv6["CIVORA_C01A_POSTGRES_DSN"]


def test_rejections_do_not_echo_credentials():
    unsafe = settings("postgresql://tester:never-print-this@remote.invalid:5432/production")
    with pytest.raises(ValueError) as error:
        approved_target(unsafe)
    assert "never-print-this" not in str(error.value)


@pytest.mark.parametrize("role_row,nonempty", [
    (("wrong_database", False, False, False), False),
    (("civora_c01a_test_abcdef123456", True, False, False), False),
    (("civora_c01a_test_abcdef123456", False, True, False), False),
    (("civora_c01a_test_abcdef123456", False, False, True), False),
    (("civora_c01a_test_abcdef123456", False, False, False), True),
])
def test_privileged_mismatched_or_nonempty_target_refused_before_ddl(tmp_path, role_row, nonempty):
    control = MagicMock()
    cursor = control.cursor.return_value.__enter__.return_value
    cursor.fetchone.side_effect = [role_row, (nonempty,)]
    with patch("psycopg.connect", return_value=control), patch("backend.services.database.Database") as database:
        with pytest.raises(ValueError):
            with disposable_postgres(tmp_path, settings()):
                raise AssertionError("Unsafe database reached body")
        database.assert_not_called()
    assert all(str(call.args[0]).startswith("SELECT") for call in cursor.execute.call_args_list)
    control.execute.assert_not_called()  # in particular no DROP on rejected target
    control.close.assert_called_once()


def test_owned_schema_only_cleanup_and_pool_reopen_after_body_failure(tmp_path):
    control = MagicMock()
    cursor = control.cursor.return_value.__enter__.return_value
    cursor.fetchone.side_effect = [("civora_c01a_test_abcdef123456", False, False, False), (False,)]
    with patch("psycopg.connect", return_value=control), patch("backend.services.database.Database") as factory:
        with pytest.raises(RuntimeError, match="synthetic body failure"):
            with disposable_postgres(tmp_path, settings()) as database:
                database._c01a_test_reopen()
                raise RuntimeError("synthetic body failure")
    assert factory.call_count == 2
    created = str(cursor.execute.call_args_list[-1].args[0])
    dropped = str(control.execute.call_args.args[0])
    schema = re.search(r"c01a_case_[0-9a-f]{32}", created).group()
    assert schema in dropped and "DROP SCHEMA" in dropped and "CASCADE" in dropped
    assert "public" not in dropped and "DROP DATABASE" not in dropped
    scoped_uri = factory.call_args.kwargs["database_url"]
    assert f"search_path={schema}" in parse_qs(urlsplit(scoped_uri).query)["options"][0]
    assert factory.return_value._postgres_pool.close.call_count == 2
    control.close.assert_called_once()
