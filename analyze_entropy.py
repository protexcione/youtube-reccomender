"""
Analisi entropia di Shannon H per profilo nel tempo (diversity decay).

Entropia di Shannon H = -Σ p_i * log2(p_i)
Applicata alla distribuzione dei video_id per profilo×giorno.
H alta = molti video diversi (diversità alta)
H bassa = pochi video dominano (convergenza/omogeneizzazione)

Produce:
  - reports/entropy_trend.png       (H per profilo nel tempo)
  - reports/entropy_mean.png        (H media su tutti i profili)
  - reports/entropy_summary.txt     (tabella numerica)

Uso:
  python analyze_entropy.py
  python analyze_entropy.py --no-plot
"""

import sys
import argparse
import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src.database import init_db, get_days_collected
from src.analysis import (
    PROFILE_LIST,
    entropy_per_profile_per_day,
    mean_entropy_per_day,
    repetition_rate_per_profile,
)
from src.config import REPORTS_DIR, SIMULATION_DAYS, HOMEPAGE_RECS_COUNT


PROFILE_COLORS = {
    "scienza": "#e74c3c",
    "cucina":  "#e67e22",
    "musica":  "#9b59b6",
    "sport":   "#2980b9",
    "gaming":  "#27ae60",
}

H_MAX_20 = math.log2(20)  # entropia max per 20 video unici in un giorno


def plot_entropy_per_profile(epd: dict, out_dir):
    days = sorted(next(iter(epd.values())).keys())
    h_max_cumulative = [math.log2(d * HOMEPAGE_RECS_COUNT) for d in days]

    fig, ax = plt.subplots(figsize=(10, 6))

    for profile in PROFILE_LIST:
        values = [epd[profile].get(d, 0.0) for d in days]
        ax.plot(days, values, marker="o", linewidth=2,
                color=PROFILE_COLORS[profile], label=profile, markersize=7)

    ax.plot(days, h_max_cumulative, color="gray", linestyle="--", linewidth=1,
            label="H max teorica (tutti unici)")
    ax.set_xlabel("Giorno")
    ax.set_ylabel("Entropia H cumulativa (bit)")
    ax.set_title(
        "Entropia cumulativa per profilo nel tempo\n(se i video si ripetono tra giorni, H cresce meno del massimo teorico)",
        fontsize=13, fontweight="bold"
    )
    ax.set_xticks(days)
    ax.legend(loc="upper left")
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    path = out_dir / "entropy_trend.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"  Salvato: {path}")


def plot_entropy_mean(mean_per_day: dict, out_dir):
    days = sorted(mean_per_day.keys())
    values = [mean_per_day[d] for d in days]
    h_max_cumulative = [math.log2(d * HOMEPAGE_RECS_COUNT) for d in days]

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(days, values, marker="o", linewidth=2.5,
            color="#8e44ad", markersize=9, label="H media profili")
    ax.fill_between(days, values, alpha=0.12, color="#8e44ad")
    ax.plot(days, h_max_cumulative, color="gray", linestyle="--", linewidth=1,
            label="H max teorica (tutti video unici)")
    ax.set_xlabel("Giorno")
    ax.set_ylabel("Entropia H cumulativa media (bit)")
    ax.set_title(
        "Entropia cumulativa media su tutti i profili nel tempo\n(distanza dalla linea grigia = video ripetuti tra giorni)",
        fontsize=13, fontweight="bold"
    )
    ax.set_xticks(days)
    for d, v in zip(days, values):
        ax.annotate(f"{v:.2f}", (d, v), textcoords="offset points",
                    xytext=(0, 10), ha="center", fontsize=9)
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    path = out_dir / "entropy_mean.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"  Salvato: {path}")


def print_summary(epd: dict, mean_per_day: dict) -> str:
    days = sorted(mean_per_day.keys())
    rep = repetition_rate_per_profile()

    lines = []
    lines.append("=" * 70)
    lines.append("ENTROPIA H CUMULATIVA — Riepilogo 7 giorni")
    lines.append("(H cumulativa: considera tutti i video visti fino a quel giorno)")
    lines.append("=" * 70)

    header = f"{'Profilo':<12}" + "".join(f"  Gg{d}" for d in days)
    lines.append(header)
    lines.append("-" * len(header))
    for profile in PROFILE_LIST:
        row = f"{profile:<12}"
        for d in days:
            h_max = math.log2(d * HOMEPAGE_RECS_COUNT)
            val = epd[profile].get(d, 0.0)
            pct = val / h_max * 100 if h_max > 0 else 0
            row += f"  {val:.2f}"
        lines.append(row)
    lines.append("-" * len(header))
    row = f"{'H max teor.':<12}"
    for d in days:
        row += f"  {math.log2(d * HOMEPAGE_RECS_COUNT):.2f}"
    lines.append(row)
    lines.append("=" * 70)

    # Tasso di ripetizione video
    lines.append("\nVIDEO RIPETUTI TRA GIORNI (stesso video in più sessioni)")
    lines.append(f"{'Profilo':<12}  {'Unici':<8}  {'Ripetuti':<10}  {'% ripetizione'}")
    lines.append("-" * 50)
    for profile in PROFILE_LIST:
        r = rep[profile]
        lines.append(
            f"{profile:<12}  {r['total_unique']:<8}  {r['repeated']:<10}  {r['rate_pct']:.1f}%"
        )

    all_means = [mean_per_day[d] for d in days]
    # Per H2 confrontiamo l'entropia al giorno 7 con H max teorica
    h_max_7 = math.log2(7 * HOMEPAGE_RECS_COUNT)
    efficiency_d7 = all_means[-1] / h_max_7 * 100
    mean_rep = sum(rep[p]["rate_pct"] for p in PROFILE_LIST) / len(PROFILE_LIST)

    lines.append(f"\nH cumulativa media giorno 7: {all_means[-1]:.4f} bit")
    lines.append(f"H max teorica giorno 7:      {h_max_7:.4f} bit")
    lines.append(f"Efficienza varietà:          {efficiency_d7:.1f}%")
    lines.append(f"Ripetizione media:           {mean_rep:.1f}% dei video visti più volte")

    h2_note = (
        "CONFERMATA (alta ripetizione = bassa diversità)" if mean_rep > 15
        else "NON CONFERMATA — YouTube propone video sempre nuovi"
    )
    lines.append(f"\nIpotesi H2 (diversity decay): {h2_note}")
    lines.append("")

    text = "\n".join(lines)
    print(text)
    return text


def main():
    parser = argparse.ArgumentParser(description="Analisi entropia Shannon")
    parser.add_argument("--no-plot", action="store_true")
    args = parser.parse_args()

    init_db()
    days = get_days_collected()
    if not days:
        print("Nessun dato nel DB.")
        sys.exit(1)

    print(f"\nAnalisi Entropia — {len(days)} giorni: {days}")
    epd = entropy_per_profile_per_day()
    mpd = mean_entropy_per_day(epd)

    summary = print_summary(epd, mpd)
    txt_path = REPORTS_DIR / "entropy_summary.txt"
    txt_path.write_text(summary, encoding="utf-8")
    print(f"  Salvato: {txt_path}")

    if not args.no_plot:
        print("\nGenerazione grafici...")
        plot_entropy_per_profile(epd, REPORTS_DIR)
        plot_entropy_mean(mpd, REPORTS_DIR)

    print("\nAnalisi Entropia completata.")


if __name__ == "__main__":
    main()
