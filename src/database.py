"""
Gestione SQLite: inizializzazione schema e operazioni CRUD.
"""

import sqlite3
import logging
from datetime import datetime
from src.config import DB_PATH

logger = logging.getLogger(__name__)


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Crea le tabelle se non esistono."""
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS seed_watches (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                profile     TEXT    NOT NULL,
                video_id    TEXT    NOT NULL,
                title       TEXT,
                channel     TEXT,
                watched_at  TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS recommendations (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                profile     TEXT    NOT NULL,
                day         INTEGER NOT NULL,
                position    INTEGER NOT NULL,
                video_id    TEXT    NOT NULL,
                title       TEXT,
                channel     TEXT,
                category    TEXT,
                scraped_at  TEXT    NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_recs_profile_day
                ON recommendations (profile, day);
        """)
    logger.info("Database inizializzato: %s", DB_PATH)


def insert_seed_watch(profile: str, video_id: str, title: str, channel: str):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO seed_watches (profile, video_id, title, channel, watched_at) VALUES (?,?,?,?,?)",
            (profile, video_id, title, channel, datetime.utcnow().isoformat()),
        )


def insert_recommendation(
    profile: str, day: int, position: int,
    video_id: str, title: str, channel: str, category: str = None
):
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO recommendations
               (profile, day, position, video_id, title, channel, category, scraped_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (profile, day, position, video_id, title, channel, category,
             datetime.utcnow().isoformat()),
        )


def get_recommendations(profile: str = None, day: int = None) -> list:
    query = "SELECT * FROM recommendations WHERE 1=1"
    params = []
    if profile:
        query += " AND profile = ?"
        params.append(profile)
    if day is not None:
        query += " AND day = ?"
        params.append(day)
    query += " ORDER BY profile, day, position"
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(query, params).fetchall()]
