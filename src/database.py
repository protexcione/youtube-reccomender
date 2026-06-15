"""
Gestione SQLite: inizializzazione schema e operazioni CRUD.
"""

import sqlite3
import logging
from datetime import datetime
from src.config import DB_PATH

logger = logging.getLogger(__name__)

# Timeout connessione: evita blocchi infiniti su lock SQLite
_CONNECT_TIMEOUT = 10  # secondi


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=_CONNECT_TIMEOUT)
    conn.row_factory = sqlite3.Row
    # WAL mode: permette letture concorrenti senza bloccare le scritture
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Crea le tabelle se non esistono."""
    try:
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

            # Aggiunge l'indice UNIQUE solo se non esiste già.
            # Prima rimuove eventuali duplicati rimasti da run precedenti
            # (mantiene solo la riga con id più alto per ogni coppia profile/video_id).
            idx_exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='index' AND name='idx_seed_dedup'"
            ).fetchone()
            if not idx_exists:
                conn.executescript("""
                    DELETE FROM seed_watches
                    WHERE id NOT IN (
                        SELECT MAX(id) FROM seed_watches GROUP BY profile, video_id
                    );
                    CREATE UNIQUE INDEX idx_seed_dedup ON seed_watches (profile, video_id);
                """)
                logger.info("Indice UNIQUE creato su seed_watches (dedup eseguito)")

        logger.info("Database inizializzato: %s", DB_PATH)
    except sqlite3.Error as e:
        logger.error("Errore inizializzazione DB: %s", e)
        raise


def insert_seed_watch(profile: str, video_id: str, title: str, channel: str) -> bool:
    """
    Inserisce un seed watch. Restituisce True se inserito, False se già presente (duplicato).
    """
    try:
        with get_connection() as conn:
            conn.execute(
                """INSERT OR IGNORE INTO seed_watches
                   (profile, video_id, title, channel, watched_at)
                   VALUES (?,?,?,?,?)""",
                (profile, video_id, title, channel, datetime.utcnow().isoformat()),
            )
            inserted = conn.execute("SELECT changes()").fetchone()[0]
            if inserted == 0:
                logger.debug("Duplicato ignorato: %s/%s", profile, video_id)
                return False
            return True
    except sqlite3.Error as e:
        logger.error("Errore INSERT seed_watch [%s/%s]: %s", profile, video_id, e)
        return False


def insert_recommendation(
    profile: str, day: int, position: int,
    video_id: str, title: str, channel: str, category: str = None
) -> bool:
    """Inserisce una raccomandazione. Restituisce True se successo."""
    try:
        with get_connection() as conn:
            conn.execute(
                """INSERT INTO recommendations
                   (profile, day, position, video_id, title, channel, category, scraped_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (profile, day, position, video_id, title, channel, category,
                 datetime.utcnow().isoformat()),
            )
            return True
    except sqlite3.Error as e:
        logger.error("Errore INSERT recommendation [%s/day%d]: %s", profile, day, e)
        return False


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
    try:
        with get_connection() as conn:
            return [dict(r) for r in conn.execute(query, params).fetchall()]
    except sqlite3.Error as e:
        logger.error("Errore SELECT recommendations: %s", e)
        return []


def get_seed_watch_count(profile: str = None) -> int:
    """Restituisce il numero di seed watch salvati (per debug/verifica)."""
    query = "SELECT COUNT(*) FROM seed_watches"
    params = []
    if profile:
        query += " WHERE profile = ?"
        params.append(profile)
    try:
        with get_connection() as conn:
            return conn.execute(query, params).fetchone()[0]
    except sqlite3.Error as e:
        logger.error("Errore COUNT seed_watches: %s", e)
        return -1
