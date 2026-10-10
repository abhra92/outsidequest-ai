from __future__ import annotations

import pytest
import requests

from config import ConfigError, load_settings
from providers import (
    HuggingFaceProvider,
    OpenAICompatibleProvider,
    ProviderAuthError,
    ProviderBadResponseError,
    ProviderConfigError,
    ProviderRateLimitError,
    ProviderServerError,
    ProviderTimeoutError,
    extract_json_text,
    get_provider,
)


class FakeResponse:
    def __init__(self, status_code: int, payload=None, text: str = ""):
        self.status_code = status_code
        self._payload = payload
        self.text = text or ("" if payload is None else str(payload))

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def post(self, url, headers=None, json=None, timeout=None):
        self.calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def chat_payload(content: str = "hello") -> dict:
    return {
        "choices": [
            {"message": {"role": "assistant", "content": content}, "finish_reason": "stop"}
        ],
        "model": "test-model",
    }


def make_provider(session, **kwargs) -> OpenAICompatibleProvider:
    options = {
        "base_url": "https://example.test/v1",
        "api_key": "test-key",
        "model": "test-model",
        "timeout": 1.0,
        "max_retries": 2,
        "backoff_seconds": 0.0,
        "session": session,
    }
    options.update(kwargs)
    return OpenAICompatibleProvider(**options)


def test_generate_success():
    session = FakeSession([FakeResponse(200, chat_payload("result"))])
    provider = make_provider(session)
    result = provider.generate("hi", system="sys", json_mode=True)

    assert result.text == "result"
    assert result.provider == "openai_compatible"
    assert result.model == "test-model"
    sent = session.calls[0]["json"]
    assert sent["response_format"] == {"type": "json_object"}
    assert sent["messages"][0] == {"role": "system", "content": "sys"}
    assert session.calls[0]["headers"]["Authorization"] == "Bearer test-key"


def test_missing_api_key_raises():
    with pytest.raises(ProviderAuthError):
        OpenAICompatibleProvider("https://example.test/v1", "", "model")


def test_auth_error_401_no_retry():
    session = FakeSession([FakeResponse(401, {"error": "unauthorized"})])
    provider = make_provider(session)

    with pytest.raises(ProviderAuthError):
        provider.generate("hi")

    assert len(session.calls) == 1


def test_rate_limit_retries_are_bounded():
    session = FakeSession(
        [FakeResponse(429, {"error": "slow down"}) for _ in range(10)]
    )
    provider = make_provider(session, max_retries=2)

    with pytest.raises(ProviderRateLimitError):
        provider.generate("hi")

    assert len(session.calls) == 3


def test_rate_limit_then_success():
    session = FakeSession(
        [
            FakeResponse(429, {"error": "slow down"}),
            FakeResponse(200, chat_payload("ok")),
        ]
    )
    provider = make_provider(session, max_retries=2)
    result = provider.generate("hi")
    assert result.text == "ok"
    assert len(session.calls) == 2


def test_server_error_maps_to_provider_error():
    session = FakeSession([FakeResponse(503, {"error": "down"}) for _ in range(3)])
    provider = make_provider(session, max_retries=1)

    with pytest.raises(ProviderServerError):
        provider.generate("hi")

    assert len(session.calls) == 2


def test_timeout_maps_to_provider_timeout():
    session = FakeSession(
        [requests.Timeout("boom"), requests.Timeout("boom"), requests.Timeout("boom")]
    )
    provider = make_provider(session, max_retries=1)

    with pytest.raises(ProviderTimeoutError):
        provider.generate("hi")

    assert len(session.calls) == 2


def test_network_error_maps_to_server_error():
    session = FakeSession(
        [requests.ConnectionError("down"), requests.ConnectionError("down")]
    )
    provider = make_provider(session, max_retries=0)

    with pytest.raises(ProviderServerError):
        provider.generate("hi")


def test_response_format_unsupported_falls_back():
    session = FakeSession(
        [
            FakeResponse(400, {"error": "response_format not supported"}),
            FakeResponse(200, chat_payload("ok without json mode")),
        ]
    )
    provider = make_provider(session)
    result = provider.generate("hi", json_mode=True)

    assert result.text == "ok without json mode"
    assert "response_format" not in session.calls[1]["json"]


def test_malformed_provider_body():
    session = FakeSession([FakeResponse(200, payload=None)])
    provider = make_provider(session)

    with pytest.raises(ProviderBadResponseError):
        provider.generate("hi")


def test_empty_content_rejected():
    session = FakeSession([FakeResponse(200, chat_payload("   "))])
    provider = make_provider(session)

    with pytest.raises(ProviderBadResponseError):
        provider.generate("hi")


def test_get_provider_openrouter(settings):
    provider = get_provider(settings)
    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.base_url == "https://openrouter.ai/api/v1"
    assert provider.model == "google/gemma-4-26b-a4b-it:free"


def test_get_provider_huggingface(settings):
    from dataclasses import replace

    hf = replace(
        settings,
        provider="huggingface",
        api_key="hf-token",
        api_key_env="HF_TOKEN",
        base_url="",
    )
    provider = get_provider(hf)
    assert isinstance(provider, HuggingFaceProvider)
    assert provider.base_url == "https://router.huggingface.co/v1"


def test_get_provider_missing_key(settings):
    from dataclasses import replace

    no_key = replace(settings, api_key=None)
    with pytest.raises(ProviderConfigError) as excinfo:
        get_provider(no_key)
    assert "OPENROUTER_API_KEY" in str(excinfo.value)


def test_load_settings_unknown_provider():
    with pytest.raises(ConfigError):
        load_settings(env={"OUTSIDEQUEST_PROVIDER": "nope"})


def test_load_settings_openai_compatible_requires_base_url():
    env = {"OUTSIDEQUEST_PROVIDER": "openai_compatible", "OUTSIDEQUEST_MODEL": "m"}
    with pytest.raises(ConfigError):
        load_settings(env=env)


def test_load_settings_reads_env(tmp_path):
    env = {
        "OUTSIDEQUEST_PROVIDER": "openrouter",
        "OPENROUTER_API_KEY": "abc",
        "OUTSIDEQUEST_DB_PATH": str(tmp_path / "x.db"),
        "OUTSIDEQUEST_MAX_RETRIES": "4",
    }
    settings = load_settings(env=env)
    assert settings.api_key == "abc"
    assert settings.max_retries == 4
    assert settings.model == "google/gemma-4-26b-a4b-it:free"
    assert settings.has_credentials


def test_extract_json_text_handles_fences_and_noise():
    raw = 'Sure! ```json\n{"a": 1}\n``` hope that helps'
    assert extract_json_text(raw) == '{"a": 1}'
