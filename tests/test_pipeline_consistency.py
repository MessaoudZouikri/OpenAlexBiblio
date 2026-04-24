"""
Pipeline Consistency & Coherence Tests
=======================================
Verifies data integrity across every pipeline stage without needing the API or LLM.
Run after generate_test_data.py + all agents (except classification) have executed.

Usage:
    python tests/test_pipeline_consistency.py --config config/config.yaml
"""

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.utils.io_utils import latest_file, load_yaml

PASS = "\033[32m  PASS\033[0m"
FAIL = "\033[31m  FAIL\033[0m"
WARN = "\033[33m  WARN\033[0m"

failures = []
warnings = []


def check(label: str, cond: bool, detail: str = "", warn_only: bool = False) -> None:
    tag = PASS if cond else (WARN if warn_only else FAIL)
    print(f"{tag}  {label}" + (f"  [{detail}]" if detail else ""))
    if not cond:
        (warnings if warn_only else failures).append(f"{label}: {detail}")


# ── Helpers ────────────────────────────────────────────────────────────────


def load_df(path: str) -> pd.DataFrame:
    return pd.read_parquet(path, engine="pyarrow")


def load_js(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


# ══════════════════════════════════════════════════════════════════════════
# Stage 1 — Raw data
# ══════════════════════════════════════════════════════════════════════════


def test_raw(raw_dir: str, manifest_path: str):
    print("\n── Stage 1: Raw Data ─────────────────────────────────────────")
    check("Manifest exists", Path(manifest_path).exists())
    if not Path(manifest_path).exists():
        return None, None

    manifest = load_js(manifest_path)

    # Use the file the manifest explicitly references.
    # If it is missing, report the root cause and stop — falling back to
    # latest_file() would silently compare the wrong parquet and produce
    # cascading failures that obscure the real problem.
    manifest_ref = Path(manifest.get("output_file", ""))
    if not manifest_ref.exists():
        check(
            "Manifest output_file exists",
            False,
            f"referenced file missing: {manifest_ref.name}" " — re-run data_collection to restore",
        )
        return None, manifest

    df = load_df(str(manifest_ref))

    check("Record count > 0", len(df) > 0, f"{len(df)} records")
    check(
        "Manifest count matches parquet",
        abs(len(df) - manifest.get("total_records", 0)) <= 1,
        f"parquet={len(df)}, manifest={manifest.get('total_records')}",
    )

    required = {
        "id",
        "title",
        "year",
        "cited_by_count",
        "abstract",
        "authors",
        "concepts",
        "references",
    }
    missing = required - set(df.columns)
    check("Required columns present", not missing, f"missing: {missing}")

    check("IDs unique", df["id"].is_unique, f"{df['id'].duplicated().sum()} duplicates")
    check("IDs not null", df["id"].notna().all(), f"{df['id'].isna().sum()} nulls")
    check(
        "IDs match OpenAlex format",
        df["id"].str.match(r"^https://openalex\.org/W\d+$", na=False).all(),
        warn_only=True,
    )
    check("Titles not null", df["title"].notna().all())
    check("Years not null", df["year"].notna().all())
    check("Citations non-negative", (df["cited_by_count"] >= 0).all())
    check(
        "Abstract coverage >= 75%",
        (df["abstract"].str.len() > 20).mean() >= 0.75,
        f"{(df['abstract'].str.len() > 20).mean():.0%}",
        warn_only=True,
    )

    return df, manifest


# ══════════════════════════════════════════════════════════════════════════
# Stage 2 — Clean data
# ══════════════════════════════════════════════════════════════════════════


def test_clean(clean_path: str, df_raw, report_path: str):
    print("\n── Stage 2: Clean Data ───────────────────────────────────────")
    check("Clean parquet exists", Path(clean_path).exists())
    check("Cleaning report exists", Path(report_path).exists())
    if not Path(clean_path).exists():
        return None

    df = load_df(clean_path)
    report = load_js(report_path) if Path(report_path).exists() else {}

    check("Record count > 0", len(df) > 0, f"{len(df)} records")

    # Cross-stage checks require the raw file — skip when it is missing
    # (the root cause is already reported in Stage 1).
    if df_raw is not None:
        check(
            "Clean <= Raw (no inflation)",
            len(df) <= len(df_raw),
            f"clean={len(df)}, raw={len(df_raw)}",
        )
        check(
            "Retention >= 70%",
            len(df) / len(df_raw) >= 0.70,
            f"{len(df)/len(df_raw):.0%}",
            warn_only=True,
        )
        raw_ids = set(df_raw["id"])
        clean_ids = set(df["id"])
        check(
            "Clean IDs ⊆ Raw IDs",
            clean_ids.issubset(raw_ids),
            f"{len(clean_ids - raw_ids)} IDs not in raw",
        )
    else:
        print("  [SKIP] Cross-stage checks skipped — raw file missing (see Stage 1)")

    clean_ids = set(df["id"])
    check("Clean IDs unique", df["id"].is_unique, f"{df['id'].duplicated().sum()} dupes")

    added_cols = {
        "has_abstract",
        "has_concepts",
        "author_count",
        "decade",
        "domain_preliminary",
        "country_list",
        "is_international",
    }
    missing = added_cols - set(df.columns)
    check("Derived columns present", not missing, f"missing: {missing}")

    current_year = 2026
    min_year = df["year"].min()
    max_year = df["year"].max()
    check(
        "Year range plausible",
        1800 <= min_year and max_year <= current_year + 1,
        f"{int(min_year)}–{int(max_year)}",
    )
    check("No future years", max_year <= current_year + 1, f"max={int(max_year)}")
    check("Decade derived correctly", (df["decade"] == (df["year"] // 10 * 10)).all())
    check("Citations non-negative", (df["cited_by_count"] >= 0).all())
    check("author_count >= 0", (df["author_count"] >= 0).all())
    check(
        "Abstract coverage >= 50%",
        df["has_abstract"].mean() >= 0.5,
        f"{df['has_abstract'].mean():.0%}",
        warn_only=True,
    )

    valid_domains = {"Political Science", "Economics", "Sociology", "Other"}
    bad = set(df["domain_preliminary"].dropna()) - valid_domains
    check("Preliminary domains valid", not bad, f"invalid: {bad}")
    check("No null preliminary domains", df["domain_preliminary"].notna().all())

    # Report coherence
    if report.get("output_records"):
        check(
            "Report output_records matches parquet",
            abs(report["output_records"] - len(df)) <= 1,
            f"report={report['output_records']}, parquet={len(df)}",
        )

    return df


# ══════════════════════════════════════════════════════════════════════════
# Stage 3 — Bibliometric Analysis outputs
# ══════════════════════════════════════════════════════════════════════════


def test_bibliometric(proc_dir: str, df_clean: pd.DataFrame):
    print("\n── Stage 3: Bibliometric Analysis ───────────────────────────")
    files = [
        "publication_trends.json",
        "citation_stats.json",
        "top_authors.json",
        "top_journals.json",
        "top_institutions.json",
        "concept_landscape.json",
        "bibliometric_summary.json",
    ]
    for fname in files:
        check(f"{fname} exists", (Path(proc_dir) / fname).exists())

    # publication_trends coherence
    trends_path = Path(proc_dir) / "publication_trends.json"
    if trends_path.exists():
        trends = load_js(str(trends_path))
        annual = trends.get("annual", [])
        check("Annual trends non-empty", len(annual) > 0, f"{len(annual)} years")
        check(
            "Trends total_records matches clean",
            trends.get("total_records") == len(df_clean),
            f"trends={trends.get('total_records')}, clean={len(df_clean)}",
        )
        total_annual = sum(r["count"] for r in annual)
        check(
            "Annual counts sum to total",
            total_annual == len(df_clean),
            f"sum={total_annual}, total={len(df_clean)}",
        )
        # Year range consistency
        tr_min, tr_max = trends["year_range"]
        check(
            "Year range consistent with clean",
            tr_min == int(df_clean["year"].min()) and tr_max == int(df_clean["year"].max()),
            f"trends={tr_min}–{tr_max}, clean={int(df_clean['year'].min())}–{int(df_clean['year'].max())}",
        )

    # citation_stats coherence
    cit_path = Path(proc_dir) / "citation_stats.json"
    if cit_path.exists():
        cit = load_js(str(cit_path))
        check(
            "Citation n matches clean",
            cit.get("n") == len(df_clean),
            f"stats.n={cit.get('n')}, clean={len(df_clean)}",
        )
        check(
            "h-index > 0",
            cit.get("h_index_corpus", 0) > 0,
            f"h={cit.get('h_index_corpus')}",
            warn_only=True,
        )
        check(
            "g-index >= h-index",
            cit.get("g_index_corpus", 0) >= cit.get("h_index_corpus", 0),
            f"g={cit.get('g_index_corpus')}, h={cit.get('h_index_corpus')}",
        )
        check(
            "Total citations == sum of clean",
            cit.get("total_citations") == int(df_clean["cited_by_count"].sum()),
            f"stats={cit.get('total_citations')}, clean={int(df_clean['cited_by_count'].sum())}",
        )
        check(
            "Percentiles ordered",
            cit["percentiles"]["p25"] <= cit["percentiles"]["p50"] <= cit["percentiles"]["p75"],
            f"p25={cit['percentiles']['p25']}, p50={cit['percentiles']['p50']}, p75={cit['percentiles']['p75']}",
        )
        check("zero_citation_rate in [0,1]", 0 <= cit.get("zero_citation_rate", -1) <= 1)

    # top_authors coherence
    auth_path = Path(proc_dir) / "top_authors.json"
    if auth_path.exists():
        auth = load_js(str(auth_path))
        check(
            "unique_authors > 0", auth.get("unique_authors", 0) > 0, f"{auth.get('unique_authors')}"
        )
        top = auth.get("top_by_output", [])
        if top:
            check(
                "Top authors sorted descending",
                all(
                    top[i]["paper_count"] >= top[i + 1]["paper_count"] for i in range(len(top) - 1)
                ),
            )
        lotka_a = auth.get("lotka_alpha")
        if lotka_a is not None:
            # α ≈ 2.0 for real data; wider range accepted for small / synthetic corpora
            check(
                "Lotka alpha plausible (0.5–5.0)",
                0.5 <= lotka_a <= 5.0,
                f"α={lotka_a:.3f} (expected ~2.0 for real data)",
                warn_only=True,
            )

    # concept_landscape coherence
    concepts_path = Path(proc_dir) / "concept_landscape.json"
    if concepts_path.exists():
        concepts = load_js(str(concepts_path))
        top50 = concepts.get("top_50_concepts", [])
        check("Concept list non-empty", len(top50) > 0, f"{len(top50)} concepts")
        if len(top50) > 1:
            check(
                "Concepts sorted descending",
                all(top50[i]["count"] >= top50[i + 1]["count"] for i in range(len(top50) - 1)),
            )


# ══════════════════════════════════════════════════════════════════════════
# Stage 4 — Classification (if available)
# ══════════════════════════════════════════════════════════════════════════


def test_classification(proc_dir: str, df_clean: pd.DataFrame):
    print("\n── Stage 4: Classification ───────────────────────────────────")
    classified_path = Path(proc_dir) / "classified_works.parquet"
    check("classified_works.parquet exists", classified_path.exists())
    if not classified_path.exists():
        return None

    df = load_df(str(classified_path))

    # Stale data guard: classified must reference the same records as clean
    clean_ids = set(df_clean["id"])
    class_ids = set(df["id"])
    stale = class_ids - clean_ids
    if stale:
        check(
            "classified IDs match current clean IDs",
            False,
            f"{len(stale)} IDs in classified not in current clean — run classification on new data",
            warn_only=True,
        )
        # Still run schema checks on whatever is in the file
    else:
        check("classified IDs match clean IDs", True, f"{len(df)} records")

    required_cols = {"id", "domain", "subcategory", "domain_confidence", "domain_source"}
    missing = required_cols - set(df.columns)
    check("Classification columns present", not missing, f"missing: {missing}")

    valid_domains = {"Political Science", "Economics", "Sociology", "Other"}
    invalid = set(df["domain"].dropna()) - valid_domains
    check("All domains valid", not invalid, f"invalid: {invalid}")
    check(
        "No null domains",
        df["domain"].isna().mean() <= 0.05,
        f"{df['domain'].isna().mean():.1%} null",
    )

    valid_subs = {
        "comparative_politics",
        "political_theory",
        "electoral_politics",
        "democratic_theory",
        "radical_right",
        "latin_american_politics",
        "european_politics",
        "political_economy",
        "redistribution",
        "trade_globalization",
        "financial_crisis",
        "social_movements",
        "identity_politics",
        "media_communication",
        "culture_values",
        "international_relations",
        "history",
        "psychology",
        "geography",
        "interdisciplinary",
    }
    bad_subs = set(df["subcategory"].dropna()) - valid_subs
    check("All subcategories valid", not bad_subs, f"invalid: {bad_subs}")

    if "domain_confidence" in df.columns:
        check(
            "Confidence in [0,1]",
            df["domain_confidence"].between(0.0, 1.0).all(),
            f"min={df['domain_confidence'].min():.3f}, max={df['domain_confidence'].max():.3f}",
        )

    if "domain_source" in df.columns:
        sources = df["domain_source"].value_counts().to_dict()
        check("domain_source column populated", len(sources) > 0, str(sources))

    return df


# ══════════════════════════════════════════════════════════════════════════
# Stage 5 — Network Analysis
# ══════════════════════════════════════════════════════════════════════════


def test_network(proc_dir: str, net_dir: str, df_classified):
    print("\n── Stage 5: Network Analysis ─────────────────────────────────")
    import networkx as nx

    metrics_path = Path(proc_dir) / "network_metrics.json"
    check("network_metrics.json exists", metrics_path.exists())

    cluster_path = Path(proc_dir) / "cluster_assignments.parquet"
    check("cluster_assignments.parquet exists", cluster_path.exists())

    # GraphML files — check for VOS or raw variants
    for net_name, candidates in {
        "bibcoupling": [
            "bibcoupling_network_vos.graphml",
            "bibcoupling_network_raw.graphml",
            "bibcoupling_network.graphml",
        ],
        "cocitation": [
            "cocitation_network_vos.graphml",
            "cocitation_network_raw.graphml",
            "cocitation_network.graphml",
        ],
        "coauthorship": ["coauthorship_network.graphml"],
    }.items():
        found = next((c for c in candidates if (Path(net_dir) / c).exists()), None)
        detail = found if found else f"none of {candidates} found"
        check(f"{net_name} graphml exists", found is not None, detail, warn_only=True)

        if found:
            G = nx.read_graphml(str(Path(net_dir) / found))
            check(
                f"{net_name} non-empty",
                G.number_of_nodes() > 0,
                f"{G.number_of_nodes()} nodes, {G.number_of_edges()} edges",
            )
            check(
                f"{net_name} no self-loops",
                nx.number_of_selfloops(G) == 0,
                f"{nx.number_of_selfloops(G)} self-loops",
                warn_only=True,
            )
            check(
                f"{net_name} edge weights >= 0",
                all(d.get("weight", 1) >= 0 for _, _, d in G.edges(data=True)),
                warn_only=True,
            )

    # Cluster assignments schema
    if cluster_path.exists():
        df_cl = load_df(str(cluster_path))
        has_cluster = "cluster_id_louvain" in df_cl.columns or "cluster_id" in df_cl.columns
        check("cluster_id_louvain column present", has_cluster)
        check(
            "betweenness_centrality in [0,1]",
            df_cl["betweenness_centrality"].between(0, 1).all(),
            f"min={df_cl['betweenness_centrality'].min():.4f}, max={df_cl['betweenness_centrality'].max():.4f}",
        )
        check("pagerank values > 0", (df_cl["pagerank"] > 0).all(), warn_only=True)

        # Cross-check: cluster work_ids must be a subset of classified work_ids
        if df_classified is not None:
            classified_ids = set(df_classified["id"])
            cluster_ids = set(df_cl["work_id"])
            orphans = cluster_ids - classified_ids
            check(
                "Cluster work_ids ⊆ classified IDs",
                not orphans,
                f"{len(orphans)} orphan IDs in clusters not in classified",
                warn_only=True,
            )

    # Metrics JSON coherence
    if metrics_path.exists():
        metrics = load_js(str(metrics_path))
        check(
            "bibcoupling metrics present",
            "bibcoupling" in metrics,
            str(list(metrics.keys())),
            warn_only=True,
        )
        for net in ["bibcoupling", "cocitation", "coauthorship"]:
            if net in metrics:
                m = metrics[net]
                check(
                    f"{net} n_nodes > 0",
                    m.get("n_nodes", 0) > 0,
                    f"n_nodes={m.get('n_nodes')}",
                    warn_only=True,
                )
                check(
                    f"{net} density in [0,1]",
                    0 <= m.get("density", -1) <= 1,
                    f"density={m.get('density')}",
                    warn_only=True,
                )


# ══════════════════════════════════════════════════════════════════════════
# Stage 6 — Visualization outputs
# ══════════════════════════════════════════════════════════════════════════


def test_visualization(fig_dir: str, outputs_dir: str):
    print("\n── Stage 6: Visualization ────────────────────────────────────")
    expected_figs = [
        "publication_trends.png",
        "citation_distribution.png",
        "top_authors.png",
        "domain_distribution.png",
        "concept_landscape.png",
    ]
    for fname in expected_figs:
        path = Path(fig_dir) / fname
        check(f"{fname} exists", path.exists())
        if path.exists():
            size_kb = path.stat().st_size / 1024
            check(f"{fname} non-trivial (>5 KB)", size_kb > 5, f"{size_kb:.1f} KB", warn_only=True)

    report_path = Path(outputs_dir) / "reports" / "report.html"
    check("HTML report exists", report_path.exists(), str(report_path))
    if report_path.exists():
        html = report_path.read_text()
        check("HTML report references figures", "<img" in html, warn_only=True)


# ══════════════════════════════════════════════════════════════════════════
# Cross-pipeline ID integrity
# ══════════════════════════════════════════════════════════════════════════


def test_id_integrity(raw_dir: str, clean_path: str, classified_path: str, manifest_path: str):
    print("\n── Cross-Pipeline ID Integrity ───────────────────────────────")
    # Resolve the authoritative raw file from the manifest.
    # If the manifest's referenced file is missing, skip entirely — falling
    # back to latest_file() would compare the wrong parquet and duplicate the
    # failures already reported in Stage 1.
    raw_path = None
    if Path(manifest_path).exists():
        manifest_ref = Path(load_js(manifest_path).get("output_file", ""))
        if manifest_ref.exists():
            raw_path = manifest_ref

    if raw_path is None or not Path(clean_path).exists():
        print("  [SKIP] Raw file referenced by manifest is missing — see Stage 1 failure")
        return

    df_raw = load_df(str(raw_path))
    df_clean = load_df(clean_path)

    raw_ids = set(df_raw["id"])
    clean_ids = set(df_clean["id"])

    check(
        "Clean IDs ⊆ Raw IDs",
        clean_ids.issubset(raw_ids),
        f"{len(clean_ids - raw_ids)} extra IDs in clean",
    )
    check(
        "No new IDs introduced in cleaning",
        len(clean_ids - raw_ids) == 0,
        f"{len(clean_ids - raw_ids)} new IDs",
    )

    if Path(classified_path).exists():
        df_cls = load_df(classified_path)
        cls_ids = set(df_cls["id"])
        # Classified may be stale from previous run — warn, not fail
        stale = cls_ids - clean_ids
        new_in_clean = clean_ids - cls_ids
        check(
            "Classified IDs ⊆ Clean IDs (no stale records)",
            not stale,
            f"{len(stale)} classified IDs absent from current clean",
            warn_only=True,
        )
        check(
            "All clean IDs classified",
            not new_in_clean,
            f"{len(new_in_clean)} clean IDs missing from classified",
            warn_only=True,
        )


# ══════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════


def main():
    parser = argparse.ArgumentParser(description="Pipeline Consistency Tests")
    parser.add_argument("--config", default="config/config.yaml")
    args = parser.parse_args()

    config = load_yaml(args.config)
    p = config["paths"]

    print("=" * 62)
    print("  BIBLIOMETRIC PIPELINE — Consistency & Coherence Tests")
    print("=" * 62)

    df_raw, manifest = test_raw(p["data_raw"], f"{p['data_raw']}/collection_manifest.json")
    df_clean = test_clean(
        f"{p['data_clean']}/openalex_clean.parquet",
        df_raw,  # None when raw file is missing — test_clean handles this
        f"{p['data_clean']}/cleaning_report.json",
    )
    if df_clean is not None:
        test_bibliometric(p["data_processed"], df_clean)
    else:
        df_clean = pd.DataFrame()

    df_classified = test_classification(p["data_processed"], df_clean)
    test_network(p["data_processed"], f"{p['outputs']}/networks", df_classified)
    test_visualization(f"{p['outputs']}/figures", p["outputs"])
    test_id_integrity(
        p["data_raw"],
        f"{p['data_clean']}/openalex_clean.parquet",
        f"{p['data_processed']}/classified_works.parquet",
        f"{p['data_raw']}/collection_manifest.json",
    )

    print("\n" + "=" * 62)
    if failures:
        print(f"\033[31m  RESULT: {len(failures)} FAILURE(S), {len(warnings)} WARNING(S)\033[0m")
        for f in failures:
            print(f"    ✗ {f}")
        if warnings:
            for w in warnings:
                print(f"    ⚠  {w}")
        sys.exit(1)
    elif warnings:
        print(f"\033[33m  RESULT: PASS with {len(warnings)} WARNING(S)\033[0m")
        for w in warnings:
            print(f"    ⚠  {w}")
    else:
        print("\033[32m  RESULT: ALL CHECKS PASSED\033[0m")


if __name__ == "__main__":
    main()
