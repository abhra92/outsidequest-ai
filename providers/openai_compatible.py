from __future__ import annotations

import json
import time
from typing import Any

import requests

from .base import (
    GenerationResult,
    InferenceProvider,
    ProviderAuthError,
    ProviderBadResponseError,
    ProviderRateLimitError,
    ProviderServerError,
    ProviderTimeoutError,
    sleep_seconds,
)


class OpenAICompatibleProvider(InferenceProvider):
    name = "openai_compatible"

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        *,
        timeout: float = 30.0,
        max_retries: int = 2,
        backoff_seconds: float = 1.0,
        session: requests.Session | None = None,
        provider_label: str | None = None,
        max_tokens: int = 1200,
        temperature: float = 0.7,
    ) -> None:
        if not api_key:
            raise ProviderAuthError("API key is empty.")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_retries = max(0, max_retries)
        self.backoff_seconds = backoff_seconds
        self.max_tokens = max_tokens
        self.temperature = temperature
        self._session = session or requests.Session()
        if provider_label:
            self.name = provider_label

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _payload(
        self, prompt: str, system: str | None, json_mode: bool
    ) -> dict[str, Any]:
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        return payload

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}/chat/completions"
        last_error: Exception | None = None
        dropped_response_format = False

        for attempt in range(self.max_retries + 1):
            try:
                response = self._session.post(
                    url, headers=self._headers(), json=payload, timeout=self.timeout
                )
            except requests.Timeout:
                last_error = ProviderTimeoutError(
                    f"Request to {self.base_url} timed out after {self.timeout}s."
                )
            except requests.RequestException as exc:
                last_error = ProviderServerError(
                    f"Network error calling {self.base_url}: {exc.__class__.__name__}."
                )
            else:
                if response.status_code == 200:
                    try:
                        return response.json()
                    except ValueError as exc:
                        raise ProviderBadResponseError(
                            "Provider returned a non-JSON response body."
                        ) from exc

                body = _safe_body(response)
                if response.status_code in (401, 403):
                    raise ProviderAuthError(
                        f"Authentication failed ({response.status_code}) at {self.base_url}. "
                        "Check your API key environment variable."
                    )
                if response.status_code == 404:
                    if "response_format" in str(payload) and not dropped_response_format:
                        dropped_response_format = True
                        payload = {
                            k: v for k, v in payload.items() if k != "response_format"
                        }
                        continue
                    raise ProviderServerError(
                        f"Model or endpoint not found (404) at {self.base_url}."
                    )
                if response.status_code == 429:
                    last_error = ProviderRateLimitError(
                        "Provider rate limit reached (429). Retry later."
                    )
                elif response.status_code >= 500:
                    last_error = ProviderServerError(
                        f"Provider server error ({response.status_code})."
                    )
                elif response.status_code == 400 and "response_format" in str(payload):
                    payload = {
                        k: v for k, v in payload.items() if k != "response_format"
                    }
                    continue
                else:
                    raise ProviderServerError(
                        f"Unexpected status {response.status_code} from provider: {body[:200]}"
                    )

            if attempt < self.max_retries:
                sleep_seconds(self.backoff_seconds * (2**attempt))

        assert last_error is not None
        raise last_error

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        json_mode: bool = False,
    ) -> GenerationResult:
        started = time.monotonic()
        data = self._post(self._payload(prompt, system, json_mode))
        try:
            choice = data["choices"][0]
            text = choice["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderBadResponseError(
                "Provider response missing choices[0].message.content."
            ) from exc
        if not isinstance(text, str) or not text.strip():
            raise ProviderBadResponseError("Provider returned empty message content.")

        model_used = data.get("model") or self.model
        finish = choice.get("finish_reason")
        return GenerationResult(
            text=text,
            provider=self.name,
            model=str(model_used),
            latency_ms=int((time.monotonic() - started) * 1000),
            finish_reason=str(finish) if finish else None,
        )


def _safe_body(response: requests.Response) -> str:
    try:
        return response.text
    except Exception:
        return ""


def extract_json_text(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        first_newline = text.find("\n")
        closing = text.rfind("```")
        if closing > 0 and first_newline != -1 and closing > first_newline:
            text = text[first_newline + 1 : closing].strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        text = text[start : end + 1]
    return text


def loads_lenient(raw: str) -> Any:
    return json.loads(extract_json_text(raw))
