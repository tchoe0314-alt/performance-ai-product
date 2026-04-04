import unittest

from backend.application.chat_workflows import decide_chat


class ApplicationChatWorkflowsTest(unittest.TestCase):
    def test_decide_chat_requires_message(self):
        with self.assertRaises(ValueError):
            decide_chat({}, decide_chat_message=lambda payload: payload)

    def test_decide_chat_delegates_to_parser(self):
        called = {}

        def fake_decider(payload):
            called["payload"] = dict(payload)
            return {"success": True, "intent": "conversation"}

        result = decide_chat(
            {"message": "hello", "context": {"strategy_mode": "assisted"}},
            decide_chat_message=fake_decider,
        )
        self.assertEqual(result["intent"], "conversation")
        self.assertEqual(called["payload"]["message"], "hello")


if __name__ == "__main__":
    unittest.main()
