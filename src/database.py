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
    """Crea le tabelle e gli indici se non esistono. Esegue migrazioni necessarie."""
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

                CREATE INDEX IF NOT EXISTS idx_recs_video_id
                    ON recommendations (video_id);
            """)

            _migrate_seed_watches_dedup(conn)
            _migrate_recommendations_dedup(conn)

        logger.info("Database inizializzato: %s", DB_PATH)
    except sqlite3.Error as e:
        logger.error("Errore inizializzazione DB: %s", e)
        raise


def _migrate_seed_watches_dedup(conn):
    """Aggiunge UNIQUE (profile, video_id) su seed_watches se non esiste."""
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='index' AND name='idx_seed_dedup'"
    ).fetchone()
    if not exists:
        conn.executescript("""
            DELETE FROM seed_watches
            WHERE id NOT IN (
                SELECT MAX(id) FROM seed_watches GROUP BY profile, video_id
            );
            CREATE UNIQUE INDEX idx_seed_dedup ON seed_watches (profile, video_id);
        """)
        logger.info("Indice UNIQUE creato su seed_watches (dedup eseguito)")


def _migrate_recommendations_dedup(conn):
    """Aggiunge UNIQUE (profile, day, position) su recommendations se non esiste."""
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='index' AND name='idx_recs_dedup'"
    ).fetchone()
    if not exists:
        conn.executescript("""
            DELETE FROM recommendations
            WHERE id NOT IN (
                SELECT MAX(id) FROM recommendations GROUP BY profile, day, position
            );
            CREATE UNIQUE INDEX idx_recs_dedup ON recommendations (profile, day, position);
        """)
        logger.info("Indice UNIQUE creato su recommendations (dedup eseguito)")


# ── CRUD ────────────────────────────────────────────────────────────────────

def insert_seed_watch(profile: str, video_id: str, title: str, channel: str) -> bool:
    """
    Inserisce un seed watch. Restituisce True se inserito, False se duplicato.
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
    """
    Inserisce una raccomandazione. Usa INSERT OR REPLACE per aggiornare
    se (profile, day, position) esiste già. Restituisce True se successo.
    """
    try:
        with get_connection() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO recommendations
                   (profile, day, position, video_id, title, channel, category, scraped_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (profile, day, position, video_id, title, channel, category,
                 datetime.utcnow().isoformat()),
            )
            return True
    except sqlite3.Error as e:
        logger.error("Errore INSERT recommendation [%s/day%d]: %s", profile, day, e)
        return False


# ── Query base ───────────────────────────────────────────────────────────────

def get_recommendations(profile: str = None, day: int = None) -> list:
    """Restituisce raccomandazioni filtrate per profilo e/o giorno."""
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
    """Restituisce il numero di seed watch salvati."""
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


# ── Query analisi ────────────────────────────────────────────────────────────

def get_days_collected() -> list:
    """Restituisce i giorni per cui esiste almeno una raccomandazione, ordinati."""
    try:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT DISTINCT day FROM recommendations ORDER BY day"
            ).fetchall()
            return [r[0] for r in rows]
    except sqlite3.Error as e:
        logger.error("Errore get_days_collected: %s", e)
        return []


def get_video_ids(profile: str, day: int) -> set:
    """
    Restituisce l'insieme dei video_id raccomandati a un profilo in un giorno.
    Usato per calcolare Jaccard similarity tra profili.
    """
    try:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT video_id FROM recommendations WHERE profile=? AND day=?",
                (profile, day)
            ).fetchall()
            return {r[0] for r in rows}
    except sqlite3.Error as e:
        logger.error("Errore get_video_ids [%s/day%d]: %s", profile, day, e)
        return set()


def get_profile_day_counts() -> list:
    """
    Restituisce lista di (profile, day, count) per ogni combinazione presente.
    Utile per verificare la completezza della raccolta dati.
    """
    try:
        with get_connection() as conn:
            rows = conn.execute("""
                SELECT profile, day, COUNT(*) as count
                FROM recommendations
                GROUP BY profile, day
                ORDER BY day, profile
            """).fetchall()
            return [dict(r) for r in rows]
    except sqlite3.Error as e:
        logger.error("Errore get_profile_day_counts: %s", e)
        return []


def get_top_videos(day: int = None, limit: int = 20) -> list:
    """
    Restituisce i video piu' raccomandati (presenti in piu' profili).
    Se day=None considera tutti i giorni.
    """
    params = []
    day_filter = ""
    if day is not None:
        day_filter = "WHERE day = ?"
        params.append(day)
    params.append(limit)
    try:
        with get_connection() as conn:
            rows = conn.execute(f"""
                SELECT video_id, title, channel,
                       COUNT(DISTINCT profile) as profile_count,
                       COUNT(*) as total_appearances
                FROM recommendations
                {day_filter}
                GROUP BY video_id
                ORDER BY profile_count DESC, total_appearances DESC
                LIMIT ?
            """, params).fetchall()
            return [dict(r) for r in rows]
    except sqlite3.Error as e:
        logger.error("Errore get_top_videos: %s", e)
        return []


def get_collection_summary() -> dict:
    """
    Riepilogo completo dello stato della raccolta dati.
    Restituisce: giorni raccolti, totale record, record per profilo, completezza %.
    """
    from src.config import PROFILES, SIMULATION_DAYS, HOMEPAGE_RECS_COUNT
    try:
        total = 0
        with get_connection() as conn:
            total = conn.execute("SELECT COUNT(*) FROM recommendations").fetchone()[0]

        days = get_days_collected()
        counts = get_profile_day_counts()

        expected_total = len(PROFILES) * SIMULATION_DAYS * HOMEPAGE_RECS_COUNT
        completeness = round(total / expected_total * 100, 1) if expected_total else 0

        per_profile = {}
        for row in counts:
            p = row["profile"]
            if p not in per_profile:
                per_profile[p] = {"days": 0, "records": 0}
            per_profile[p]["days"] += 1
            per_profile[p]["records"] += row["count"]

        return {
            "days_collected": days,
            "total_records": total,
            "expected_total": expected_total,
            "completeness_pct": completeness,
            "per_profile": per_profile,
        }
    except sqlite3.Error as e:
        logger.error("Errore get_collection_summary: %s", e)
        return {}
