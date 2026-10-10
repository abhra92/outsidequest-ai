from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from pydantic import ValidationError

import safety
from config import Settings
from models import (
    ENVIRONMENT_LABELS,
    INTEREST_LABELS,
    MAX_STEPS_BY_DURATION,
    Mission,
    MissionContent,
    MissionRequest,
)
from providers import (
    ProviderConfigError,
    ProviderError,
    extract_json_text,
    get_provider,
)

FALLBACK_PATH = Path(__file__).resolve().parent / "assets" / "fallback_missions.json"

SYSTEM_PROMPT = (
    "You are OutsideQuest, a careful designer of short outdoor missions. "
    "You write practical, inclusive instructions for ordinary public outdoor spaces. "
    "You never suggest trespassing, approaching wildlife, eating or touching unknown "
    "plants or animals, unsafe roads or railways, risky physical feats, or medical or "
    "mental-health claims. You answer with a single JSON object and nothing else."
)


class MissionValidationError(Exception):
    pass


@dataclass
class MissionOutcome:
    mission: Mission
    warnings: list[str] = field(default_factory=list)
    error: str | None = None
    attempts: int = 0


def build_prompt(request: MissionRequest) -> str:
    interests = ", ".join(INTEREST_LABELS[i] for i in request.interests) or "any"
    return (
        f"Create one outdoor mission as JSON.\n"
        f"Duration: {request.duration_minutes} minutes.\n"
        f"Environment: {ENVIRONMENT_LABELS[request.environment]}.\n"
        f"Difficulty: {request.difficulty}.\n"
        f"Interests: {interests}.\n"
        f"\n"
        f"Rules:\n"
        f"- Everything must fit inside {request.duration_minutes} minutes.\n"
        f"- No special equipment. No continuous phone use; the phone stays pocketed "
        f"after reading the mission.\n"
        f"- Public, legal, ordinary spaces only. Never private or restricted areas.\n"
        f"- Do not require touching or tasting unknown plants, animals, or insects, "
        f"and never approach wildlife.\n"
        f"- Stay clear of traffic; safety_notes must mention road or traffic awareness.\n"
        f"- No medical or mental-health claims, no links, no HTML.\n"
        f"- Numbered steps: 3 to {MAX_STEPS_BY_DURATION[request.duration_minutes]} steps, "
        f"each 5 to 300 characters.\n"
        f"\n"
        f"Return JSON with exactly these keys:\n"
        f'{{"title": string (3-90 chars), "introduction": string (20-600 chars), '
        f'"steps": [string] (3-{MAX_STEPS_BY_DURATION[request.duration_minutes]} items), '
        f'"observation_goal": string (10-400 chars), '
        f'"completion_condition": string (10-400 chars), '
        f'"safety_notes": [string] (1-6 items, each 5-300 chars)}}'
    )


def parse_mission(raw_text: str, request: MissionRequest, *, provider: str, model: str) -> Mission:
    try:
        payload = json.loads(extract_json_text(raw_text))
    except (json.JSONDecodeError, ValueError) as exc:
        raise MissionValidationError(f"Model output is not valid JSON ({exc.__class__.__name__}).") from exc
    if not isinstance(payload, dict):
        raise MissionValidationError("Model output must be a JSON object.")

    try:
        content = MissionContent.model_validate(payload)
    except ValidationError as exc:
        summary = "; ".join(
            f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in exc.errors()[:4]
        )
        raise MissionValidationError(f"Model output failed validation: {summary}") from exc

    max_steps = MAX_STEPS_BY_DURATION[int(request.duration_minutes)]
    if len(content.steps) > max_steps:
        raise MissionValidationError(
            f"Mission has {len(content.steps)} steps; limit for "
            f"{request.duration_minutes} minutes is {max_steps}."
        )

    report = safety.check_mission(content)
    if not report.ok:
        raise MissionValidationError("Safety check failed: " + "; ".join(report.violations))

    return Mission(
        **content.model_dump(),
        duration_minutes=request.duration_minutes,
        environment=request.environment,
        difficulty=request.difficulty,
        source="ai",
        provider=provider,
        model=model,
    )


@lru_cache(maxsize=1)
def load_fallbacks() -> tuple[Mission, ...]:
    data = json.loads(FALLBACK_PATH.read_text(encoding="utf-8"))
    return tuple(_to_fallback(item) for item in data)


def _to_fallback(item: dict) -> Mission:
    content = MissionContent.model_validate(item)
    return Mission(
        **content.model_dump(),
        duration_minutes=item["duration_minutes"],
        environment=item["environment"],
        difficulty=item["difficulty"],
        source="curated_fallback",
        provider=None,
        model=None,
    )


def select_fallback(request: MissionRequest) -> Mission:
    candidates = [m for m in load_fallbacks() if int(m.duration_minutes) == int(request.duration_minutes)]
    if not candidates:
        candidates = list(load_fallbacks())
    if not candidates:
        raise RuntimeError("No curated fallback missions available.")

    def score(mission: Mission) -> int:
        value = 0
        if mission.environment == request.environment:
            value += 2
        if mission.difficulty == request.difficulty:
            value += 1
        return -value

    ordered = sorted(candidates, key=score)
    return ordered[0].model_copy(deep=True)


def _fallback_outcome(request: MissionRequest, warnings: list[str], error: str | None, attempts: int) -> MissionOutcome:
    mission = select_fallback(request)
    warnings = list(warnings)
    warnings.append(
        "Curated fallback mission shown. This mission was written by the project authors, "
        "not generated by an AI model."
    )
    return MissionOutcome(mission=mission, warnings=warnings, error=error, attempts=attempts)


def generate_mission(
    request: MissionRequest,
    settings: Settings,
    provider=None,
) -> MissionOutcome:
    warnings: list[str] = []
    errors: list[str] = []
    attempts_used = 0

    if provider is None:
        try:
            provider = get_provider(settings)
        except ProviderConfigError as exc:
            return _fallback_outcome(request, [str(exc)], str(exc), 0)
        except ProviderError as exc:
            return _fallback_outcome(request, [str(exc)], str(exc), 0)

    if not settings.has_credentials:
        message = f"Missing API key: set {settings.api_key_env}."
        return _fallback_outcome(request, [message], message, 0)

    last_prompt_suffix = ""
    for attempt in range(1, settings.max_generation_attempts + 1):
        attempts_used = attempt
        prompt = build_prompt(request) + last_prompt_suffix
        try:
            result = provider.generate(prompt, system=SYSTEM_PROMPT, json_mode=True)
        except ProviderError as exc:
            errors.append(str(exc))
            if type(exc).__name__ == "ProviderAuthError":
                return _fallback_outcome(request, warnings, str(exc), attempts_used)
            last_prompt_suffix = ""
            continue

        try:
            mission = parse_mission(
                result.text,
                request,
                provider=result.provider,
                model=result.model,
            )
        except MissionValidationError as exc:
            errors.append(str(exc))
            last_prompt_suffix = (
                "\n\nYour previous answer was rejected. Reply with only a corrected "
                "JSON object that follows every rule."
            )
            continue

        return MissionOutcome(
            mission=mission,
            warnings=list(warnings),
            error=None,
            attempts=attempts_used,
        )

    return _fallback_outcome(request, warnings, "; ".join(errors) or "Generation failed.", attempts_used)
