from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol

import requests


class AIProviderUnavailable(RuntimeError):
    """Raised when the configured language provider is intentionally unavailable."""


@dataclass(frozen=True)
class AIResponse:
    output_text: str
    provider: str
    model: str
    raw: Any = None


class AIProvider(Protocol):
    name: str

    def generate_text(self, *, model: str, messages: List[Dict[str, str]]) -> AIResponse:
        ...

    def generate_json(
        self,
        *,
        model: str,
        messages: List[Dict[str, str]],
        schema: Optional[Dict[str, Any]] = None,
        schema_name: str = "civora_json",
    ) -> AIResponse:
        ...


class DisabledAIProvider:
    name = "none"

    def generate_text(self, *, model: str, messages: List[Dict[str, str]]) -> AIResponse:
        raise AIProviderUnavailable("Civora language provider is disabled.")

    def generate_json(
        self,
        *,
        model: str,
        messages: List[Dict[str, str]],
        schema: Optional[Dict[str, Any]] = None,
        schema_name: str = "civora_json",
    ) -> AIResponse:
        raise AIProviderUnavailable("Civora language provider is disabled.")


def _env_float(name: str, default: float) -> float:
    raw = str(os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except Exception:
        return default


class OpenAIProvider:
    name = "openai"

    def __init__(self, *, api_key: str = "", timeout_seconds: Optional[float] = None) -> None:
        self.api_key = api_key or str(os.getenv("OPENAI_API_KEY") or "")
        configured_timeout = _env_float("CIVORA_OPENAI_TIMEOUT_SECONDS", 20.0)
        self.timeout_seconds = max(1.0, float(timeout_seconds if timeout_seconds is not None else configured_timeout))
        self._client: Any = None

    def _load_client(self) -> Any:
        if self._client is not None:
            return self._client
        if not self.api_key:
            raise AIProviderUnavailable("OPENAI_API_KEY is missing.")
        from openai import OpenAI

        self._client = OpenAI(api_key=self.api_key, timeout=self.timeout_seconds)
        return self._client

    def generate_text(self, *, model: str, messages: List[Dict[str, str]]) -> AIResponse:
        try:
            response = self._load_client().responses.create(model=model, input=messages)
        except Exception as exc:
            raise AIProviderUnavailable(f"OpenAI provider request failed: {exc}") from exc
        return AIResponse(output_text=str(response.output_text or ""), provider=self.name, model=model, raw=response)

    def generate_json(
        self,
        *,
        model: str,
        messages: List[Dict[str, str]],
        schema: Optional[Dict[str, Any]] = None,
        schema_name: str = "civora_json",
    ) -> AIResponse:
        text_format = None
        if schema:
            text_format = {
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "schema": schema,
                    "strict": True,
                }
            }
        try:
            response = self._load_client().responses.create(model=model, input=messages, text=text_format)
        except Exception as exc:
            raise AIProviderUnavailable(f"OpenAI provider request failed: {exc}") from exc
        return AIResponse(output_text=str(response.output_text or ""), provider=self.name, model=model, raw=response)


class OllamaProvider:
    name = "ollama"

    def __init__(self, *, base_url: str = "", timeout_seconds: float = 45.0) -> None:
        self.base_url = (base_url or str(os.getenv("CIVORA_OLLAMA_BASE_URL") or "http://localhost:11434")).rstrip("/")
        self.timeout_seconds = timeout_seconds

    def _post_chat(self, *, model: str, messages: List[Dict[str, str]], json_mode: bool = False) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
        }
        if json_mode:
            payload["format"] = "json"
        try:
            response = requests.post(f"{self.base_url}/api/chat", json=payload, timeout=self.timeout_seconds)
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            raise AIProviderUnavailable(f"Ollama provider request failed: {exc}") from exc
        if not isinstance(data, dict):
            raise AIProviderUnavailable("Ollama returned an invalid response.")
        return data

    def generate_text(self, *, model: str, messages: List[Dict[str, str]]) -> AIResponse:
        data = self._post_chat(model=model, messages=messages, json_mode=False)
        text = str(dict(data.get("message") or {}).get("content") or "")
        return AIResponse(output_text=text, provider=self.name, model=model, raw=data)

    def generate_json(
        self,
        *,
        model: str,
        messages: List[Dict[str, str]],
        schema: Optional[Dict[str, Any]] = None,
        schema_name: str = "civora_json",
    ) -> AIResponse:
        data = self._post_chat(model=model, messages=messages, json_mode=True)
        text = str(dict(data.get("message") or {}).get("content") or "")
        json.loads(text)
        return AIResponse(output_text=text, provider=self.name, model=model, raw=data)


class _LegacyResponses:
    def __init__(self, provider: AIProvider) -> None:
        self.provider = provider

    def create(self, *, model: str, input: List[Dict[str, str]], text: Optional[Dict[str, Any]] = None, **_: Any) -> AIResponse:
        fmt = dict(dict(text or {}).get("format") or {})
        schema = dict(fmt.get("schema") or {})
        schema_name = str(fmt.get("name") or "civora_json")
        if schema:
            return self.provider.generate_json(model=model, messages=input, schema=schema, schema_name=schema_name)
        return self.provider.generate_text(model=model, messages=input)


class LegacyResponsesClient:
    def __init__(self, provider: AIProvider) -> None:
        self.responses = _LegacyResponses(provider)


_provider_cache: Optional[AIProvider] = None
_legacy_cache: Optional[LegacyResponsesClient] = None


def _provider_name() -> str:
    configured = str(os.getenv("CIVORA_AI_PROVIDER") or os.getenv("CIVORA_LLM_PROVIDER") or "").strip().lower()
    if configured:
        return configured
    return "openai" if str(os.getenv("OPENAI_API_KEY") or "").strip() else "none"


def get_ai_provider() -> AIProvider:
    global _provider_cache
    if _provider_cache is not None:
        return _provider_cache
    provider_name = _provider_name()
    if provider_name in {"none", "disabled", "off"}:
        _provider_cache = DisabledAIProvider()
    elif provider_name in {"ollama", "local"}:
        _provider_cache = OllamaProvider()
    elif provider_name == "openai":
        _provider_cache = OpenAIProvider()
    else:
        raise AIProviderUnavailable(f"Unsupported Civora language provider: {provider_name}")
    return _provider_cache


def get_legacy_responses_client() -> LegacyResponsesClient:
    global _legacy_cache
    if _legacy_cache is None:
        _legacy_cache = LegacyResponsesClient(get_ai_provider())
    return _legacy_cache


def reset_ai_provider_cache() -> None:
    global _provider_cache, _legacy_cache
    _provider_cache = None
    _legacy_cache = None
