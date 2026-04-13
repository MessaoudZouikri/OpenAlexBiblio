"""
Bibliometric Analysis Agent
============================
Computes publication trends, citation statistics, author/journal/institution
productivity metrics, and concept landscape from the clean dataset.
Outputs: multiple JSON files in data/processed/

Standalone:
    python src/agents/bibliometric_analysis.py --config config/config.yaml
"""
import argparse
import logging
import sys
from collections import Counter, defaultdict
from datetime import datetime
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.utils.io_utils import load_parquet, save_json, load_yaml
from src.utils.logging_utils import setup_logger


def compute_hindex(citations: list) -> int:
    """Compute h-index from a list of citation counts."""
    sorted_cites = sorted(citations, reverse=True)
    h = 0
    for i, c in enumerate(sorted_cites, 1):
        if c >= i:
            h = i
        else:
            break
    return h


def compute_gindex(citations: list) -> int:
    """Compute g-index from a list of citation counts."""
    sorted_cites = sorted(citations, reverse=True)
    g = 0
    cumsum = 0
    for i, c in enumerate(sorted_cites, 1):
        cumsum += c
        if cumsum >= i * i:
            g = i
        else:
            break
    return g


def safe_div(a, b, default=0.0):
    return a / b if b else default


def safe_list(val) -> list:
    """Coerce a value to a plain Python list (handles numpy arrays, None, scalars)."""
    if val is None:
        return []
    if isinstance(val, list):
        return val
    try:
        return list(val)
    except Exception:
        return []


def publication_trends(df: pd.DataFrame) -> dict:
    """Annual and decadal publication counts with growth rates."""
    annual = df.groupby("year").size().reset_index(name="count")
    annual = annual.sort_values("year")
    annual["cumulative"] = annual["count"].cumsum()
    annual["yoy_growth_pct"] = annual["count"].pct_change() * 100

    decadal = df.groupby("decade").size().reset_index(name="count")

    domain_annual = (
        df.groupby(["year", "domain_preliminary"]).size()
        .reset_index(name="count")
        .pivot(index="year", columns="domain_preliminary", values="count")
        .fillna(0)
        .astype(int)
        .reset_index()
    )

    return {
        "annual": annual.replace({np.nan: None}).to_dict(orient="records"),
        "decadal": decadal.to_dict(orient="records"),
        "domain_annual": domain_annual.to_dict(orient="records"),
        "total_records": len(df),
        "year_range": [int(df["year"].min()), int(df["year"].max())],
    }


def citation_stats(df: pd.DataFrame) -> dict:
    """Citation distribution and corpus-level indices."""
    cites = df["cited_by_count"].tolist()
    cites_nonzero = [c for c in cites if c > 0]

    p_values = [25, 50, 75, 90, 95, 99]
    percentiles = {f"p{p}": float(np.percentile(cites, p)) for p in p_values}

    return {
        "total_citations": int(sum(cites)),
        "mean": round(float(np.mean(cites)), 2),
        "median": float(np.median(cites)),
        "std": round(float(np.std(cites)), 2),
        "min": int(min(cites)),
        "max": int(max(cites)),
        "percentiles": percentiles,
        "h_index_corpus": compute_hindex(cites),
        "g_index_corpus": compute_gindex(cites),
        "zero_citation_count": int(sum(1 for c in cites if c == 0)),
        "zero_citation_rate": round(safe_div(sum(1 for c in cites if c == 0), len(cites)), 4),
        "top1pct_threshold": float(np.percentile(cites, 99)),
        "top10pct_threshold": float(np.percentile(cites, 90)),
        "top1pct_count": int(sum(1 for c in cites if c >= np.percentile(cites, 99))),
        "top10pct_count": int(sum(1 for c in cites if c >= np.percentile(cites, 90))),
        "n": len(cites),
    }


def author_productivity(df: pd.DataFrame) -> dict:
    """Author output and citation metrics including Lotka's law fit."""
    author_papers: dict = defaultdict(list)
    author_cites: dict = defaultdict(int)

    for _, row in df.iterrows():
        author_list = row.get("authors") if row.get("authors") is not None else []
        if not isinstance(author_list, (list, tuple)):
            try:
                author_list = list(author_list)
            except Exception:
                author_list = []
        for author in author_list:
            aid = author.get("id") or author.get("name", "")
            if not aid:
                continue
            author_papers[aid].append({
                "work_id": row["id"],
                "name": author.get("name", ""),
                "citations": row["cited_by_count"],
            })
            author_cites[aid] += row["cited_by_count"]

    # Build author stats
    author_stats = []
    for aid, papers in author_papers.items():
        name = papers[0]["name"] if papers else aid
        total_cites = author_cites[aid]
        n_papers = len(papers)
        author_stats.append({
            "id": aid,
            "name": name,
            "paper_count": n_papers,
            "total_citations": total_cites,
            "mean_citations_per_paper": round(safe_div(total_cites, n_papers), 2),
            "h_index": compute_hindex([p["citations"] for p in papers]),
        })

    author_stats.sort(key=lambda x: x["paper_count"], reverse=True)
    top_by_output = author_stats[:20]
    top_by_cites = sorted(author_stats, key=lambda x: x["total_citations"], reverse=True)[:20]

    # Lotka's law fit
    paper_counts = [a["paper_count"] for a in author_stats]
    freq = Counter(paper_counts)
    if len(freq) > 3:
        xs = np.log(list(freq.keys()))
        ys = np.log(list(freq.values()))
        try:
            slope, intercept, r, _, _ = stats.linregress(xs, ys)
            lotka_alpha = -slope
            lotka_r2 = r ** 2
        except Exception:
            lotka_alpha = None
            lotka_r2 = None
    else:
        lotka_alpha = None
        lotka_r2 = None

    return {
        "unique_authors": len(author_stats),
        "top_by_output": top_by_output,
        "top_by_citations": top_by_cites,
        "lotka_alpha": round(float(lotka_alpha), 4) if lotka_alpha else None,
        "lotka_r2": round(float(lotka_r2), 4) if lotka_r2 else None,
        "single_paper_authors": int(sum(1 for a in author_stats if a["paper_count"] == 1)),
        "n_authors_analyzed": len(author_stats),
    }


def journal_analysis(df: pd.DataFrame) -> dict:
    """Journal frequency, citation metrics, and Bradford zones."""
    journal_data = df[df["journal"].str.len() > 0].copy()
    
    j_groups = journal_data.groupby("journal").agg(
        paper_count=("id", "count"),
        total_citations=("cited_by_count", "sum"),
        mean_citations=("cited_by_count", "mean"),
    ).reset_index()
    j_groups = j_groups.sort_values("paper_count", ascending=False)

    # Bradford's zones (rough approximation by thirds)
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
            .head(20).round(2).to_dict(orient="records"),
        "bradford_zones": {
            "zone1_journals": len(zone1),
            "zone2_journals": len(zone2),
            "zone3_journals": len(zone3),
        },
    }


def institution_analysis(df: pd.DataFrame) -> dict:
    """Institutional output and citations."""
    inst_papers: dict = defaultdict(lambda: {"count": 0, "citations": 0, "name": ""})

    for _, row in df.iterrows():
        seen = set()
        for inst in safe_list(row.get("institutions")):
            iid = inst.get("id", "") if isinstance(inst, dict) else ""
            if not iid or iid in seen:
                continue
            seen.add(iid)
            inst_papers[iid]["count"] += 1
            inst_papers[iid]["citations"] += row["cited_by_count"]
            inst_papers[iid]["name"] = inst.get("name", iid)

    inst_list = [
        {"id": k, "name": v["name"], "paper_count": v["count"], "total_citations": v["citations"]}
        for k, v in inst_papers.items()
    ]
    inst_list.sort(key=lambda x: x["paper_count"], reverse=True)

    return {
        "unique_institutions": len(inst_list),
        "top_by_output": inst_list[:20],
        "top_by_citations": sorted(inst_list, key=lambda x: x["total_citations"], reverse=True)[:20],
    }


def concept_landscape(df: pd.DataFrame) -> dict:
    """Top concepts and co-occurrence matrix."""
    concept_counts: Counter = Counter()
    concept_cooccur: dict = defaultdict(Counter)

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

    cooccur_matrix = {
        a: {b: concept_cooccur[a].get(b, 0) for b in top_names}
        for a in top_names
    }

    return {
        "top_50_concepts": top_50,
        "cooccurrence_matrix_top20": cooccur_matrix,
    }


def main():
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
        "h_index_corpus": cit_stats["h_index_corpus"],
        "g_index_corpus": cit_stats["g_index_corpus"],
        "unique_authors": auth_stats["unique_authors"],
        "unique_journals": j_stats["unique_journals"],
        "unique_institutions": inst_stats["unique_institutions"],
        "domain_distribution": df["domain_preliminary"].value_counts().to_dict(),
    }
    save_json(summary, f"{proc_dir}/bibliometric_summary.json")

    logger.info("=== Bibliometric Analysis Agent complete ===")
    logger.info("Summary: %d records, h=%d, %d authors",
                len(df), cit_stats["h_index_corpus"], auth_stats["unique_authors"])


if __name__ == "__main__":
    main()
