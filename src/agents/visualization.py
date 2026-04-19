"""
Visualization Agent
===================
Generates publication-ready figures from processed bibliometric data.
Outputs: PNG/SVG figures in data/outputs/figures/

Standalone:
    python src/agents/visualization.py --config config/config.yaml
"""

import argparse
import os
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.utils.io_utils import load_json, load_parquet, load_yaml
from src.utils.logging_utils import setup_logger

STYLE = {
    "figure.figsize": (10, 6),
    "axes.spines.top": False,
    "axes.spines.right": False,
    "font.family": "DejaVu Sans",
    "axes.titlesize": 13,
    "axes.labelsize": 11,
}
plt.rcParams.update(STYLE)


def fig_publication_trends(trends: dict, fig_dir: str) -> None:
    annual = pd.DataFrame(trends["annual"])
    if annual.empty:
        return
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Left: annual counts
    ax = axes[0]
    ax.bar(annual["year"], annual["count"], color="#2d6be4", alpha=0.85, width=0.8)
    ax.set_title("Annual Publication Count")
    ax.set_xlabel("Year")
    ax.set_ylabel("Publications")

    # Right: domain annual breakdown
    if trends.get("domain_annual"):
        df_domain = pd.DataFrame(trends["domain_annual"]).set_index("year")
        df_domain = df_domain.fillna(0)
        colors = ["#2d6be4", "#e84343", "#27ae60", "#f39c12"]
        df_domain.plot(kind="bar", stacked=True, ax=axes[1], color=colors[: len(df_domain.columns)])
        axes[1].set_title("Publications by Domain")
        axes[1].set_xlabel("Year")
        axes[1].set_ylabel("Publications")
        axes[1].legend(title="Domain", fontsize=8)
        axes[1].tick_params(axis="x", rotation=45)

    plt.tight_layout()
    plt.savefig(f"{fig_dir}/publication_trends.png", dpi=150, bbox_inches="tight")
    plt.close()


def fig_citation_distribution(cit_stats: dict, fig_dir: str) -> None:
    if not cit_stats:
        return
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    # Left: citation distribution text summary (simulated bars from percentiles)
    pcts = cit_stats.get("percentiles", {})
    labels = list(pcts.keys())
    values = list(pcts.values())
    axes[0].barh(labels, values, color="#e84343", alpha=0.8)
    axes[0].set_title("Citation Percentiles")
    axes[0].set_xlabel("Citations")
    axes[0].axvline(
        cit_stats.get("mean", 0),
        color="navy",
        linestyle="--",
        label=f"Mean={cit_stats.get('mean'):.1f}",
    )
    axes[0].legend(fontsize=9)

    # Right: corpus-level indices
    indices = {
        "h-index": cit_stats.get("h_index_corpus", 0),
        "g-index": cit_stats.get("g_index_corpus", 0),
        "zero-citation\n rate (%)": round(cit_stats.get("zero_citation_rate", 0) * 100, 1),
    }
    bars = axes[1].bar(
        list(indices.keys()),
        list(indices.values()),
        color=["#2d6be4", "#27ae60", "#e8a327"],
        alpha=0.85,
    )
    axes[1].set_title("Corpus Citation Indices")
    for bar, val in zip(bars, indices.values()):
        axes[1].text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.5,
            str(val),
            ha="center",
            va="bottom",
            fontsize=10,
        )

    plt.tight_layout()
    plt.savefig(f"{fig_dir}/citation_distribution.png", dpi=150, bbox_inches="tight")
    plt.close()


def fig_top_authors(authors: dict, fig_dir: str) -> None:
    top = authors.get("top_by_output", [])[:15]
    if not top:
        return
    names = [a["name"][:25] for a in top]
    counts = [a["paper_count"] for a in top]
    fig, axes = plt.subplots(1, 2, figsize=(15, 6))
    axes[0].barh(names[::-1], counts[::-1], color="#2d6be4", alpha=0.85)
    axes[0].set_title("Top 15 Authors by Output")
    axes[0].set_xlabel("Papers")

    top_c = authors.get("top_by_citations", [])[:15]
    names_c = [a["name"][:25] for a in top_c]
    cites_c = [a["total_citations"] for a in top_c]
    axes[1].barh(names_c[::-1], cites_c[::-1], color="#e84343", alpha=0.85)
    axes[1].set_title("Top 15 Authors by Citations")
    axes[1].set_xlabel("Total Citations")

    plt.tight_layout()
    plt.savefig(f"{fig_dir}/top_authors.png", dpi=150, bbox_inches="tight")
    plt.close()


def fig_domain_distribution(df: pd.DataFrame, fig_dir: str) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    domain_counts = df["domain"].value_counts()
    colors = ["#2d6be4", "#e84343", "#27ae60", "#f39c12", "#9b59b6"]
    domain_counts.plot(
        kind="pie",
        ax=axes[0],
        colors=colors[: len(domain_counts)],
        autopct="%1.1f%%",
        startangle=90,
    )
    axes[0].set_title("Domain Distribution")
    axes[0].set_ylabel("")

    sub_counts = df.groupby(["domain", "subcategory"]).size().reset_index(name="count")
    sub_counts = sub_counts.sort_values(["domain", "count"], ascending=[True, False])
    sub_counts["label"] = sub_counts["domain"].str[:3] + "/" + sub_counts["subcategory"]
    sub_top = sub_counts.head(15)
    axes[1].barh(sub_top["label"][::-1], sub_top["count"][::-1], color="#2d6be4", alpha=0.75)
    axes[1].set_title("Top 15 Subcategories")
    axes[1].set_xlabel("Papers")

    plt.tight_layout()
    plt.savefig(f"{fig_dir}/domain_distribution.png", dpi=150, bbox_inches="tight")
    plt.close()


def fig_concept_landscape(concepts: dict, fig_dir: str) -> None:
    top_50 = concepts.get("top_50_concepts", [])[:30]
    if not top_50:
        return
    names = [c["concept"] for c in top_50]
    counts = [c["count"] for c in top_50]

    fig, ax = plt.subplots(figsize=(12, 8))
    ax.barh(
        names[::-1],
        counts[::-1],
        color=plt.cm.viridis(np.linspace(0.3, 0.9, len(names))),
        alpha=0.85,
    )
    ax.set_title("Top 30 OpenAlex Concepts in Populism Literature")
    ax.set_xlabel("Frequency (number of papers)")
    plt.tight_layout()
    plt.savefig(f"{fig_dir}/concept_landscape.png", dpi=150, bbox_inches="tight")
    plt.close()


def fig_cross_domain_heatmap(metrics: dict, fig_dir: str) -> None:
    """
    Generate 4-panel heatmap visualization for cross-domain coupling metrics.

    Panels:
    1. Association Strength (AS) - normalized by expected random coupling
    2. Coupling Strength Index (CSI) - ratio to minimum domain size
    3. Jaccard Similarity - shared intellectual foundation (0-1)
    4. Raw Coupling Counts - baseline absolute counts

    Uses enhanced metrics if available, falls back to raw matrix only.
    """
    # Try to get enhanced metrics first, fall back to raw matrix
    has_enhanced = "enhanced_cross_domain_metrics" in metrics or "association_strength" in metrics

    if has_enhanced:
        # New enhanced metrics format
        enhanced = metrics.get("enhanced_cross_domain_metrics", metrics)
        domains = enhanced.get("metadata", {}).get(
            "domains", ["Political Science", "Economics", "Sociology", "Other"]
        )

        raw_matrix = enhanced.get("raw_coupling_matrix", {})
        as_matrix = enhanced.get("association_strength", {})
        csi_matrix = enhanced.get("coupling_strength_index", {})
        jaccard_matrix = enhanced.get("jaccard_similarity", {})
    else:
        # Fall back to simple raw matrix
        matrix = metrics.get("cross_domain_matrix")
        if not matrix:
            return
        domains = ["Political Science", "Economics", "Sociology", "Other"]
        raw_matrix = matrix
        as_matrix = None
        csi_matrix = None
        jaccard_matrix = None

    # Convert matrices to numpy arrays
    raw_data = np.array([[raw_matrix.get(d1, {}).get(d2, 0) for d2 in domains] for d1 in domains])
    if raw_data.sum() == 0:
        return

    # Create 4-panel heatmap if enhanced metrics available
    if has_enhanced and as_matrix:
        fig, axes = plt.subplots(2, 2, figsize=(14, 12))

        # Panel 1: Association Strength (log scale)
        as_data = np.array([[as_matrix.get(d1, {}).get(d2, 0) for d2 in domains] for d1 in domains])
        ax = axes[0, 0]
        im1 = ax.imshow(as_data, cmap="RdBu_r", aspect="auto", vmin=0.5, vmax=2.0)
        ax.axhline(y=-0.5, color="black", linewidth=0.5)
        ax.axvline(x=-0.5, color="black", linewidth=0.5)
        ax.set_xticks(range(len(domains)))
        ax.set_yticks(range(len(domains)))
        ax.set_xticklabels([d[:10] for d in domains], rotation=45, ha="right", fontsize=9)
        ax.set_yticklabels([d[:10] for d in domains], fontsize=9)
        ax.set_title(
            "Association Strength (AS)\nAS > 1.0 = Stronger than random", fontsize=11, weight="bold"
        )
        for i in range(len(domains)):
            for j in range(len(domains)):
                ax.text(
                    j,
                    i,
                    f"{as_data[i, j]:.2f}",
                    ha="center",
                    va="center",
                    color="white" if abs(as_data[i, j] - 1.0) > 0.4 else "black",
                    fontsize=8,
                )
        plt.colorbar(im1, ax=ax, label="AS Value")

        # Panel 2: Coupling Strength Index
        csi_data = np.array(
            [[csi_matrix.get(d1, {}).get(d2, 0) for d2 in domains] for d1 in domains]
        )
        ax = axes[0, 1]
        im2 = ax.imshow(csi_data, cmap="YlOrRd", aspect="auto")
        ax.axhline(y=-0.5, color="black", linewidth=0.5)
        ax.axvline(x=-0.5, color="black", linewidth=0.5)
        ax.set_xticks(range(len(domains)))
        ax.set_yticks(range(len(domains)))
        ax.set_xticklabels([d[:10] for d in domains], rotation=45, ha="right", fontsize=9)
        ax.set_yticklabels([d[:10] for d in domains], fontsize=9)
        ax.set_title(
            "Coupling Strength Index (CSI)\nShared refs / min domain size",
            fontsize=11,
            weight="bold",
        )
        for i in range(len(domains)):
            for j in range(len(domains)):
                ax.text(
                    j,
                    i,
                    f"{csi_data[i, j]:.2f}",
                    ha="center",
                    va="center",
                    color="white" if csi_data[i, j] > csi_data.max() * 0.6 else "black",
                    fontsize=8,
                )
        plt.colorbar(im2, ax=ax, label="CSI Value")

        # Panel 3: Jaccard Similarity
        jaccard_data = np.array(
            [
                [jaccard_matrix.get(d1, {}).get(d2, 1.0 if d1 == d2 else 0) for d2 in domains]
                for d1 in domains
            ]
        )
        ax = axes[1, 0]
        im3 = ax.imshow(jaccard_data, cmap="Blues", aspect="auto", vmin=0, vmax=1)
        ax.axhline(y=-0.5, color="black", linewidth=0.5)
        ax.axvline(x=-0.5, color="black", linewidth=0.5)
        ax.set_xticks(range(len(domains)))
        ax.set_yticks(range(len(domains)))
        ax.set_xticklabels([d[:10] for d in domains], rotation=45, ha="right", fontsize=9)
        ax.set_yticklabels([d[:10] for d in domains], fontsize=9)
        ax.set_title(
            "Jaccard Similarity\nShared intellectual foundation (0-1)", fontsize=11, weight="bold"
        )
        for i in range(len(domains)):
            for j in range(len(domains)):
                ax.text(
                    j,
                    i,
                    f"{jaccard_data[i, j]:.2f}",
                    ha="center",
                    va="center",
                    color="white" if jaccard_data[i, j] > 0.5 else "black",
                    fontsize=8,
                )
        plt.colorbar(im3, ax=ax, label="Jaccard Value")

        # Panel 4: Raw Coupling Counts
        ax = axes[1, 1]
        im4 = ax.imshow(raw_data, cmap="Greys", aspect="auto")
        ax.axhline(y=-0.5, color="black", linewidth=0.5)
        ax.axvline(x=-0.5, color="black", linewidth=0.5)
        ax.set_xticks(range(len(domains)))
        ax.set_yticks(range(len(domains)))
        ax.set_xticklabels([d[:10] for d in domains], rotation=45, ha="right", fontsize=9)
        ax.set_yticklabels([d[:10] for d in domains], fontsize=9)
        ax.set_title("Raw Coupling Counts\nAbsolute shared references", fontsize=11, weight="bold")
        for i in range(len(domains)):
            for j in range(len(domains)):
                ax.text(
                    j,
                    i,
                    str(int(raw_data[i, j])),
                    ha="center",
                    va="center",
                    color="white" if raw_data[i, j] > raw_data.max() * 0.6 else "black",
                    fontsize=8,
                )
        plt.colorbar(im4, ax=ax, label="Count")

        fig.suptitle(
            "Cross-Domain Bibliographic Coupling Analysis\n(Multiple Interpretable Metrics)",
            fontsize=13,
            weight="bold",
            y=0.995,
        )
        plt.tight_layout()
        plt.savefig(f"{fig_dir}/cross_domain_heatmap_enhanced.png", dpi=150, bbox_inches="tight")
        plt.close()

    # Also save simple version for backward compatibility
    fig, ax = plt.subplots(figsize=(7, 6))
    im = ax.imshow(raw_data, cmap="Blues", aspect="auto")
    ax.set_xticks(range(len(domains)))
    ax.set_yticks(range(len(domains)))
    ax.set_xticklabels([d[:8] for d in domains], rotation=45, ha="right")
    ax.set_yticklabels([d[:8] for d in domains])
    ax.set_title("Cross-Domain Bibliographic Coupling Matrix (Raw Counts)")
    for i in range(len(domains)):
        for j in range(len(domains)):
            ax.text(
                j,
                i,
                str(int(raw_data[i, j])),
                ha="center",
                va="center",
                color="white" if raw_data[i, j] > raw_data.max() * 0.6 else "black",
                fontsize=9,
            )
    plt.colorbar(im, ax=ax, label="Shared References")
    plt.tight_layout()
    plt.savefig(f"{fig_dir}/cross_domain_heatmap.png", dpi=150, bbox_inches="tight")
    plt.close()


def generate_html_report(fig_dir: str, config: dict) -> None:
    figures = list(Path(fig_dir).glob("*.png"))
    html = [
        "<html><head><style>",
        "body{font-family:Arial,sans-serif;max-width:1200px;margin:auto;padding:20px}",
        "img{max-width:100%;border:1px solid #ddd;margin:10px 0;border-radius:4px}",
        "h1{color:#2d6be4}h2{color:#444;border-bottom:1px solid #ddd}",
        "</style></head><body>",
        "<h1>Bibliometric Pipeline — Populism Literature</h1>",
        f"<p><em>Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}</em></p>",
        "<p>Mode: " + config["pipeline"]["mode"] + "</p>",
    ]
    report_path = Path(f"{config['paths']['outputs']}/reports/report.html")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_dir = report_path.parent
    for fig in sorted(figures):
        title = fig.stem.replace("_", " ").title()
        img_src = Path(os.path.relpath(fig, report_dir)).as_posix()
        html.append(f"<h2>{title}</h2>")
        html.append(f"<img src='{img_src}' alt='{title}'>")
    html.append("</body></html>")
    with open(report_path, "w") as f:
        f.write("\n".join(html))


def main():
    parser = argparse.ArgumentParser(description="Visualization Agent")
    parser.add_argument("--config", default="config/config.yaml")
    args = parser.parse_args()

    config = load_yaml(args.config)
    logger = setup_logger("visualization", config["paths"]["logs"])
    logger.info("=== Visualization Agent starting ===")

    proc_dir = config["paths"]["data_processed"]
    fig_dir = config["paths"]["outputs"] + "/figures"
    Path(fig_dir).mkdir(parents=True, exist_ok=True)

    # Load available data
    try:
        trends = load_json(f"{proc_dir}/publication_trends.json")
        fig_publication_trends(trends, fig_dir)
        logger.info("Generated: publication_trends.png")
    except Exception as e:
        logger.warning("publication_trends: %s", e)

    try:
        cit = load_json(f"{proc_dir}/citation_stats.json")
        fig_citation_distribution(cit, fig_dir)
        logger.info("Generated: citation_distribution.png")
    except Exception as e:
        logger.warning("citation_distribution: %s", e)

    try:
        authors = load_json(f"{proc_dir}/top_authors.json")
        fig_top_authors(authors, fig_dir)
        logger.info("Generated: top_authors.png")
    except Exception as e:
        logger.warning("top_authors: %s", e)

    try:
        df = load_parquet(f"{proc_dir}/classified_works.parquet")
        fig_domain_distribution(df, fig_dir)
        logger.info("Generated: domain_distribution.png")
    except Exception as e:
        logger.warning("domain_distribution: %s", e)

    try:
        concepts = load_json(f"{proc_dir}/concept_landscape.json")
        fig_concept_landscape(concepts, fig_dir)
        logger.info("Generated: concept_landscape.png")
    except Exception as e:
        logger.warning("concept_landscape: %s", e)

    try:
        metrics = load_json(f"{proc_dir}/network_metrics.json")
        fig_cross_domain_heatmap(metrics, fig_dir)
        logger.info("Generated: cross_domain_heatmap.png")
    except Exception as e:
        logger.warning("cross_domain_heatmap: %s", e)

    try:
        generate_html_report(fig_dir, config)
        logger.info("Generated: HTML report")
    except Exception as e:
        logger.warning("HTML report: %s", e)

    logger.info("=== Visualization Agent complete ===")


if __name__ == "__main__":
    main()
