import tempfile
import unittest
from pathlib import Path

from backend.services.auth_store import AuthStore
from backend.services.database import Database
from backend.services.project_store import ProjectStore


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

        self.assertEqual(invite["status"], "accepted")
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
        self.projects.invite_project_member(
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

    def test_admin_can_remove_non_owner_member(self):
        project = self.projects.save_project(
            user_id=self.owner["user_id"],
            project_id=None,
            name="Admin Site",
            description="",
        )
        self.projects.invite_project_member(
            actor_user_id=self.owner["user_id"],
            project_id=project["project_id"],
            email=self.editor["email"],
            role="admin",
        )
        self.projects.invite_project_member(
            actor_user_id=self.editor["user_id"],
            project_id=project["project_id"],
            email=self.viewer["email"],
            role="viewer",
        )

        removed = self.projects.remove_project_member(
            actor_user_id=self.editor["user_id"],
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
