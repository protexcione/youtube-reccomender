"""
Analisi Settimana 3 — Venerdi: Grafo convergenza NetworkX.

Nodi = profili (5), archi = Jaccard similarity per giorno.
Produce un grafo per ogni giorno + un grafo animato (GIF) che mostra
l'evoluzione della convergenza nel tempo.

Produce:
  - reports/graph_day{N}.png        (grafo statico per ogni giorno)
  - reports/graph_convergence.gif   (animazione 7 frame)
  - reports/graph_summary.txt       (metriche di rete per giorno)

Uso:
  python analyze_graph.py
  python analyze_graph.py --no-gif       # solo PNG statici
  python analyze_graph.py --threshold 0  # mostra tutti gli archi
"""

import sys
import argparse

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import networkx as nx

from src.database import init_db, get_days_collected
from src.analysis import PROFILE_LIST, jaccard_over_time
from src.config import REPORTS_DIR


PROFILE_COLORS = {
    "scienza": "#e74c3c",
    "cucina":  "#e67e22",
    "musica":  "#9b59b6",
    "sport":   "#2980b9",
    "gaming":  "#27ae60",
}

# Layout fisso per tutti i giorni (posizioni dei nodi costanti)
_FIXED_POS = {
    "scienza": (0.0,  0.95),
    "cucina":  (0.90, 0.29),
    "musica":  (0.56, -0.76),
    "sport":   (-0.56, -0.76),
    "gaming":  (-0.90, 0.29),
}


def build_graph(matrix: dict, threshold: float = 0.0) -> nx.Graph:
    """Costruisce un grafo pesato dai valori Jaccard della matrice."""
    G = nx.Graph()
    G.add_nodes_from(PROFILE_LIST)
    for i, a in enumerate(PROFILE_LIST):
        for b in PROFILE_LIST[i+1:]:
            w = matrix[(a, b)]
            if w >= threshold:
                G.add_edge(a, b, weight=w)
    return G


def _draw_graph(ax, G: nx.Graph, day: int, max_weight: float = 0.15):
    ax.clear()
    pos = _FIXED_POS

    # Archi — spessore e opacità proporzionali al peso
    edges = G.edges(data=True)
    edge_list = [(u, v) for u, v, d in edges]
    weights = [d["weight"] for u, v, d in G.edges(data=True)]

    if edge_list:
        widths = [w / max_weight * 6 + 0.5 for w in weights]
        alphas = [min(w / max_weight, 1.0) * 0.85 + 0.1 for w in weights]
        for (u, v), width, alpha in zip(edge_list, widths, alphas):
            nx.draw_networkx_edges(
                G, pos, edgelist=[(u, v)], width=width,
                alpha=alpha, edge_color="#555555", ax=ax
            )
        # Etichette peso sugli archi
        edge_labels = {(u, v): f"{d['weight']:.2f}" for u, v, d in G.edges(data=True)}
        nx.draw_networkx_edge_labels(
            G, pos, edge_labels=edge_labels,
            font_size=7, font_color="#333333", ax=ax
        )

    # Nodi
    node_colors = [PROFILE_COLORS[n] for n in G.nodes()]
    nx.draw_networkx_nodes(
        G, pos, node_color=node_colors,
        node_size=1800, alpha=0.95, ax=ax
    )
    nx.draw_networkx_labels(
        G, pos, font_size=9, font_weight="bold",
        font_color="white", ax=ax
    )

    # Metriche sul grafo
    if G.number_of_edges() > 0:
        avg_w = np.mean(weights)
        density = nx.density(G)
        ax.set_title(
            f"Grafo convergenza — Giorno {day}\n"
            f"Jaccard medio: {avg_w:.3f}  |  Densità: {density:.2f}",
            fontsize=12, fontweight="bold"
        )
    else:
        ax.set_title(f"Grafo convergenza — Giorno {day}\n(nessun arco sopra soglia)",
                     fontsize=12, fontweight="bold")

    ax.set_xlim(-1.3, 1.3)
    ax.set_ylim(-1.1, 1.2)
    ax.axis("off")


def plot_static_graphs(jot: dict, threshold: float, out_dir):
    max_weight = max(
        (v for matrix in jot.values() for (a, b), v in matrix.items() if a != b),
        default=0.15
    )
    for day in sorted(jot.keys()):
        G = build_graph(jot[day], threshold)
        fig, ax = plt.subplots(figsize=(7, 7))
        _draw_graph(ax, G, day, max_weight)
        plt.tight_layout()
        path = out_dir / f"graph_day{day}.png"
        fig.savefig(path, dpi=130)
        plt.close(fig)
        print(f"  Salvato: {path}")


def plot_animated_gif(jot: dict, threshold: float, out_dir):
    days = sorted(jot.keys())
    max_weight = max(
        (v for matrix in jot.values() for (a, b), v in matrix.items() if a != b),
        default=0.15
    )
    graphs = [build_graph(jot[d], threshold) for d in days]

    fig, ax = plt.subplots(figsize=(7, 7))

    def update(frame):
        _draw_graph(ax, graphs[frame], days[frame], max_weight)

    ani = animation.FuncAnimation(
        fig, update, frames=len(days), interval=1000, repeat=True
    )
    path = out_dir / "graph_convergence.gif"
    ani.save(str(path), writer="pillow", fps=1)
    plt.close(fig)
    print(f"  Salvato: {path}")


def print_summary(jot: dict, threshold: float) -> str:
    days = sorted(jot.keys())
    lines = []
    lines.append("=" * 60)
    lines.append("GRAFO CONVERGENZA — Metriche di rete per giorno")
    lines.append(f"(soglia archi: Jaccard >= {threshold})")
    lines.append("=" * 60)
    lines.append(f"{'Giorno':<8} {'Archi':>6} {'Densità':>9} {'J.medio':>9} {'J.max':>9}")
    lines.append("-" * 45)

    for day in days:
        G = build_graph(jot[day], threshold)
        weights = [d["weight"] for _, _, d in G.edges(data=True)]
        avg_w = np.mean(weights) if weights else 0.0
        max_w = max(weights) if weights else 0.0
        density = nx.density(G)
        n_edges = G.number_of_edges()
        lines.append(
            f"  Gg{day:<5} {n_edges:>6} {density:>9.3f} {avg_w:>9.3f} {max_w:>9.3f}"
        )

    lines.append("=" * 60)

    # Giorno con massima convergenza
    day_avg = {}
    for day in days:
        weights = [jot[day][(a, b)] for a in PROFILE_LIST for b in PROFILE_LIST if a < b]
        day_avg[day] = np.mean(weights) if weights else 0.0
    best_day = max(day_avg, key=day_avg.get)
    worst_day = min(day_avg, key=day_avg.get)
    lines.append(f"\nGiorno più convergente:   Gg{best_day}  (J.medio={day_avg[best_day]:.4f})")
    lines.append(f"Giorno meno convergente:  Gg{worst_day}  (J.medio={day_avg[worst_day]:.4f})")

    # Coppia più connessa in media
    pair_avg = {}
    for a in PROFILE_LIST:
        for b in PROFILE_LIST:
            if a < b:
                pair_avg[(a, b)] = np.mean([jot[d][(a, b)] for d in days])
    best_pair = max(pair_avg, key=pair_avg.get)
    lines.append(f"Coppia più simile:        {best_pair[0]}–{best_pair[1]}  (J={pair_avg[best_pair]:.4f})")
    lines.append("")

    text = "\n".join(lines)
    print(text)
    return text


def main():
    parser = argparse.ArgumentParser(description="Grafo convergenza NetworkX")
    parser.add_argument("--threshold", type=float, default=0.0,
                        help="Soglia minima Jaccard per disegnare un arco (default: 0)")
    parser.add_argument("--no-gif", action="store_true", help="Non generare GIF animata")
    args = parser.parse_args()

    init_db()
    days = get_days_collected()
    if not days:
        print("Nessun dato nel DB.")
        sys.exit(1)

    print(f"\nAnalisi Grafo NetworkX — {len(days)} giorni: {days}")

    jot = jaccard_over_time()
    summary = print_summary(jot, args.threshold)

    txt_path = REPORTS_DIR / "graph_summary.txt"
    txt_path.write_text(summary, encoding="utf-8")
    print(f"  Salvato: {txt_path}")

    print("\nGenerazione grafici statici...")
    plot_static_graphs(jot, args.threshold, REPORTS_DIR)

    if not args.no_gif:
        print("Generazione GIF animata...")
        try:
            plot_animated_gif(jot, args.threshold, REPORTS_DIR)
        except Exception as e:
            print(f"  GIF non generata ({e}) — installa pillow: pip install pillow")

    print("\nAnalisi Grafo completata.")


if __name__ == "__main__":
    main()
