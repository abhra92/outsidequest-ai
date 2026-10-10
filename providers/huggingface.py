from __future__ import annotations

import requests

from .openai_compatible import OpenAICompatibleProvider

HF_ROUTER_BASE_URL = "https://router.huggingface.co/v1"


class HuggingFaceProvider(OpenAICompatibleProvider):
    name = "huggingface"

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        timeout: float = 30.0,
        max_retries: int = 2,
        backoff_seconds: float = 1.0,
        session: requests.Session | None = None,
        base_url: str = HF_ROUTER_BASE_URL,
        max_tokens: int = 1200,
        temperature: float = 0.7,
    ) -> None:
        super().__init__(
            base_url,
            api_key,
            model,
            timeout=timeout,
            max_retries=max_retries,
            backoff_seconds=backoff_seconds,
            session=session,
            provider_label="huggingface",
            max_tokens=max_tokens,
            temperature=temperature,
        )
