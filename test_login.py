"""
Test Martedì: verifica che credenziali e login funzionino per UN profilo.
Utile per testare prima di eseguire setup_profiles.py su tutti e 5.

Esegui con: python test_login.py scienza
"""

import sys
import time
from src.logger import setup_logging
from src.driver import get_driver
from src.credentials import get_credentials, get_all_credentials
from src.youtube_login import ensure_logged_in

logger = setup_logging("yt_recommender")


def test_credentials():
    print("--- Test file .env ---")
    creds = get_all_credentials()
    if not creds:
        print("  ❌ Nessuna credenziale trovata nel file .env")
        print("  → Copia .env.example in .env e inserisci le tue credenziali")
        return False
    for profile, (email, _) in creds.items():
        print(f"  ✅ {profile:<10} → {email}")
    return True


def test_single_login(profile_name: str):
    print(f"\n--- Test login profilo '{profile_name}' ---")
    try:
        email, password = get_credentials(profile_name)
        print(f"  Email: {email}")
    except ValueError as e:
        print(f"  ❌ {e}")
        return False

    print("  Avvio Chrome... (può richiedere qualche secondo)")
    driver = get_driver(profile_name)
    try:
        ok = ensure_logged_in(driver, email, password, profile_name)
        if ok:
            print(f"  ✅ Login riuscito per '{profile_name}'")
        else:
            print(f"  ❌ Login fallito per '{profile_name}'")
            print("     → Prova ad aprire Chrome manualmente e controlla se ci sono")
            print("       verifiche di sicurezza Google sull'account")
        time.sleep(2)
        return ok
    finally:
        driver.quit()


if __name__ == "__main__":
    profile = sys.argv[1] if len(sys.argv) > 1 else "scienza"

    ok_env = test_credentials()
    if not ok_env:
        sys.exit(1)

    ok_login = test_single_login(profile)
    sys.exit(0 if ok_login else 1)
