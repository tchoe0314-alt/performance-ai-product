import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.services.auth_store import AuthStore
from backend.services.database import Database


class AuthStoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmpdir.name) / "auth.db")
        self.store = AuthStore(self.db)
        registered = self.store.register_user(email="user@example.com", password="password123", name="User")
        self.token = registered["token"]

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_authenticate_token_tolerates_locked_last_used_update(self):
        real_connect = self.db.connect

        class LockedUpdateConnection:
            def __init__(self, connection):
                self._connection = connection

            def execute(self, sql, params=()):
                if "UPDATE auth_tokens SET last_used_at" in sql:
                    raise sqlite3.OperationalError("database is locked")
                return self._connection.execute(sql, params)

            def commit(self):
                return self._connection.commit()

            def close(self):
                return self._connection.close()

        with patch.object(self.db, "connect", side_effect=lambda: LockedUpdateConnection(real_connect())):
            user = self.store.authenticate_token(self.token)

        self.assertIsNotNone(user)
        self.assertEqual(user["email"], "user@example.com")

    def test_register_user_maps_postgres_duplicate_email_to_value_error(self):
        class DuplicateEmailConnection:
            def execute(self, _sql, _params=()):
                raise Exception('duplicate key value violates unique constraint "users_email_key"')

            def rollback(self):
                self.rolled_back = True

            def close(self):
                pass

        connection = DuplicateEmailConnection()
        with patch.object(self.db, "connect", return_value=connection):
            with self.assertRaises(ValueError) as ctx:
                self.store.register_user(email="user@example.com", password="password123", name="User")

        self.assertEqual(str(ctx.exception), "That email is already registered.")


if __name__ == "__main__":
    unittest.main()
