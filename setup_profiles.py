"""
Inizializza i 5 profili Chrome senza login.
Ogni profilo ha cookie isolati — YouTube personalizza tramite cronologia di navigazione.

Esegui con: python setup_profiles.py
"""

import sys
import time
import logging
from src.logger import setup_logging
from src.config import PROFILES
from src.driver import get_driver

logger = setup_logging("yt_recommender")


def setup_profile(profile_name: str) -> bool:
    logger.info("=" * 50)
    logger.info("Setup profilo: %s", profile_name.upper())
    logger.info("=" * 50)

    driver = get_driver(profile_name)
    try:
        # Apri YouTube per inizializzare i cookie del profilo
        driver.get("https://www.youtube.com")
        time.sleep(4)

        # Accetta cookie se compare il banner
        try:
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            btn = WebDriverWait(driver, 6).until(
                EC.element_to_be_clickable((By.XPATH,
                    "//button[.//span[contains(text(),'Accetta') or contains(text(),'Accept')]]"
                ))
            )
            btn.click()
            logger.info("[%s] Banner cookie accettato", profile_name)
            time.sleep(2)
        except Exception:
            logger.info("[%s] Nessun banner cookie", profile_name)

        title = driver.title
        ok = "YouTube" in title
        if ok:
            logger.info("[%s] ✅ Profilo pronto — %s", profile_name, title)
        else:
            logger.warning("[%s] ❌ Pagina inattesa: %s", profile_name, title)
        return ok
    finally:
        driver.quit()


def main():
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
        time.sleep(2)

    print("\n" + "=" * 50)
    print("RIEPILOGO SETUP PROFILI")
    print("=" * 50)
    for profile, ok in results.items():
        print(f"  {profile:<10} {'✅ Pronto' if ok else '❌ Fallito'}")

    if all(results.values()):
        print("\n🎉 Tutti i profili sono pronti!")
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
