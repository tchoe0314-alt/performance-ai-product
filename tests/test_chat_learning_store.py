import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.services.chat_learning_store import append_chat_interaction_event


class ChatLearningStoreTest(unittest.TestCase):
    def test_append_uses_configured_learning_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "learning.jsonl"
            env = {
                "CIVORA_CHAT_LEARNING_PATH": str(path),
                "CIVORA_ENABLE_CHAT_LEARNING": "1",
                "CIVORA_DISABLE_CHAT_LEARNING": "",
            }
            with patch.dict(os.environ, env, clear=False):
                append_chat_interaction_event({"message": "hello"})

            rows = [json.loads(line) for line in path.read_text().splitlines()]

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["event_type"], "interaction")
        self.assertEqual(rows[0]["message"], "hello")
        self.assertIn("ts", rows[0])

    def test_append_is_disabled_by_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "learning.jsonl"
            env = {
                "CIVORA_CHAT_LEARNING_PATH": str(path),
                "CIVORA_ENABLE_CHAT_LEARNING": "",
                "CIVORA_DISABLE_CHAT_LEARNING": "",
            }
            with patch.dict(os.environ, env, clear=False):
                append_chat_interaction_event({"message": "hello"})

            self.assertFalse(path.exists())

    def test_append_can_be_disabled_for_test_and_privacy_contexts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "learning.jsonl"
            env = {
                "CIVORA_CHAT_LEARNING_PATH": str(path),
                "CIVORA_DISABLE_CHAT_LEARNING": "1",
            }
            with patch.dict(os.environ, env, clear=False):
                append_chat_interaction_event({"message": "hello"})

            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
