"""
Raccolta raccomandazioni dalla homepage YouTube.
Ogni profilo visita la homepage e salva le prime N raccomandazioni nel DB.

Uso:
  python scrape_homepage.py                  # tutti i profili, giorno auto
  python scrape_homepage.py scienza          # profilo singolo
  python scrape_homepage.py scienza --day 3  # profilo + giorno specifico
  python scrape_homepage.py --day 1          # tutti i profili, giorno 1
"""

import sys
import time
import random
import logging
import argparse

from src.logger import setup_logging
from src.config import PROFILES, HOMEPAGE_RECS_COUNT
from src.driver import get_driver, safe_quit
from src.database import init_db, get_recommendations
from src.scraper import scrape_homepage, get_day_recommendation_count

logger = setup_logging("yt_recommender")

_MAX_RETRIES = 2  # retry automatici per profili falliti


def _detect_next_day() -> int:
    """
    Calcola il giorno successivo da raccogliere guardando il DB.
    Se non ci sono dati restituisce 1; altrimenti il massimo giorno già raccolto + 1.
    """
    from src.database import get_recommendations
    from src.config import SIMULATION_DAYS
    recs = get_recommendations()
    if not recs:
        return 1
    max_day = max(r["day"] for r in recs)
    return min(max_day + 1, SIMULATION_DAYS)


def run_profile(profile: str, day: int) -> bool:
    """
    Esegue lo scraping homepage per un singolo profilo.
    Restituisce True se almeno metà delle raccomandazioni target sono state raccolte.
    """
    logger.info("=" * 55)
    logger.info("SCRAPING HOMEPAGE — Profilo: %s | Giorno: %d", profile.upper(), day)
    logger.info("=" * 55)

    # Controlla se i dati esistono già
    already = get_day_recommendation_count(profile, day)
    if already >= HOMEPAGE_RECS_COUNT:
        logger.info("[%s] Giorno %d già completato (%d record nel DB) — skip", profile, day, already)
        return True

    driver = None
    try:
        driver = get_driver(profile)

        # Carica YouTube per attivare la sessione
        driver.get("https://www.youtube.com")
        time.sleep(random.uniform(2, 4))

        recs = scrape_homepage(driver, profile, day)

        success = len(recs) >= (HOMEPAGE_RECS_COUNT // 2)
        if not success:
            logger.warning("[%s] Giorno %d: solo %d/%d raccomandazioni raccolte", profile, day, len(recs), HOMEPAGE_RECS_COUNT)
        return success

    except RuntimeError as e:
        logger.error("[%s] Errore configurazione: %s", profile, e)
        return False
    finally:
        safe_quit(driver)


def _run_profiles_with_retry(profiles: list[str], day: int) -> dict[str, bool]:
    """Esegue scraping per ogni profilo con retry automatico per i falliti."""
    results = {}
    to_run = list(profiles)

    for round_num in range(_MAX_RETRIES + 1):
        if round_num > 0:
            if not to_run:
                break
            logger.info("Retry round %d/%d per: %s", round_num, _MAX_RETRIES, ", ".join(to_run))
            time.sleep(random.uniform(30, 60))

        still_failing = []
        for i, profile in enumerate(to_run):
            try:
                ok = run_profile(profile, day)
            except Exception as e:
                logger.error("[%s] Crash inatteso: %s", profile, e)
                ok = False
            results[profile] = ok
            if not ok:
                still_failing.append(profile)
            if i < len(to_run) - 1:
                pause = random.uniform(10, 20)
                logger.info("Pausa %ds prima del prossimo profilo...", int(pause))
                time.sleep(pause)

        to_run = still_failing

    return results


def main():
    parser = argparse.ArgumentParser(description="Scraping homepage YouTube per tutti i profili")
    parser.add_argument("profile", nargs="?", help="Profilo singolo (es. scienza)")
    parser.add_argument("--day", type=int, default=None, help="Giorno della simulazione (1-7)")
    args = parser.parse_args()

    init_db()

    # Determina profili
    if args.profile:
        if args.profile not in PROFILES:
            logger.error("Profilo '%s' non esiste. Disponibili: %s", args.profile, list(PROFILES.keys()))
            sys.exit(1)
        profiles = [args.profile]
    else:
        profiles = list(PROFILES.keys())

    # Determina giorno
    day = args.day if args.day is not None else _detect_next_day()
    logger.info("Raccolta dati per GIORNO %d — %d profili", day, len(profiles))

    results = _run_profiles_with_retry(profiles, day)

    # Riepilogo
    print("\n" + "=" * 55)
    print(f"RIEPILOGO SCRAPING HOMEPAGE — Giorno {day}")
    print("=" * 55)
    for profile, ok in results.items():
        count = get_day_recommendation_count(profile, day)
        status = f"OK ({count} raccomandazioni)" if ok else f"FALLITO ({count} raccomandazioni)"
        print(f"  {profile:<10} {status}")

    failed = [p for p, ok in results.items() if not ok]
    if failed:
        print(f"\nProfili falliti: {', '.join(failed)}")
        print(f"  -> python scrape_homepage.py {failed[0]} --day {day}")
        sys.exit(1)
    else:
        print(f"\nScraping giorno {day} completato per tutti i profili!")
        sys.exit(0)


if __name__ == "__main__":
    main()
