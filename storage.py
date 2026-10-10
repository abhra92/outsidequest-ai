from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from models import Mission

MAX_REFLECTION_LENGTH = 500

_SCHEMA = """
CREATE TABLE IF NOT EXISTS completions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    completed_at TEXT NOT NULL,
    title TEXT NOT NULL,
    duration_minutes INTEGER NOT NULL,
    environment TEXT NOT NULL,
    difficulty TEXT NOT NULL,
    source TEXT NOT NULL,
    reflection TEXT
);
"""


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


class MissionStore:
    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def init_db(self) -> None:
        with self._connect() as connection:
            connection.executescript(_SCHEMA)

    def save_completion(
        self,
        mission: Mission,
        reflection: str | None = None,
        *,
        completed_at: str | None = None,
    ) -> int:
        clean_reflection = (reflection or "").strip()
        if len(clean_reflection) > MAX_REFLECTION_LENGTH:
            clean_reflection = clean_reflection[:MAX_REFLECTION_LENGTH]
        stamp = completed_at or _utc_now()
        with self._connect() as connection:
            connection.executescript(_SCHEMA)
            cursor = connection.execute(
                """
                INSERT INTO completions (
                    created_at, completed_at, title, duration_minutes,
                    environment, difficulty, source, reflection
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    stamp,
                    stamp,
                    mission.title,
                    int(mission.duration_minutes),
                    mission.environment,
                    mission.difficulty,
                    mission.source,
                    clean_reflection or None,
                ),
            )
            return int(cursor.lastrowid)

    def list_completions(self, limit: int = 50) -> list[dict]:
        with self._connect() as connection:
            connection.executescript(_SCHEMA)
            rows = connection.execute(
                "SELECT * FROM completions ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def count(self) -> int:
        with self._connect() as connection:
            connection.executescript(_SCHEMA)
            row = connection.execute("SELECT COUNT(*) AS n FROM completions").fetchone()
        return int(row["n"])

    def clear(self) -> int:
        with self._connect() as connection:
            connection.executescript(_SCHEMA)
            cursor = connection.execute("DELETE FROM completions")
            return cursor.rowcount
