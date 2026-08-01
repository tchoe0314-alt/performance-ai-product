import unittest
from unittest import mock

from backend.services.database import Database, _PostgresConnection


class DatabasePoolTests(unittest.TestCase):
    def test_pooled_connection_returns_raw_connection_once(self) -> None:
        raw_connection = mock.Mock()
        pool = mock.Mock()
        connection = _PostgresConnection(raw_connection, pool=pool)

        connection.close()
        connection.close()

        pool.putconn.assert_called_once_with(raw_connection)
        raw_connection.close.assert_not_called()

    def test_pool_uses_configured_bounds_and_waits_until_ready(self) -> None:
        database = Database.__new__(Database)
        database.database_url = "postgresql://example.invalid/civora"
        database._postgres_pool = None
        fake_pool = mock.Mock()

        with mock.patch("psycopg_pool.ConnectionPool", return_value=fake_pool) as pool_class, mock.patch.dict(
            "os.environ",
            {
                "CIVORA_DATABASE_CONNECT_TIMEOUT_SECONDS": "7",
                "CIVORA_DATABASE_POOL_MIN_SIZE": "2",
                "CIVORA_DATABASE_POOL_MAX_SIZE": "6",
            },
            clear=False,
        ):
            database._initialize_postgres_pool()

        pool_class.assert_called_once_with(
            database.database_url,
            kwargs={"autocommit": False, "connect_timeout": 7.0},
            min_size=2,
            max_size=6,
            open=True,
            timeout=10.0,
            name="civora-api",
        )
        fake_pool.wait.assert_called_once_with(timeout=30.0)

    def test_connect_borrows_from_pool_and_close_returns_it(self) -> None:
        database = Database.__new__(Database)
        database.storage_kind = "postgres"
        database.database_url = "postgresql://example.invalid/civora"
        raw_connection = mock.Mock()
        pool = mock.Mock()
        pool.getconn.return_value = raw_connection
        database._postgres_pool = pool

        with mock.patch.dict(
            "os.environ",
            {"CIVORA_DATABASE_CONNECT_TIMEOUT_SECONDS": "4"},
            clear=False,
        ):
            connection = database.connect()
            connection.close()

        pool.getconn.assert_called_once_with(timeout=10.0)
        pool.putconn.assert_called_once_with(raw_connection)


if __name__ == "__main__":
    unittest.main()
