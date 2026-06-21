"""
Analisi Settimana 3 — Martedi: Overlap % giornaliero + trend temporale.

Overlap% = |A ∩ B| / min(|A|, |B|) × 100  (quanto del profilo minore
           è già visto dall'altro profilo — più intuitivo del Jaccard).

Produce:
  - reports/overlap_trend.png          (overlap medio nel tempo)
  - reports/overlap_heatmap_pairs.png  (heatmap coppia × giorno)
  - reports/overlap_summary.txt        (tabella numerica)

Uso:
  python analyze_overlap.py
  python analyze_overlap.py --no-plot
"""

import sys
import argparse
from itertools import combinations

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

from src.database import init_db, get_days_collected
from src.analysis import (
    PROFILE_LIST, overlap_percent, overlap_over_time, mean_overlap_per_day,
)
from src.config import REPORTS_DIR


PAIRS = [(a, b) for a, b in combinations(PROFILE_LIST, 2)]
PAIR_LABELS = [f"{a}\n{b}" for a, b in PAIRS]


def plot_overlap_trend(mean_per_day: dict, out_dir):
    days = sorted(mean_per_day.keys())
    values = [mean_per_day[d] for d in days]

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(days, values, marker="o", linewidth=2.5, color="#2980b9", markersize=9)
    ax.fill_between(days, values, alpha=0.12, color="#2980b9")
    ax.set_xlabel("Giorno")
    ax.set_ylabel("Overlap medio (%)")
    ax.set_title(
        "Overlap medio tra profili nel tempo\n(% di video in comune rispetto al profilo più piccolo)",
        fontsize=13, fontweight="bold"
    )
    ax.set_xticks(days)
    ax.set_ylim(0, max(values) * 1.4 + 1)
    ax.grid(True, alpha=0.3)
    for d, v in zip(days, values):
        ax.annotate(f"{v:.1f}%", (d, v), textcoords="offset points",
                    xytext=(0, 10), ha="center", fontsize=9)
    plt.tight_layout()
    path = out_dir / "overlap_trend.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"  Salvato: {path}")


def plot_overlap_heatmap_pairs(oot: dict, out_dir):
    days = sorted(oot.keys())
    n_pairs = len(PAIRS)
    arr = np.zeros((n_pairs, len(days)))
    for j, day in enumerate(days):
        for i, (a, b) in enumerate(PAIRS):
            arr[i, j] = oot[day].get((a, b), 0.0)

    fig, ax = plt.subplots(figsize=(10, 6))
    sns.heatmap(
        arr,
        xticklabels=[f"Gg{d}" for d in days],
        yticklabels=[f"{a}–{b}" for a, b in PAIRS],
        annot=True,
        fmt=".0f",
        vmin=0,
        cmap="Blues",
        linewidths=0.4,
        ax=ax,
    )
    ax.set_title("Overlap % per coppia di profili × giorno", fontsize=13, fontweight="bold")
    ax.set_xlabel("Giorno")
    ax.set_ylabel("Coppia di profili")
    plt.tight_layout()
    path = out_dir / "overlap_heatmap_pairs.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"  Salvato: {path}")


def print_summary(oot: dict, mean_per_day: dict) -> str:
    days = sorted(oot.keys())

    lines = []
    lines.append("=" * 70)
    lines.append("OVERLAP % — Riepilogo 7 giorni")
    lines.append("=" * 70)

    header = f"{'Coppia':<22}" + "".join(f"  Gg{d}" for d in days)
    lines.append(header)
    lines.append("-" * len(header))
    for a, b in PAIRS:
        row = f"{a}–{b:<{21 - len(a)}}"
        for d in days:
            row += f"  {oot[d].get((a, b), 0.0):4.1f}"
        lines.append(row)
    lines.append("-" * len(header))
    row = f"{'MEDIA':<22}"
    for d in days:
        row += f"  {mean_per_day[d]:4.1f}"
    lines.append(row)
    lines.append("=" * 70)

    all_means = [mean_per_day[d] for d in days]
    delta = all_means[-1] - all_means[0]
    trend = "CRESCITA" if delta > 0.5 else ("CALO" if delta < -0.5 else "STABILE")
    lines.append(f"\nOverlap medio giorno 1:  {all_means[0]:.2f}%")
    lines.append(f"Overlap medio giorno 7:  {all_means[-1]:.2f}%")
    lines.append(f"Variazione (Δ):          {delta:+.2f}%  → {trend}")

    pair_means = {}
    for a, b in PAIRS:
        pair_means[(a, b)] = sum(oot[d].get((a, b), 0) for d in days) / len(days)
    most_sim = max(pair_means, key=pair_means.get)
    least_sim = min(pair_means, key=pair_means.get)
    lines.append(f"\nCoppia più sovrapposta:  {most_sim[0]}–{most_sim[1]}  ({pair_means[most_sim]:.2f}%)")
    lines.append(f"Coppia meno sovrapposta: {least_sim[0]}–{least_sim[1]}  ({pair_means[least_sim]:.2f}%)")

    # Confronto con H1
    max_overlap = max(max(oot[d].get((a, b), 0) for a, b in PAIRS) for d in days)
    lines.append(f"\nOverlap massimo osservato:  {max_overlap:.1f}%")
    lines.append(f"Ipotesi H1 (30-40%):        {'CONFERMATA' if max_overlap >= 30 else 'NON CONFERMATA'}")
    lines.append("")

    text = "\n".join(lines)
    print(text)
    return text


def main():
    parser = argparse.ArgumentParser(description="Analisi overlap % giornaliero")
    parser.add_argument("--no-plot", action="store_true")
    args = parser.parse_args()

    init_db()
    days = get_days_collected()
    if not days:
        print("Nessun dato nel DB.")
        sys.exit(1)

    print(f"\nAnalisi Overlap — {len(days)} giorni: {days}")
    oot = overlap_over_time()
    mpd = mean_overlap_per_day(oot)

    summary = print_summary(oot, mpd)
    txt_path = REPORTS_DIR / "overlap_summary.txt"
    txt_path.write_text(summary, encoding="utf-8")
    print(f"  Salvato: {txt_path}")

    if not args.no_plot:
        print("\nGenerazione grafici...")
        plot_overlap_trend(mpd, REPORTS_DIR)
        plot_overlap_heatmap_pairs(oot, REPORTS_DIR)

    print("\nAnalisi Overlap completata.")


if __name__ == "__main__":
    main()
