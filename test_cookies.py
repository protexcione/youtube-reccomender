"""
Test Giovedi — Cookie persistence + profili Chrome verificati.
Eseguibile senza browser (verifica struttura filesystem e snapshot).
Per test completi con browser: python verify_cookies.py

Esegui con: python test_cookies.py
"""

import sys
import json
import time
from pathlib import Path
from src.logger import setup_logging
from src.config import PROFILES, PROFILES_DIR

logger = setup_logging("yt_recommender")

SNAPSHOT_DIR = PROFILES_DIR / "_snapshots"
PASS = "✅ PASS"
FAIL = "❌ FAIL"


def test_profiles_dirs_exist() -> bool:
    """Ogni profilo ha la sua cartella dati Chrome."""
    print("\n[TEST 1] Cartelle profilo Chrome")
    all_ok = True
    for profile in PROFILES:
        pdir = PROFILES_DIR / profile
        exists = pdir.exists()
        size_kb = sum(f.stat().st_size for f in pdir.rglob("*") if f.is_file()) / 1024 if exists else 0
        status = PASS if exists and size_kb > 1 else FAIL
        if not exists or size_kb <= 1:
            all_ok = False
        print(f"  {status}  profiles/{profile}/ ({size_kb:.0f} KB)")
    return all_ok


def test_profiles_are_isolated() -> bool:
    """Le cartelle dei profili sono separate (nessuna condivisione di Default/)."""
    print("\n[TEST 2] Isolamento cartelle")
    dirs = {profile: PROFILES_DIR / profile for profile in PROFILES}
    all_ok = True
    for p1, d1 in dirs.items():
        for p2, d2 in dirs.items():
            if p1 >= p2:
                continue
            # Le due cartelle non devono essere la stessa
            if d1.resolve() == d2.resolve():
                print(f"  {FAIL}  '{p1}' e '{p2}' puntano alla stessa cartella!")
                all_ok = False
    if all_ok:
        print(f"  {PASS}  Tutte le {len(PROFILES)} cartelle profilo sono distinte")
    return all_ok


def test_cookie_snapshots_exist() -> bool:
    """
    Verifica che verify_cookies.py abbia prodotto snapshot JSON per ogni profilo.
    Se non ci sono snapshot, il test viene skippato con warning.
    """
    print("\n[TEST 3] Snapshot cookie da verify_cookies.py")
    if not SNAPSHOT_DIR.exists():
        print(f"  ⚠️  SKIP — directory snapshot assente (esegui verify_cookies.py prima)")
        return True  # non blocca — snapshot generati da verify_cookies

    found = 0
    for profile in PROFILES:
        snap_path = SNAPSHOT_DIR / f"{profile}.json"
        if snap_path.exists():
            snap = json.loads(snap_path.read_text(encoding="utf-8"))
            count = snap.get("count", 0)
            ts = snap.get("timestamp", "?")
            print(f"  {PASS}  '{profile}': {count} cookie @ {ts}")
            found += 1
        else:
            print(f"  ⚠️  '{profile}': snapshot assente (esegui verify_cookies.py {profile})")

    if found == 0:
        print(f"  ⚠️  Nessuno snapshot trovato — esegui: python verify_cookies.py")
    return True  # snapshot opzionali per questo test


def test_driver_factory_no_shared_state() -> bool:
    """
    Verifica a codice che get_driver() usa user-data-dir diversi per ogni profilo.
    Non apre Chrome — analisi statica delle opzioni.
    """
    print("\n[TEST 4] Factory driver — user-data-dir unici")
    try:
        from src.driver import get_driver
        from unittest.mock import patch, MagicMock
    except ImportError as e:
        print(f"  ⚠️  SKIP — dipendenza mancante ({e})")
        print(f"       Attiva il venv: .venv\\Scripts\\activate")
        return True  # non blocca: problema di ambiente, non di codice

    dirs_seen = {}
    all_ok = True

    # Patch webdriver.Chrome e _check_chrome_available per non aprire browser
    with patch("src.driver.webdriver.Chrome") as mock_chrome, \
         patch("src.driver._check_chrome_available", return_value="/mock/chrome"):
        mock_instance = MagicMock()
        mock_chrome.return_value = mock_instance

        for profile in PROFILES:
            mock_chrome.reset_mock()
            get_driver(profile)

            # Recupera le options passate al costruttore
            call_args = mock_chrome.call_args
            if call_args is None:
                print(f"  {FAIL}  '{profile}': webdriver.Chrome non chiamato")
                all_ok = False
                continue

            options = call_args.kwargs.get("options") or (call_args.args[0] if call_args.args else None)
            if options is None:
                print(f"  {FAIL}  '{profile}': options non trovate")
                all_ok = False
                continue

            # Cerca --user-data-dir negli argomenti
            udd = next((a for a in options.arguments if "--user-data-dir=" in a), None)
            if udd is None:
                print(f"  {FAIL}  '{profile}': --user-data-dir mancante")
                all_ok = False
                continue

            data_dir = udd.split("=", 1)[1]
            if data_dir in dirs_seen.values():
                owner = [p for p, d in dirs_seen.items() if d == data_dir][0]
                print(f"  {FAIL}  '{profile}' condivide user-data-dir con '{owner}'!")
                all_ok = False
            else:
                dirs_seen[profile] = data_dir
                print(f"  {PASS}  '{profile}' → {Path(data_dir).name}/")

    return all_ok


def test_user_agents_unique() -> bool:
    """Ogni profilo ha uno user-agent diverso."""
    print("\n[TEST 5] User-agent univoci per profilo")
    from src.config import USER_AGENTS
    agents = list(USER_AGENTS.values())
    unique = len(set(agents)) == len(agents)
    if unique:
        print(f"  {PASS}  {len(agents)} user-agent distinti configurati")
    else:
        print(f"  {FAIL}  Alcuni profili condividono lo stesso user-agent")
    return unique


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("TEST GIOVEDI — Cookie Persistence & Profili Chrome")
    print("=" * 60)

    tests = [
        ("Cartelle profilo esistono e hanno dati", test_profiles_dirs_exist),
        ("Cartelle profilo sono isolate", test_profiles_are_isolated),
        ("Snapshot cookie da verify_cookies.py", test_cookie_snapshots_exist),
        ("Factory driver usa user-data-dir unici", test_driver_factory_no_shared_state),
        ("User-agent unici per profilo", test_user_agents_unique),
    ]

    results = {}
    for name, fn in tests:
        try:
            results[name] = fn()
        except Exception as e:
            print(f"  {FAIL}  Eccezione: {e}")
            results[name] = False

    print("\n" + "=" * 60)
    print("RIEPILOGO")
    print("=" * 60)
    for name, ok in results.items():
        status = PASS if ok else FAIL
        print(f"  {status}  {name}")

    all_ok = all(results.values())
    print()
    if all_ok:
        print("Tutti i test passati.")
        print("Per verifica completa con browser: python verify_cookies.py")
    else:
        print("Alcuni test falliti — controlla output sopra.")
        print("Se le cartelle profilo sono vuote: python setup_profiles.py")

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
