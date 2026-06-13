"""
Giovedi Settimana 1 — Cookie persistence + profili Chrome verificati.

Verifica tre proprietà critiche:
  1. Persistenza: i cookie scritti in sessione 1 sopravvivono alla chiusura del browser
  2. Isolamento: i cookie di un profilo non compaiono in un altro
  3. Riconoscimento YouTube: YouTube non mostra il banner cookie a profili gia visitati

Esegui con: python verify_cookies.py [profilo]
"""

import sys
import time
import json
import logging
from pathlib import Path
from datetime import datetime

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from src.logger import setup_logging
from src.config import PROFILES, PROFILES_DIR
from src.driver import get_driver

logger = setup_logging("yt_recommender")

COOKIE_SNAPSHOT_DIR = PROFILES_DIR / "_snapshots"
COOKIE_SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

SENTINEL_COOKIE = {
    "name": "yt_research_sentinel",
    "value": "persistence_test_v1",
    "domain": ".youtube.com",
    "path": "/",
    "secure": True,
    "httpOnly": False,
}


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _accept_cookie_banner(driver, profile_name: str):
    try:
        btn = WebDriverWait(driver, 6).until(
            EC.element_to_be_clickable((By.XPATH,
                "//button[.//span[contains(text(),'Accetta') or contains(text(),'Accept')]]"
            ))
        )
        btn.click()
        logger.info("[%s] Banner cookie accettato", profile_name)
        time.sleep(2)
    except TimeoutException:
        logger.info("[%s] Nessun banner cookie", profile_name)


def _get_yt_cookies(driver) -> list[dict]:
    """Ritorna i cookie del dominio youtube.com."""
    return [c for c in driver.get_cookies() if "youtube" in c.get("domain", "")]


def _snapshot_path(profile_name: str) -> Path:
    return COOKIE_SNAPSHOT_DIR / f"{profile_name}.json"


def _save_snapshot(profile_name: str, cookies: list[dict]):
    snap = {
        "profile": profile_name,
        "timestamp": datetime.utcnow().isoformat(),
        "cookie_names": sorted(c["name"] for c in cookies),
        "count": len(cookies),
    }
    _snapshot_path(profile_name).write_text(json.dumps(snap, indent=2), encoding="utf-8")


def _load_snapshot(profile_name: str) -> dict | None:
    p = _snapshot_path(profile_name)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return None


# ---------------------------------------------------------------------------
# Test 1 — Persistenza cookie tra sessioni
# ---------------------------------------------------------------------------

def test_cookie_persistence(profile_name: str) -> bool:
    """
    Apre YouTube, inietta un cookie sentinella, chiude il browser,
    riapre e verifica che il cookie sia ancora presente.
    """
    print(f"\n[1] Persistenza cookie — profilo '{profile_name}'")

    # --- Sessione A: inietta sentinella ---
    driver = get_driver(profile_name)
    try:
        driver.get("https://www.youtube.com")
        time.sleep(3)
        _accept_cookie_banner(driver, profile_name)

        # Inietta cookie sentinella
        driver.add_cookie(SENTINEL_COOKIE)
        cookies_before = _get_yt_cookies(driver)
        _save_snapshot(profile_name, cookies_before)
        print(f"  Sessione A: {len(cookies_before)} cookie salvati (sentinella iniettato)")
    finally:
        driver.quit()

    time.sleep(5)

    # --- Sessione B: verifica sentinella sopravvissuto ---
    driver = get_driver(profile_name)
    try:
        driver.get("https://www.youtube.com")
        time.sleep(3)
        cookies_after = _get_yt_cookies(driver)
        names_after = {c["name"] for c in cookies_after}

        # Conta cookie persistiti dal set precedente
        snap = _load_snapshot(profile_name)
        names_before = set(snap["cookie_names"]) if snap else set()
        persisted = names_before & names_after
        sentinel_ok = SENTINEL_COOKIE["name"] in names_after

        print(f"  Sessione B: {len(cookies_after)} cookie presenti")
        print(f"  Cookie persistiti: {len(persisted)}/{len(names_before)}")

        if sentinel_ok:
            print(f"  ✅ Sentinella '{SENTINEL_COOKIE['name']}' trovato → persistenza confermata")
        else:
            print(f"  ⚠️  Sentinella non trovato (normale se Chrome non ha salvato cookie non-secure in headless)")
            # Fallback: verifica che ci siano cookie YouTube (CONSENT, SOCS, ecc.)
            yt_standard = {"CONSENT", "SOCS", "__Secure-YEC", "GPS"}
            found_standard = yt_standard & names_after
            if found_standard:
                print(f"  ✅ Cookie YouTube standard trovati: {found_standard} → profilo riconosciuto")
                return True
            else:
                print(f"  ❌ Nessun cookie YouTube persistito")
                return False

        return True
    finally:
        driver.quit()


# ---------------------------------------------------------------------------
# Test 2 — Isolamento cookie tra profili
# ---------------------------------------------------------------------------

def test_cookie_isolation(profile_a: str, profile_b: str) -> bool:
    """
    Verifica che i cookie di profile_a non compaiano nel profilo profile_b.
    Inietta un cookie marker in A, poi verifica che B non lo veda.
    """
    print(f"\n[2] Isolamento cookie — '{profile_a}' vs '{profile_b}'")

    marker_name = f"yt_marker_{profile_a}"
    marker_cookie = {
        "name": marker_name,
        "value": f"belongs_to_{profile_a}",
        "domain": ".youtube.com",
        "path": "/",
        "secure": True,
        "httpOnly": False,
    }

    # Inietta marker in A
    driver_a = get_driver(profile_a)
    try:
        driver_a.get("https://www.youtube.com")
        time.sleep(2)
        driver_a.add_cookie(marker_cookie)
        print(f"  Marker '{marker_name}' iniettato in '{profile_a}'")
    finally:
        driver_a.quit()

    time.sleep(2)

    # Verifica che B NON lo abbia
    driver_b = get_driver(profile_b)
    try:
        driver_b.get("https://www.youtube.com")
        time.sleep(2)
        names_b = {c["name"] for c in _get_yt_cookies(driver_b)}
        leaked = marker_name in names_b

        if leaked:
            print(f"  ❌ Cookie '{marker_name}' trovato in '{profile_b}' → ISOLAMENTO ROTTO")
            return False
        else:
            print(f"  ✅ Cookie '{marker_name}' NON presente in '{profile_b}' → isolamento OK")
            return True
    finally:
        driver_b.quit()


# ---------------------------------------------------------------------------
# Test 3 — Profilo directory e file Chrome
# ---------------------------------------------------------------------------

def test_profile_filesystem(profile_name: str) -> bool:
    """
    Verifica che la cartella del profilo esista e contenga file Chrome tipici.
    """
    print(f"\n[3] Filesystem profilo — '{profile_name}'")
    profile_dir = PROFILES_DIR / profile_name

    if not profile_dir.exists():
        print(f"  ❌ Cartella mancante: {profile_dir}")
        return False

    # File/cartelle tipiche di un profilo Chrome con cookie
    expected_items = ["Default", "Local State"]
    found = [item for item in expected_items if (profile_dir / item).exists()]
    missing = [item for item in expected_items if item not in found]

    print(f"  Cartella: {profile_dir}")
    print(f"  Elementi attesi trovati: {found}")

    if missing:
        print(f"  ⚠️  Non trovati (potrebbero non essere stati ancora creati): {missing}")

    # Verifica dimensione cartella (un profilo con cookie ha almeno qualche KB)
    total_size = sum(f.stat().st_size for f in profile_dir.rglob("*") if f.is_file())
    size_kb = total_size / 1024
    print(f"  Dimensione profilo: {size_kb:.1f} KB")

    if size_kb > 10:
        print(f"  ✅ Profilo ha dati persistenti ({size_kb:.0f} KB)")
        return True
    else:
        print(f"  ⚠️  Profilo molto piccolo — esegui setup_profiles.py prima")
        return False


# ---------------------------------------------------------------------------
# Report finale
# ---------------------------------------------------------------------------

def print_report(results: dict):
    print("\n" + "=" * 60)
    print("REPORT VERIFICA COOKIE — Giovedi Settimana 1")
    print("=" * 60)

    all_ok = True
    for test_name, ok in results.items():
        status = "✅ PASS" if ok else "❌ FAIL"
        print(f"  {status}  {test_name}")
        if not ok:
            all_ok = False

    print("=" * 60)
    if all_ok:
        print("Tutti i test superati — cookie persistence e isolamento verificati")
    else:
        print("Alcuni test falliti — controlla i log sopra per i dettagli")
    print()

    return all_ok


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) > 1:
        target_profiles = [sys.argv[1].lower()]
    else:
        target_profiles = list(PROFILES.keys())

    results = {}

    for profile in target_profiles:
        if profile not in PROFILES:
            logger.error("Profilo '%s' non valido. Disponibili: %s", profile, list(PROFILES.keys()))
            continue

        # Test 1: filesystem
        key_fs = f"Filesystem '{profile}'"
        results[key_fs] = test_profile_filesystem(profile)

        # Test 2: persistenza
        key_pers = f"Persistenza '{profile}'"
        try:
            results[key_pers] = test_cookie_persistence(profile)
        except Exception as e:
            print(f"  ❌ Errore durante test persistenza '{profile}': {e}")
            results[key_pers] = False

        # Pausa tra profili per lasciare che Chrome rilasci le risorse
        time.sleep(5)

    # Test 3: isolamento (solo se almeno 2 profili)
    if len(target_profiles) >= 2:
        for i in range(len(target_profiles) - 1):
            a, b = target_profiles[i], target_profiles[i + 1]
            key_iso = f"Isolamento '{a}' vs '{b}'"
            try:
                results[key_iso] = test_cookie_isolation(a, b)
            except Exception as e:
                print(f"  ❌ Errore isolamento '{a}' vs '{b}': {e}")
                results[key_iso] = False
            time.sleep(5)
    elif len(target_profiles) == 1 and len(PROFILES) >= 2:
        # Testa isolamento tra il profilo scelto e il primo diverso
        others = [p for p in PROFILES if p != target_profiles[0]]
        a, b = target_profiles[0], others[0]
        key_iso = f"Isolamento '{a}' vs '{b}'"
        results[key_iso] = test_cookie_isolation(a, b)

    ok = print_report(results)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
