from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Environment = Literal["garden", "park", "neighborhood", "other_public"]
Difficulty = Literal["easy", "moderate", "challenging"]
Interest = Literal["plants", "birds", "colors", "sounds", "movement", "mindful"]
Duration = Literal[10, 20, 30]

ENVIRONMENT_LABELS: dict[str, str] = {
    "garden": "Garden / backyard",
    "park": "Park",
    "neighborhood": "Neighborhood",
    "other_public": "Other safe public outdoor space",
}

DIFFICULTY_LABELS: dict[str, str] = {
    "easy": "Easy",
    "moderate": "Moderate",
    "challenging": "Challenging",
}

INTEREST_LABELS: dict[str, str] = {
    "plants": "Plants",
    "birds": "Birds",
    "colors": "Colors",
    "sounds": "Sounds",
    "movement": "Movement",
    "mindful": "Mindful observation",
}

MAX_STEPS_BY_DURATION: dict[int, int] = {10: 4, 20: 6, 30: 8}

_FORBIDDEN_MARKUP = re.compile(
    r"<\s*script|<\s*iframe|<\s*object|<\s*embed|<\s*style|<\s*a\s+href|javascript:|data:text/html",
    re.IGNORECASE,
)


def _reject_markup(value: str, field_name: str) -> str:
    if _FORBIDDEN_MARKUP.search(value):
        raise ValueError(f"{field_name} must not contain HTML markup or scripts.")
    return value


class MissionRequest(BaseModel):
    duration_minutes: Duration
    environment: Environment
    difficulty: Difficulty
    interests: list[Interest] = Field(default_factory=list, max_length=6)


class MissionContent(BaseModel):
    title: str = Field(min_length=3, max_length=90)
    introduction: str = Field(min_length=20, max_length=600)
    steps: list[str] = Field(min_length=3, max_length=8)
    observation_goal: str = Field(min_length=10, max_length=400)
    completion_condition: str = Field(min_length=10, max_length=400)
    safety_notes: list[str] = Field(min_length=1, max_length=6)

    @field_validator("title", "introduction", "observation_goal", "completion_condition")
    @classmethod
    def _text_is_clean(cls, value: str) -> str:
        return _reject_markup(value, "text")

    @field_validator("steps", "safety_notes")
    @classmethod
    def _items_are_clean(cls, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        for index, item in enumerate(values):
            stripped = item.strip()
            if not stripped:
                raise ValueError("list items must not be empty")
            if len(stripped) < 5:
                raise ValueError(f"list item {index + 1} is too short")
            if len(stripped) > 300:
                raise ValueError(f"list item {index + 1} is too long (max 300 chars)")
            cleaned.append(_reject_markup(stripped, f"list item {index + 1}"))
        return cleaned


class Mission(MissionContent):
    duration_minutes: Duration
    environment: Environment
    difficulty: Difficulty
    source: Literal["ai", "curated_fallback"]
    provider: str | None = None
    model: str | None = None
