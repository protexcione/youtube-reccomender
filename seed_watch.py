"""
Script Mercoledi Settimana 1:
Ogni profilo cerca i suoi canali seed e guarda 10 video.

Esegui con:
  python seed_watch.py              # tutti i profili
  python seed_watch.py scienza      # profilo singolo
  python seed_watch.py --retry      # ripete solo i profili falliti nell'ultima run
"""

import sys
import time
import random
import logging

from src.logger import setup_logging
from src.config import PROFILES, SEED_VIDEOS_PER_PROFILE
from src.driver import get_driver, safe_quit
from src.database import init_db
from src.search import search_videos
from src.watcher import watch_seed_videos

logger = setup_logging("yt_recommender")

# Numero massimo di retry automatici per profili falliti
_MAX_PROFILE_RETRIES = 2


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

    driver = None
    try:
        driver = get_driver(profile_name)

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

    except RuntimeError as e:
        # Errori di configurazione (Chrome non trovato, ecc.) — non riprovare
        logger.error("[%s] Errore configurazione: %s", profile_name, e)
        return False
    finally:
        safe_quit(driver)


def _run_profiles_with_retry(profiles: list[str]) -> dict[str, bool]:
    """
    Esegue seed watching per ogni profilo, con retry automatico per quelli falliti.
    Restituisce dict {profile: ok}.
    """
    results = {}
    to_run = list(profiles)

    for retry_round in range(_MAX_PROFILE_RETRIES + 1):
        if retry_round > 0:
            if not to_run:
                break
            logger.info(
                "Retry automatico round %d/%d per profili falliti: %s",
                retry_round, _MAX_PROFILE_RETRIES, ", ".join(to_run)
            )
            pause = random.uniform(30, 60)
            logger.info("Pausa %ds prima del retry...", int(pause))
            time.sleep(pause)

        still_failing = []
        for i, profile in enumerate(to_run):
            try:
                ok = run_profile(profile)
            except Exception as e:
                logger.error("[%s] Crash inatteso: %s", profile, e)
                ok = False
            results[profile] = ok
            if not ok:
                still_failing.append(profile)
            # Pausa tra profili (tranne dopo l'ultimo)
            if i < len(to_run) - 1:
                pause = random.uniform(10, 20)
                logger.info("Pausa %ds prima del prossimo profilo...", int(pause))
                time.sleep(pause)

        to_run = still_failing

    return results


def main():
    init_db()

    args = sys.argv[1:]

    if args and args[0] == "--retry":
        # --retry: modalità interattiva — chiede quali profili ripetere
        profiles = list(PROFILES.keys())
        logger.info("Modalita' retry: eseguo tutti i profili")
    elif args:
        profile_arg = args[0].lower()
        if profile_arg not in PROFILES:
            logger.error("Profilo '%s' non esiste. Disponibili: %s", profile_arg, list(PROFILES.keys()))
            sys.exit(1)
        profiles = [profile_arg]
    else:
        profiles = list(PROFILES.keys())

    results = _run_profiles_with_retry(profiles)

    # Riepilogo
    print("\n" + "=" * 55)
    print("RIEPILOGO SEED WATCHING")
    print("=" * 55)
    for profile, ok in results.items():
        print(f"  {profile:<10} {'OK - seed watching completato' if ok else 'FALLITO'}")

    failed = [p for p, ok in results.items() if not ok]
    if failed:
        print(f"\nProfili falliti dopo {_MAX_PROFILE_RETRIES} retry: {', '.join(failed)}")
        print(f"  -> python seed_watch.py {failed[0]}")
        sys.exit(1)
    else:
        print("\nSeed watching completato per tutti i profili!")
        print("Ora YouTube iniziera' a personalizzare le raccomandazioni.")
        sys.exit(0)


if __name__ == "__main__":
    main()
