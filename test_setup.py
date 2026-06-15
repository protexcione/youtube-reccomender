"""
Test Giorno 1: verifica ambiente, struttura cartelle e database.
Esegui con: python test_setup.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    print("--- Test importazioni ---")
    try:
        import selenium; print(f"  ✅ selenium {selenium.__version__}")
        import pandas;   print(f"  ✅ pandas {pandas.__version__}")
        import networkx; print(f"  ✅ networkx {networkx.__version__}")
        import matplotlib; print(f"  ✅ matplotlib {matplotlib.__version__}")
        return True
    except ImportError as e:
        print(f"  ❌ {e}")
        return False

def test_structure():
    print("--- Test struttura cartelle ---")
    from src.config import PROFILES_DIR, DATA_RAW_DIR, DATA_PROCESSED_DIR, LOGS_DIR, REPORTS_DIR
    ok = True
    for d in [PROFILES_DIR, DATA_RAW_DIR, DATA_PROCESSED_DIR, LOGS_DIR, REPORTS_DIR]:
        if d.exists():
            print(f"  ✅ {d}")
        else:
            print(f"  ❌ MANCANTE: {d}")
            ok = False
    return ok

def test_database():
    print("--- Test database ---")
    from src.database import init_db, insert_seed_watch, get_recommendations
    from src.config import DB_PATH
    try:
        init_db()
        print(f"  ✅ DB creato: {DB_PATH}")
        # insert_seed_watch usa INSERT OR IGNORE: sicuro da rieseguire più volte
        insert_seed_watch("scienza", "test123", "Test Video", "Test Channel")
        print("  ✅ Insert seed_watch OK")
        return True
    except Exception as e:
        print(f"  Errore inizializzazione DB: {e}")
        print(f"  ❌ {e}")
        return False

def test_logger():
    print("--- Test logger ---")
    from src.logger import setup_logging
    from src.config import LOGS_DIR
    try:
        logger = setup_logging("test")
        logger.info("Logger funzionante")
        log_file = LOGS_DIR / "test.log"
        print(f"  ✅ Log scritto in {log_file}")
        return True
    except Exception as e:
        print(f"  ❌ {e}")
        return False

if __name__ == "__main__":
    results = [
        test_imports(),
        test_structure(),
        test_database(),
        test_logger(),
    ]
    print()
    if all(results):
        print("🎉 GIORNO 1 COMPLETATO — Ambiente pronto!")
        sys.exit(0)
    else:
        print("⚠️  Alcuni test falliti — controlla gli errori sopra.")
        sys.exit(1)
