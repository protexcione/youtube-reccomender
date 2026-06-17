"""
Test Lunedi Settimana 2: scraping homepage YouTube.
Verifica il modulo src/scraper.py senza browser (mock Selenium).

Esegui con:
  python test_scraper.py
"""

import sys
import gc
import sqlite3
import tempfile
import unittest
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch, call

logging.basicConfig(level=logging.WARNING)

import src.scraper
import src.database


def _make_mock_item(video_id="abc123", title="Test Title", channel="Test Channel"):
    """Crea un mock di ytd-rich-item-renderer con dati realistici."""
    item = MagicMock()

    # Mock link con href e title
    link = MagicMock()
    link.get_attribute.side_effect = lambda attr: {
        "href": f"https://www.youtube.com/watch?v={video_id}",
        "title": title,
    }.get(attr, "")
    link.text = title
    item.find_element.return_value = link

    # Mock channel element
    channel_el = MagicMock()
    channel_el.text = channel
    item.find_elements.return_value = [channel_el]

    return item


class TestScrapeHomepage(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db_path = Path(self.tmp.name)
        import src.database as db
        self._orig_db = db.DB_PATH
        db.DB_PATH = self.db_path
        db.init_db()

    def tearDown(self):
        import src.database as db
        db.DB_PATH = self._orig_db
        gc.collect()
        try:
            self.db_path.unlink(missing_ok=True)
        except PermissionError:
            pass

    @patch("src.scraper.check_rate_limited", return_value=False)
    @patch("src.scraper.register_success")
    @patch("src.scraper.WebDriverWait")
    def test_scrape_returns_list(self, mock_wait, mock_reg, mock_rl):
        driver = MagicMock()
        items = [_make_mock_item(f"vid{i}", f"Titolo {i}", "Canale") for i in range(25)]
        driver.find_elements.return_value = items

        with patch("src.scraper.time.sleep"), \
             patch("src.scraper._scroll_to_load"):
            result = src.scraper.scrape_homepage(driver, "scienza", day=1, max_results=20)

        self.assertIsInstance(result, list)
        self.assertLessEqual(len(result), 20)

    @patch("src.scraper.check_rate_limited", return_value=False)
    @patch("src.scraper.register_success")
    @patch("src.scraper.WebDriverWait")
    def test_scrape_saves_to_db(self, mock_wait, mock_reg, mock_rl):
        driver = MagicMock()
        items = [_make_mock_item(f"vid{i}", f"Titolo {i}", "Canale") for i in range(5)]
        driver.find_elements.return_value = items

        with patch("src.scraper.time.sleep"), \
             patch("src.scraper._scroll_to_load"):
            result = src.scraper.scrape_homepage(driver, "scienza", day=1, max_results=5)

        import src.database as db
        recs = db.get_recommendations(profile="scienza", day=1)
        self.assertEqual(len(recs), len(result))
        self.assertGreater(len(recs), 0)

    @patch("src.scraper.check_rate_limited", return_value=False)
    @patch("src.scraper.register_success")
    @patch("src.scraper.WebDriverWait")
    def test_scrape_position_is_sequential(self, mock_wait, mock_reg, mock_rl):
        driver = MagicMock()
        items = [_make_mock_item(f"v{i}", f"T{i}", "C") for i in range(3)]
        driver.find_elements.return_value = items

        with patch("src.scraper.time.sleep"), \
             patch("src.scraper._scroll_to_load"):
            result = src.scraper.scrape_homepage(driver, "scienza", day=1, max_results=3)

        positions = [r["position"] for r in result]
        self.assertEqual(positions, list(range(len(result))))

    @patch("src.scraper.register_block")
    @patch("src.scraper.check_rate_limited", return_value=True)
    def test_scrape_returns_empty_on_rate_limit(self, mock_rl, mock_reg):
        driver = MagicMock()
        with patch("src.scraper.time.sleep"), \
             patch("src.scraper.backoff_wait"):
            result = src.scraper.scrape_homepage(driver, "scienza", day=1, retries=1)
        self.assertEqual(result, [])
        mock_reg.assert_called()

    @patch("src.scraper.check_rate_limited", return_value=False)
    @patch("src.scraper.register_success")
    @patch("src.scraper.WebDriverWait")
    def test_scrape_skips_non_video_items(self, mock_wait, mock_reg, mock_rl):
        # Item senza href valido
        bad_item = MagicMock()
        bad_link = MagicMock()
        bad_link.get_attribute.return_value = "https://www.youtube.com/channel/abc"
        bad_link.text = ""
        bad_item.find_element.return_value = bad_link
        bad_item.find_elements.return_value = []

        good_item = _make_mock_item("goodvid", "Good Video", "Good Channel")

        driver = MagicMock()
        driver.find_elements.return_value = [bad_item, good_item]

        with patch("src.scraper.time.sleep"), \
             patch("src.scraper._scroll_to_load"):
            result = src.scraper.scrape_homepage(driver, "scienza", day=1, max_results=5)

        video_ids = [r["video_id"] for r in result]
        self.assertNotIn("", video_ids)
        self.assertIn("goodvid", video_ids)

    @patch("src.scraper.check_rate_limited", return_value=False)
    @patch("src.scraper.register_success")
    @patch("src.scraper.WebDriverWait")
    def test_scrape_different_days_dont_conflict(self, mock_wait, mock_reg, mock_rl):
        driver = MagicMock()
        items = [_make_mock_item(f"v{i}", f"T{i}", "C") for i in range(3)]
        driver.find_elements.return_value = items

        with patch("src.scraper.time.sleep"), \
             patch("src.scraper._scroll_to_load"):
            src.scraper.scrape_homepage(driver, "scienza", day=1, max_results=3)
            # Giorno 2 stessi video_id — devono essere inseriti (no UNIQUE cross-day)
            result2 = src.scraper.scrape_homepage(driver, "scienza", day=2, max_results=3)

        import src.database as db
        day1 = db.get_recommendations(profile="scienza", day=1)
        day2 = db.get_recommendations(profile="scienza", day=2)
        self.assertGreater(len(day1), 0)
        self.assertGreater(len(day2), 0)

    def test_get_day_recommendation_count(self):
        import src.database as db
        db.insert_recommendation("scienza", 1, 0, "v1", "T1", "C1")
        db.insert_recommendation("scienza", 1, 1, "v2", "T2", "C2")
        db.insert_recommendation("scienza", 2, 0, "v3", "T3", "C3")

        count_day1 = src.scraper.get_day_recommendation_count("scienza", 1)
        count_day2 = src.scraper.get_day_recommendation_count("scienza", 2)
        count_day3 = src.scraper.get_day_recommendation_count("scienza", 3)

        self.assertEqual(count_day1, 2)
        self.assertEqual(count_day2, 1)
        self.assertEqual(count_day3, 0)


class TestExtractHelpers(unittest.TestCase):

    def test_extract_video_id_and_title_valid(self):
        item = _make_mock_item("dQw4w9WgXcQ", "Never Gonna Give You Up")
        vid_id, title = src.scraper._extract_video_id_and_title(item)
        self.assertEqual(vid_id, "dQw4w9WgXcQ")
        self.assertEqual(title, "Never Gonna Give You Up")

    def test_extract_video_id_and_title_no_watch_url(self):
        item = MagicMock()
        link = MagicMock()
        link.get_attribute.side_effect = lambda a: {
            "href": "https://www.youtube.com/channel/UC123",
            "title": ""
        }.get(a, "")
        link.text = ""
        item.find_element.return_value = link
        vid_id, title = src.scraper._extract_video_id_and_title(item)
        self.assertEqual(vid_id, "")
        self.assertEqual(title, "")

    def test_extract_channel_found(self):
        item = MagicMock()
        ch = MagicMock()
        ch.text = "Kurzgesagt"
        item.find_elements.return_value = [ch]
        channel = src.scraper._extract_channel(item)
        self.assertEqual(channel, "Kurzgesagt")

    def test_extract_channel_fallback_sconosciuto(self):
        item = MagicMock()
        item.find_elements.return_value = []
        channel = src.scraper._extract_channel(item)
        self.assertEqual(channel, "Sconosciuto")


def main():
    print("=" * 60)
    print("TEST LUNEDI SETTIMANA 2 — Scraping Homepage")
    print("=" * 60)

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for cls in [TestScrapeHomepage, TestExtractHelpers]:
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
        print("Tutti i test superati — scraper homepage verificato!")
        sys.exit(0)


if __name__ == "__main__":
    main()
