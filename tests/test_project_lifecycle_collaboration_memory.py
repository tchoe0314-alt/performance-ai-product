import tempfile
import unittest
import importlib
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.services.auth_store import AuthStore
from backend.services.database import Database
from backend.services.project_store import ProjectStore
from backend.application.chat_workflows import decide_chat


api_app_module = importlib.import_module("backend.api.app")


class ProjectLifecycleCollaborationMemoryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name) / "civora-test.db")
        self.auth = AuthStore(self.db)
        self.projects = ProjectStore(self.db)
        owner_registration = self.auth.register_user(
            email="owner@example.com",
            password="password-1",
            name="Owner",
        )
        reviewer_registration = self.auth.register_user(
            email="reviewer@example.com",
            password="password-1",
            name="Reviewer",
        )
        self.owner = owner_registration["user"]
        self.owner_token = owner_registration["token"]
        self.reviewer = reviewer_registration["user"]
        self.project = self.projects.save_project(
            user_id=self.owner["user_id"],
            project_id=None,
            name="Margo Street Site",
            description="Commercial site",
            project_input={"manual_fields": {"lot_width": 1000, "lot_height": 1000}},
            latest_result={"final_plan": {"project_name": "Margo Street Site"}},
            metadata={"source": "test"},
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_duplicate_archive_delete_and_restore_preserve_independent_project_state(self):
        duplicate = self.projects.duplicate_project(
            user_id=self.owner["user_id"],
            project_id=self.project["project_id"],
        )

        self.assertNotEqual(duplicate["project_id"], self.project["project_id"])
        self.assertEqual(duplicate["name"], "Margo Street Site Copy")
        self.assertEqual(duplicate["project_input"]["manual_fields"]["lot_width"], 1000)
        self.assertEqual(duplicate["metadata"]["duplicated_from_project_id"], self.project["project_id"])

        archived = self.projects.set_project_archived(
            user_id=self.owner["user_id"],
            project_id=duplicate["project_id"],
            archived=True,
        )
        self.assertIsNotNone(archived["archived_at"])
        active_ids = {
            item["project_id"]
            for item in self.projects.list_projects(
                user_id=self.owner["user_id"],
                include_archived=False,
            )
        }
        self.assertNotIn(duplicate["project_id"], active_ids)

        self.assertTrue(
            self.projects.delete_project(
                user_id=self.owner["user_id"],
                project_id=duplicate["project_id"],
            )
        )
        self.assertIsNone(
            self.projects.get_project(
                user_id=self.owner["user_id"],
                project_id=duplicate["project_id"],
            )
        )
        deleted = [
            item
            for item in self.projects.list_projects(
                user_id=self.owner["user_id"],
                include_deleted=True,
            )
            if item["project_id"] == duplicate["project_id"]
        ]
        self.assertEqual(len(deleted), 1)
        self.assertIsNotNone(deleted[0]["deleted_at"])
        with self.assertRaisesRegex(ValueError, "Restore it before saving"):
            self.projects.save_project(
                user_id=self.owner["user_id"],
                project_id=duplicate["project_id"],
                name="Should not revive silently",
            )

        restored = self.projects.restore_project(
            user_id=self.owner["user_id"],
            project_id=duplicate["project_id"],
        )
        self.assertIsNone(restored["deleted_at"])
        self.assertIsNone(restored["archived_at"])
        self.assertEqual(restored["latest_result"]["final_plan"]["project_name"], "Margo Street Site")

    def test_inaccessible_project_id_cannot_be_claimed_by_save(self):
        with self.assertRaisesRegex(ValueError, "editor access"):
            self.projects.save_project(
                user_id=self.reviewer["user_id"],
                project_id=self.project["project_id"],
                name="Attempted takeover",
            )
        unchanged = self.projects.get_project(
            user_id=self.owner["user_id"],
            project_id=self.project["project_id"],
        )
        self.assertEqual(unchanged["user_id"], self.owner["user_id"])
        self.assertEqual(unchanged["name"], "Margo Street Site")

    def test_presence_comments_mentions_and_review_requests_obey_roles(self):
        self.projects.invite_project_member(
            actor_user_id=self.owner["user_id"],
            project_id=self.project["project_id"],
            email=self.reviewer["email"],
            role="reviewer",
        )
        updated_member = self.projects.update_project_member_role(
            actor_user_id=self.owner["user_id"],
            project_id=self.project["project_id"],
            user_id=self.reviewer["user_id"],
            role="editor",
        )
        self.assertEqual(updated_member["previous_role"], "reviewer")
        self.assertEqual(updated_member["role"], "editor")
        presence = self.projects.record_project_presence(
            user_id=self.reviewer["user_id"],
            project_id=self.project["project_id"],
            context={"mode": "review", "selected_object_id": "building-a", "secret": "discard"},
        )
        self.assertEqual(presence["context"]["selected_object_id"], "building-a")
        self.assertNotIn("secret", presence["context"])

        comment = self.projects.add_project_comment(
            user_id=self.reviewer["user_id"],
            project_id=self.project["project_id"],
            body="@owner@example.com Verify the west entrance.",
            mentions=["owner@example.com"],
            object_id="building-a",
        )
        self.assertEqual(comment["mentions"], ["owner@example.com"])
        resolved = self.projects.update_project_comment_status(
            user_id=self.reviewer["user_id"],
            project_id=self.project["project_id"],
            comment_id=comment["comment_id"],
            status="resolved",
        )
        self.assertEqual(resolved["status"], "resolved")

        review_request = self.projects.create_review_request(
            user_id=self.owner["user_id"],
            project_id=self.project["project_id"],
            assigned_email=self.reviewer["email"],
            message="Review drainage and access.",
        )
        updated = self.projects.update_review_request_status(
            user_id=self.reviewer["user_id"],
            project_id=self.project["project_id"],
            request_id=review_request["request_id"],
            status="completed",
        )
        self.assertEqual(updated["status"], "completed")

        collaboration = self.projects.project_collaboration_surface(
            user_id=self.owner["user_id"],
            project_id=self.project["project_id"],
        )
        self.assertEqual(len(collaboration["presence"]), 1)
        self.assertEqual(collaboration["comments"][0]["status"], "resolved")
        self.assertEqual(collaboration["review_requests"][0]["status"], "completed")

    def test_memory_is_off_by_default_explicit_and_suggestion_only(self):
        consent = self.projects.get_memory_consent(user_id=self.owner["user_id"])
        self.assertFalse(consent["personal_enabled"])
        with self.assertRaisesRegex(ValueError, "Enable personal memory"):
            self.projects.add_engineering_memory(
                user_id=self.owner["user_id"],
                scope="personal",
                category="preference",
                label="Preferred layer naming",
                value={"prefix": "CIV"},
            )

        self.projects.update_memory_consent(
            user_id=self.owner["user_id"],
            personal_enabled=True,
            company_enabled=True,
            global_learning_enabled=False,
        )
        personal = self.projects.add_engineering_memory(
            user_id=self.owner["user_id"],
            scope="personal",
            category="preference",
            label="Preferred layer naming",
            value={"prefix": "CIV"},
        )
        project_memory = self.projects.add_engineering_memory(
            user_id=self.owner["user_id"],
            scope="project",
            category="decision",
            label="Preserve west entrance",
            value={"reason": "fire access review"},
            project_id=self.project["project_id"],
        )
        company = self.projects.add_engineering_memory(
            user_id=self.owner["user_id"],
            scope="company",
            category="template_preference",
            label="Default utility colors",
            value={"water": "blue", "sanitary": "green"},
            project_id=self.project["project_id"],
        )

        surface = self.projects.list_engineering_memory(
            user_id=self.owner["user_id"],
            project_id=self.project["project_id"],
        )
        self.assertEqual({item["scope"] for item in surface["items"]}, {"personal", "project", "company"})
        self.assertTrue(all(item["suggestion_only"] for item in surface["items"]))
        self.assertTrue(all(not item["engineering_authority"] for item in surface["items"]))
        self.assertFalse(surface["rules"]["silent_learning"])
        self.assertFalse(surface["rules"]["overrides_standards"])

        self.assertTrue(
            self.projects.delete_engineering_memory(
                user_id=self.owner["user_id"],
                memory_id=personal["memory_id"],
            )
        )
        refreshed = self.projects.list_engineering_memory(
            user_id=self.owner["user_id"],
            project_id=self.project["project_id"],
        )
        self.assertNotIn(personal["memory_id"], {item["memory_id"] for item in refreshed["items"]})
        self.assertIn(project_memory["memory_id"], {item["memory_id"] for item in refreshed["items"]})
        self.assertIn(company["memory_id"], {item["memory_id"] for item in refreshed["items"]})

        self.projects.invite_project_member(
            actor_user_id=self.owner["user_id"],
            project_id=self.project["project_id"],
            email=self.reviewer["email"],
            role="reviewer",
        )
        reviewer_memory = self.projects.add_engineering_memory(
            user_id=self.reviewer["user_id"],
            scope="project",
            category="review_note",
            label="Confirm west entrance width",
            value={"status": "needs review"},
            project_id=self.project["project_id"],
        )
        self.assertTrue(
            self.projects.delete_engineering_memory(
                user_id=self.owner["user_id"],
                memory_id=reviewer_memory["memory_id"],
            )
        )
        self.assertFalse(
            self.projects.delete_engineering_memory(
                user_id=self.reviewer["user_id"],
                memory_id=company["memory_id"],
            )
        )

    def test_chat_uses_the_same_governed_memory_store(self):
        context = {"current_project": {"project_id": self.project["project_id"]}}
        saved = decide_chat(
            {
                "message": "Remember for this project that the west entrance must remain available for fire access",
                "context": context,
            },
            decide_chat_message=lambda _payload: {"assistant_message": "fallback"},
            project_store=self.projects,
            user_id=self.owner["user_id"],
        )
        self.assertEqual(saved["action_taken"], "saved_engineering_memory")
        self.assertIn("suggestion-only", saved["assistant_message"])

        listed = decide_chat(
            {"message": "What do you remember?", "context": context},
            decide_chat_message=lambda _payload: {"assistant_message": "fallback"},
            project_store=self.projects,
            user_id=self.owner["user_id"],
        )
        self.assertEqual(listed["action_taken"], "listed_engineering_memory")
        self.assertIn("west entrance", listed["assistant_message"].lower())

        blocked = decide_chat(
            {"message": "Remember my preference that I use 90 degree parking", "context": context},
            decide_chat_message=lambda _payload: {"assistant_message": "fallback"},
            project_store=self.projects,
            user_id=self.owner["user_id"],
        )
        self.assertEqual(blocked["action_taken"], "blocked_engineering_memory")
        self.assertIn("Enable personal memory", blocked["assistant_message"])

    def test_authenticated_api_exposes_reversible_lifecycle_collaboration_and_memory(self):
        headers = {"Authorization": f"Bearer {self.owner_token}"}
        with (
            patch.object(api_app_module, "AUTH_STORE", self.auth),
            patch.object(api_app_module, "PROJECT_STORE", self.projects),
            TestClient(api_app_module.app) as client,
        ):
            duplicated = client.post(
                f"/api/projects/{self.project['project_id']}/duplicate",
                headers=headers,
                json={},
            )
            self.assertEqual(duplicated.status_code, 200)
            duplicate_id = duplicated.json()["project"]["project_id"]

            archived = client.patch(
                f"/api/projects/{duplicate_id}/archive",
                headers=headers,
                json={"archived": True},
            )
            self.assertEqual(archived.status_code, 200)
            self.assertIsNotNone(archived.json()["project"]["archived_at"])

            deleted = client.delete(f"/api/projects/{duplicate_id}", headers=headers)
            self.assertEqual(deleted.status_code, 200)
            deleted_list = client.get("/api/projects-deleted", headers=headers)
            self.assertIn(duplicate_id, {item["project_id"] for item in deleted_list.json()["projects"]})
            restored = client.post(f"/api/projects/{duplicate_id}/restore", headers=headers)
            self.assertEqual(restored.status_code, 200)

            invited = client.post(
                f"/api/projects/{self.project['project_id']}/admin/invites",
                headers=headers,
                json={"email": self.reviewer["email"], "role": "reviewer"},
            )
            self.assertEqual(invited.status_code, 200)
            role_changed = client.patch(
                f"/api/projects/{self.project['project_id']}/admin/members/{self.reviewer['user_id']}",
                headers=headers,
                json={"role": "editor"},
            )
            self.assertEqual(role_changed.status_code, 200)
            self.assertEqual(role_changed.json()["member"]["role"], "editor")

            presence = client.post(
                f"/api/projects/{self.project['project_id']}/presence",
                headers=headers,
                json={"context": {"mode": "draw", "selected_object_id": "building-a", "secret": "discard"}},
            )
            self.assertEqual(presence.status_code, 200)
            self.assertNotIn("secret", presence.json()["presence"]["context"])
            comment = client.post(
                f"/api/projects/{self.project['project_id']}/comments",
                headers=headers,
                json={"body": "Review the west entrance.", "mentions": []},
            )
            self.assertEqual(comment.status_code, 200)
            review = client.post(
                f"/api/projects/{self.project['project_id']}/review-requests",
                headers=headers,
                json={"message": "Review access and drainage."},
            )
            self.assertEqual(review.status_code, 200)

            consent = client.patch(
                "/api/memory/consent",
                headers=headers,
                json={"personal_enabled": True, "company_enabled": False, "global_learning_enabled": False},
            )
            self.assertEqual(consent.status_code, 200)
            memory = client.post(
                "/api/memory",
                headers=headers,
                json={
                    "scope": "personal",
                    "category": "preference",
                    "label": "Preferred plan orientation",
                    "value": {"north": "up"},
                    "project_id": self.project["project_id"],
                },
            )
            self.assertEqual(memory.status_code, 200)
            self.assertTrue(memory.json()["memory"]["suggestion_only"])
            self.assertFalse(memory.json()["memory"]["engineering_authority"])


if __name__ == "__main__":
    unittest.main()
