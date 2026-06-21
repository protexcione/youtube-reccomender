"""
Analisi Jaccard similarity tra profili per ogni giorno di raccolta.

Produce:
  - reports/jaccard_matrix_dayN.png  (heatmap 5×5 per ogni giorno)
  - reports/jaccard_trend.png        (Jaccard medio nel tempo)
  - reports/jaccard_summary.txt      (tabella numerica)

Uso:
  python analyze_jaccard.py
  python analyze_jaccard.py --day 3      # solo il giorno 3
  python analyze_jaccard.py --no-plot    # solo testo, nessun grafico
"""

import sys
import argparse
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from itertools import combinations

from src.database import init_db, get_days_collected
from src.analysis import (
    PROFILE_LIST, jaccard_matrix, jaccard_over_time, mean_jaccard_per_day
)
from src.config import REPORTS_DIR


def _matrix_to_array(matrix: dict) -> np.ndarray:
    n = len(PROFILE_LIST)
    arr = np.zeros((n, n))
    for i, a in enumerate(PROFILE_LIST):
        for j, b in enumerate(PROFILE_LIST):
            arr[i, j] = matrix[(a, b)]
    return arr


def plot_jaccard_heatmap(day: int, matrix: dict, out_dir: Path):
    arr = _matrix_to_array(matrix)
    fig, ax = plt.subplots(figsize=(7, 6))
    sns.heatmap(
        arr,
        xticklabels=PROFILE_LIST,
        yticklabels=PROFILE_LIST,
        annot=True,
        fmt=".2f",
        vmin=0,
        vmax=1,
        cmap="YlOrRd",
        linewidths=0.5,
        ax=ax,
    )
    ax.set_title(f"Jaccard Similarity — Giorno {day}", fontsize=14, fontweight="bold")
    ax.set_xlabel("Profilo")
    ax.set_ylabel("Profilo")
    plt.tight_layout()
    path = out_dir / f"jaccard_matrix_day{day}.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"  Salvato: {path}")
    return path


def plot_jaccard_trend(mean_per_day: dict, out_dir: Path):
    days = sorted(mean_per_day.keys())
    values = [mean_per_day[d] for d in days]

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(days, values, marker="o", linewidth=2, color="#e74c3c", markersize=8)
    ax.fill_between(days, values, alpha=0.15, color="#e74c3c")
    ax.set_xlabel("Giorno")
    ax.set_ylabel("Jaccard similarity media")
    ax.set_title("Convergenza delle raccomandazioni nel tempo\n(Jaccard medio su tutte le coppie di profili)",
                 fontsize=13, fontweight="bold")
    ax.set_xticks(days)
    ax.set_ylim(0, 1)
    ax.grid(True, alpha=0.3)

    # Annotazioni valori
    for d, v in zip(days, values):
        ax.annotate(f"{v:.3f}", (d, v), textcoords="offset points",
                    xytext=(0, 10), ha="center", fontsize=9)

    plt.tight_layout()
    path = out_dir / "jaccard_trend.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"  Salvato: {path}")
    return path


def print_summary(jot: dict, mean_per_day: dict):
    days = sorted(jot.keys())
    pairs = [(a, b) for a, b in combinations(PROFILE_LIST, 2)]

    lines = []
    lines.append("=" * 65)
    lines.append("JACCARD SIMILARITY — Riepilogo 7 giorni")
    lines.append("=" * 65)

    # Tabella giorno × coppia
    header = f"{'Coppia':<22}" + "".join(f" Gg{d:>2}" for d in days)
    lines.append(header)
    lines.append("-" * len(header))
    for a, b in pairs:
        row = f"{a}–{b:<{21-len(a)}}"
        for d in days:
            row += f"  {jot[d][(a, b)]:.2f}"
        lines.append(row)

    lines.append("-" * len(header))
    row = f"{'MEDIA':<22}"
    for d in days:
        row += f"  {mean_per_day[d]:.2f}"
    lines.append(row)
    lines.append("=" * 65)

    # Statistiche globali
    all_means = [mean_per_day[d] for d in days]
    lines.append(f"\nJaccard medio giorno 1:  {all_means[0]:.4f}")
    lines.append(f"Jaccard medio giorno 7:  {all_means[-1]:.4f}")
    delta = all_means[-1] - all_means[0]
    trend = "CRESCITA" if delta > 0.01 else ("CALO" if delta < -0.01 else "STABILE")
    lines.append(f"Variazione (Δ):          {delta:+.4f}  → {trend}")

    # Coppia più simile e meno simile (media su tutti i giorni)
    pair_means = {}
    for a, b in pairs:
        pair_means[(a, b)] = sum(jot[d][(a, b)] for d in days) / len(days)
    most_sim = max(pair_means, key=pair_means.get)
    least_sim = min(pair_means, key=pair_means.get)
    lines.append(f"\nCoppia più simile:       {most_sim[0]}–{most_sim[1]}  ({pair_means[most_sim]:.4f})")
    lines.append(f"Coppia meno simile:      {least_sim[0]}–{least_sim[1]}  ({pair_means[least_sim]:.4f})")
    lines.append("")

    text = "\n".join(lines)
    print(text)
    return text


def main():
    parser = argparse.ArgumentParser(description="Analisi Jaccard similarity")
    parser.add_argument("--day", type=int, default=None, help="Analizza solo questo giorno")
    parser.add_argument("--no-plot", action="store_true", help="Non generare grafici")
    args = parser.parse_args()

    init_db()
    days = get_days_collected()
    if not days:
        print("Nessun dato nel DB. Esegui prima la raccolta.")
        sys.exit(1)

    if args.day:
        if args.day not in days:
            print(f"Giorno {args.day} non presente nel DB. Giorni disponibili: {days}")
            sys.exit(1)
        days_to_analyze = [args.day]
    else:
        days_to_analyze = days

    print(f"\nAnalisi Jaccard — {len(days_to_analyze)} giorno/i: {days_to_analyze}")

    jot = {d: jaccard_matrix(d) for d in days_to_analyze}
    mean_per_day = mean_jaccard_per_day(jot)

    summary_text = print_summary(jot, mean_per_day)

    # Salva testo
    txt_path = REPORTS_DIR / "jaccard_summary.txt"
    txt_path.write_text(summary_text, encoding="utf-8")
    print(f"  Salvato: {txt_path}")

    if not args.no_plot:
        print("\nGenerazione grafici...")
        for d in days_to_analyze:
            plot_jaccard_heatmap(d, jot[d], REPORTS_DIR)
        if len(days_to_analyze) > 1:
            plot_jaccard_trend(mean_per_day, REPORTS_DIR)

    print("\nAnalisi Jaccard completata.")


if __name__ == "__main__":
    main()
