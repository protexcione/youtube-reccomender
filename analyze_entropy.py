"""
Analisi Settimana 3 — Mercoledi: Entropia H per giorno per profilo.

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
)
from src.config import REPORTS_DIR


PROFILE_COLORS = {
    "scienza": "#e74c3c",
    "cucina":  "#e67e22",
    "musica":  "#9b59b6",
    "sport":   "#2980b9",
    "gaming":  "#27ae60",
}

H_MAX_20 = math.log2(20)  # entropia massima teorica con 20 video distinti ≈ 4.32


def plot_entropy_per_profile(epd: dict, out_dir):
    days = sorted(next(iter(epd.values())).keys())
    fig, ax = plt.subplots(figsize=(10, 6))

    for profile in PROFILE_LIST:
        values = [epd[profile].get(d, 0.0) for d in days]
        ax.plot(days, values, marker="o", linewidth=2,
                color=PROFILE_COLORS[profile], label=profile, markersize=7)

    ax.axhline(H_MAX_20, color="gray", linestyle="--", linewidth=1,
               label=f"H max teorica ({H_MAX_20:.2f})")
    ax.set_xlabel("Giorno")
    ax.set_ylabel("Entropia H (bit)")
    ax.set_title(
        "Entropia delle raccomandazioni per profilo nel tempo\n(H alta = maggiore varietà, H bassa = convergenza)",
        fontsize=13, fontweight="bold"
    )
    ax.set_xticks(days)
    ax.set_ylim(0, H_MAX_20 * 1.15)
    ax.legend(loc="lower right")
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    path = out_dir / "entropy_trend.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"  Salvato: {path}")


def plot_entropy_mean(mean_per_day: dict, out_dir):
    days = sorted(mean_per_day.keys())
    values = [mean_per_day[d] for d in days]

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(days, values, marker="o", linewidth=2.5,
            color="#8e44ad", markersize=9)
    ax.fill_between(days, values, alpha=0.12, color="#8e44ad")
    ax.axhline(H_MAX_20, color="gray", linestyle="--", linewidth=1,
               label=f"H max teorica ({H_MAX_20:.2f} bit)")
    ax.set_xlabel("Giorno")
    ax.set_ylabel("Entropia H media (bit)")
    ax.set_title(
        "Entropia media su tutti i profili nel tempo\n(indica se la diversità aumenta o diminuisce)",
        fontsize=13, fontweight="bold"
    )
    ax.set_xticks(days)
    ax.set_ylim(0, H_MAX_20 * 1.2)
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

    lines = []
    lines.append("=" * 65)
    lines.append("ENTROPIA H — Riepilogo 7 giorni")
    lines.append(f"(H max teorica con 20 video distinti: {H_MAX_20:.4f} bit)")
    lines.append("=" * 65)

    header = f"{'Profilo':<12}" + "".join(f"  Gg{d}" for d in days)
    lines.append(header)
    lines.append("-" * len(header))
    for profile in PROFILE_LIST:
        row = f"{profile:<12}"
        for d in days:
            row += f"  {epd[profile].get(d, 0.0):.2f}"
        lines.append(row)
    lines.append("-" * len(header))
    row = f"{'MEDIA':<12}"
    for d in days:
        row += f"  {mean_per_day[d]:.2f}"
    lines.append(row)
    lines.append("=" * 65)

    all_means = [mean_per_day[d] for d in days]
    delta = all_means[-1] - all_means[0]
    trend = "CRESCITA (più varietà)" if delta > 0.05 else (
            "CALO (meno varietà = convergenza)" if delta < -0.05 else "STABILE")
    lines.append(f"\nH media giorno 1:  {all_means[0]:.4f} bit")
    lines.append(f"H media giorno 7:  {all_means[-1]:.4f} bit")
    lines.append(f"Variazione (Δ):    {delta:+.4f} bit  → {trend}")

    # Profilo con entropia più bassa (più convergente)
    profile_means = {
        p: sum(epd[p].get(d, 0) for d in days) / len(days)
        for p in PROFILE_LIST
    }
    most_conv = min(profile_means, key=profile_means.get)
    least_conv = max(profile_means, key=profile_means.get)
    lines.append(f"\nProfilo più convergente:  {most_conv} (H media {profile_means[most_conv]:.4f})")
    lines.append(f"Profilo più diversificato: {least_conv} (H media {profile_means[least_conv]:.4f})")

    # Verifica H2
    h2_confirmed = delta < -0.05
    lines.append(f"\nIpotesi H2 (H scende nel tempo): {'CONFERMATA' if h2_confirmed else 'NON CONFERMATA'}")
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
