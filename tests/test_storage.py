from __future__ import annotations

import sqlite3

from mission_engine import load_fallbacks, select_fallback
from models import MissionRequest
from storage import MAX_REFLECTION_LENGTH, MissionStore


def make_request(**overrides) -> MissionRequest:
    payload = {
        "duration_minutes": 10,
        "environment": "garden",
        "difficulty": "easy",
        "interests": [],
    }
    payload.update(overrides)
    return MissionRequest(**payload)


def test_database_created_and_completion_saved(tmp_path):
    db_path = tmp_path / "history.db"
    store = MissionStore(db_path)
    store.init_db()

    mission = select_fallback(make_request())
    row_id = store.save_completion(mission, "Saw a robin.")

    assert db_path.exists()
    assert row_id >= 1
    assert store.count() == 1

    rows = store.list_completions()
    assert rows[0]["title"] == mission.title
    assert rows[0]["reflection"] == "Saw a robin."
    assert rows[0]["source"] == "curated_fallback"
    assert rows[0]["duration_minutes"] == 10


def test_list_order_newest_first(tmp_path):
    store = MissionStore(tmp_path / "history.db")
    first = select_fallback(make_request())
    second = select_fallback(make_request(duration_minutes=20, environment="park"))

    store.save_completion(first, completed_at="2026-10-01T10:00:00+00:00")
    store.save_completion(second, completed_at="2026-10-02T10:00:00+00:00")

    rows = store.list_completions()
    assert rows[0]["title"] == second.title
    assert rows[1]["title"] == first.title


def test_clear_history(tmp_path):
    store = MissionStore(tmp_path / "history.db")
    mission = select_fallback(make_request())
    store.save_completion(mission)
    store.save_completion(mission)

    removed = store.clear()
    assert removed == 2
    assert store.count() == 0


def test_reflection_truncated(tmp_path):
    store = MissionStore(tmp_path / "history.db")
    mission = select_fallback(make_request())
    long_reflection = "x" * (MAX_REFLECTION_LENGTH + 200)
    store.save_completion(mission, long_reflection)

    rows = store.list_completions()
    assert len(rows[0]["reflection"]) == MAX_REFLECTION_LENGTH


def test_schema_contains_no_location_or_credentials(tmp_path):
    db_path = tmp_path / "history.db"
    store = MissionStore(db_path)
    store.init_db()

    with sqlite3.connect(db_path) as connection:
        columns = [row[1] for row in connection.execute("PRAGMA table_info(completions)")]

    forbidden = {"gps", "lat", "lon", "latitude", "longitude", "password", "token", "api_key", "email"}
    assert forbidden.isdisjoint(columns)


def test_save_without_reflection(tmp_path):
    store = MissionStore(tmp_path / "history.db")
    mission = select_fallback(make_request())
    store.save_completion(mission, None)

    rows = store.list_completions()
    assert rows[0]["reflection"] is None


def test_select_fallback_prefers_environment_match():
    mission = select_fallback(make_request(environment="neighborhood", duration_minutes=20))
    assert mission.environment == "neighborhood"
    assert mission.duration_minutes == 20


def test_load_fallbacks_cached_and_validated():
    first = load_fallbacks()
    second = load_fallbacks()
    assert first is second
    durations = {int(m.duration_minutes) for m in first}
    assert durations == {10, 20, 30}
