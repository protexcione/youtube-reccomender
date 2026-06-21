"""
Test ricerca video e seed watching per un singolo profilo.
Guarda solo 2 video (non 10) per tenere il test veloce.

Esegui con: python test_seed_watch.py scienza
"""

import sys
import time
from src.logger import setup_logging
from src.config import PROFILES
from src.driver import get_driver
from src.database import init_db, get_recommendations
from src.search import search_videos
from src.watcher import watch_video

logger = setup_logging("yt_recommender")


def test_search(driver, profile_name: str) -> list:
    print(f"\n--- Test ricerca video per '{profile_name}' ---")
    channel = PROFILES[profile_name][0]  # primo canale seed
    print(f"  Cerco: '{channel}'")
    videos = search_videos(driver, channel, max_results=3)
    if videos:
        for v in videos:
            print(f"  [OK] {v['channel']} — {v['title'][:60]}")
    else:
        print("  [ERRORE] Nessun video trovato")
    return videos


def test_watch(driver, profile_name: str, videos: list) -> bool:
    print(f"\n--- Test visione 2 video per '{profile_name}' ---")
    if not videos:
        print("  [SKIP] Nessun video da guardare")
        return False

    ok_count = 0
    for video in videos[:2]:
        print(f"  Guardo: {video['title'][:50]}...")
        ok = watch_video(driver, video, profile_name)
        print(f"  {'[OK]' if ok else '[ERRORE]'}")
        if ok:
            ok_count += 1
        time.sleep(3)

    return ok_count > 0


def test_db_records(profile_name: str):
    print(f"\n--- Test record database per '{profile_name}' ---")
    from src.database import get_connection
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM seed_watches WHERE profile = ?", (profile_name,)
        ).fetchall()
    if rows:
        print(f"  [OK] {len(rows)} record salvati nel DB")
        for r in rows:
            print(f"       {r['channel']} — {r['title'][:50]}")
    else:
        print("  [ERRORE] Nessun record nel DB")
    return len(rows) > 0


if __name__ == "__main__":
    profile = sys.argv[1] if len(sys.argv) > 1 else "scienza"

    if profile not in PROFILES:
        print(f"Profilo '{profile}' non esiste. Disponibili: {list(PROFILES.keys())}")
        sys.exit(1)

    init_db()
    driver = get_driver(profile)

    try:
        driver.get("https://www.youtube.com")
        time.sleep(3)

        videos = test_search(driver, profile)
        ok_watch = test_watch(driver, profile, videos)
        ok_db = test_db_records(profile)

        print("\n" + "=" * 50)
        if ok_watch and ok_db:
            print(f"MERCOLEDI OK — seed watching funziona per '{profile}'")
            print("Ora esegui: python seed_watch.py (per tutti i profili)")
        else:
            print("Qualcosa non ha funzionato — controlla i log sopra")
    finally:
        driver.quit()
