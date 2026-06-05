"""
Script Martedì Settimana 1:
Inizializza e fa il login per tutti e 5 i profili.

Esegui con: python setup_profiles.py
Oppure un profilo solo: python setup_profiles.py scienza
"""

import sys
import time
import logging
from src.logger import setup_logging
from src.config import PROFILES, HEADLESS
from src.driver import get_driver
from src.credentials import get_credentials
from src.youtube_login import ensure_logged_in

logger = setup_logging("yt_recommender")


def setup_profile(profile_name: str) -> bool:
    logger.info("=" * 50)
    logger.info("Setup profilo: %s", profile_name.upper())
    logger.info("=" * 50)

    try:
        email, password = get_credentials(profile_name)
    except ValueError as e:
        logger.error(str(e))
        return False

    driver = get_driver(profile_name)
    try:
        success = ensure_logged_in(driver, email, password, profile_name)
        if success:
            logger.info("[%s] Profilo pronto ✅", profile_name)
        else:
            logger.warning("[%s] Login fallito — controlla le credenziali nel .env", profile_name)
        time.sleep(2)
        return success
    finally:
        driver.quit()


def main():
    # Profilo singolo o tutti
    if len(sys.argv) > 1:
        profiles_to_setup = [sys.argv[1].lower()]
    else:
        profiles_to_setup = list(PROFILES.keys())

    results = {}
    for profile in profiles_to_setup:
        if profile not in PROFILES:
            logger.error("Profilo '%s' non esiste. Disponibili: %s", profile, list(PROFILES.keys()))
            continue
        results[profile] = setup_profile(profile)
        time.sleep(3)  # pausa tra profili

    # Riepilogo finale
    print("\n" + "=" * 50)
    print("RIEPILOGO SETUP PROFILI")
    print("=" * 50)
    for profile, ok in results.items():
        status = "✅ Loggato" if ok else "❌ Fallito"
        print(f"  {profile:<10} {status}")

    failed = [p for p, ok in results.items() if not ok]
    if failed:
        print(f"\n⚠️  Profili da sistemare: {', '.join(failed)}")
        print("   → Controlla le credenziali nel file .env")
        sys.exit(1)
    else:
        print("\n🎉 Tutti i profili sono pronti!")
        sys.exit(0)


if __name__ == "__main__":
    main()
