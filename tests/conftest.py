from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import Settings  # noqa: E402

VALID_MISSION = {
    "title": "Backyard Bird Count",
    "introduction": (
        "Spend a few quiet minutes noticing the birds that already live near you, "
        "without leaving your own outdoor space."
    ),
    "steps": [
        "Find a safe spot to stand or sit with a clear view of trees or sky.",
        "Watch quietly and count each bird you can see for three full minutes.",
        "Note the smallest bird and the largest bird you spotted today.",
    ],
    "observation_goal": "Count at least three birds and describe the smallest one you saw.",
    "completion_condition": "You counted three birds and can name one thing the smallest one was doing.",
    "safety_notes": [
        "Stay on stable ground and keep traffic in mind if your space borders a road.",
        "Observe birds from a distance; never feed, chase, or touch wildlife.",
    ],
}


@pytest.fixture
def valid_mission_payload() -> dict:
    return json.loads(json.dumps(VALID_MISSION))


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        provider="openrouter",
        model="google/gemma-4-26b-a4b-it:free",
        base_url="https://openrouter.ai/api/v1",
        api_key_env="OPENROUTER_API_KEY",
        api_key="test-key-not-real",
        timeout_seconds=5.0,
        max_retries=2,
        max_generation_attempts=3,
        retry_backoff_seconds=0.0,
        db_path=tmp_path / "test.db",
        max_tokens=1200,
        temperature=0.7,
    )
