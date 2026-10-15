import tempfile
import unittest
from pathlib import Path

from backend.services.auth_store import AuthStore
from backend.services.database import Database
from backend.services.project_store import ProjectStore
from tests.remediation.identity_fixtures import invite_test_member, accept_test_invitation


class ProjectTeamAdminTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name) / "civora-test.db")
        self.auth = AuthStore(self.db)
        self.projects = ProjectStore(self.db)
        self.owner = self.auth.register_user(email="owner@example.com", password="password-1", name="Owner")["user"]
        self.editor = self.auth.register_user(email="editor@example.com", password="password-1", name="Editor")["user"]
        self.viewer = self.auth.register_user(email="viewer@example.com", password="password-1", name="Viewer")["user"]

    def tearDown(self):
        self.tmp.cleanup()

    def test_project_owner_gets_default_team_and_owner_membership(self):
        project = self.projects.save_project(
            user_id=self.owner["user_id"],
            project_id=None,
            name="Customer Site",
            description="",
        )

        self.assertTrue(project["organization_id"].startswith("org_"))
        self.assertEqual(project["access_role"], "owner")
        admin = self.projects.project_admin_surface(
            user_id=self.owner["user_id"],
            project_id=project["project_id"],
        )
        self.assertEqual(admin["current_user_role"], "owner")
        self.assertTrue(admin["permissions"]["can_manage_access"])
        self.assertEqual(admin["members"][0]["role"], "owner")
        self.assertIn("owner", admin["roles"])
        self.assertTrue(any(item["action"] == "project_owner_membership_created" for item in admin["audit_log"]))

    def test_invite_existing_user_adds_member_and_audit_log(self):
        project = self.projects.save_project(
            user_id=self.owner["user_id"],
            project_id=None,
            name="Shared Site",
            description="",
        )

        invite = self.projects.invite_project_member(
            actor_user_id=self.owner["user_id"],
            project_id=project["project_id"],
            email=self.editor["email"],
            role="editor",
        )

        self.assertEqual(invite["status"], "pending")
        self.assertIsNone(self.projects.project_role(user_id=self.editor["user_id"],project_id=project["project_id"]))
        accept_test_invitation(self.projects,invite,actor_user_id=self.owner["user_id"])
        self.assertEqual(self.projects.project_role(user_id=self.editor["user_id"], project_id=project["project_id"]), "editor")
        shared = self.projects.get_project(user_id=self.editor["user_id"], project_id=project["project_id"])
        self.assertEqual(shared["access_role"], "editor")
        saved = self.projects.save_project(
            user_id=self.editor["user_id"],
            project_id=project["project_id"],
            name="Shared Site Updated",
            description="",
        )
        self.assertEqual(saved["name"], "Shared Site Updated")
        audit_actions = [
            item["action"]
            for item in self.projects.project_audit_log(
                user_id=self.owner["user_id"],
                project_id=project["project_id"],
            )
        ]
        self.assertIn("project_member_added", audit_actions)

    def test_viewer_can_read_but_cannot_edit_or_manage_access(self):
        project = self.projects.save_project(
            user_id=self.owner["user_id"],
            project_id=None,
            name="Read Only Site",
            description="",
        )
        invite_test_member(self.projects,
            actor_user_id=self.owner["user_id"],
            project_id=project["project_id"],
            email=self.viewer["email"],
            role="viewer",
        )

        self.assertIsNotNone(self.projects.get_project(user_id=self.viewer["user_id"], project_id=project["project_id"]))
        with self.assertRaises(ValueError):
            self.projects.save_project(
                user_id=self.viewer["user_id"],
                project_id=project["project_id"],
                name="Should Not Save",
                description="",
            )
        with self.assertRaises(ValueError):
            self.projects.invite_project_member(
                actor_user_id=self.viewer["user_id"],
                project_id=project["project_id"],
                email="other@example.com",
                role="viewer",
            )

    def test_reviewer_can_review_but_cannot_edit_or_manage_access(self):
        project = self.projects.save_project(
            user_id=self.owner["user_id"],
            project_id=None,
            name="Review Site",
            description="",
        )
        invite_test_member(self.projects,
            actor_user_id=self.owner["user_id"],
            project_id=project["project_id"],
            email=self.viewer["email"],
            role="reviewer",
        )

        admin_surface = self.projects.project_admin_surface(
            user_id=self.viewer["user_id"],
            project_id=project["project_id"],
        )
        self.assertEqual(admin_surface["current_user_role"], "reviewer")
        self.assertTrue(admin_surface["permissions"]["can_view"])
        self.assertTrue(admin_surface["permissions"]["can_review"])
        self.assertFalse(admin_surface["permissions"]["can_edit"])
        self.assertFalse(admin_surface["permissions"]["can_manage_access"])
        with self.assertRaises(ValueError):
            self.projects.save_project(
                user_id=self.viewer["user_id"],
                project_id=project["project_id"],
                name="Reviewer Should Not Save",
                description="",
            )

    def test_only_creator_can_manage_access_even_when_member_is_admin(self):
        project = self.projects.save_project(
            user_id=self.owner["user_id"],
            project_id=None,
            name="Admin Site",
            description="",
        )
        invite_test_member(self.projects,
            actor_user_id=self.owner["user_id"],
            project_id=project["project_id"],
            email=self.editor["email"],
            role="admin",
        )
        invite_test_member(self.projects,
            actor_user_id=self.owner["user_id"],
            project_id=project["project_id"],
            email=self.viewer["email"],
            role="viewer",
        )

        with self.assertRaisesRegex(ValueError, "Only the project creator"):
            self.projects.invite_project_member(actor_user_id=self.editor["user_id"], project_id=project["project_id"], email="other@example.test", role="editor")
        with self.assertRaisesRegex(ValueError, "Only the project creator"):
            self.projects.update_project_member_role(actor_user_id=self.editor["user_id"], project_id=project["project_id"], user_id=self.viewer["user_id"], role="editor")
        with self.assertRaisesRegex(ValueError, "Only the project creator"):
            self.projects.remove_project_member(actor_user_id=self.editor["user_id"], project_id=project["project_id"], user_id=self.viewer["user_id"])
        self.assertFalse(self.projects.project_admin_surface(user_id=self.editor["user_id"], project_id=project["project_id"])["permissions"]["can_manage_access"])
        self.assertEqual(self.projects.project_role(user_id=self.viewer["user_id"], project_id=project["project_id"]), "viewer")
        removed = self.projects.remove_project_member(
            actor_user_id=self.owner["user_id"],
            project_id=project["project_id"],
            user_id=self.viewer["user_id"],
        )

        self.assertTrue(removed)
        self.assertIsNone(self.projects.project_role(user_id=self.viewer["user_id"], project_id=project["project_id"]))
        audit_actions = [
            item["action"]
            for item in self.projects.project_audit_log(
                user_id=self.owner["user_id"],
                project_id=project["project_id"],
            )
        ]
        self.assertIn("project_member_removed", audit_actions)


if __name__ == "__main__":
    unittest.main()
