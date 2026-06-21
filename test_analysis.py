"""
Test funzioni di analisi: Jaccard, overlap, entropia, ripetizione.

Esegui con:
  python test_analysis.py
"""

import gc
import sys
import math
import tempfile
import unittest
import logging
from pathlib import Path

logging.basicConfig(level=logging.WARNING)

import src.database
from src.analysis import (
    jaccard, jaccard_matrix, jaccard_over_time, mean_jaccard_per_day,
    overlap_percent, overlap_over_time, mean_overlap_per_day,
    entropy, entropy_per_profile_per_day, mean_entropy_per_day,
    repetition_rate_per_profile,
    cross_profile_video_counts, PROFILE_LIST,
)


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


def _insert_recs(profiles, day, video_map):
    """video_map: {profile: [video_id, ...]}"""
    for p in profiles:
        vids = video_map.get(p, [])
        for pos, vid in enumerate(vids):
            src.database.insert_recommendation(p, day, pos, vid, f"T{vid}", "C")


class TestJaccardFunction(unittest.TestCase):

    def test_identical_sets(self):
        self.assertAlmostEqual(jaccard({"a", "b"}, {"a", "b"}), 1.0)

    def test_disjoint_sets(self):
        self.assertAlmostEqual(jaccard({"a"}, {"b"}), 0.0)

    def test_partial_overlap(self):
        # |A∩B|=1, |A∪B|=3
        self.assertAlmostEqual(jaccard({"a", "b"}, {"b", "c"}), 1/3)

    def test_empty_sets(self):
        self.assertAlmostEqual(jaccard(set(), set()), 0.0)

    def test_one_empty(self):
        self.assertAlmostEqual(jaccard({"a"}, set()), 0.0)


class TestJaccardMatrix(unittest.TestCase):

    def setUp(self):
        self.db_path, self.orig = _setup_tmp_db(src.database)
        # Giorno 1: scienza e cucina condividono "shared"
        _insert_recs(PROFILE_LIST, 1, {
            "scienza": ["shared", "s1", "s2"],
            "cucina":  ["shared", "c1", "c2"],
            "musica":  ["m1", "m2", "m3"],
            "sport":   ["sp1", "sp2", "sp3"],
            "gaming":  ["g1", "g2", "g3"],
        })

    def tearDown(self):
        _teardown_tmp_db(src.database, self.db_path, self.orig)

    def test_diagonal_is_one(self):
        m = jaccard_matrix(1)
        for p in PROFILE_LIST:
            self.assertAlmostEqual(m[(p, p)], 1.0)

    def test_symmetric(self):
        m = jaccard_matrix(1)
        for a in PROFILE_LIST:
            for b in PROFILE_LIST:
                self.assertAlmostEqual(m[(a, b)], m[(b, a)])

    def test_known_overlap(self):
        m = jaccard_matrix(1)
        # scienza ∩ cucina = {shared}, ∪ = 5 → 1/5 = 0.2
        self.assertAlmostEqual(m[("scienza", "cucina")], 1/5)

    def test_no_overlap_gives_zero(self):
        m = jaccard_matrix(1)
        self.assertAlmostEqual(m[("scienza", "musica")], 0.0)


class TestJaccardOverTime(unittest.TestCase):

    def setUp(self):
        self.db_path, self.orig = _setup_tmp_db(src.database)
        for day in [1, 2, 3]:
            _insert_recs(PROFILE_LIST, day, {
                "scienza": [f"s{day}_1", f"s{day}_2", "shared"],
                "cucina":  [f"c{day}_1", "shared", f"c{day}_2"],
                "musica":  [f"m{day}_{i}" for i in range(3)],
                "sport":   [f"sp{day}_{i}" for i in range(3)],
                "gaming":  [f"g{day}_{i}" for i in range(3)],
            })

    def tearDown(self):
        _teardown_tmp_db(src.database, self.db_path, self.orig)

    def test_returns_all_days(self):
        jot = jaccard_over_time()
        self.assertEqual(set(jot.keys()), {1, 2, 3})

    def test_mean_jaccard_per_day_keys(self):
        jot = jaccard_over_time()
        mpd = mean_jaccard_per_day(jot)
        self.assertEqual(set(mpd.keys()), {1, 2, 3})

    def test_mean_jaccard_in_range(self):
        jot = jaccard_over_time()
        mpd = mean_jaccard_per_day(jot)
        for v in mpd.values():
            self.assertGreaterEqual(v, 0.0)
            self.assertLessEqual(v, 1.0)


class TestOverlap(unittest.TestCase):

    def setUp(self):
        self.db_path, self.orig = _setup_tmp_db(src.database)
        _insert_recs(PROFILE_LIST, 1, {
            "scienza": ["v1", "v2", "v3", "v4"],
            "cucina":  ["v1", "v2", "x1", "x2"],
            "musica":  ["m1", "m2", "m3", "m4"],
            "sport":   ["sp1", "sp2", "sp3", "sp4"],
            "gaming":  ["g1", "g2", "g3", "g4"],
        })

    def tearDown(self):
        _teardown_tmp_db(src.database, self.db_path, self.orig)

    def test_overlap_known_value(self):
        op = overlap_percent(1)
        # scienza∩cucina=2, min(4,4)=4 → 50%
        self.assertAlmostEqual(op[("scienza", "cucina")], 50.0)

    def test_overlap_symmetric(self):
        op = overlap_percent(1)
        self.assertAlmostEqual(op[("scienza", "cucina")], op[("cucina", "scienza")])

    def test_no_overlap_zero(self):
        op = overlap_percent(1)
        self.assertAlmostEqual(op[("scienza", "musica")], 0.0)

    def test_mean_overlap_in_range(self):
        oot = {1: overlap_percent(1)}
        mpd = mean_overlap_per_day(oot)
        self.assertGreaterEqual(mpd[1], 0.0)
        self.assertLessEqual(mpd[1], 100.0)


class TestEntropy(unittest.TestCase):

    def setUp(self):
        self.db_path, self.orig = _setup_tmp_db(src.database)
        # Caso uniforme: 4 video distinti → H = log2(4) = 2
        _insert_recs(["scienza"], 1, {
            "scienza": ["v1", "v2", "v3", "v4"],
        })
        # Caso concentrato: stesso video ripetuto (non possibile per UNIQUE, ma testiamo logica)

    def tearDown(self):
        _teardown_tmp_db(src.database, self.db_path, self.orig)

    def test_entropy_uniform(self):
        recs = [{"video_id": f"v{i}"} for i in range(4)]
        ids = {r["video_id"] for r in recs}
        h = entropy(ids, recs)
        self.assertAlmostEqual(h, math.log2(4), places=5)

    def test_entropy_single(self):
        recs = [{"video_id": "v1"}]
        ids = {"v1"}
        self.assertAlmostEqual(entropy(ids, recs), 0.0)

    def test_entropy_empty(self):
        self.assertAlmostEqual(entropy(set(), []), 0.0)

    def test_entropy_per_profile_structure(self):
        epd = entropy_per_profile_per_day()
        self.assertIn("scienza", epd)
        self.assertIn(1, epd["scienza"])
        self.assertGreaterEqual(epd["scienza"][1], 0.0)

    def test_mean_entropy_per_day(self):
        epd = entropy_per_profile_per_day()
        mpd = mean_entropy_per_day(epd)
        self.assertIn(1, mpd)
        self.assertGreaterEqual(mpd[1], 0.0)

    def test_repetition_rate_no_repeats(self):
        rep = repetition_rate_per_profile()
        self.assertIn("scienza", rep)
        # Con 4 video unici nel giorno 1, tasso ripetizione = 0
        self.assertEqual(rep["scienza"]["rate_pct"], 0.0)


class TestCrossProfileCounts(unittest.TestCase):

    def setUp(self):
        self.db_path, self.orig = _setup_tmp_db(src.database)
        _insert_recs(PROFILE_LIST, 1, {
            "scienza": ["shared", "s1"],
            "cucina":  ["shared", "c1"],
            "musica":  ["m1"],
            "sport":   ["sp1"],
            "gaming":  ["g1"],
        })

    def tearDown(self):
        _teardown_tmp_db(src.database, self.db_path, self.orig)

    def test_shared_video_count(self):
        counts = cross_profile_video_counts(day=1)
        self.assertEqual(counts.get("shared", 0), 2)

    def test_unique_video_count(self):
        counts = cross_profile_video_counts(day=1)
        self.assertEqual(counts.get("s1", 0), 1)

    def test_all_day_counts(self):
        counts = cross_profile_video_counts()
        self.assertIn("shared", counts)


def main():
    print("=" * 60)
    print("TEST SETTIMANA 3 — Analisi Jaccard & Metriche")
    print("=" * 60)

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for cls in [
        TestJaccardFunction, TestJaccardMatrix, TestJaccardOverTime,
        TestOverlap, TestEntropy, TestCrossProfileCounts,
    ]:
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
        print("Tutti i test superati — analisi Jaccard verificata!")
        sys.exit(0)


if __name__ == "__main__":
    main()
