from __future__ import annotations

from collections.abc import Sequence

from config import Settings

from .base import (
    GenerationResult,
    InferenceProvider,
    ProviderAuthError,
    ProviderBadResponseError,
    ProviderConfigError,
    ProviderError,
    ProviderRateLimitError,
    ProviderServerError,
    ProviderTimeoutError,
)
from .huggingface import HF_ROUTER_BASE_URL, HuggingFaceProvider
from .openai_compatible import OpenAICompatibleProvider, extract_json_text, loads_lenient

__all__ = [
    "GenerationResult",
    "InferenceProvider",
    "ProviderAuthError",
    "ProviderBadResponseError",
    "ProviderConfigError",
    "ProviderError",
    "ProviderRateLimitError",
    "ProviderServerError",
    "ProviderTimeoutError",
    "HuggingFaceProvider",
    "OpenAICompatibleProvider",
    "StaticProvider",
    "extract_json_text",
    "get_provider",
    "loads_lenient",
    "HF_ROUTER_BASE_URL",
]


class StaticProvider(InferenceProvider):
    name = "static"

    def __init__(self, responses: Sequence[str] | None = None) -> None:
        self.responses = list(responses or [])
        self.calls = 0

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        json_mode: bool = False,
    ) -> GenerationResult:
        index = min(self.calls, max(len(self.responses) - 1, 0))
        text = self.responses[index] if self.responses else "{}"
        self.calls += 1
        return GenerationResult(
            text=text,
            provider=self.name,
            model="static-fixture",
            latency_ms=1,
        )


def get_provider(settings: Settings, session=None) -> InferenceProvider:
    if not settings.api_key:
        raise ProviderConfigError(
            f"Missing API key: set the {settings.api_key_env} environment variable "
            "(copy .env.example to .env)."
        )

    if settings.provider == "huggingface":
        return HuggingFaceProvider(
            settings.api_key,
            settings.model,
            timeout=settings.timeout_seconds,
            max_retries=settings.max_retries,
            backoff_seconds=settings.retry_backoff_seconds,
            session=session,
            base_url=settings.base_url or HF_ROUTER_BASE_URL,
            max_tokens=settings.max_tokens,
            temperature=settings.temperature,
        )

    return OpenAICompatibleProvider(
        settings.base_url,
        settings.api_key,
        settings.model,
        timeout=settings.timeout_seconds,
        max_retries=settings.max_retries,
        backoff_seconds=settings.retry_backoff_seconds,
        session=session,
        provider_label=settings.provider,
        max_tokens=settings.max_tokens,
        temperature=settings.temperature,
    )
