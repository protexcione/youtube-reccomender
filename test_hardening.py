"""
Test Sabato Settimana 1: Debug + Hardening
Verifica che tutte le protezioni implementate funzionino correttamente
senza richiedere un browser reale (usa mock/unit test).

Esegui con:
  python test_hardening.py
"""

import sys
import sqlite3
import tempfile
import unittest
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

# Setup logging minimo per i test
logging.basicConfig(level=logging.WARNING)

# Import anticipato dei moduli src per permettere il patching con @patch
import src.rate_limiter
import src.database
import src.driver
import src.watcher
import src.search


# ── 1. Rate Limiter ──────────────────────────────────────────────────────────

class TestRateLimiter(unittest.TestCase):

    def setUp(self):
        # Reset stato globale prima di ogni test
        import src.rate_limiter as rl
        rl._consecutive_blocks = 0

    def test_no_block_on_normal_page(self):
        from src.rate_limiter import check_rate_limited
        driver = MagicMock()
        driver.current_url = "https://www.youtube.com/results?search_query=test"
        driver.title = "test - YouTube"
        self.assertFalse(check_rate_limited(driver))

    def test_block_on_sorry_url(self):
        from src.rate_limiter import check_rate_limited
        driver = MagicMock()
        driver.current_url = "https://www.google.com/sorry/index?continue=https://youtube.com"
        driver.title = "Before you continue"
        self.assertTrue(check_rate_limited(driver))

    def test_block_on_captcha_title(self):
        from src.rate_limiter import check_rate_limited
        driver = MagicMock()
        driver.current_url = "https://www.youtube.com/"
        driver.title = "Prima di continuare su YouTube"
        self.assertTrue(check_rate_limited(driver))

    def test_block_on_unusual_traffic(self):
        from src.rate_limiter import check_rate_limited
        driver = MagicMock()
        driver.current_url = "https://www.youtube.com/"
        driver.title = "Unusual traffic detected"
        self.assertTrue(check_rate_limited(driver))

    def test_register_success_resets_counter(self):
        import src.rate_limiter as rl
        from src.rate_limiter import register_block, register_success
        register_block()
        register_block()
        self.assertEqual(rl._consecutive_blocks, 2)
        register_success()
        self.assertEqual(rl._consecutive_blocks, 0)

    def test_backoff_increases_with_blocks(self):
        import src.rate_limiter as rl
        from src.rate_limiter import register_block
        register_block()
        block1 = rl._consecutive_blocks
        register_block()
        block2 = rl._consecutive_blocks
        self.assertGreater(block2, block1)

    def test_driver_exception_returns_false(self):
        from src.rate_limiter import check_rate_limited
        driver = MagicMock()
        driver.current_url = PropertyMock(side_effect=Exception("driver dead"))
        # Non deve sollevare eccezioni
        result = check_rate_limited(driver)
        self.assertFalse(result)


# ── 2. Database ──────────────────────────────────────────────────────────────

class TestDatabase(unittest.TestCase):

    def setUp(self):
        # Usa un DB temporaneo per i test
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db_path = Path(self.tmp.name)

    def tearDown(self):
        self.db_path.unlink(missing_ok=True)

    def _get_module(self):
        """Carica database con DB_PATH patchato."""
        import importlib
        import src.database as db_mod
        # Patch DB_PATH per usare il DB temporaneo
        original = db_mod.DB_PATH
        db_mod.DB_PATH = self.db_path
        return db_mod, original

    def test_init_db_creates_tables(self):
        db, orig = self._get_module()
        try:
            db.init_db()
            conn = sqlite3.connect(self.db_path)
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
            conn.close()
            self.assertIn("seed_watches", tables)
            self.assertIn("recommendations", tables)
        finally:
            db.DB_PATH = orig

    def test_insert_seed_watch_returns_true(self):
        db, orig = self._get_module()
        try:
            db.init_db()
            result = db.insert_seed_watch("scienza", "abc123", "Test Video", "Test Channel")
            self.assertTrue(result)
        finally:
            db.DB_PATH = orig

    def test_insert_seed_watch_dedup(self):
        db, orig = self._get_module()
        try:
            db.init_db()
            db.insert_seed_watch("scienza", "abc123", "Test Video", "Test Channel")
            # Secondo inserimento dello stesso video deve restituire False
            result = db.insert_seed_watch("scienza", "abc123", "Test Video", "Test Channel")
            self.assertFalse(result)
            # Verifica che ci sia un solo record nel DB
            count = db.get_seed_watch_count("scienza")
            self.assertEqual(count, 1)
        finally:
            db.DB_PATH = orig

    def test_insert_seed_watch_different_profiles_ok(self):
        db, orig = self._get_module()
        try:
            db.init_db()
            db.insert_seed_watch("scienza", "abc123", "Test Video", "Test Channel")
            # Stesso video, profilo diverso: deve essere permesso
            result = db.insert_seed_watch("cucina", "abc123", "Test Video", "Test Channel")
            self.assertTrue(result)
            self.assertEqual(db.get_seed_watch_count(), 2)
        finally:
            db.DB_PATH = orig

    def test_insert_recommendation_returns_bool(self):
        db, orig = self._get_module()
        try:
            db.init_db()
            result = db.insert_recommendation(
                profile="scienza", day=1, position=1,
                video_id="xyz", title="Rec Video", channel="Channel"
            )
            self.assertTrue(result)
        finally:
            db.DB_PATH = orig

    def test_get_recommendations_returns_list(self):
        db, orig = self._get_module()
        try:
            db.init_db()
            db.insert_recommendation("scienza", 1, 1, "v1", "T1", "C1")
            db.insert_recommendation("cucina", 1, 1, "v2", "T2", "C2")
            recs = db.get_recommendations(profile="scienza")
            self.assertEqual(len(recs), 1)
            self.assertEqual(recs[0]["video_id"], "v1")
        finally:
            db.DB_PATH = orig

    def test_get_seed_watch_count(self):
        db, orig = self._get_module()
        try:
            db.init_db()
            self.assertEqual(db.get_seed_watch_count(), 0)
            db.insert_seed_watch("scienza", "v1", "T1", "C1")
            db.insert_seed_watch("scienza", "v2", "T2", "C2")
            self.assertEqual(db.get_seed_watch_count(), 2)
            self.assertEqual(db.get_seed_watch_count("scienza"), 2)
            self.assertEqual(db.get_seed_watch_count("cucina"), 0)
        finally:
            db.DB_PATH = orig


# ── 3. Driver ────────────────────────────────────────────────────────────────

class TestDriver(unittest.TestCase):

    def test_safe_quit_with_none(self):
        from src.driver import safe_quit
        # Non deve sollevare eccezioni
        safe_quit(None)

    def test_safe_quit_ignores_exception(self):
        from src.driver import safe_quit
        driver = MagicMock()
        driver.quit.side_effect = Exception("already dead")
        safe_quit(driver)  # non deve propagare l'eccezione

    @patch("src.driver.shutil.which", return_value=None)
    def test_get_driver_raises_if_no_chrome(self, mock_which):
        from src.driver import get_driver
        with self.assertRaises(RuntimeError) as ctx:
            get_driver("scienza")
        self.assertIn("Chrome", str(ctx.exception))

    @patch("src.driver.shutil.which", return_value="/usr/bin/google-chrome")
    @patch("src.driver.webdriver.Chrome")
    def test_get_driver_raises_on_webdriver_exception(self, mock_chrome, mock_which):
        from selenium.common.exceptions import WebDriverException
        from src.driver import get_driver
        mock_chrome.side_effect = WebDriverException("chrome not reachable")
        with self.assertRaises(RuntimeError):
            get_driver("scienza")


# ── 4. Watcher ───────────────────────────────────────────────────────────────

class TestWatcher(unittest.TestCase):

    def _make_video(self, video_id="abc123"):
        return {"video_id": video_id, "title": "Test Video", "channel": "Test Channel"}

    @patch("src.watcher.insert_seed_watch", return_value=True)
    @patch("src.watcher.check_rate_limited", return_value=False)
    @patch("src.watcher._simulate_watching")
    @patch("src.watcher._try_play")
    @patch("src.watcher.WebDriverWait")
    def test_watch_video_success(self, mock_wait, mock_play, mock_sim, mock_rl, mock_insert):
        from src.watcher import watch_video
        driver = MagicMock()
        result = watch_video(driver, self._make_video(), "scienza")
        self.assertTrue(result)
        mock_insert.assert_called_once()

    @patch("src.watcher.check_rate_limited", return_value=False)
    @patch("src.watcher.WebDriverWait")
    def test_watch_video_timeout_retries(self, mock_wait, mock_rl):
        from selenium.common.exceptions import TimeoutException
        from src.watcher import watch_video
        driver = MagicMock()
        # driver.get() non solleva eccezioni, ma WebDriverWait sì
        mock_wait.return_value.until.side_effect = TimeoutException()
        with patch("src.watcher.time.sleep"):
            result = watch_video(driver, self._make_video(), "scienza")
        self.assertFalse(result)
        # Deve aver provato _WATCH_RETRIES volte
        from src.watcher import _WATCH_RETRIES
        self.assertEqual(driver.get.call_count, _WATCH_RETRIES)

    @patch("src.watcher.backoff_wait")
    @patch("src.watcher.register_block")
    @patch("src.watcher.check_rate_limited", return_value=True)
    def test_watch_video_rate_limited(self, mock_rl, mock_reg, mock_backoff):
        from src.watcher import watch_video
        driver = MagicMock()
        with patch("src.watcher.time.sleep"):
            result = watch_video(driver, self._make_video(), "scienza")
        self.assertFalse(result)
        mock_reg.assert_called()

    @patch("src.watcher.watch_video")
    def test_watch_seed_videos_counts_success(self, mock_watch):
        from src.watcher import watch_seed_videos
        mock_watch.side_effect = [True, False, True, True, False]
        videos = [self._make_video(f"v{i}") for i in range(5)]
        driver = MagicMock()
        with patch("src.watcher.time.sleep"):
            count = watch_seed_videos(driver, "scienza", videos)
        self.assertEqual(count, 3)

    def test_simulate_watching_handles_js_error(self):
        from src.watcher import _simulate_watching
        driver = MagicMock()
        driver.execute_script.side_effect = Exception("JS error")
        # Non deve sollevare eccezioni
        with patch("src.watcher.time.sleep"), patch("src.watcher.random.random", return_value=0.0):
            _simulate_watching(driver, 5)


# ── 5. Search ────────────────────────────────────────────────────────────────

class TestSearch(unittest.TestCase):

    @patch("src.search.register_success")
    @patch("src.search.check_rate_limited", return_value=False)
    @patch("src.search.WebDriverWait")
    def test_search_returns_empty_on_no_results(self, mock_wait, mock_rl, mock_reg):
        from selenium.common.exceptions import TimeoutException
        from src.search import search_videos
        mock_wait.return_value.until.side_effect = TimeoutException()
        driver = MagicMock()
        with patch("src.search.time.sleep"):
            results = search_videos(driver, "test query", max_results=5)
        self.assertEqual(results, [])

    @patch("src.search.backoff_wait")
    @patch("src.search.register_block")
    @patch("src.search.check_rate_limited", return_value=True)
    def test_search_detects_rate_limit(self, mock_rl, mock_reg, mock_backoff):
        from src.search import search_videos
        driver = MagicMock()
        with patch("src.search.time.sleep"):
            results = search_videos(driver, "test", retries=1)
        self.assertEqual(results, [])
        mock_reg.assert_called()

    @patch("src.search.register_success")
    @patch("src.search.check_rate_limited", return_value=False)
    @patch("src.search.WebDriverWait")
    def test_search_parses_video_renderer(self, mock_wait, mock_rl, mock_reg):
        from src.search import search_videos

        # Mock renderer con link valido
        renderer = MagicMock()
        link = MagicMock()
        link.get_attribute.side_effect = lambda attr: {
            "href": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "title": "Never Gonna Give You Up",
        }.get(attr, "")
        link.text = "Never Gonna Give You Up"
        renderer.find_element.return_value = link
        renderer.find_elements.return_value = []  # channel = Sconosciuto

        driver = MagicMock()
        driver.find_elements.return_value = [renderer]

        with patch("src.search.time.sleep"):
            results = search_videos(driver, "test", max_results=1)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["video_id"], "dQw4w9WgXcQ")


# ── Runner ───────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("TEST SABATO SETTIMANA 1 — Debug + Hardening")
    print("=" * 60)

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    for test_class in [
        TestRateLimiter,
        TestDatabase,
        TestDriver,
        TestWatcher,
        TestSearch,
    ]:
        suite.addTests(loader.loadTestsFromTestCase(test_class))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 60)
    total = result.testsRun
    passed = total - len(result.failures) - len(result.errors)
    print(f"Risultato: {passed}/{total} test passati")

    if result.failures or result.errors:
        print(f"  Falliti:  {len(result.failures)}")
        print(f"  Errori:   {len(result.errors)}")
        sys.exit(1)
    else:
        print("Tutti i test superati — hardening verificato!")
        sys.exit(0)


if __name__ == "__main__":
    main()
