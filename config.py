from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")

DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "outsidequest.db"


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class ProviderPreset:
    base_url: str
    api_key_env: str
    default_model: str


PROVIDER_PRESETS: dict[str, ProviderPreset] = {
    "openrouter": ProviderPreset(
        base_url="https://openrouter.ai/api/v1",
        api_key_env="OPENROUTER_API_KEY",
        default_model="google/gemma-4-26b-a4b-it:free",
    ),
    "huggingface": ProviderPreset(
        base_url="https://router.huggingface.co/v1",
        api_key_env="HF_TOKEN",
        default_model="google/gemma-4-26B-A4B-it",
    ),
    "openai_compatible": ProviderPreset(
        base_url="",
        api_key_env="OUTSIDEQUEST_API_KEY",
        default_model="",
    ),
}


@dataclass(frozen=True)
class Settings:
    provider: str
    model: str
    base_url: str
    api_key_env: str
    api_key: str | None
    timeout_seconds: float
    max_retries: int
    max_generation_attempts: int
    retry_backoff_seconds: float
    db_path: Path
    max_tokens: int
    temperature: float

    @property
    def has_credentials(self) -> bool:
        return bool(self.api_key)


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be a number, got {raw!r}") from exc


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer, got {raw!r}") from exc


def load_settings(env: dict[str, str] | None = None) -> Settings:
    source = os.environ if env is None else env

    provider = (source.get("OUTSIDEQUEST_PROVIDER") or "openrouter").strip().lower()
    if provider not in PROVIDER_PRESETS:
        known = ", ".join(sorted(PROVIDER_PRESETS))
        raise ConfigError(
            f"Unknown OUTSIDEQUEST_PROVIDER {provider!r}. Known providers: {known}."
        )

    preset = PROVIDER_PRESETS[provider]

    base_url = (source.get("OUTSIDEQUEST_BASE_URL") or preset.base_url).rstrip("/")
    if not base_url:
        raise ConfigError(
            "OUTSIDEQUEST_BASE_URL must be set when OUTSIDEQUEST_PROVIDER=openai_compatible."
        )

    model = (
        source.get("OUTSIDEQUEST_MODEL") or preset.default_model
    ).strip()
    if not model:
        raise ConfigError(
            "OUTSIDEQUEST_MODEL must be set when OUTSIDEQUEST_PROVIDER=openai_compatible."
        )

    api_key_env = source.get("OUTSIDEQUEST_API_KEY_ENV") or preset.api_key_env
    api_key = source.get(api_key_env) or source.get("OUTSIDEQUEST_API_KEY")

    timeout = _env_float("OUTSIDEQUEST_TIMEOUT", 30.0) if env is None else float(
        source.get("OUTSIDEQUEST_TIMEOUT", 30.0)
    )
    max_retries = _env_int("OUTSIDEQUEST_MAX_RETRIES", 2) if env is None else int(
        source.get("OUTSIDEQUEST_MAX_RETRIES", 2)
    )
    attempts = _env_int("OUTSIDEQUEST_MAX_ATTEMPTS", 3) if env is None else int(
        source.get("OUTSIDEQUEST_MAX_ATTEMPTS", 3)
    )
    backoff = _env_float("OUTSIDEQUEST_RETRY_BACKOFF", 1.0) if env is None else float(
        source.get("OUTSIDEQUEST_RETRY_BACKOFF", 1.0)
    )
    max_tokens = _env_int("OUTSIDEQUEST_MAX_TOKENS", 1200) if env is None else int(
        source.get("OUTSIDEQUEST_MAX_TOKENS", 1200)
    )
    temperature = _env_float("OUTSIDEQUEST_TEMPERATURE", 0.7) if env is None else float(
        source.get("OUTSIDEQUEST_TEMPERATURE", 0.7)
    )

    db_raw = source.get("OUTSIDEQUEST_DB_PATH") or str(DEFAULT_DB_PATH)
    db_path = Path(db_raw).expanduser()

    if max_retries < 0 or attempts < 1:
        raise ConfigError("OUTSIDEQUEST_MAX_RETRIES >= 0 and OUTSIDEQUEST_MAX_ATTEMPTS >= 1 required.")

    return Settings(
        provider=provider,
        model=model,
        base_url=base_url,
        api_key_env=api_key_env,
        api_key=api_key,
        timeout_seconds=timeout,
        max_retries=max_retries,
        max_generation_attempts=attempts,
        retry_backoff_seconds=backoff,
        db_path=db_path,
        max_tokens=max_tokens,
        temperature=temperature,
    )
