"""
Modulo analisi dati — Settimana 3.
Calcola Jaccard similarity, overlap %, entropia e statistiche per le visualizzazioni.
"""

import math
from itertools import combinations
from src.database import get_video_ids, get_days_collected, get_recommendations
from src.config import PROFILES, SIMULATION_DAYS


PROFILE_LIST = list(PROFILES.keys())


# ── Jaccard similarity ────────────────────────────────────────────────────────

def jaccard(set_a: set, set_b: set) -> float:
    """Jaccard similarity tra due insiemi di video."""
    if not set_a and not set_b:
        return 0.0
    union = set_a | set_b
    if not union:
        return 0.0
    return len(set_a & set_b) / len(union)


def jaccard_matrix(day: int) -> dict:
    """
    Restituisce matrice Jaccard 5×5 per un dato giorno.
    Chiavi: (profile_a, profile_b), valore: float [0,1].
    La matrice è simmetrica; diagonale = 1.0.
    """
    video_sets = {p: get_video_ids(p, day) for p in PROFILE_LIST}
    matrix = {}
    for p in PROFILE_LIST:
        for q in PROFILE_LIST:
            if p == q:
                matrix[(p, q)] = 1.0
            else:
                matrix[(p, q)] = jaccard(video_sets[p], video_sets[q])
    return matrix


def jaccard_over_time() -> dict:
    """
    Restituisce {day: jaccard_matrix(day)} per tutti i giorni con dati.
    """
    days = get_days_collected()
    return {d: jaccard_matrix(d) for d in days}


def mean_jaccard_per_day(jot: dict) -> dict:
    """
    Dato l'output di jaccard_over_time(), restituisce {day: mean_jaccard}
    calcolando la media sulle coppie distinte (esclude diagonale).
    """
    result = {}
    pairs = [(a, b) for a, b in combinations(PROFILE_LIST, 2)]
    for day, matrix in jot.items():
        values = [matrix[(a, b)] for a, b in pairs]
        result[day] = sum(values) / len(values) if values else 0.0
    return result


# ── Overlap % ────────────────────────────────────────────────────────────────

def overlap_percent(day: int) -> dict:
    """
    Overlap % per ogni coppia di profili al giorno dato.
    Overlap% = |A ∩ B| / min(|A|, |B|) * 100  (simmetrico rispetto alla dimensione minore).
    """
    video_sets = {p: get_video_ids(p, day) for p in PROFILE_LIST}
    result = {}
    for a, b in combinations(PROFILE_LIST, 2):
        sa, sb = video_sets[a], video_sets[b]
        denom = min(len(sa), len(sb))
        pct = (len(sa & sb) / denom * 100) if denom > 0 else 0.0
        result[(a, b)] = pct
        result[(b, a)] = pct
    return result


def overlap_over_time() -> dict:
    """Restituisce {day: overlap_percent(day)} per tutti i giorni."""
    days = get_days_collected()
    return {d: overlap_percent(d) for d in days}


def mean_overlap_per_day(oot: dict) -> dict:
    """Media dell'overlap % su tutte le coppie per giorno."""
    pairs = [(a, b) for a, b in combinations(PROFILE_LIST, 2)]
    result = {}
    for day, matrix in oot.items():
        values = [matrix.get((a, b), 0.0) for a, b in pairs]
        result[day] = sum(values) / len(values) if values else 0.0
    return result


# ── Entropia H ───────────────────────────────────────────────────────────────

def entropy(video_ids: set, all_recs: list) -> float:
    """
    Entropia di Shannon per un insieme di raccomandazioni.
    Distribuzione: frequenza normalizzata dei video_id.
    """
    if not video_ids:
        return 0.0
    total = len(all_recs)
    freq = {}
    for r in all_recs:
        vid = r["video_id"]
        freq[vid] = freq.get(vid, 0) + 1
    h = 0.0
    for count in freq.values():
        p = count / total
        if p > 0:
            h -= p * math.log2(p)
    return h


def cumulative_entropy_per_profile(up_to_day: int, profile: str) -> float:
    """
    Entropia cumulativa: considera tutti i video visti dal profilo
    fino al giorno `up_to_day` (incluso).
    Se gli stessi video si ripetono tra giorni diversi, H è più bassa.
    H max = log2(up_to_day * 20) se tutti i video sono unici.
    """
    recs = [r for r in get_recommendations(profile=profile)
            if r["day"] <= up_to_day]
    if not recs:
        return 0.0
    ids = {r["video_id"] for r in recs}
    return entropy(ids, recs)


def entropy_per_profile_per_day() -> dict:
    """
    Restituisce {profile: {day: H_cumulativa}} per tutti i profili e giorni.
    H calcolata su tutti i video visti fino a quel giorno — se gli stessi
    video si ripetono tra giorni, H è inferiore al massimo teorico.
    """
    days = get_days_collected()
    result = {p: {} for p in PROFILE_LIST}
    for day in days:
        for profile in PROFILE_LIST:
            result[profile][day] = cumulative_entropy_per_profile(day, profile)
    return result


def repetition_rate_per_profile() -> dict:
    """
    Per ogni profilo: quanti video appaiono in più di un giorno?
    Restituisce {profile: {"repeated": n, "total_unique": n, "rate_pct": float}}.
    """
    result = {}
    for profile in PROFILE_LIST:
        recs = get_recommendations(profile=profile)
        from collections import Counter
        day_sets = {}
        for r in recs:
            day_sets.setdefault(r["day"], set()).add(r["video_id"])
        all_vids = [r["video_id"] for r in recs]
        freq = Counter(all_vids)
        repeated = sum(1 for v, c in freq.items() if c > 1)
        total_unique = len(freq)
        result[profile] = {
            "repeated": repeated,
            "total_unique": total_unique,
            "rate_pct": repeated / total_unique * 100 if total_unique else 0.0,
        }
    return result


def mean_entropy_per_day(epd: dict) -> dict:
    """Dato {profile: {day: H}}, restituisce {day: mean_H}."""
    days = get_days_collected()
    result = {}
    for day in days:
        values = [epd[p].get(day, 0.0) for p in PROFILE_LIST]
        result[day] = sum(values) / len(values) if values else 0.0
    return result


# ── Statistiche generali ─────────────────────────────────────────────────────

def cross_profile_video_counts(day: int = None) -> dict:
    """
    Per ogni video_id, conta in quanti profili appare (opzionalmente filtrato per giorno).
    Restituisce {video_id: count}.
    """
    recs = get_recommendations(day=day)
    counts = {}
    for r in recs:
        vid = r["video_id"]
        profile = r["profile"]
        if vid not in counts:
            counts[vid] = set()
        counts[vid].add(profile)
    return {vid: len(profiles) for vid, profiles in counts.items()}


def unique_videos_per_profile_per_day() -> dict:
    """Restituisce {profile: {day: n_unique_videos}}."""
    days = get_days_collected()
    result = {p: {} for p in PROFILE_LIST}
    for day in days:
        for profile in PROFILE_LIST:
            result[profile][day] = len(get_video_ids(profile, day))
    return result
