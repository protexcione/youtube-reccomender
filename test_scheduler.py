"""
Test scheduler APScheduler.
Verifica logica di stato, rilevamento giorno e configurazione job.
Nessun browser, nessuna attesa reale.

Esegui con:
  python test_scheduler.py
"""

import gc
import sys
import json
import sqlite3
import tempfile
import unittest
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

logging.basicConfig(level=logging.WARNING)

import src.database
import scheduler as sched_mod


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


class TestState(unittest.TestCase):
    """Verifica salvataggio e caricamento stato scheduler."""

    def setUp(self):
        self.tmp_state = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        self.tmp_state.close()
        self.state_path = Path(self.tmp_state.name)
        self._orig_state = sched_mod.STATE_FILE
        sched_mod.STATE_FILE = self.state_path

    def tearDown(self):
        sched_mod.STATE_FILE = self._orig_state
        gc.collect()
        try:
            self.state_path.unlink(missing_ok=True)
        except PermissionError:
            pass

    def test_load_state_default_when_missing(self):
        self.state_path.unlink()
        state = sched_mod.load_state()
        self.assertEqual(state["runs_completed"], 0)
        self.assertIsNone(state["last_run"])
        self.assertEqual(state["last_day"], 0)

    def test_save_and_load_state(self):
        state = {"runs_completed": 3, "last_run": "2024-01-03T10:00:00", "last_day": 3}
        sched_mod.save_state(state)
        loaded = sched_mod.load_state()
        self.assertEqual(loaded["runs_completed"], 3)
        self.assertEqual(loaded["last_day"], 3)

    def test_save_state_invalid_path_no_crash(self):
        sched_mod.STATE_FILE = Path("/nonexistent/path/state.json")
        sched_mod.save_state({"runs_completed": 1, "last_run": None, "last_day": 1})
        # Non deve sollevare eccezioni
        sched_mod.STATE_FILE = self.state_path


class TestNextDay(unittest.TestCase):
    """Verifica rilevamento del giorno successivo da raccogliere."""

    def setUp(self):
        self.db_path, self.orig = _setup_tmp_db(src.database)

    def tearDown(self):
        _teardown_tmp_db(src.database, self.db_path, self.orig)

    def test_next_day_empty_db(self):
        day = sched_mod.next_day_to_run()
        self.assertEqual(day, 1)

    def test_next_day_after_day1(self):
        # Inserisci dati per il giorno 1
        for p in ["scienza", "cucina", "musica", "sport", "gaming"]:
            for pos in range(20):
                src.database.insert_recommendation(p, 1, pos, f"v{pos}", "T", "C")
        day = sched_mod.next_day_to_run()
        self.assertEqual(day, 2)

    def test_next_day_skips_partial_day(self):
        # Solo 10 record per giorno 1 (incompleto) — deve proporre comunque giorno 1
        for p in ["scienza"]:
            for pos in range(10):
                src.database.insert_recommendation(p, 1, pos, f"v{pos}", "T", "C")
        # Giorno 1 è "in lista" perché ha almeno 1 record
        days = src.database.get_days_collected()
        self.assertEqual(days, [1])
        # next_day_to_run considera giorno 1 presente → propone 2
        day = sched_mod.next_day_to_run()
        self.assertEqual(day, 2)

    def test_next_day_none_when_all_complete(self):
        # Inserisci tutti i 7 giorni
        for d in range(1, 8):
            for p in ["scienza", "cucina", "musica", "sport", "gaming"]:
                for pos in range(20):
                    src.database.insert_recommendation(p, d, pos, f"v{d}{pos}", "T", "C")
        day = sched_mod.next_day_to_run()
        self.assertIsNone(day)


class TestIsDayComplete(unittest.TestCase):
    """Verifica rilevamento completezza di un giorno."""

    def setUp(self):
        self.db_path, self.orig = _setup_tmp_db(src.database)

    def tearDown(self):
        _teardown_tmp_db(src.database, self.db_path, self.orig)

    def test_incomplete_day(self):
        src.database.insert_recommendation("scienza", 1, 0, "v1", "T", "C")
        self.assertFalse(sched_mod.is_day_complete(1))

    def test_complete_day(self):
        for p in ["scienza", "cucina", "musica", "sport", "gaming"]:
            for pos in range(20):
                src.database.insert_recommendation(p, 1, pos, f"v{pos}", "T", "C")
        self.assertTrue(sched_mod.is_day_complete(1))

    def test_missing_profile_makes_incomplete(self):
        # Solo 4 profili su 5
        for p in ["scienza", "cucina", "musica", "sport"]:
            for pos in range(20):
                src.database.insert_recommendation(p, 1, pos, f"v{pos}", "T", "C")
        self.assertFalse(sched_mod.is_day_complete(1))


class TestSchedulerConfig(unittest.TestCase):
    """Verifica la configurazione del job APScheduler senza eseguirlo."""

    def test_scraping_job_shuts_down_when_all_done(self):
        scheduler = MagicMock()
        state = {"runs_completed": 0, "last_run": None, "last_day": 0}

        with patch("scheduler.next_day_to_run", return_value=None), \
             patch("scheduler._print_final_summary"), \
             patch("scheduler.save_state"):
            sched_mod.scraping_job(state, scheduler)

        scheduler.shutdown.assert_called_once_with(wait=False)

    def test_scraping_job_increments_state(self):
        scheduler = MagicMock()
        state = {"runs_completed": 2, "last_run": None, "last_day": 2}

        mock_results = {p: True for p in ["scienza", "cucina", "musica", "sport", "gaming"]}

        with patch("scheduler.next_day_to_run", return_value=3), \
             patch("scheduler._print_final_summary"), \
             patch("scheduler.save_state") as mock_save, \
             patch("scrape_homepage._run_profiles_with_retry", return_value=mock_results):
            sched_mod.scraping_job(state, scheduler)

        self.assertEqual(state["runs_completed"], 3)
        self.assertEqual(state["last_day"], 3)
        mock_save.assert_called_once()

    def test_scraping_job_shuts_down_on_last_day(self):
        from src.config import SIMULATION_DAYS
        scheduler = MagicMock()
        state = {"runs_completed": SIMULATION_DAYS - 1, "last_run": None, "last_day": SIMULATION_DAYS - 1}
        mock_results = {p: True for p in ["scienza", "cucina", "musica", "sport", "gaming"]}

        with patch("scheduler.next_day_to_run", return_value=SIMULATION_DAYS), \
             patch("scheduler._print_final_summary"), \
             patch("scheduler.save_state"), \
             patch("scrape_homepage._run_profiles_with_retry", return_value=mock_results):
            sched_mod.scraping_job(state, scheduler)

        scheduler.shutdown.assert_called_once_with(wait=False)

    def test_interval_default_is_24h(self):
        self.assertEqual(sched_mod.DEFAULT_INTERVAL_HOURS, 24)


def main():
    print("=" * 60)
    print("TEST MERCOLEDI SETTIMANA 2 — Scheduler APScheduler")
    print("=" * 60)

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for cls in [TestState, TestNextDay, TestIsDayComplete, TestSchedulerConfig]:
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
        print("Tutti i test superati — scheduler verificato!")
        sys.exit(0)


if __name__ == "__main__":
    main()
