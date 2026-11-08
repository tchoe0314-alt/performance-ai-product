import unittest

from backend.scripts.canary_revision import resolve_revision


class CanaryRevisionTests(unittest.TestCase):
    def test_schedule_uses_approved_release_not_main_or_override(self):
        self.assertEqual(resolve_revision("schedule", "a" * 40, "b" * 40, "c" * 40), "b" * 40)

    def test_push_cannot_override_candidate(self):
        self.assertEqual(resolve_revision("push", "a" * 40, "b" * 40, "c" * 40), "a" * 40)

    def test_manual_default_and_explicit_candidate(self):
        self.assertEqual(resolve_revision("workflow_dispatch", "a" * 40, "b" * 40), "b" * 40)
        self.assertEqual(resolve_revision("workflow_dispatch", "a" * 40, "b" * 40, "c" * 40), "c" * 40)

    def test_invalid_revision_fails_closed(self):
        for value in ("", "main", "abc1234", "g" * 40, "$(echo unsafe)"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                resolve_revision("schedule", "a" * 40, value)

    def test_unknown_event_fails_closed(self):
        with self.assertRaises(ValueError):
            resolve_revision("pull_request", "a" * 40, "b" * 40)
