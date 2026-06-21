"""
Test schema DB raccomandazioni giornaliere.
Verifica vincoli UNIQUE, migrazioni e query di analisi. Nessun browser richiesto.

Esegui con:
  python test_database_schema.py
"""

import gc
import sys
import sqlite3
import tempfile
import unittest
import logging
from pathlib import Path

logging.basicConfig(level=logging.WARNING)

import src.database


def _setup_tmp_db(db_mod):
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = Path(tmp.name)
    orig = db_mod.DB_PATH
    db_mod.DB_PATH = db_path
    db_mod.init_db()
    return db_path, orig


def _teardown_tmp_db(db_mod, db_path, orig):
    db_mod.DB_PATH = orig
    gc.collect()
    try:
        db_path.unlink(missing_ok=True)
        Path(str(db_path) + "-wal").unlink(missing_ok=True)
        Path(str(db_path) + "-shm").unlink(missing_ok=True)
    except PermissionError:
        pass


class TestSchema(unittest.TestCase):
    """Verifica struttura tabelle e indici."""

    def setUp(self):
        self.db_path, self.orig = _setup_tmp_db(src.database)

    def tearDown(self):
        _teardown_tmp_db(src.database, self.db_path, self.orig)

    def _indexes(self):
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()
        conn.close()
        return {r[0] for r in rows}

    def test_tables_created(self):
        conn = sqlite3.connect(self.db_path)
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        conn.close()
        self.assertIn("seed_watches", tables)
        self.assertIn("recommendations", tables)

    def test_seed_watches_unique_index(self):
        self.assertIn("idx_seed_dedup", self._indexes())

    def test_recommendations_unique_index(self):
        self.assertIn("idx_recs_dedup", self._indexes())

    def test_recommendations_profile_day_index(self):
        self.assertIn("idx_recs_profile_day", self._indexes())

    def test_recommendations_video_id_index(self):
        self.assertIn("idx_recs_video_id", self._indexes())

    def test_init_db_idempotent(self):
        # Chiamare init_db due volte non deve sollevare eccezioni
        src.database.init_db()
        src.database.init_db()


class TestRecommendationsDedup(unittest.TestCase):
    """Verifica deduplicazione raccomandazioni con INSERT OR REPLACE."""

    def setUp(self):
        self.db_path, self.orig = _setup_tmp_db(src.database)

    def tearDown(self):
        _teardown_tmp_db(src.database, self.db_path, self.orig)

    def test_insert_recommendation_ok(self):
        ok = src.database.insert_recommendation("scienza", 1, 0, "v1", "T1", "C1")
        self.assertTrue(ok)

    def test_insert_recommendation_replace_on_duplicate_position(self):
        src.database.insert_recommendation("scienza", 1, 0, "v1", "T1", "C1")
        # Stessa posizione, video diverso: deve rimpiazzare
        ok = src.database.insert_recommendation("scienza", 1, 0, "v2", "T2", "C2")
        self.assertTrue(ok)
        recs = src.database.get_recommendations(profile="scienza", day=1)
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["video_id"], "v2")

    def test_different_positions_all_inserted(self):
        for i in range(5):
            src.database.insert_recommendation("scienza", 1, i, f"v{i}", f"T{i}", "C")
        recs = src.database.get_recommendations(profile="scienza", day=1)
        self.assertEqual(len(recs), 5)

    def test_same_video_different_profiles_both_inserted(self):
        src.database.insert_recommendation("scienza", 1, 0, "shared_vid", "T", "C")
        src.database.insert_recommendation("cucina",  1, 0, "shared_vid", "T", "C")
        recs = src.database.get_recommendations(day=1)
        self.assertEqual(len(recs), 2)

    def test_same_video_different_days_both_inserted(self):
        src.database.insert_recommendation("scienza", 1, 0, "same_vid", "T", "C")
        src.database.insert_recommendation("scienza", 2, 0, "same_vid", "T", "C")
        recs = src.database.get_recommendations(profile="scienza")
        self.assertEqual(len(recs), 2)


class TestQueryHelpers(unittest.TestCase):
    """Verifica le query di analisi dei dati raccolti."""

    def setUp(self):
        self.db_path, self.orig = _setup_tmp_db(src.database)
        # Popola DB con dati di test
        profiles = ["scienza", "cucina", "musica"]
        for p in profiles:
            for day in [1, 2, 3]:
                for pos in range(5):
                    vid = f"vid_{p}_{day}_{pos}" if pos > 0 else "shared_vid"
                    src.database.insert_recommendation(p, day, pos, vid, f"T{pos}", "C")

    def tearDown(self):
        _teardown_tmp_db(src.database, self.db_path, self.orig)

    def test_get_days_collected(self):
        days = src.database.get_days_collected()
        self.assertEqual(days, [1, 2, 3])

    def test_get_days_collected_empty(self):
        # DB con solo seed_watches
        conn = sqlite3.connect(self.db_path)
        conn.execute("DELETE FROM recommendations")
        conn.commit()
        conn.close()
        days = src.database.get_days_collected()
        self.assertEqual(days, [])

    def test_get_video_ids_returns_set(self):
        ids = src.database.get_video_ids("scienza", 1)
        self.assertIsInstance(ids, set)
        self.assertEqual(len(ids), 5)

    def test_get_video_ids_shared(self):
        # shared_vid deve apparire in tutti i profili al giorno 1
        for p in ["scienza", "cucina", "musica"]:
            ids = src.database.get_video_ids(p, 1)
            self.assertIn("shared_vid", ids)

    def test_get_video_ids_empty_profile(self):
        ids = src.database.get_video_ids("gaming", 1)
        self.assertEqual(ids, set())

    def test_get_profile_day_counts(self):
        counts = src.database.get_profile_day_counts()
        self.assertGreater(len(counts), 0)
        for row in counts:
            self.assertIn("profile", row)
            self.assertIn("day", row)
            self.assertIn("count", row)
            self.assertEqual(row["count"], 5)

    def test_get_top_videos_all_days(self):
        top = src.database.get_top_videos(limit=5)
        self.assertGreater(len(top), 0)
        # shared_vid deve essere in cima (presente in tutti i profili)
        self.assertEqual(top[0]["video_id"], "shared_vid")
        self.assertEqual(top[0]["profile_count"], 3)

    def test_get_top_videos_single_day(self):
        top = src.database.get_top_videos(day=2, limit=5)
        self.assertGreater(len(top), 0)
        self.assertEqual(top[0]["video_id"], "shared_vid")

    def test_get_collection_summary_structure(self):
        s = src.database.get_collection_summary()
        self.assertIn("days_collected", s)
        self.assertIn("total_records", s)
        self.assertIn("expected_total", s)
        self.assertIn("completeness_pct", s)
        self.assertIn("per_profile", s)

    def test_get_collection_summary_counts(self):
        s = src.database.get_collection_summary()
        self.assertEqual(s["days_collected"], [1, 2, 3])
        self.assertEqual(s["total_records"], 3 * 3 * 5)  # 3 profili x 3 giorni x 5 pos
        self.assertGreater(s["expected_total"], 0)

    def test_get_recommendations_filter_profile(self):
        recs = src.database.get_recommendations(profile="scienza")
        self.assertTrue(all(r["profile"] == "scienza" for r in recs))

    def test_get_recommendations_filter_day(self):
        recs = src.database.get_recommendations(day=2)
        self.assertTrue(all(r["day"] == 2 for r in recs))

    def test_get_recommendations_filter_both(self):
        recs = src.database.get_recommendations(profile="cucina", day=3)
        self.assertTrue(all(r["profile"] == "cucina" and r["day"] == 3 for r in recs))
        self.assertEqual(len(recs), 5)


class TestMigrationOnExistingData(unittest.TestCase):
    """Verifica che init_db() gestisca DB con duplicati preesistenti."""

    def setUp(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        self.db_path = Path(tmp.name)
        self.orig = src.database.DB_PATH
        src.database.DB_PATH = self.db_path

        # Crea schema minimo senza UNIQUE indexes (simula DB vecchio)
        conn = sqlite3.connect(self.db_path)
        conn.executescript("""
            CREATE TABLE seed_watches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile TEXT NOT NULL, video_id TEXT NOT NULL,
                title TEXT, channel TEXT, watched_at TEXT NOT NULL
            );
            CREATE TABLE recommendations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile TEXT NOT NULL, day INTEGER NOT NULL,
                position INTEGER NOT NULL, video_id TEXT NOT NULL,
                title TEXT, channel TEXT, category TEXT, scraped_at TEXT NOT NULL
            );
        """)
        # Inserisce duplicati
        conn.execute("INSERT INTO seed_watches (profile,video_id,title,channel,watched_at) VALUES ('scienza','v1','T','C','2024')")
        conn.execute("INSERT INTO seed_watches (profile,video_id,title,channel,watched_at) VALUES ('scienza','v1','T','C','2024')")
        conn.execute("INSERT INTO recommendations (profile,day,position,video_id,title,channel,scraped_at) VALUES ('scienza',1,0,'vid','T','C','2024')")
        conn.execute("INSERT INTO recommendations (profile,day,position,video_id,title,channel,scraped_at) VALUES ('scienza',1,0,'vid2','T2','C','2024')")
        conn.commit()
        conn.close()

    def tearDown(self):
        _teardown_tmp_db(src.database, self.db_path, self.orig)

    def test_init_db_deduplicates_and_adds_indexes(self):
        src.database.init_db()  # non deve sollevare eccezioni
        # Verifica che i duplicati siano stati rimossi
        conn = sqlite3.connect(self.db_path)
        sw_count = conn.execute("SELECT COUNT(*) FROM seed_watches").fetchone()[0]
        rc_count = conn.execute("SELECT COUNT(*) FROM recommendations").fetchone()[0]
        indexes = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()}
        conn.close()
        self.assertEqual(sw_count, 1)
        self.assertEqual(rc_count, 1)
        self.assertIn("idx_seed_dedup", indexes)
        self.assertIn("idx_recs_dedup", indexes)


def main():
    print("=" * 60)
    print("TEST MARTEDI SETTIMANA 2 — Schema DB Raccomandazioni")
    print("=" * 60)

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for cls in [TestSchema, TestRecommendationsDedup, TestQueryHelpers, TestMigrationOnExistingData]:
        suite.addTests(loader.loadTestsFromTestCase(cls))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 60)
    total = result.testsRun
    passed = total - len(result.failures) - len(result.errors)
    print(f"Risultato: {passed}/{total} test passati")
    if result.failures or result.errors:
        print(f"  Falliti: {len(result.failures)}  Errori: {len(result.errors)}")
        sys.exit(1)
    else:
        print("Tutti i test superati — schema DB verificato!")
        sys.exit(0)


if __name__ == "__main__":
    main()
