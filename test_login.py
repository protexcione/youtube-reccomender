"""
Test Martedì: verifica che i 5 profili Chrome isolati si inizializzino correttamente.

Esegui con: python test_login.py
Oppure un profilo solo: python test_login.py scienza
"""

import sys
import time
from selenium.webdriver.common.by import By
from src.logger import setup_logging
from src.config import PROFILES
from src.driver import get_driver

logger = setup_logging("yt_recommender")


def test_profile_isolation(profile_name: str) -> bool:
    print(f"\n--- Test profilo '{profile_name}' ---")
    driver = get_driver(profile_name)
    try:
        driver.get("https://www.youtube.com")
        time.sleep(4)

        # Accetta cookie se compare
        try:
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH,
                    "//button[.//span[contains(text(),'Accetta') or contains(text(),'Accept')]]"
                ))
            )
            btn.click()
            time.sleep(2)
        except Exception:
            pass

        # Verifica che siamo su YouTube
        assert "YouTube" in driver.title, f"Titolo inatteso: {driver.title}"
        print(f"  ✅ YouTube caricato: {driver.title}")

        # Verifica che NON sia loggato (nessun avatar)
        avatars = driver.find_elements(By.CSS_SELECTOR, "button#avatar-btn")
        if avatars:
            print(f"  ⚠️  Profilo loggato con un account Google")
        else:
            print(f"  ✅ Profilo anonimo — nessun account collegato")

        # Verifica isolamento cookie: cartella profilo esiste
        from src.config import PROFILES_DIR
        profile_dir = PROFILES_DIR / profile_name
        assert profile_dir.exists(), f"Cartella profilo mancante: {profile_dir}"
        print(f"  ✅ Cookie isolati in: {profile_dir}")

        return True
    except Exception as e:
        print(f"  ❌ Errore: {e}")
        return False
    finally:
        driver.quit()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        profiles = [sys.argv[1].lower()]
    else:
        profiles = list(PROFILES.keys())

    results = {}
    for p in profiles:
        results[p] = test_profile_isolation(p)
        time.sleep(2)

    print("\n" + "=" * 50)
    print("RIEPILOGO TEST PROFILI")
    print("=" * 50)
    for p, ok in results.items():
        print(f"  {p:<10} {'✅ OK' if ok else '❌ Fallito'}")

    sys.exit(0 if all(results.values()) else 1)
