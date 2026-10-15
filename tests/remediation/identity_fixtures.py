"""Explicit proof delivery for synthetic role fixtures, never production code.

Tests use a fake mailbox, not a direct SQL membership/verification bypass.
Callers must have authored the disposable accounts themselves.
"""
from backend.services.email_delivery import FakeEmailSender
from backend.services.identity_proofs import IdentityProofStore


def accept_test_invitation(store, invite, *, actor_user_id):
    connection=store.db.connect()
    try:
        user=connection.execute("SELECT user_id FROM users WHERE email=?",(invite["email"],)).fetchone()
        if user is None:raise AssertionError("Synthetic invite fixture needs an authored recipient account.")
    finally:connection.close()
    sender=FakeEmailSender(); proofs=IdentityProofStore(store.db,sender=sender)
    proofs.send_invitation(actor_user_id=actor_user_id,invite_id=invite["invite_id"])
    code=sender.messages[-1].text.splitlines()[0].split(": ",1)[1]
    proofs.consume(user_id=user["user_id"],token=code,purpose="accept_invite")
    return {**invite,"status":"accepted","accepted_by_user_id":user["user_id"]}


def invite_test_member(store, **kwargs):
    invite=store.invite_project_member(**kwargs)
    return accept_test_invitation(store,invite,actor_user_id=kwargs["actor_user_id"])
