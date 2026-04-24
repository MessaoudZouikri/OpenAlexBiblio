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
from src.utils.llm_client import OllamaClient
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
    mean_val = cit_stats.get("mean_citations", 0)
    axes[0].axvline(
        mean_val,
        color="navy",
        linestyle="--",
        label=f"Mean={mean_val:.1f}",
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
    if df.empty or "domain" not in df.columns or "subcategory" not in df.columns:
        return

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


def fig_publication_types(type_stats: dict, fig_dir: str) -> None:
    rows = type_stats.get("types", [])
    if not rows:
        return

    labels = [r["type"].replace("-", "-\n") for r in rows]
    freqs = [r["frequency"] for r in rows]
    pcts = [r["percentage"] for r in rows]
    cumuls = [r["cumulative_percentage"] for r in rows]
    total = type_stats.get("total", sum(freqs))

    colors = ["#2d6be4", "#27ae60", "#f39c12", "#9b59b6", "#e84343"][: len(rows)]
    x = np.arange(len(rows))

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # ── Left: Pareto chart (bars + cumulative % line) ──────────────────────
    ax1 = axes[0]
    bars = ax1.bar(x, freqs, color=colors, alpha=0.85, width=0.55, zorder=2)
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, fontsize=10)
    ax1.set_ylabel("Number of records")
    ax1.set_title("Publication Types — Pareto Chart")
    ax1.grid(axis="y", linestyle="--", alpha=0.4, zorder=1)

    for bar, pct in zip(bars, pcts):
        ax1.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + total * 0.005,
            f"{pct:.1f}%",
            ha="center",
            va="bottom",
            fontsize=9,
            fontweight="bold",
        )

    ax2 = ax1.twinx()
    ax2.plot(
        x,
        cumuls,
        color="#e84343",
        marker="o",
        linewidth=2,
        markersize=6,
        label="Cumulative %",
        zorder=3,
    )
    ax2.set_ylim(0, 110)
    ax2.set_ylabel("Cumulative %", color="#e84343")
    ax2.tick_params(axis="y", labelcolor="#e84343")
    ax2.axhline(80, color="#e84343", linestyle=":", alpha=0.5)
    ax2.spines["right"].set_visible(True)

    # ── Right: descriptive statistics table ───────────────────────────────
    ax3 = axes[1]
    ax3.axis("off")

    col_labels = ["Type", "Frequency", "%", "Cumul. %"]
    table_data = [
        [
            r["type"],
            f"{r['frequency']:,}",
            f"{r['percentage']:.1f}",
            f"{r['cumulative_percentage']:.1f}",
        ]
        for r in rows
    ]
    table_data.append(["Total", f"{total:,}", "100.0", ""])

    tbl = ax3.table(
        cellText=table_data,
        colLabels=col_labels,
        cellLoc="center",
        loc="center",
        bbox=[0.0, 0.1, 1.0, 0.85],
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(10)

    for (row_idx, col_idx), cell in tbl.get_celld().items():
        cell.set_edgecolor("#cccccc")
        if row_idx == 0:
            cell.set_facecolor("#2d6be4")
            cell.set_text_props(color="white", fontweight="bold")
        elif row_idx == len(table_data):
            cell.set_facecolor("#f0f0f0")
            cell.set_text_props(fontweight="bold")
        else:
            cell.set_facecolor("white" if row_idx % 2 == 1 else "#f8f8f8")

    ax3.set_title("Frequency Table", pad=12)

    plt.tight_layout()
    plt.savefig(f"{fig_dir}/publication_types.png", dpi=150, bbox_inches="tight")
    plt.close()


def fig_type_by_domain(df: pd.DataFrame, fig_dir: str) -> None:
    if "type" not in df.columns or "domain" not in df.columns or df.empty:
        return

    domain_order = ["Political Science", "Economics", "Sociology", "Other"]
    type_order = ["article", "book-chapter", "dissertation", "preprint"]
    type_colors = ["#2d6be4", "#27ae60", "#f39c12", "#9b59b6"]

    df_f = df[df["domain"].isin(domain_order) & df["type"].isin(type_order)].copy()
    if df_f.empty:
        return

    ct = pd.crosstab(df_f["type"], df_f["domain"])
    ct = ct.reindex(index=type_order, columns=domain_order, fill_value=0)

    domain_totals = ct.sum(axis=0)
    type_totals = ct.sum(axis=1)
    grand_total = int(ct.values.sum())

    fig, axes = plt.subplots(1, 2, figsize=(16, 6))

    # ── Left: grouped bar chart (no cumulative line) ───────────────────────
    ax = axes[0]
    n_types = len(type_order)
    bar_width = 0.18
    x = np.arange(len(domain_order))

    for i, (pub_type, color) in enumerate(zip(type_order, type_colors)):
        offsets = x + (i - n_types / 2 + 0.5) * bar_width
        vals = [int(ct.loc[pub_type, domain]) for domain in domain_order]
        ax.bar(offsets, vals, width=bar_width, color=color, alpha=0.85, label=pub_type, zorder=2)

    ax.set_xticks(x)
    ax.set_xticklabels([d.replace(" ", "\n") for d in domain_order], fontsize=10)
    ax.set_ylabel("Number of records")
    ax.set_title("Publication Types by Domain")
    ax.legend(title="Type", fontsize=8, title_fontsize=9, loc="upper right")
    ax.grid(axis="y", linestyle="--", alpha=0.4, zorder=1)

    # ── Right: cross-tab table (n, % within domain) ────────────────────────
    ax2 = axes[1]
    ax2.axis("off")

    domain_short = ["Pol. Science", "Economics", "Sociology", "Other"]
    col_labels = ["Type"] + domain_short + ["Total"]

    table_data = []
    for pub_type in type_order:
        row = [pub_type]
        for domain in domain_order:
            n = int(ct.loc[pub_type, domain])
            pct = n / domain_totals[domain] * 100 if domain_totals[domain] > 0 else 0.0
            row.append(f"{n:,} ({pct:.1f}%)")
        total_n = int(type_totals[pub_type])
        total_pct = total_n / grand_total * 100 if grand_total > 0 else 0.0
        row.append(f"{total_n:,} ({total_pct:.1f}%)")
        table_data.append(row)

    total_row = ["Total"]
    for domain in domain_order:
        total_row.append(f"{int(domain_totals[domain]):,} (100%)")
    total_row.append(f"{grand_total:,} (100%)")
    table_data.append(total_row)

    n_data_rows = len(table_data)
    tbl = ax2.table(
        cellText=table_data,
        colLabels=col_labels,
        cellLoc="center",
        loc="center",
        bbox=[0.0, 0.05, 1.0, 0.88],
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(8.5)

    for (row_idx, col_idx), cell in tbl.get_celld().items():
        cell.set_edgecolor("#cccccc")
        if row_idx == 0:
            cell.set_facecolor("#2d6be4")
            cell.set_text_props(color="white", fontweight="bold")
        elif row_idx == n_data_rows:
            cell.set_facecolor("#f0f0f0")
            cell.set_text_props(fontweight="bold")
        else:
            cell.set_facecolor("white" if row_idx % 2 == 1 else "#f8f8f8")

    ax2.set_title("Cross-tabulation: n (% within domain)", pad=12)

    plt.tight_layout()
    plt.savefig(f"{fig_dir}/publication_types_by_domain.png", dpi=150, bbox_inches="tight")
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


_HTML_CSS = """
body {
    font-family: 'Segoe UI', Arial, sans-serif;
    max-width: 1100px;
    margin: auto;
    padding: 30px 20px;
    color: #222;
    background: #fafafa;
}
h1 { color: #2d6be4; border-bottom: 3px solid #2d6be4; padding-bottom: 8px; }
h2 { color: #333; border-bottom: 1px solid #ddd; margin-top: 40px; }
.meta { color: #666; font-size: 0.9em; margin-bottom: 30px; }
.figure-block {
    background: #fff;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    padding: 20px;
    margin: 20px 0;
    box-shadow: 0 1px 3px rgba(0,0,0,.06);
}
img { max-width: 100%; border-radius: 4px; display: block; margin: 12px 0; }
.data-summary {
    background: #f0f4ff;
    border-left: 4px solid #2d6be4;
    padding: 10px 14px;
    margin: 10px 0;
    font-size: 0.88em;
    color: #444;
}
.interpretation { background: #f6fff6; border-left: 4px solid #27ae60; padding: 10px 14px; margin: 10px 0; }
.interp-label { font-size: 0.78em; color: #888; font-style: italic; margin-bottom: 4px; }
"""


def _build_figure_summaries(proc_dir: str) -> dict:
    """Load processed JSON/Parquet files and return per-figure text summaries."""
    s: dict = {}

    try:
        trends = load_json(f"{proc_dir}/publication_trends.json")
        annual = trends.get("annual", [])
        total = sum(r["count"] for r in annual)
        years = [r["year"] for r in annual]
        year_range = f"{min(years)}–{max(years)}" if years else "unknown"
        dom_str = ""
        domain_annual = trends.get("domain_annual", [])
        if domain_annual:
            domains = [k for k in domain_annual[0] if k != "year"]
            totals = {d: sum(r.get(d, 0) for r in domain_annual) for d in domains}
            lead = max(totals, key=lambda d: totals[d])
            dom_str = f" Leading domain: {lead}."
        s["publication_trends"] = (
            f"{total:,} records spanning {year_range} ({len(annual)} annual data points).{dom_str}"
        )
    except Exception:
        s["publication_trends"] = ""

    try:
        cit = load_json(f"{proc_dir}/citation_stats.json")
        mean_val = cit.get("mean_citations")
        mean_str = f"{mean_val:.1f}" if isinstance(mean_val, (int, float)) else "N/A"
        zero_rate = cit.get("zero_citation_rate", 0)
        zero_str = f"{zero_rate * 100:.1f}%" if isinstance(zero_rate, (int, float)) else "N/A"
        total_cit = cit.get("total_citations", 0)
        total_str = f"{total_cit:,}" if isinstance(total_cit, int) else str(total_cit)
        s["citation_distribution"] = (
            f"Total citations: {total_str}. "
            f"h-index: {cit.get('h_index_corpus', 'N/A')}, "
            f"g-index: {cit.get('g_index_corpus', 'N/A')}. "
            f"Mean: {mean_str} citations/paper. "
            f"Zero-citation rate: {zero_str}."
        )
    except Exception:
        s["citation_distribution"] = ""

    try:
        authors = load_json(f"{proc_dir}/top_authors.json")
        top = authors.get("top_by_output", [{}])
        lotka = authors.get("lotka_alpha")
        lotka_str = f"{lotka:.2f}" if isinstance(lotka, float) else "N/A"
        n_authors = authors.get("unique_authors", "N/A")
        n_authors_str = f"{n_authors:,}" if isinstance(n_authors, int) else str(n_authors)
        s["top_authors"] = (
            f"Unique authors: {n_authors_str}. "
            f"Most prolific: {top[0].get('name','N/A')} ({top[0].get('paper_count','N/A')} papers). "
            f"Lotka exponent: {lotka_str}."
        )
    except Exception:
        s["top_authors"] = ""

    try:
        df = load_parquet(f"{proc_dir}/classified_works.parquet")
        counts = df["domain"].value_counts()
        total_w = len(df)
        breakdown = "; ".join(f"{d}: {c} ({100 * c / total_w:.1f}%)" for d, c in counts.items())
        stage_str = ""
        if "domain_source" in df.columns:
            stages = df["domain_source"].value_counts().to_dict()
            stage_str = (
                " Classification stages: " + ", ".join(f"{k}={v}" for k, v in stages.items()) + "."
            )
        s["domain_distribution"] = f"{total_w:,} works. {breakdown}.{stage_str}"
    except Exception:
        s["domain_distribution"] = ""

    try:
        concepts = load_json(f"{proc_dir}/concept_landscape.json")
        top5 = [c["concept"] for c in concepts.get("top_50_concepts", [])[:5]]
        s["concept_landscape"] = f"Top concepts: {', '.join(top5)}." if top5 else ""
    except Exception:
        s["concept_landscape"] = ""

    try:
        type_stats = load_json(f"{proc_dir}/publication_types.json")
        rows = type_stats.get("types", [])
        total = type_stats.get("total", 0)
        breakdown = "; ".join(
            f"{r['type']}: {r['frequency']:,} ({r['percentage']:.1f}%)" for r in rows
        )
        s["publication_types"] = f"{total:,} works. {breakdown}."
    except Exception:
        s["publication_types"] = ""

    try:
        df_cls = load_parquet(f"{proc_dir}/classified_works.parquet")
        domain_order = ["Political Science", "Economics", "Sociology", "Other"]
        type_order = ["article", "book-chapter", "dissertation", "preprint"]
        df_f = df_cls[df_cls["domain"].isin(domain_order) & df_cls["type"].isin(type_order)]
        if not df_f.empty:
            ct = pd.crosstab(df_f["type"], df_f["domain"])
            ct = ct.reindex(index=type_order, columns=domain_order, fill_value=0)
            lead_type = ct.sum(axis=1).idxmax()
            lead_domain = ct.sum(axis=0).idxmax()
            s["publication_types_by_domain"] = (
                f"Dominant type overall: {lead_type}. "
                f"Largest domain: {lead_domain} ({int(ct.sum(axis=0)[lead_domain]):,} works). "
                f"Cross-tabulation of {len(type_order)} publication types × {len(domain_order)} domains."
            )
        else:
            s["publication_types_by_domain"] = ""
    except Exception:
        s["publication_types_by_domain"] = ""

    try:
        metrics = load_json(f"{proc_dir}/network_metrics.json")
        enhanced = metrics.get("enhanced_cross_domain_metrics", {})
        idcr = enhanced.get("inter_domain_ratio", "N/A")
        meta = enhanced.get("metadata", {})
        idcr_str = f"{idcr * 100:.1f}%" if isinstance(idcr, float) else str(idcr)
        hmap = (
            f"Inter-domain coupling ratio (IDCR): {idcr_str}. "
            f"Cross-domain edges: {meta.get('n_inter_domain_edges','N/A')}, "
            f"intra-domain: {meta.get('n_intra_domain_edges','N/A')}. "
            f"Total coupling strength: {meta.get('total_coupling_strength','N/A')}."
        )
        s["cross_domain_heatmap"] = hmap
        s["cross_domain_heatmap_enhanced"] = hmap
    except Exception:
        s["cross_domain_heatmap"] = ""
        s["cross_domain_heatmap_enhanced"] = ""

    return s


def _llm_interpret(client: OllamaClient, figure_stem: str, data_summary: str) -> str:
    """Generate a 2-3 sentence bibliometric interpretation via Ollama. Returns '' on failure."""
    system_prompt = (
        "You are a bibliometrics expert writing concise analytical interpretations "
        "for peer-reviewed academic reports on populism research. "
        "Write exactly 2-3 sentences interpreting the significance of the data. "
        "Use bibliometric terminology. Do not restate raw numbers — interpret their meaning."
    )
    title = figure_stem.replace("_", " ").title()
    text, ok = client.generate(
        system_prompt,
        f"Write a 2-3 sentence interpretation for the '{title}' figure.\n\nKey data: {data_summary}",
    )
    return text.strip() if ok and text else ""


def generate_html_report(
    fig_dir: str,
    config: dict,
    proc_dir: str = None,
    llm_client: OllamaClient = None,
) -> None:
    figures = sorted(Path(fig_dir).glob("*.png"))
    summaries = _build_figure_summaries(proc_dir) if proc_dir else {}
    now = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
    mode = config["pipeline"]["mode"]

    report_path = Path(f"{config['paths']['outputs']}/reports/report.html")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_dir = report_path.parent

    lines = [
        "<!DOCTYPE html><html lang='en'><head>",
        "<meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width, initial-scale=1'>",
        "<title>Bibliometric Analysis Report</title>",
        f"<style>{_HTML_CSS}</style>",
        "</head><body>",
        "<h1>A Bibliometric Analysis Pipeline Using OpenAlex Data</h1>",
        f"<p class='meta'>Generated: {now} &nbsp;|&nbsp; Mode: {mode}</p>",
    ]

    for fig in figures:
        stem = fig.stem
        title = stem.replace("_", " ").title()
        img_src = Path(os.path.relpath(fig, report_dir)).as_posix()
        summary = summaries.get(stem, "")
        interpretation = ""
        if llm_client and summary:
            interpretation = _llm_interpret(llm_client, stem, summary)

        lines.append("<div class='figure-block'>")
        lines.append(f"<h2>{title}</h2>")
        lines.append(f"<img src='{img_src}' alt='{title}'>")
        if summary:
            lines.append(f"<div class='data-summary'>{summary}</div>")
        if interpretation:
            lines.append("<div class='interpretation'>")
            lines.append("<div class='interp-label'>Auto-generated interpretation (Ollama)</div>")
            lines.append(f"<p>{interpretation}</p>")
            lines.append("</div>")
        lines.append("</div>")

    lines.append("</body></html>")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def generate_markdown_report(
    fig_dir: str,
    config: dict,
    proc_dir: str = None,
    llm_client: OllamaClient = None,
) -> None:
    figures = sorted(Path(fig_dir).glob("*.png"))
    summaries = _build_figure_summaries(proc_dir) if proc_dir else {}
    now = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
    mode = config["pipeline"]["mode"]

    report_path = Path(f"{config['paths']['outputs']}/reports/report.md")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_dir = report_path.parent

    lines = [
        "# A Bibliometric Analysis Pipeline Using OpenAlex Data",
        "",
        f"*Generated: {now} | Mode: {mode}*",
        "",
        "---",
        "",
    ]

    for fig in figures:
        stem = fig.stem
        title = stem.replace("_", " ").title()
        img_src = Path(os.path.relpath(fig, report_dir)).as_posix()
        summary = summaries.get(stem, "")
        interpretation = ""
        if llm_client and summary:
            interpretation = _llm_interpret(llm_client, stem, summary)

        lines.append(f"## {title}")
        lines.append("")
        lines.append(f"![{title}]({img_src})")
        lines.append("")
        if summary:
            lines.append(f"> **Data:** {summary}")
            lines.append("")
        if interpretation:
            lines.append(f"> **Interpretation** *(auto-generated via Ollama)*: {interpretation}")
            lines.append("")
        lines.append("---")
        lines.append("")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description="Visualization Agent")
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--llm-config", default="config/llm.yaml")
    args = parser.parse_args()

    config = load_yaml(args.config)
    logger = setup_logger("visualization", config["paths"]["logs"])
    logger.info("=== Visualization Agent starting ===")

    proc_dir = config["paths"]["data_processed"]
    fig_dir = config["paths"]["outputs"] + "/figures"
    Path(fig_dir).mkdir(parents=True, exist_ok=True)

    # Load available data and generate figures
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

    df_classified = None
    try:
        df_classified = load_parquet(f"{proc_dir}/classified_works.parquet")
    except Exception as e:
        logger.warning("classified_works.parquet load failed: %s", e)

    if df_classified is not None:
        try:
            fig_domain_distribution(df_classified, fig_dir)
            logger.info("Generated: domain_distribution.png")
        except Exception as e:
            logger.warning("domain_distribution: %s", e)

        try:
            fig_type_by_domain(df_classified, fig_dir)
            logger.info("Generated: publication_types_by_domain.png")
        except Exception as e:
            logger.warning("publication_types_by_domain: %s", e)

    try:
        concepts = load_json(f"{proc_dir}/concept_landscape.json")
        fig_concept_landscape(concepts, fig_dir)
        logger.info("Generated: concept_landscape.png")
    except Exception as e:
        logger.warning("concept_landscape: %s", e)

    try:
        type_stats = load_json(f"{proc_dir}/publication_types.json")
        fig_publication_types(type_stats, fig_dir)
        logger.info("Generated: publication_types.png")
    except Exception as e:
        logger.warning("publication_types: %s", e)

    try:
        metrics = load_json(f"{proc_dir}/network_metrics.json")
        fig_cross_domain_heatmap(metrics, fig_dir)
        logger.info("Generated: cross_domain_heatmap.png")
    except Exception as e:
        logger.warning("cross_domain_heatmap: %s", e)

    # Set up LLM client for report interpretations (temperature=0 for determinism)
    llm_client = None
    try:
        llm_cfg = load_yaml(args.llm_config)
        llm_client = OllamaClient(
            endpoint=llm_cfg.get("endpoint", "http://localhost:11434"),
            model=llm_cfg.get("model", "qwen2.5:7b"),
            temperature=0.0,
            max_tokens=400,
            fallback_models=llm_cfg.get("fallback_models", []),
        )
        if not llm_client.is_available():
            logger.info("Ollama unavailable — reports will use data summaries only")
            llm_client = None
        else:
            logger.info("Ollama available — generating LLM interpretations for reports")
    except Exception as exc:
        logger.warning("LLM client init failed: %s", exc)
        llm_client = None

    try:
        generate_html_report(fig_dir, config, proc_dir, llm_client)
        logger.info("Generated: report.html")
    except Exception as e:
        logger.warning("HTML report: %s", e)

    try:
        generate_markdown_report(fig_dir, config, proc_dir, llm_client)
        logger.info("Generated: report.md")
    except Exception as e:
        logger.warning("Markdown report: %s", e)

    logger.info("=== Visualization Agent complete ===")


if __name__ == "__main__":
    main()
