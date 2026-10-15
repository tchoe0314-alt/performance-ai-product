"""Hashed, expiring, single-use email proof. Delivery is injected explicitly.

No fake sender is selected by environment or exposed via an outbox endpoint.
Without an approved sender, delivery fails closed; test outboxes remain local.
"""
import hashlib
import os
import secrets
import time

from .email_delivery import EmailMessage, UnconfiguredEmailSender


def _digest(token):
    return hashlib.sha256(str(token or "").encode()).hexdigest()


class IdentityProofStore:
    def __init__(self, db, *, sender=None):
        self.db = db
        self.sender = sender if sender is not None else UnconfiguredEmailSender()

    def is_verified(self, user_id):
        connection=self.db.connect()
        try:
            return connection.execute("""SELECT 1 FROM verified_email_addresses v
                JOIN users u ON u.user_id=v.user_id AND u.email=v.email
                WHERE v.user_id=?""",(user_id,)).fetchone() is not None
        finally: connection.close()

    def _issue(self, *, user_id, email, purpose, invite_id=None):
        token=secrets.token_urlsafe(32); now=time.time()
        connection=self.db.connect()
        try:
            connection.execute("""INSERT INTO identity_challenges
                (token_digest,user_id,email,purpose,invite_id,created_at,expires_at,consumed_at)
                VALUES (?,?,?,?,?,?,?,NULL)""",
                (_digest(token),user_id,email,purpose,invite_id,now,now+3600))
            connection.commit()
        finally: connection.close()
        try:
            self.sender.send(EmailMessage(email,"Civora email confirmation",
                f"Confirmation code: {token}\nExpires in one hour. Do not share this code."))
        except Exception:
            connection=self.db.connect()
            try:
                connection.execute("UPDATE identity_challenges SET consumed_at=? WHERE token_digest=?",(time.time(),_digest(token)))
                connection.commit()
            finally: connection.close()
            raise

    def request_email_verification(self, *, user_id):
        connection=self.db.connect()
        try:
            row=connection.execute("SELECT email FROM users WHERE user_id=?",(user_id,)).fetchone()
            if row is None: raise ValueError("Account not found.")
            email=row["email"]
        finally: connection.close()
        self._issue(user_id=user_id,email=email,purpose="verify_email")

    def validate_enrollment(self, *, email, token):
        """Read-only preflight; acceptance still rechecks atomically after signup."""
        connection=self.db.connect()
        try:
            row=connection.execute("""SELECT c.created_at,c.expires_at FROM identity_challenges c
                JOIN project_invites i ON i.invite_id=c.invite_id
                JOIN projects p ON p.project_id=i.project_id
                WHERE c.token_digest=? AND c.email=? AND c.purpose='accept_invite'
                    AND c.user_id IS NULL AND c.consumed_at IS NULL
                    AND i.email=c.email AND i.status='pending' AND p.deleted_at IS NULL
                    AND i.invited_by_user_id=p.user_id AND i.role IN ('viewer','reviewer','editor','admin')""",
                (_digest(token),str(email or "").strip().lower())).fetchone()
            now=time.time()
            if row is None or row["created_at"]>now or row["expires_at"]<=now:
                raise ValueError("Invitation is invalid, expired or unavailable.")
        finally:connection.close()

    def request_password_reset(self, *, email):
        # Same response for known/unknown accounts; configuration status must
        # not become an account-existence oracle either.
        if isinstance(self.sender,UnconfiguredEmailSender):
            raise RuntimeError("Email delivery is not configured.")
        connection=self.db.connect()
        try:
            user=connection.execute("SELECT user_id,email FROM users WHERE email=?",(str(email or "").strip().lower(),)).fetchone()
        finally:connection.close()
        if user is not None:self._issue(user_id=user["user_id"],email=user["email"],purpose="reset_password")

    def reset_password(self, *, email, token, new_password):
        connection=self.db.connect()
        try:
            user=connection.execute("SELECT user_id FROM users WHERE email=?",(str(email or "").strip().lower(),)).fetchone()
        finally:connection.close()
        if user is None:raise ValueError("Confirmation is invalid, expired or already used.")
        return self.consume(user_id=user["user_id"],token=token,purpose="reset_password",new_password=new_password)

    def send_invitation(self, *, actor_user_id, invite_id, project_id=None):
        connection=self.db.connect()
        try:
            row=connection.execute("""SELECT i.email,i.project_id FROM project_invites i
                JOIN projects p ON p.project_id=i.project_id
                WHERE i.invite_id=? AND i.status='pending' AND p.user_id=? AND p.deleted_at IS NULL""",
                (invite_id,actor_user_id)).fetchone()
            if row is None or (project_id is not None and row["project_id"] != project_id):
                raise ValueError("Pending invitation not found or not owned.")
            email=row["email"]
        finally: connection.close()
        self._issue(user_id=None,email=email,purpose="accept_invite",invite_id=invite_id)

    def revoke_invitation(self, *, actor_user_id, project_id, invite_id):
        connection=self.db.connect()
        try:
            if self.db.storage_kind != "postgres": connection.execute("BEGIN IMMEDIATE")
            suffix=" FOR UPDATE" if self.db.storage_kind == "postgres" else ""
            row=connection.execute("""SELECT i.status FROM project_invites i
                JOIN projects p ON p.project_id=i.project_id
                WHERE i.invite_id=? AND i.project_id=? AND p.user_id=?"""+suffix,
                (invite_id,project_id,actor_user_id)).fetchone()
            if row is None or row["status"] != "pending":
                raise ValueError("Pending invitation not found or not owned.")
            now=time.time()
            connection.execute("UPDATE project_invites SET status='revoked',updated_at=? WHERE invite_id=?",(now,invite_id))
            connection.execute("UPDATE identity_challenges SET consumed_at=? WHERE invite_id=? AND consumed_at IS NULL",(now,invite_id))
            connection.commit()
        except Exception:
            connection.rollback(); raise
        finally:connection.close()

    def consume(self, *, user_id, token, purpose, new_password=None):
        if purpose not in ("verify_email","accept_invite","reset_password"):
            raise ValueError("Unsupported identity proof purpose.")
        if purpose=="reset_password" and (not isinstance(new_password,str) or not 8<=len(new_password)<=1024):
            raise ValueError("New password must contain8 to1024 characters.")
        if purpose!="reset_password" and new_password is not None:
            raise ValueError("Password changes require a password-reset proof.")
        now=time.time(); connection=self.db.connect()
        try:
            if self.db.storage_kind != "postgres": connection.execute("BEGIN IMMEDIATE")
            suffix=" FOR UPDATE" if self.db.storage_kind == "postgres" else ""
            proof=connection.execute("SELECT * FROM identity_challenges WHERE token_digest=?"+suffix,(_digest(token),)).fetchone()
            user=connection.execute("SELECT email FROM users WHERE user_id=?",(user_id,)).fetchone()
            if (proof is None or user is None or proof["purpose"] != purpose or proof["consumed_at"] is not None
                    or proof["created_at"] > now or proof["expires_at"] <= now or proof["email"] != user["email"]
                    or (proof["user_id"] is not None and proof["user_id"] != user_id)):
                raise ValueError("Confirmation is invalid, expired or already used.")
            project_id=None
            if purpose == "accept_invite":
                invite=connection.execute("""SELECT i.*,p.user_id AS project_owner,p.deleted_at,p.organization_id
                    FROM project_invites i JOIN projects p ON p.project_id=i.project_id
                    WHERE i.invite_id=?"""+suffix,(proof["invite_id"],)).fetchone()
                if (invite is None or invite["status"] != "pending" or invite["deleted_at"] is not None
                        or invite["email"] != user["email"] or invite["invited_by_user_id"] != invite["project_owner"]
                        or invite["role"] not in ("viewer","reviewer","editor","admin")):
                    raise ValueError("Invitation is no longer available.")
                project_id=invite["project_id"]
                if invite["project_owner"] != user_id:
                    connection.execute("""INSERT INTO project_members
                        (project_id,user_id,role,invited_email,created_at,updated_at) VALUES (?,?,?,?,?,?)
                        ON CONFLICT(project_id,user_id) DO UPDATE SET role=excluded.role,updated_at=excluded.updated_at""",
                        (project_id,user_id,invite["role"],user["email"],now,now))
                connection.execute("""UPDATE project_invites SET status='accepted',accepted_by_user_id=?,updated_at=?
                    WHERE invite_id=? AND status='pending'""",(user_id,now,invite["invite_id"]))
                from .project_store import ProjectStore
                ProjectStore(self.db)._log_access_event(connection,actor_user_id=user_id,
                    organization_id=invite["organization_id"],project_id=project_id,
                    target_user_id=user_id,target_email=user["email"],action="project_member_added",
                    role=invite["role"],metadata={"invite_id":invite["invite_id"],"proof":"single_use_email_confirmation"})
            connection.execute("""UPDATE identity_challenges SET consumed_at=?
                WHERE token_digest=? AND consumed_at IS NULL""",(now,_digest(token)))
            if purpose=="reset_password":
                from .auth_store import _hash_password
                salt=os.urandom(16).hex()
                connection.execute("UPDATE users SET password_salt=?,password_hash=?,updated_at=? WHERE user_id=?",
                    (salt,_hash_password(new_password,salt),now,user_id))
                connection.execute("DELETE FROM auth_tokens WHERE user_id=?",(user_id,))
                connection.execute("UPDATE identity_challenges SET consumed_at=? WHERE user_id=? AND consumed_at IS NULL",(now,user_id))
            connection.execute("""INSERT INTO verified_email_addresses(user_id,email,verified_at) VALUES (?,?,?)
                ON CONFLICT(user_id) DO UPDATE SET email=excluded.email,verified_at=excluded.verified_at""",
                (user_id,user["email"],now))
            connection.commit()
            return {"verified":True,"project_id":project_id}
        except Exception:
            connection.rollback()
            raise
        finally: connection.close()
