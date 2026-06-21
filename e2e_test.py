"""
Test end-to-end: 1 profilo completo da zero a seed watching.

Simula lo scenario di un nuovo utente: azzera il profilo scelto,
esegue setup → seed watching → verifica DB, e produce un report.

Esegui con:
  python e2e_test.py            # usa profilo 'scienza' di default
  python e2e_test.py cucina     # profilo specifico
  python e2e_test.py scienza --keep-data   # non azzera il DB prima
"""

import sys
import time
import shutil
import sqlite3
import logging
from pathlib import Path
from datetime import datetime

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from src.logger import setup_logging
from src.config import PROFILES, PROFILES_DIR, DB_PATH, SEED_VIDEOS_PER_PROFILE
from src.driver import get_driver
from src.database import init_db, get_connection
from src.search import search_videos

logger = setup_logging("yt_recommender")

PASS = "✅ PASS"
FAIL = "❌ FAIL"
WARN = "⚠️  WARN"


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

class E2EReport:
    def __init__(self, profile: str):
        self.profile = profile
        self.started_at = datetime.now()
        self.steps: list[dict] = []
        self.metrics: dict = {}

    def step(self, name: str, ok: bool, detail: str = ""):
        icon = PASS if ok else FAIL
        self.steps.append({"name": name, "ok": ok, "detail": detail})
        detail_str = f" — {detail}" if detail else ""
        print(f"  {icon}  {name}{detail_str}")
        return ok

    def warn(self, name: str, detail: str = ""):
        self.steps.append({"name": name, "ok": True, "detail": detail})
        detail_str = f" — {detail}" if detail else ""
        print(f"  {WARN}  {name}{detail_str}")

    def metric(self, key: str, value):
        self.metrics[key] = value

    def print_summary(self):
        elapsed = (datetime.now() - self.started_at).total_seconds()
        passed = sum(1 for s in self.steps if s["ok"])
        total = len(self.steps)
        all_ok = all(s["ok"] for s in self.steps)

        print("\n" + "=" * 60)
        print(f"REPORT E2E — Profilo '{self.profile}'")
        print(f"Durata: {elapsed:.0f}s | Step: {passed}/{total} passati")
        print("=" * 60)
        for s in self.steps:
            icon = PASS if s["ok"] else FAIL
            detail = f" — {s['detail']}" if s["detail"] else ""
            print(f"  {icon}  {s['name']}{detail}")
        if self.metrics:
            print("\nMetriche:")
            for k, v in self.metrics.items():
                print(f"  {k}: {v}")
        print("=" * 60)
        if all_ok:
            print("Test end-to-end SUPERATO — pipeline completa funzionante")
        else:
            failed = [s["name"] for s in self.steps if not s["ok"]]
            print(f"Test end-to-end FALLITO — step critici: {', '.join(failed)}")
        print()
        return all_ok


def _accept_cookie_banner(driver, profile_name: str):
    try:
        btn = WebDriverWait(driver, 6).until(
            EC.element_to_be_clickable((By.XPATH,
                "//button[.//span[contains(text(),'Accetta') or contains(text(),'Accept')]]"
            ))
        )
        btn.click()
        time.sleep(2)
    except TimeoutException:
        pass


def _count_seed_watches(profile: str) -> int:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as n FROM seed_watches WHERE profile = ?", (profile,)
        ).fetchone()
        return row["n"] if row else 0


def _get_seed_watches(profile: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM seed_watches WHERE profile = ? ORDER BY watched_at",
            (profile,)
        ).fetchall()
        return [dict(r) for r in rows]


def _reset_profile_data(profile: str, keep_data: bool):
    """Azzera i dati del profilo nel DB (non tocca i cookie Chrome)."""
    if keep_data:
        logger.info("[E2E] --keep-data: dati esistenti mantenuti")
        return
    with get_connection() as conn:
        deleted = conn.execute(
            "DELETE FROM seed_watches WHERE profile = ?", (profile,)
        ).rowcount
        conn.execute(
            "DELETE FROM recommendations WHERE profile = ?", (profile,)
        )
    logger.info("[E2E] Reset DB: rimossi %d record seed_watches per '%s'", deleted, profile)


# ---------------------------------------------------------------------------
# Step 1 — Precondizioni
# ---------------------------------------------------------------------------

def step_preconditions(report: E2EReport) -> bool:
    print("\n[STEP 1] Precondizioni")
    ok = True

    # DB path esiste
    ok &= report.step("DB path configurato", DB_PATH.parent.exists(),
                      str(DB_PATH))

    # Profilo valido
    ok &= report.step(f"Profilo '{report.profile}' presente in config",
                      report.profile in PROFILES,
                      str(list(PROFILES[report.profile])))

    # Cartella profilo Chrome
    profile_dir = PROFILES_DIR / report.profile
    has_chrome_data = profile_dir.exists() and any(profile_dir.iterdir())
    if has_chrome_data:
        size_kb = sum(f.stat().st_size for f in profile_dir.rglob("*") if f.is_file()) / 1024
        report.step("Profilo Chrome esistente (cookie pronti)", True,
                    f"{size_kb:.0f} KB")
    else:
        report.warn("Profilo Chrome assente — verrà inizializzato da zero",
                    "esegui setup_profiles.py per pre-riscaldare il profilo")
        ok &= True  # non bloccante

    return ok


# ---------------------------------------------------------------------------
# Step 2 — Inizializzazione DB
# ---------------------------------------------------------------------------

def step_init_db(report: E2EReport) -> bool:
    print("\n[STEP 2] Inizializzazione database")
    try:
        init_db()
        # Verifica tabelle
        with get_connection() as conn:
            tables = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()}
        report.step("Tabella seed_watches", "seed_watches" in tables)
        report.step("Tabella recommendations", "recommendations" in tables)
        return True
    except Exception as e:
        report.step("Inizializzazione DB", False, str(e))
        return False


# ---------------------------------------------------------------------------
# Step 3 — Reset dati profilo
# ---------------------------------------------------------------------------

def step_reset(report: E2EReport, keep_data: bool) -> bool:
    print("\n[STEP 3] Reset dati profilo nel DB")
    try:
        before = _count_seed_watches(report.profile)
        _reset_profile_data(report.profile, keep_data)
        after = _count_seed_watches(report.profile)
        if keep_data:
            report.warn("Reset saltato (--keep-data)", f"{before} record esistenti mantenuti")
        else:
            report.step("Reset seed_watches nel DB", True,
                        f"{before} record rimossi → {after} record")
        return True
    except Exception as e:
        report.step("Reset DB", False, str(e))
        return False


# ---------------------------------------------------------------------------
# Step 4 — Caricamento YouTube e accettazione cookie
# ---------------------------------------------------------------------------

def step_youtube_load(report: E2EReport, driver) -> bool:
    print("\n[STEP 4] Caricamento YouTube")
    try:
        driver.get("https://www.youtube.com")
        time.sleep(3)
        _accept_cookie_banner(driver, report.profile)

        title_ok = "YouTube" in driver.title
        report.step("YouTube caricato", title_ok, driver.title)

        # Verifica che siamo sulla homepage (non su una pagina di errore)
        url_ok = "youtube.com" in driver.current_url
        report.step("URL homepage corretta", url_ok, driver.current_url)

        return title_ok and url_ok
    except Exception as e:
        report.step("Caricamento YouTube", False, str(e))
        return False


# ---------------------------------------------------------------------------
# Step 5 — Ricerca video seed
# ---------------------------------------------------------------------------

def step_search(report: E2EReport, driver) -> list[dict]:
    print("\n[STEP 5] Ricerca video seed")
    channels = PROFILES[report.profile]
    all_videos = []
    seen_ids = set()
    per_channel = SEED_VIDEOS_PER_PROFILE // len(channels) + 1

    for channel in channels:
        if len(all_videos) >= SEED_VIDEOS_PER_PROFILE:
            break
        try:
            results = search_videos(driver, channel, max_results=per_channel)
            new = [v for v in results if v["video_id"] not in seen_ids]
            for v in new:
                if len(all_videos) < SEED_VIDEOS_PER_PROFILE:
                    all_videos.append(v)
                    seen_ids.add(v["video_id"])
            report.step(f"Ricerca '{channel}'", len(new) > 0,
                        f"{len(new)} video trovati")
            time.sleep(2)
        except Exception as e:
            report.step(f"Ricerca '{channel}'", False, str(e))

    report.metric("Video seed trovati", len(all_videos))
    enough = len(all_videos) >= (SEED_VIDEOS_PER_PROFILE // 2)
    report.step("Numero video seed sufficiente",
                enough, f"{len(all_videos)}/{SEED_VIDEOS_PER_PROFILE}")
    return all_videos[:SEED_VIDEOS_PER_PROFILE]


# ---------------------------------------------------------------------------
# Step 6 — Seed watching (versione veloce per test: 8s per video)
# ---------------------------------------------------------------------------

def step_watch(report: E2EReport, driver, videos: list[dict]) -> int:
    print("\n[STEP 6] Seed watching (modalità test: 8s per video)")
    from selenium.common.exceptions import TimeoutException as TE
    from src.database import insert_seed_watch

    watched = 0
    for i, video in enumerate(videos, 1):
        url = f"https://www.youtube.com/watch?v={video['video_id']}"
        try:
            driver.get(url)
            time.sleep(3)
            # Attendi il player
            WebDriverWait(driver, 12).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "video.html5-main-video"))
            )
            # Guarda 8 secondi (test rapido)
            time.sleep(8)
            insert_seed_watch(
                profile=report.profile,
                video_id=video["video_id"],
                title=video["title"],
                channel=video["channel"],
            )
            watched += 1
            print(f"    [{i}/{len(videos)}] Guardato: {video['title'][:55]}")
            time.sleep(2)
        except TE:
            print(f"    [{i}/{len(videos)}] Timeout: {video['video_id']}")
        except Exception as e:
            print(f"    [{i}/{len(videos)}] Errore: {e}")

    report.metric("Video guardati", watched)
    ok = watched >= (SEED_VIDEOS_PER_PROFILE // 2)
    report.step("Seed watching completato",
                ok, f"{watched}/{len(videos)} video guardati con successo")
    return watched


# ---------------------------------------------------------------------------
# Step 7 — Verifica DB post-watching
# ---------------------------------------------------------------------------

def step_verify_db(report: E2EReport, expected_watched: int) -> bool:
    print("\n[STEP 7] Verifica database")
    records = _get_seed_watches(report.profile)
    count = len(records)

    count_ok = count == expected_watched
    report.step("Record DB corrispondono ai video guardati",
                count_ok, f"{count} record in seed_watches")

    if records:
        # Verifica che tutti i record abbiano i campi obbligatori
        complete = all(r.get("video_id") and r.get("watched_at") for r in records)
        report.step("Tutti i record hanno video_id e watched_at", complete)

        # Verifica unicità video_id
        ids = [r["video_id"] for r in records]
        unique = len(ids) == len(set(ids))
        report.step("Nessun duplicato video_id", unique,
                    f"{len(set(ids))} ID unici su {len(ids)}")

        # Canali rappresentati
        channels_found = {r["channel"] for r in records if r.get("channel")}
        report.metric("Canali nei record DB", len(channels_found))
        report.step("Almeno 1 canale registrato nel DB",
                    len(channels_found) > 0, str(channels_found))

    return count_ok


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    profile = sys.argv[1].lower() if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "scienza"
    keep_data = "--keep-data" in sys.argv

    if profile not in PROFILES:
        print(f"Profilo '{profile}' non valido. Disponibili: {list(PROFILES.keys())}")
        sys.exit(1)

    print("=" * 60)
    print(f"TEST END-TO-END — Pipeline completa")
    print(f"Profilo: {profile.upper()} | Keep data: {keep_data}")
    print(f"Avvio: {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 60)

    report = E2EReport(profile)
    driver = None

    try:
        # Step 1: precondizioni
        if not step_preconditions(report):
            report.print_summary()
            sys.exit(1)

        # Step 2: init DB
        if not step_init_db(report):
            report.print_summary()
            sys.exit(1)

        # Step 3: reset
        step_reset(report, keep_data)

        # Step 4-6: browser
        driver = get_driver(profile)
        t_browser = time.time()

        if not step_youtube_load(report, driver):
            report.print_summary()
            sys.exit(1)

        videos = step_search(report, driver)
        if not videos:
            report.step("Pipeline seed watching", False, "Nessun video trovato")
            report.print_summary()
            sys.exit(1)

        watched = step_watch(report, driver, videos)

    except KeyboardInterrupt:
        print("\n\nInterrotto dall'utente.")
        sys.exit(130)
    except Exception as e:
        logger.exception("Errore inatteso nel test E2E")
        report.step("Errore inatteso", False, str(e))
    finally:
        if driver:
            driver.quit()

    # Step 7: verifica DB (fuori dal try del driver)
    step_verify_db(report, watched if 'watched' in dir() else 0)
    report.metric("Tempo totale", f"{(datetime.now() - report.started_at).total_seconds():.0f}s")

    ok = report.print_summary()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
