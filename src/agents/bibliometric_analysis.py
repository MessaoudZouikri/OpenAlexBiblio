"""
Bibliometric Analysis Agent
===========================
Computes publication trends, citation statistics, author/journal/institution
productivity metrics, and the concept landscape from the clean dataset.

Outputs: multiple JSON files in data/processed/

Standalone:
    python src/agents/bibliometric_analysis.py --config config/config.yaml
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from datetime import datetime, UTC
from itertools import combinations
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.utils.io_utils import load_parquet, save_json, load_yaml, safe_list
from src.utils.logging_utils import setup_logger


# ═══════════════════════════════════════════════════════════════════════════
# Bibliometric Indices
# ═══════════════════════════════════════════════════════════════════════════


def compute_hindex(citations: Iterable[int]) -> int:
    """Compute h-index from a list of citation counts."""
    sorted_cites = sorted((int(c) for c in citations), reverse=True)
    h = 0
    for i, c in enumerate(sorted_cites, start=1):
        if c >= i:
            h = i
        else:
            break
    return h


def compute_gindex(citations: Iterable[int]) -> int:
    """Compute g-index from a list of citation counts."""
    sorted_cites = sorted((int(c) for c in citations), reverse=True)
    g = 0
    cumsum = 0
    for i, c in enumerate(sorted_cites, start=1):
        cumsum += c
        if cumsum >= i * i:
            g = i
        else:
            break
    return g


def safe_div(a: float, b: float, default: float = 0.0) -> float:
    """Divide a by b, returning ``default`` if b is zero/falsy."""
    return a / b if b else default


# ═══════════════════════════════════════════════════════════════════════════
# Publication Trends
# ═══════════════════════════════════════════════════════════════════════════


def publication_trends(df: pd.DataFrame) -> Dict[str, Any]:
    """Annual + decadal publication counts with growth rates and domain breakdown."""
    if df.empty:
        return {
            "annual": [],
            "decadal": [],
            "domain_annual": [],
            "total_records": 0,
            "year_range": [None, None],
        }

    annual = df.groupby("year").size().reset_index(name="count").sort_values("year")
    annual["cumulative"] = annual["count"].cumsum()
    annual["yoy_growth_pct"] = annual["count"].pct_change() * 100

    decadal = (
        df.groupby("decade").size().reset_index(name="count")
        if "decade" in df.columns
        else pd.DataFrame()
    )

    if "domain_preliminary" in df.columns:
        domain_annual = (
            df.groupby(["year", "domain_preliminary"])
            .size()
            .reset_index(name="count")
            .pivot(index="year", columns="domain_preliminary", values="count")
            .fillna(0)
            .astype(int)
            .reset_index()
        )
    else:
        domain_annual = pd.DataFrame()

    return {
        "annual": annual.replace({np.nan: None}).to_dict(orient="records"),
        "decadal": decadal.to_dict(orient="records") if not decadal.empty else [],
        "domain_annual": domain_annual.to_dict(orient="records") if not domain_annual.empty else [],
        "total_records": len(df),
        "year_range": [int(df["year"].min()), int(df["year"].max())],
    }


# ═══════════════════════════════════════════════════════════════════════════
# Citation Statistics
# ═══════════════════════════════════════════════════════════════════════════


def citation_stats(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Citation distribution and corpus-level indices.

    Exposes both modern names (``h_index``, ``g_index``, ``median_citations``)
    and legacy aliases (``h_index_corpus``, ``g_index_corpus``) for
    backward compatibility.
    """
    if df.empty or "cited_by_count" not in df.columns:
        return {
            "total_citations": 0,
            "mean_citations": 0.0,
            "median_citations": 0.0,
            "std": 0.0,
            "min": 0,
            "max": 0,
            "percentiles": {},
            "citation_percentiles": {},
            "h_index": 0,
            "g_index": 0,
            "h_index_corpus": 0,
            "g_index_corpus": 0,
            "zero_citation_count": 0,
            "zero_citation_rate": 0.0,
            "top1pct_threshold": 0.0,
            "top10pct_threshold": 0.0,
            "top1pct_count": 0,
            "top10pct_count": 0,
            "n": 0,
        }

    cites = df["cited_by_count"].astype(int).tolist()
    p_vals = [25, 50, 75, 90, 95, 99]
    percentiles = {f"p{p}": float(np.percentile(cites, p)) for p in p_vals}

    h = compute_hindex(cites)
    g = compute_gindex(cites)
    p99 = float(np.percentile(cites, 99))
    p90 = float(np.percentile(cites, 90))

    return {
        "total_citations": int(sum(cites)),
        "mean_citations": round(float(np.mean(cites)), 2),
        "median_citations": float(np.median(cites)),
        "std": round(float(np.std(cites)), 2),
        "min": int(min(cites)),
        "max": int(max(cites)),
        "percentiles": percentiles,
        "citation_percentiles": percentiles,  # alias expected by some tests
        "h_index": h,
        "g_index": g,
        "h_index_corpus": h,  # legacy alias
        "g_index_corpus": g,  # legacy alias
        "zero_citation_count": int(sum(1 for c in cites if c == 0)),
        "zero_citation_rate": round(safe_div(sum(1 for c in cites if c == 0), len(cites)), 4),
        "top1pct_threshold": p99,
        "top10pct_threshold": p90,
        "top1pct_count": int(sum(1 for c in cites if c >= p99)),
        "top10pct_count": int(sum(1 for c in cites if c >= p90)),
        "n": len(cites),
    }


# ═══════════════════════════════════════════════════════════════════════════
# Author Productivity (with Lotka's Law)
# ═══════════════════════════════════════════════════════════════════════════


def _extract_author_identity(author: Any) -> Tuple[str, str]:
    """Return (id, name) for an author, handling both dict and string forms."""
    if isinstance(author, dict):
        aid = author.get("id") or author.get("name", "")
        name = author.get("name", "") or aid
        return aid, name
    if isinstance(author, str):
        return author, author
    return "", ""


def author_productivity(df: pd.DataFrame) -> Dict[str, Any]:
    """Author output and citation metrics including Lotka's law fit."""
    author_papers: Dict[str, List[dict]] = defaultdict(list)
    author_cites: Dict[str, int] = defaultdict(int)

    for _, row in df.iterrows():
        for author in safe_list(row.get("authors")):
            aid, name = _extract_author_identity(author)
            if not aid:
                continue
            author_papers[aid].append(
                {
                    "work_id": row.get("id", ""),
                    "name": name,
                    "citations": int(row.get("cited_by_count", 0) or 0),
                }
            )
            author_cites[aid] += int(row.get("cited_by_count", 0) or 0)

    author_stats: List[dict] = []
    for aid, papers in author_papers.items():
        n_papers = len(papers)
        total_cites = author_cites[aid]
        author_name = papers[0]["name"] if papers else aid
        avg_cites = round(safe_div(total_cites, n_papers), 2)
        author_stats.append(
            {
                "id": aid,
                "name": author_name,
                "author": author_name,
                "paper_count": n_papers,
                "works_count": n_papers,
                "total_citations": total_cites,
                "mean_citations_per_paper": avg_cites,
                "avg_citations": avg_cites,
                "h_index": compute_hindex(p["citations"] for p in papers),
            }
        )

    author_stats.sort(key=lambda a: a["paper_count"], reverse=True)
    top_by_output = author_stats[:20]
    top_by_cites = sorted(author_stats, key=lambda a: a["total_citations"], reverse=True)[:20]

    # Lotka's law fit: log(n_authors with p papers) ~ -alpha * log(p)
    paper_counts = [a["paper_count"] for a in author_stats]
    freq = Counter(paper_counts)
    lotka_alpha: Optional[float] = None
    lotka_r2: Optional[float] = None
    if len(freq) > 3:
        try:
            xs = np.log(list(freq.keys()))
            ys = np.log(list(freq.values()))
            slope, _, r, _, _ = stats.linregress(xs, ys)
            lotka_alpha = -float(slope)
            lotka_r2 = float(r**2)
        except Exception:
            pass

    return {
        "unique_authors": len(author_stats),
        "n_authors_analyzed": len(author_stats),
        "top_by_output": top_by_output,
        "top_by_citations": top_by_cites,
        "top_authors": top_by_output,  # alias for test compatibility
        "author_stats": top_by_output,  # alias for test compatibility
        "lotka_alpha": round(lotka_alpha, 4) if lotka_alpha is not None else None,
        "lotka_r2": round(lotka_r2, 4) if lotka_r2 is not None else None,
        "single_paper_authors": int(sum(1 for a in author_stats if a["paper_count"] == 1)),
    }


def author_productivity_metrics(df: pd.DataFrame) -> Dict[str, Any]:
    """Alias retained for backward compatibility."""
    return author_productivity(df)


# ═══════════════════════════════════════════════════════════════════════════
# Self-Citation Detection
# ═══════════════════════════════════════════════════════════════════════════


def detect_self_citations(
    citation_records: List[Dict[str, Any]],
) -> List[int]:
    """
    Count self-citations for each citation record.

    Expected input format — a list of dicts, each with:
        - ``citing_author``: the author doing the citing (str)
        - ``cited_authors``: the list of authors being cited (list[str])

    Returns:
        A list of the same length giving the number of self-citations per record.
        A self-citation occurs when the ``citing_author`` also appears in
        ``cited_authors`` (normalized for case/whitespace).
    """
    counts: List[int] = []
    for record in citation_records or []:
        citing = str(record.get("citing_author", "")).strip().lower()
        if not citing:
            counts.append(0)
            continue
        cited = [str(a).strip().lower() for a in record.get("cited_authors", []) if a]
        counts.append(sum(1 for a in cited if a == citing))
    return counts


# ═══════════════════════════════════════════════════════════════════════════
# Journal Analysis (incl. Bradford's Law Zones)
# ═══════════════════════════════════════════════════════════════════════════


def journal_analysis(df: pd.DataFrame) -> Dict[str, Any]:
    """Journal frequency, citation metrics, and Bradford-style zoning."""
    if "journal" not in df.columns or df.empty:
        return {
            "unique_journals": 0,
            "top_by_output": [],
            "top_by_citations": [],
            "bradford_zones": {"zone1_journals": 0, "zone2_journals": 0, "zone3_journals": 0},
        }

    journal_data = df[df["journal"].astype(str).str.len() > 0].copy()
    if journal_data.empty:
        return {
            "unique_journals": 0,
            "top_by_output": [],
            "top_by_citations": [],
            "bradford_zones": {"zone1_journals": 0, "zone2_journals": 0, "zone3_journals": 0},
        }

    j_groups = (
        journal_data.groupby("journal")
        .agg(
            paper_count=("id", "count"),
            total_citations=("cited_by_count", "sum"),
            mean_citations=("cited_by_count", "mean"),
        )
        .reset_index()
        .sort_values("paper_count", ascending=False)
    )

    total_papers = j_groups["paper_count"].sum()
    j_groups["cumsum"] = j_groups["paper_count"].cumsum()
    third = total_papers / 3
    zone1 = j_groups[j_groups["cumsum"] <= third]
    zone2 = j_groups[(j_groups["cumsum"] > third) & (j_groups["cumsum"] <= 2 * third)]
    zone3 = j_groups[j_groups["cumsum"] > 2 * third]

    return {
        "unique_journals": int(len(j_groups)),
        "top_by_output": j_groups.head(20).round(2).to_dict(orient="records"),
        "top_by_citations": j_groups.sort_values("total_citations", ascending=False)
        .head(20)
        .round(2)
        .to_dict(orient="records"),
        "bradford_zones": {
            "zone1_journals": int(len(zone1)),
            "zone2_journals": int(len(zone2)),
            "zone3_journals": int(len(zone3)),
        },
    }


# ═══════════════════════════════════════════════════════════════════════════
# Institution Analysis
# ═══════════════════════════════════════════════════════════════════════════


def institution_analysis(df: pd.DataFrame) -> Dict[str, Any]:
    """Institutional output and citation totals."""
    inst_papers: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"count": 0, "citations": 0, "name": ""}
    )

    for _, row in df.iterrows():
        seen = set()
        for inst in safe_list(row.get("institutions")):
            iid = inst.get("id", "") if isinstance(inst, dict) else ""
            if not iid or iid in seen:
                continue
            seen.add(iid)
            inst_papers[iid]["count"] += 1
            inst_papers[iid]["citations"] += int(row.get("cited_by_count", 0) or 0)
            inst_papers[iid]["name"] = inst.get("name", iid) or iid

    inst_list = [
        {"id": k, "name": v["name"], "paper_count": v["count"], "total_citations": v["citations"]}
        for k, v in inst_papers.items()
    ]
    inst_list.sort(key=lambda x: x["paper_count"], reverse=True)

    return {
        "unique_institutions": len(inst_list),
        "top_by_output": inst_list[:20],
        "top_by_citations": sorted(inst_list, key=lambda x: x["total_citations"], reverse=True)[
            :20
        ],
    }


# ═══════════════════════════════════════════════════════════════════════════
# Concept Landscape
# ═══════════════════════════════════════════════════════════════════════════


def concept_landscape(df: pd.DataFrame) -> Dict[str, Any]:
    """Top concepts and their co-occurrence matrix (top-20)."""
    concept_counts: Counter = Counter()
    concept_cooccur: Dict[str, Counter] = defaultdict(Counter)

    for _, row in df.iterrows():
        concepts = safe_list(row.get("concepts"))
        names = [c["name"] for c in concepts if isinstance(c, dict) and c.get("name")]
        for name in names:
            concept_counts[name] += 1
        for a, b in combinations(sorted(set(names)), 2):
            concept_cooccur[a][b] += 1
            concept_cooccur[b][a] += 1

    top_50 = [{"concept": c, "count": n} for c, n in concept_counts.most_common(50)]
    top_names = [c["concept"] for c in top_50[:20]]
    cooccur_matrix = {a: {b: concept_cooccur[a].get(b, 0) for b in top_names} for a in top_names}

    return {
        "top_50_concepts": top_50,
        "cooccurrence_matrix_top20": cooccur_matrix,
    }


# ═══════════════════════════════════════════════════════════════════════════
# CLI Entry Point
# ═══════════════════════════════════════════════════════════════════════════


def main() -> None:
    parser = argparse.ArgumentParser(description="Bibliometric Analysis Agent")
    parser.add_argument("--config", default="config/config.yaml")
    args = parser.parse_args()

    config = load_yaml(args.config)
    logger = setup_logger("bibliometric_analysis", config["paths"]["logs"])
    logger.info("=== Bibliometric Analysis Agent starting ===")

    clean_path = f"{config['paths']['data_clean']}/openalex_clean.parquet"
    df = load_parquet(clean_path)
    logger.info("Loaded %d records", len(df))

    proc_dir = config["paths"]["data_processed"]
    Path(proc_dir).mkdir(parents=True, exist_ok=True)

    logger.info("Computing publication trends...")
    pub_trends = publication_trends(df)
    save_json(pub_trends, f"{proc_dir}/publication_trends.json")

    logger.info("Computing citation statistics...")
    cit_stats = citation_stats(df)
    save_json(cit_stats, f"{proc_dir}/citation_stats.json")

    logger.info("Computing author productivity...")
    auth_stats = author_productivity(df)
    save_json(auth_stats, f"{proc_dir}/top_authors.json")

    logger.info("Computing journal analysis...")
    j_stats = journal_analysis(df)
    save_json(j_stats, f"{proc_dir}/top_journals.json")

    logger.info("Computing institution analysis...")
    inst_stats = institution_analysis(df)
    save_json(inst_stats, f"{proc_dir}/top_institutions.json")

    logger.info("Computing concept landscape...")
    concepts = concept_landscape(df)
    save_json(concepts, f"{proc_dir}/concept_landscape.json")

    summary = {
        "timestamp": datetime.now(UTC).isoformat(),
        "n_records": len(df),
        "year_range": pub_trends["year_range"],
        "total_citations": cit_stats["total_citations"],
        "h_index": cit_stats["h_index"],
        "g_index": cit_stats["g_index"],
        "unique_authors": auth_stats["unique_authors"],
        "unique_journals": j_stats["unique_journals"],
        "unique_institutions": inst_stats["unique_institutions"],
        "domain_distribution": (
            df["domain_preliminary"].value_counts().to_dict()
            if "domain_preliminary" in df.columns
            else {}
        ),
    }
    save_json(summary, f"{proc_dir}/bibliometric_summary.json")

    logger.info("=== Bibliometric Analysis Agent complete ===")
    logger.info(
        "Summary: %d records, h=%d, %d authors",
        len(df),
        cit_stats["h_index"],
        auth_stats["unique_authors"],
    )


if __name__ == "__main__":
    main()
