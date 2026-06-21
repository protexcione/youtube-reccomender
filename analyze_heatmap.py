"""
Analisi Settimana 3 — Giovedi: Heatmap profilo × categoria × giorno.

La categoria è inferita da titolo+canale via keyword (src/categorizer.py),
poiché non raccolta via scraping (settimana 2 sabato saltata).

Produce:
  - reports/heatmap_profile_category.png   (profilo × categoria, tutti i giorni)
  - reports/heatmap_category_day.png       (categoria × giorno, tutti i profili)
  - reports/category_summary.txt           (tabella distribuzione)

Uso:
  python analyze_heatmap.py
  python analyze_heatmap.py --no-plot
"""

import sys
import argparse
from collections import defaultdict

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

from src.database import init_db, get_days_collected, get_recommendations
from src.analysis import PROFILE_LIST
from src.categorizer import classify
from src.config import REPORTS_DIR


CATEGORIES = [
    "Scienza & Tech",
    "Cucina & Food",
    "Musica",
    "Sport",
    "Gaming & Videogiochi",
    "News & Attualità",
    "Intrattenimento",
    "Altro",
]


def build_counts(recs: list) -> dict:
    """
    Restituisce {profile: {category: count}} su tutte le raccomandazioni date.
    """
    counts = {p: defaultdict(int) for p in PROFILE_LIST}
    for r in recs:
        cat = classify(r.get("title", ""), r.get("channel", ""))
        counts[r["profile"]][cat] += 1
    return counts


def build_category_day_counts(days: list) -> dict:
    """Restituisce {category: {day: count}} su tutti i profili."""
    counts = {cat: defaultdict(int) for cat in CATEGORIES}
    for day in days:
        recs = get_recommendations(day=day)
        for r in recs:
            cat = classify(r.get("title", ""), r.get("channel", ""))
            counts[cat][day] += 1
    return counts


def plot_profile_category_heatmap(counts: dict, out_dir):
    arr = np.zeros((len(PROFILE_LIST), len(CATEGORIES)))
    for i, profile in enumerate(PROFILE_LIST):
        total = sum(counts[profile].values()) or 1
        for j, cat in enumerate(CATEGORIES):
            arr[i, j] = counts[profile].get(cat, 0) / total * 100

    fig, ax = plt.subplots(figsize=(13, 6))
    sns.heatmap(
        arr,
        xticklabels=[c.replace(" & ", "\n& ") for c in CATEGORIES],
        yticklabels=PROFILE_LIST,
        annot=True,
        fmt=".0f",
        cmap="YlOrRd",
        vmin=0,
        linewidths=0.4,
        ax=ax,
        cbar_kws={"label": "% raccomandazioni"},
    )
    ax.set_title(
        "Distribuzione categorie per profilo (% su 7 giorni)",
        fontsize=13, fontweight="bold"
    )
    ax.set_xlabel("Categoria")
    ax.set_ylabel("Profilo")
    plt.tight_layout()
    path = out_dir / "heatmap_profile_category.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"  Salvato: {path}")


def plot_category_day_heatmap(cat_day_counts: dict, days: list, out_dir):
    arr = np.zeros((len(CATEGORIES), len(days)))
    for i, cat in enumerate(CATEGORIES):
        for j, day in enumerate(days):
            arr[i, j] = cat_day_counts[cat].get(day, 0)

    fig, ax = plt.subplots(figsize=(11, 7))
    sns.heatmap(
        arr,
        xticklabels=[f"Gg{d}" for d in days],
        yticklabels=CATEGORIES,
        annot=True,
        fmt=".0f",
        cmap="Blues",
        linewidths=0.4,
        ax=ax,
        cbar_kws={"label": "n. video (tutti i profili)"},
    )
    ax.set_title(
        "Volume per categoria × giorno (tutti i profili sommati)",
        fontsize=13, fontweight="bold"
    )
    ax.set_xlabel("Giorno")
    ax.set_ylabel("Categoria")
    plt.tight_layout()
    path = out_dir / "heatmap_category_day.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"  Salvato: {path}")


def print_summary(counts: dict, cat_day_counts: dict, days: list) -> str:
    lines = []
    lines.append("=" * 70)
    lines.append("DISTRIBUZIONE CATEGORIE — Riepilogo")
    lines.append("(categoria inferita da titolo+canale via keyword)")
    lines.append("=" * 70)

    # Tabella profilo × categoria (conteggi assoluti)
    col_w = 10
    header = f"{'Categoria':<22}" + "".join(f"{p:>{col_w}}" for p in PROFILE_LIST) + f"{'TOTALE':>{col_w}}"
    lines.append(header)
    lines.append("-" * len(header))

    cat_totals = {}
    for cat in CATEGORIES:
        row = f"{cat:<22}"
        total = 0
        for profile in PROFILE_LIST:
            n = counts[profile].get(cat, 0)
            row += f"{n:>{col_w}}"
            total += n
        row += f"{total:>{col_w}}"
        cat_totals[cat] = total
        lines.append(row)

    lines.append("-" * len(header))
    row = f"{'TOTALE':<22}"
    grand = 0
    for profile in PROFILE_LIST:
        n = sum(counts[profile].values())
        row += f"{n:>{col_w}}"
        grand += n
    row += f"{grand:>{col_w}}"
    lines.append(row)
    lines.append("=" * 70)

    # Nota sul classificatore
    altro_pct = cat_totals.get("Altro", 0) / grand * 100
    classified = grand - cat_totals.get("Altro", 0)
    lines.append(f"\nNota metodologica: {altro_pct:.0f}% dei video non classificati da keyword")
    lines.append(f"Video classificati: {classified}/{grand} ({100-altro_pct:.0f}%)")

    # Categoria dominante per profilo (esclude Altro)
    lines.append("\nCATEGORIA DOMINANTE PER PROFILO (escluso 'Altro')")
    for profile in PROFILE_LIST:
        filtered = {k: v for k, v in counts[profile].items() if k != "Altro"}
        if filtered:
            dom = max(filtered, key=filtered.get)
            pct = filtered[dom] / sum(counts[profile].values()) * 100
            lines.append(f"  {profile:<10}  {dom}  ({pct:.0f}% del totale profilo)")

    # Categoria più trasversale tra quelle classificate (escluso Altro)
    sorted_cats_no_altro = sorted(
        [(c, t) for c, t in cat_totals.items() if c != "Altro"],
        key=lambda x: x[1], reverse=True
    )
    lines.append("\nCATEGORIE PIÙ TRASVERSALI (escluso 'Altro')")
    for cat, tot in sorted_cats_no_altro[:5]:
        # Conta in quanti profili appare almeno 1 video di questa categoria
        n_profiles = sum(1 for p in PROFILE_LIST if counts[p].get(cat, 0) > 0)
        lines.append(f"  {cat:<22}  {tot:>4} video  ({tot/grand*100:.1f}%)  [{n_profiles}/5 profili]")

    # Verifica H3 — escludi Altro
    if sorted_cats_no_altro:
        top_cat, top_tot = sorted_cats_no_altro[0]
        top_pct = top_tot / grand * 100
        n_profiles_top = sum(1 for p in PROFILE_LIST if counts[p].get(top_cat, 0) > 0)
        h3_note = (
            f"CONFERMATA — '{top_cat}' appare in {n_profiles_top}/5 profili ({top_pct:.1f}% del totale)"
            if n_profiles_top >= 4
            else f"PARZIALE — '{top_cat}' presente in {n_profiles_top}/5 profili ({top_pct:.1f}%)"
        )
    else:
        h3_note = "NON VALUTABILE — classificazione insufficiente"
    lines.append(f"\nIpotesi H3 (categoria 'calamita'): {h3_note}")
    lines.append("")

    text = "\n".join(lines)
    print(text)
    return text


def main():
    parser = argparse.ArgumentParser(description="Heatmap profilo × categoria × giorno")
    parser.add_argument("--no-plot", action="store_true")
    args = parser.parse_args()

    init_db()
    days = get_days_collected()
    if not days:
        print("Nessun dato nel DB.")
        sys.exit(1)

    print(f"\nAnalisi Heatmap Categorie — {len(days)} giorni: {days}")

    all_recs = get_recommendations()
    counts = build_counts(all_recs)
    cat_day_counts = build_category_day_counts(days)

    summary = print_summary(counts, cat_day_counts, days)
    txt_path = REPORTS_DIR / "category_summary.txt"
    txt_path.write_text(summary, encoding="utf-8")
    print(f"  Salvato: {txt_path}")

    if not args.no_plot:
        print("\nGenerazione grafici...")
        plot_profile_category_heatmap(counts, REPORTS_DIR)
        plot_category_day_heatmap(cat_day_counts, days, REPORTS_DIR)

    print("\nAnalisi Heatmap completata.")


if __name__ == "__main__":
    main()
