"""Synthetic session records only. Never opens an existing database."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from backend.services.auth_store import AuthStore
from backend.services.database import Database


class SessionSecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="civora-session-test-")
        self.db = Database(Path(self.temp.name)/"synthetic.sqlite",database_url="sqlite-local-only")
        self.auth = AuthStore(self.db,session_ttl_seconds=100,session_idle_seconds=30)
        self.clock = patch("backend.services.auth_store._now",return_value=1000)
        self.now = self.clock.start()
        account = self.auth.register_user(email="test@example.test",password="Synthetic-password-123",name="Test")
        self.token = account["token"]; self.user = account["user"]["user_id"]

    def tearDown(self):
        self.clock.stop(); self.temp.cleanup()

    def test_only_hashes_stored_and_legacy_raw_tokens_rejected(self):
        connection=self.db.connect()
        try:
            stored=connection.execute("SELECT token FROM auth_tokens").fetchone()["token"]
            self.assertTrue(stored.startswith("sha256:")); self.assertNotEqual(stored,self.token)
            connection.execute("INSERT INTO auth_tokens VALUES (?, ?, ?, ?)",("legacy-raw",self.user,1000,1000)); connection.commit()
        finally: connection.close()
        self.assertIsNone(self.auth.authenticate_token("legacy-raw"))
        self.assertIsNotNone(self.auth.authenticate_token(self.token))

    def test_exact_idle_expiry_and_absolute_expiry(self):
        self.now.return_value=1030
        self.assertIsNone(self.auth.authenticate_token(self.token))
        self.now.return_value=1000
        for timestamp in (1029,1058,1087,1099):
            self.now.return_value=timestamp
            self.assertIsNotNone(self.auth.authenticate_token(self.token))
        self.now.return_value=1100
        self.assertIsNone(self.auth.authenticate_token(self.token))

    def test_future_session_cannot_authenticate(self):
        self.now.return_value=999
        self.assertIsNone(self.auth.authenticate_token(self.token))

    def test_rotation_has_one_winner_and_does_not_extend_absolute_expiry(self):
        self.now.return_value=1020
        def rotate(_):
            try: return self.auth.rotate_session(self.token)
            except ValueError: return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            winners=[token for token in pool.map(rotate,range(2)) if token]
        self.assertEqual(len(winners),1)
        self.assertIsNone(self.auth.authenticate_token(self.token))
        self.assertIsNotNone(self.auth.authenticate_token(winners[0]))
        for timestamp in (1049,1078,1099):
            self.now.return_value=timestamp; self.assertIsNotNone(self.auth.authenticate_token(winners[0]))
        self.now.return_value=1100
        self.assertIsNone(self.auth.authenticate_token(winners[0]))

    def test_revoke_all_needs_password_and_does_not_revoke_other_user(self):
        second=self.auth.login(email="test@example.test",password="Synthetic-password-123")["token"]
        other=self.auth.register_user(email="other@example.test",password="Synthetic-password-456",name="Other")["token"]
        with self.assertRaises(ValueError): self.auth.revoke_all_sessions(user_id=self.user,password="wrong")
        self.assertIsNotNone(self.auth.authenticate_token(self.token))
        self.auth.revoke_all_sessions(user_id=self.user,password="Synthetic-password-123")
        self.assertIsNone(self.auth.authenticate_token(self.token)); self.assertIsNone(self.auth.authenticate_token(second))
        self.assertIsNotNone(self.auth.authenticate_token(other))


if __name__ == "__main__": unittest.main()
