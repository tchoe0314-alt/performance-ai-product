import unittest

from backend.application.session_workflows import maybe_export_session


class ApplicationSessionWorkflowsTest(unittest.TestCase):
    def test_maybe_export_session_returns_empty_without_session(self):
        self.assertEqual(maybe_export_session(None, export_session_state=lambda sid: {"session_id": sid}), {})

    def test_maybe_export_session_returns_export(self):
        exported = maybe_export_session("s1", export_session_state=lambda sid: {"session_id": sid, "messages": []})
        self.assertEqual(exported["session_id"], "s1")

    def test_maybe_export_session_swallows_errors(self):
        exported = maybe_export_session("s1", export_session_state=lambda sid: (_ for _ in ()).throw(RuntimeError("boom")))
        self.assertEqual(exported, {})


if __name__ == "__main__":
    unittest.main()
