from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


class ProviderError(Exception):
    """Base class for inference provider failures."""


class ProviderConfigError(ProviderError):
    pass


class ProviderAuthError(ProviderError):
    pass


class ProviderRateLimitError(ProviderError):
    pass


class ProviderTimeoutError(ProviderError):
    pass


class ProviderServerError(ProviderError):
    pass


class ProviderBadResponseError(ProviderError):
    pass


@dataclass(frozen=True)
class GenerationResult:
    text: str
    provider: str
    model: str
    latency_ms: int
    finish_reason: str | None = None
    attempts: int = field(default=1)


class InferenceProvider(ABC):
    name: str = "base"

    @abstractmethod
    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        json_mode: bool = False,
    ) -> GenerationResult:
        raise NotImplementedError


def sleep_seconds(seconds: float) -> None:
    if seconds > 0:
        time.sleep(seconds)
