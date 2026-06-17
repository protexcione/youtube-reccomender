"""
Inspector del database — mostra lo stato attuale della raccolta dati.

Uso:
  python inspect_db.py              # riepilogo generale
  python inspect_db.py --top        # top video (piu' profili in comune)
  python inspect_db.py --day 1      # dettaglio giorno specifico
  python inspect_db.py --matrix     # matrice profilo x giorno con conteggi
"""

import sys
import argparse
from src.database import (
    init_db, get_collection_summary, get_profile_day_counts,
    get_top_videos, get_recommendations, get_days_collected,
)
from src.config import PROFILES, SIMULATION_DAYS, HOMEPAGE_RECS_COUNT


def print_summary():
    s = get_collection_summary()
    if not s:
        print("Database vuoto o errore di lettura.")
        return

    print("\n" + "=" * 60)
    print("STATO RACCOLTA DATI")
    print("=" * 60)
    print(f"  Giorni raccolti:  {s['days_collected']} su {SIMULATION_DAYS}")
    print(f"  Record totali:    {s['total_records']} / {s['expected_total']} attesi")
    print(f"  Completezza:      {s['completeness_pct']}%")

    print("\n  Per profilo:")
    for profile in PROFILES:
        info = s["per_profile"].get(profile, {"days": 0, "records": 0})
        bar = "#" * info["days"] + "." * (SIMULATION_DAYS - info["days"])
        print(f"    {profile:<10} [{bar}]  {info['records']:>3} record ({info['days']}/{SIMULATION_DAYS} giorni)")


def print_matrix():
    counts = get_profile_day_counts()
    days = get_days_collected()
    if not days:
        print("Nessun dato nel DB.")
        return

    # Costruisce la matrice
    data = {}
    for row in counts:
        data[(row["profile"], row["day"])] = row["count"]

    profiles = list(PROFILES.keys())
    print("\n" + "=" * 60)
    print("MATRICE PROFILO x GIORNO (n. raccomandazioni)")
    print("=" * 60)
    header = f"{'Profilo':<12}" + "".join(f"  G{d}" for d in days)
    print(header)
    print("-" * len(header))
    for p in profiles:
        row_str = f"{p:<12}"
        for d in days:
            n = data.get((p, d), 0)
            mark = f"{n:>4}" if n >= HOMEPAGE_RECS_COUNT else f"{n:>3}!"
            row_str += mark
        print(row_str)
    print("\n  (!) = meno di", HOMEPAGE_RECS_COUNT, "raccomandazioni — giorno incompleto")


def print_top(day: int = None):
    top = get_top_videos(day=day, limit=15)
    label = f"Giorno {day}" if day else "Tutti i giorni"
    print(f"\n{'=' * 60}")
    print(f"TOP VIDEO PIU' DIFFUSI — {label}")
    print(f"{'=' * 60}")
    print(f"  {'Profili':>7}  {'Titolo':<45}  Canale")
    print(f"  {'-'*7}  {'-'*45}  {'-'*20}")
    for v in top:
        stars = "*" * v["profile_count"]
        title = (v["title"] or "")[:44]
        channel = (v["channel"] or "")[:20]
        print(f"  {stars:>7}  {title:<45}  {channel}")
    print(f"\n  * = presente in 1 profilo, ***** = presente in tutti e 5")


def print_day_detail(day: int):
    recs = get_recommendations(day=day)
    if not recs:
        print(f"Nessun dato per il giorno {day}.")
        return

    print(f"\n{'=' * 60}")
    print(f"DETTAGLIO GIORNO {day}")
    print(f"{'=' * 60}")
    current_profile = None
    for r in recs:
        if r["profile"] != current_profile:
            current_profile = r["profile"]
            print(f"\n  [{current_profile.upper()}]")
        title = (r["title"] or "")[:50]
        channel = (r["channel"] or "")[:20]
        print(f"    {r['position']:>2}. {title:<50}  {channel}")


def main():
    parser = argparse.ArgumentParser(description="Inspector database YouTube Recommender")
    parser.add_argument("--top", action="store_true", help="Mostra top video comuni")
    parser.add_argument("--day", type=int, default=None, help="Dettaglio giorno specifico")
    parser.add_argument("--matrix", action="store_true", help="Matrice profilo x giorno")
    args = parser.parse_args()

    init_db()

    if args.day and not args.top and not args.matrix:
        print_summary()
        print_day_detail(args.day)
    elif args.top:
        print_top(day=args.day)
    elif args.matrix:
        print_matrix()
    else:
        print_summary()
        print_matrix()


if __name__ == "__main__":
    main()
