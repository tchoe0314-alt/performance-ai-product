"""Email ownership/invitation proof with a private in-memory fake sender."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from backend.services.auth_store import AuthStore
from backend.services.database import Database
from backend.services.email_delivery import FakeEmailSender
from backend.services.identity_proofs import IdentityProofStore
from backend.services.project_store import ProjectStore


class IdentityProofTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="civora-identity-")
        self.db=Database(Path(self.temp.name)/"synthetic.sqlite",database_url="sqlite-local-only")
        auth=AuthStore(self.db)
        self.owner=auth.register_user(email="owner@example.test",password="Synthetic-only-123",name="Owner")["user"]["user_id"]
        # Models an attacker pre-registering the intended recipient address.
        self.recipient=auth.register_user(email="recipient@example.test",password="Synthetic-only-123",name="Unverified")["user"]["user_id"]
        self.other=auth.register_user(email="other@example.test",password="Synthetic-only-123",name="Other")["user"]["user_id"]
        self.projects=ProjectStore(self.db)
        self.project=self.projects.save_project(user_id=self.owner,project_id=None,name="Synthetic")
        self.sender=FakeEmailSender(); self.proofs=IdentityProofStore(self.db,sender=self.sender)

    def tearDown(self): self.temp.cleanup()

    def code(self): return self.sender.messages[-1].text.splitlines()[0].split(": ",1)[1]

    def invite(self):
        invite=self.projects.invite_project_member(actor_user_id=self.owner,project_id=self.project["project_id"],email="recipient@example.test",role="editor")
        self.proofs.send_invitation(actor_user_id=self.owner,invite_id=invite["invite_id"])
        return invite,self.code()

    def test_pre_registered_email_does_not_receive_access_without_proof(self):
        invite,code=self.invite()
        self.assertEqual(invite["status"],"pending")
        self.assertFalse(self.proofs.is_verified(self.recipient))
        self.assertIsNone(self.projects.get_project(user_id=self.recipient,project_id=self.project["project_id"]))
        result=self.proofs.consume(user_id=self.recipient,token=code,purpose="accept_invite")
        self.assertEqual(result["project_id"],self.project["project_id"])
        self.assertTrue(self.proofs.is_verified(self.recipient))
        self.assertEqual(self.projects.project_role(user_id=self.recipient,project_id=self.project["project_id"]),"editor")

    def test_wrong_account_wrong_purpose_and_replay_reject(self):
        _,code=self.invite()
        for user,purpose in ((self.other,"accept_invite"),(self.recipient,"verify_email")):
            with self.assertRaises(ValueError):self.proofs.consume(user_id=user,token=code,purpose=purpose)
        self.proofs.consume(user_id=self.recipient,token=code,purpose="accept_invite")
        with self.assertRaises(ValueError):self.proofs.consume(user_id=self.recipient,token=code,purpose="accept_invite")

    def test_hashes_only_and_expiry_exact_boundary(self):
        with patch("backend.services.identity_proofs.time.time",return_value=1000):
            self.proofs.request_email_verification(user_id=self.recipient)
        code=self.code(); connection=self.db.connect()
        try:
            row=connection.execute("SELECT token_digest FROM identity_challenges").fetchone()
            self.assertNotEqual(row["token_digest"],code)
            self.assertEqual(len(row["token_digest"]),64)
        finally:connection.close()
        with patch("backend.services.identity_proofs.time.time",return_value=4600),self.assertRaises(ValueError):
            self.proofs.consume(user_id=self.recipient,token=code,purpose="verify_email")
        self.assertFalse(self.proofs.is_verified(self.recipient))

    def test_revoked_invite_cannot_be_accepted(self):
        invite,code=self.invite()
        with self.assertRaises(ValueError):
            self.proofs.revoke_invitation(actor_user_id=self.other,project_id=self.project["project_id"],invite_id=invite["invite_id"])
        self.proofs.revoke_invitation(actor_user_id=self.owner,project_id=self.project["project_id"],invite_id=invite["invite_id"])
        with self.assertRaises(ValueError):self.proofs.consume(user_id=self.recipient,token=code,purpose="accept_invite")
        self.assertIsNone(self.projects.get_project(user_id=self.recipient,project_id=self.project["project_id"]))

    def test_single_use_has_one_concurrent_winner(self):
        _,code=self.invite()
        def consume(_):
            try:self.proofs.consume(user_id=self.recipient,token=code,purpose="accept_invite");return "accepted"
            except ValueError:return "rejected"
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(consume,range(2))),["accepted","rejected"])

    def test_unconfigured_sender_invalidates_undelivered_challenge(self):
        proofs=IdentityProofStore(self.db)
        with self.assertRaises(RuntimeError):proofs.request_email_verification(user_id=self.recipient)
        connection=self.db.connect()
        try:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM identity_challenges WHERE consumed_at IS NULL").fetchone()[0],0)
        finally:connection.close()

    def test_ordinary_member_cannot_send_owner_invitation(self):
        invite,_=self.invite()
        with self.assertRaises(ValueError):self.proofs.send_invitation(actor_user_id=self.other,invite_id=invite["invite_id"])


if __name__ == "__main__":unittest.main()
