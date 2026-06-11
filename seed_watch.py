"""
Script Mercoledi Settimana 1:
Ogni profilo cerca i suoi canali seed e guarda 10 video.

Esegui con:
  python seed_watch.py              # tutti i profili
  python seed_watch.py scienza      # profilo singolo
"""

import sys
import time
import random
import logging

from src.logger import setup_logging
from src.config import PROFILES, SEED_VIDEOS_PER_PROFILE
from src.driver import get_driver
from src.database import init_db
from src.search import search_videos
from src.watcher import watch_seed_videos

logger = setup_logging("yt_recommender")


def collect_seed_videos(driver, profile_name: str) -> list[dict]:
    """
    Cerca video per ogni canale seed del profilo fino a raggiungere
    SEED_VIDEOS_PER_PROFILE video totali.
    """
    channels = PROFILES[profile_name]
    all_videos = []
    seen_ids = set()

    videos_per_channel = SEED_VIDEOS_PER_PROFILE // len(channels) + 1

    for channel in channels:
        if len(all_videos) >= SEED_VIDEOS_PER_PROFILE:
            break
        results = search_videos(driver, channel, max_results=videos_per_channel)
        for v in results:
            if v["video_id"] not in seen_ids and len(all_videos) < SEED_VIDEOS_PER_PROFILE:
                all_videos.append(v)
                seen_ids.add(v["video_id"])
        time.sleep(random.uniform(2, 4))

    return all_videos[:SEED_VIDEOS_PER_PROFILE]


def run_profile(profile_name: str) -> bool:
    logger.info("=" * 55)
    logger.info("SEED WATCHING — Profilo: %s", profile_name.upper())
    logger.info("=" * 55)

    driver = get_driver(profile_name)
    try:
        # Carica YouTube per attivare la sessione
        driver.get("https://www.youtube.com")
        time.sleep(3)

        # Cerca video seed
        logger.info("[%s] Raccolta video seed...", profile_name)
        videos = collect_seed_videos(driver, profile_name)

        if not videos:
            logger.error("[%s] Nessun video seed trovato!", profile_name)
            return False

        logger.info("[%s] Trovati %d video seed. Inizio visione...", profile_name, len(videos))
        for v in videos:
            logger.info("  - [%s] %s", v["channel"], v["title"])

        # Guarda i video
        watched = watch_seed_videos(driver, profile_name, videos)

        success = watched >= (SEED_VIDEOS_PER_PROFILE // 2)  # ok se almeno meta' guardati
        logger.info("[%s] Guardati %d/%d video seed", profile_name, watched, len(videos))
        return success

    finally:
        driver.quit()


def main():
    init_db()

    if len(sys.argv) > 1:
        profiles = [sys.argv[1].lower()]
    else:
        profiles = list(PROFILES.keys())

    results = {}
    for profile in profiles:
        if profile not in PROFILES:
            logger.error("Profilo '%s' non esiste. Disponibili: %s", profile, list(PROFILES.keys()))
            continue
        try:
            results[profile] = run_profile(profile)
        except Exception as e:
            logger.error("[%s] Crash inatteso: %s — continuo con il prossimo profilo", profile, e)
            results[profile] = False
        if len(profiles) > 1:
            pause = random.uniform(10, 20)
            logger.info("Pausa %ds prima del prossimo profilo...", int(pause))
            time.sleep(pause)

    # Riepilogo
    print("\n" + "=" * 55)
    print("RIEPILOGO SEED WATCHING")
    print("=" * 55)
    for profile, ok in results.items():
        print(f"  {profile:<10} {'OK - seed watching completato' if ok else 'FALLITO'}")

    failed = [p for p, ok in results.items() if not ok]
    if failed:
        print(f"\nProfili da ripetere: {', '.join(failed)}")
        print(f"  -> python seed_watch.py {failed[0]}")
        sys.exit(1)
    else:
        print("\nSeed watching completato per tutti i profili!")
        print("Ora YouTube iniziera' a personalizzare le raccomandazioni.")
        sys.exit(0)


if __name__ == "__main__":
    main()
