"""Explicitly gated local disposable-PostgreSQL verification, never DATABASE_URL.

Importing this module makes no connections. An approval string is an operator
attestation, not proof that a database is safe: an empty target and nonprivileged
role are checked before any DDL. Only the schema created by this invocation may
be dropped. This helper neither installs a server nor creates/drops databases.
"""
from contextlib import contextmanager
import os
import re
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit
import uuid


APPROVAL = "I_APPROVE_DISPOSABLE_C01A_DATABASE"


def approved_target(settings):
    if settings.get("CIVORA_C01A_POSTGRES_APPROVAL") != APPROVAL:
        raise ValueError("Explicit disposable database approval is required.")
    if settings.get("DATABASE_URL"):
        raise ValueError("Unset ordinary DATABASE_URL; this lane never uses it.")
    if any(key.startswith("PG") for key in settings):
        raise ValueError("Unset inherited PostgreSQL routing/credential variables for this lane.")
    value = settings.get("CIVORA_C01A_POSTGRES_DSN", "")
    try:
        target = urlsplit(value)
        port = target.port
        query = parse_qs(target.query, keep_blank_values=True, strict_parsing=True)
        valid = (
            target.scheme in {"postgres", "postgresql"}
            and target.hostname in {"127.0.0.1", "::1"}
            and port is not None and 1 <= port <= 65535
            and bool(target.username)
            and re.fullmatch(r"/civora_c01a_test_[a-f0-9]{12}", target.path)
            and not target.fragment
            and set(query) <= {"sslmode"}
            and all(len(values) == 1 for values in query.values())
            and ("sslmode" not in query or query["sslmode"][0] in {"disable", "require", "verify-full"})
        )
    except (ValueError, TypeError):
        valid = False
    if not valid:
        # Do not include credentials, hostnames or the submitted URL in errors.
        raise ValueError("Expected a literal-loopback, explicit-port disposable C01a database URI.")
    return value


@contextmanager
def disposable_postgres(tmp_path, settings):
    uri = approved_target(settings)  # must run BEFORE driver import/connection
    import psycopg
    from psycopg import sql
    from backend.services.database import Database

    schema = "c01a_case_" + uuid.uuid4().hex
    pools = []
    created = False
    control = psycopg.connect(uri, autocommit=True, connect_timeout=5,
                              application_name="civora-c01a-verification",
                              passfile=os.devnull,
                              options="-c statement_timeout=10000 -c lock_timeout=5000")
    try:
        with control.cursor() as cursor:
            cursor.execute("SELECT current_database(), rolsuper, rolcreatedb, rolcreaterole FROM pg_roles WHERE rolname = current_user")
            row = cursor.fetchone()
            if not row or row[0] != urlsplit(uri).path[1:] or any(row[1:]):
                raise ValueError("A matching disposable database and nonprivileged test role are required.")
            cursor.execute("SELECT EXISTS(SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                           "WHERE n.nspname NOT LIKE 'pg_%' AND n.nspname <> 'information_schema' "
                           "AND c.relkind IN ('r','p','f','v','m','S'))")
            if cursor.fetchone()[0]:
                raise ValueError("Disposable target must contain no user relations before this case.")
            cursor.execute(sql.SQL("CREATE SCHEMA {} AUTHORIZATION CURRENT_USER").format(sql.Identifier(schema)))
            created = True
        parsed = urlsplit(uri)
        options = parse_qs(parsed.query)
        options.update({"options": [f"-c search_path={schema} -c statement_timeout=10000 -c lock_timeout=5000"],
                        "passfile": [os.devnull],
                        "application_name": ["civora-c01a-verification"]})
        scoped_uri = urlunsplit(parsed._replace(query=urlencode(options, doseq=True)))

        def reopen():
            database = Database(tmp_path / "unused-postgres.db", database_url=scoped_uri)
            pools.append(database)
            database._c01a_test_reopen = reopen
            return database
        yield reopen()
    finally:
        # End every owned pool before removing only the exact schema allocated
        # above. No DROP DATABASE, public-schema cleanup or fallback names.
        try:
            for database in reversed(pools):
                database._postgres_pool.close()
            if created:
                control.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
        finally:
            control.close()
