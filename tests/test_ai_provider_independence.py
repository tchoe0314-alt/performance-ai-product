import unittest
from unittest.mock import Mock, patch

import parsers.ai_parser as ai_parser
from backend.ai.provider import (
    AIProviderUnavailable,
    DisabledAIProvider,
    LegacyResponsesClient,
    OllamaProvider,
    get_ai_provider,
    reset_ai_provider_cache,
)
from parsers.ai_parser import ask_mode, command_mode
from parsers.chat_intent_parser import build_chat_memory_summary, decide_chat_message


def _reset() -> None:
    ai_parser.client = None
    reset_ai_provider_cache()


class AIProviderIndependenceTests(unittest.TestCase):
    def tearDown(self) -> None:
        _reset()

    def test_default_provider_is_disabled_without_openai_key(self) -> None:
        with patch.dict("os.environ", {"CIVORA_AI_PROVIDER": "", "OPENAI_API_KEY": ""}, clear=False):
            _reset()
            provider = get_ai_provider()

        self.assertIsInstance(provider, DisabledAIProvider)

    def test_legacy_responses_client_exposes_provider_failures(self) -> None:
        client = LegacyResponsesClient(DisabledAIProvider())

        with self.assertRaises(AIProviderUnavailable):
            client.responses.create(model="gpt-5", input=[{"role": "user", "content": "hello"}])

    def test_ollama_provider_uses_local_chat_endpoint(self) -> None:
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"message": {"content": '{"ok": true}'}}

        with patch("backend.ai.provider.requests.post", return_value=response) as post:
            provider = OllamaProvider(base_url="http://local-ollama", timeout_seconds=1)
            result = provider.generate_json(
                model="llama3.1",
                messages=[{"role": "user", "content": "return ok"}],
                schema={"type": "object"},
            )

        self.assertEqual(result.output_text, '{"ok": true}')
        self.assertEqual(result.provider, "ollama")
        post.assert_called_once()
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["model"], "llama3.1")
        self.assertEqual(payload["format"], "json")
        self.assertFalse(payload["stream"])

    def test_command_mode_falls_back_to_deterministic_parser_when_ai_disabled(self) -> None:
        with patch.dict("os.environ", {"CIVORA_AI_PROVIDER": "none", "OPENAI_API_KEY": ""}, clear=False):
            _reset()
            parsed = command_mode(
                "Design a civil site plan for a 120 ft by 100 ft lot. "
                "Include one 60 ft by 40 ft building centered on the lot, "
                "parking for 10 cars, one 12 ft wide driveway, 10 ft setbacks, "
                "and storm drainage with 2 inlets and 1 pipe."
            )

        self.assertEqual(parsed["lot"]["w"], 120.0)
        self.assertEqual(parsed["lot"]["h"], 100.0)
        self.assertEqual(parsed["site_plan"]["parking_count"]["value"], 10)
        self.assertEqual(parsed["site_plan"]["building_width"]["value"], 60.0)
        self.assertEqual(parsed["drainage"]["inlet_count"]["value"], 2)
        self.assertEqual(parsed["meta"]["language_provider"], "deterministic_fallback")

    def test_ask_mode_reports_language_provider_unavailable_without_crashing(self) -> None:
        with patch.dict("os.environ", {"CIVORA_AI_PROVIDER": "none", "OPENAI_API_KEY": ""}, clear=False):
            _reset()
            answer = ask_mode("what can you do?")

        self.assertIn("language provider is disabled", answer)

    def test_chat_memory_uses_local_heuristic_when_ai_disabled(self) -> None:
        with patch.dict("os.environ", {"CIVORA_AI_PROVIDER": "none", "OPENAI_API_KEY": ""}, clear=False):
            _reset()
            memory = build_chat_memory_summary(
                [
                    {"role": "user", "content": "Make sure you never guess when details are missing."},
                    {"role": "user", "content": "Prefer drainage before utilities."},
                ]
            )

        self.assertTrue(any("never guess" in item for item in memory["preferences"] + memory["constraints"]))

    def test_decide_chat_still_works_with_provider_disabled(self) -> None:
        with patch.dict("os.environ", {"CIVORA_AI_PROVIDER": "none", "OPENAI_API_KEY": ""}, clear=False):
            _reset()
            result = decide_chat_message({"message": "hello", "context": {}})

        self.assertEqual(result["intent"], "conversation")
        self.assertEqual(result["run_mode"], "none")


if __name__ == "__main__":
    unittest.main()
