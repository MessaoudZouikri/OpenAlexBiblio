"""
Validation Agents
=================
Four independent validators: Data (D1/D2), Statistical, Classification, Network.
Each reads from disk, applies checks, writes a report JSON, and signals PASS/FAIL.

Usage:
    python src/agents/validation/data_validator.py --stage D1 --config config/config.yaml
    python src/agents/validation/statistical_validator.py --config config/config.yaml
    python src/agents/validation/classification_validator.py --config config/config.yaml
    python src/agents/validation/network_validator.py --config config/config.yaml
"""

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src.utils.io_utils import latest_file, load_json, load_parquet, load_yaml, save_json
from src.utils.llm_client import VALID_DOMAINS, VALID_SUBCATEGORIES
from src.utils.logging_utils import setup_logger

# ── Shared helpers ────────────────────────────────────────────────────────


def _make_report(agent: str, stage: str = "") -> dict:
    return {
        "agent": agent,
        "stage": stage,
        "timestamp": datetime.now(UTC).isoformat(),
        "status": "PASS",
        "errors": [],
        "warnings": [],
        "checks": [],
    }


def _check(report: dict, name: str, passed: bool, detail: str = "", is_error: bool = True) -> None:
    report["checks"].append({"name": name, "passed": passed, "detail": detail})
    if not passed:
        if is_error:
            report["errors"].append(f"{name}: {detail}")
            report["status"] = "FAIL"
        else:
            report["warnings"].append(f"{name}: {detail}")


# ═══════════════════════════════════════════════════════════════════════════
# DATA VALIDATOR
# ═══════════════════════════════════════════════════════════════════════════

REQUIRED_RAW_COLS = {
    "id",
    "title",
    "year",
    "cited_by_count",
    "authors",
    "concepts",
    "references",
    "abstract",
}

REQUIRED_CLEAN_COLS = REQUIRED_RAW_COLS | {
    "has_abstract",
    "has_concepts",
    "author_count",
    "domain_preliminary",
    "decade",
    "country_list",
}


def validate_data(config: dict, stage: str = "D1") -> dict:
    logger = setup_logger("data_validator", config["paths"]["logs"])
    logger.info("=== Data Validator [%s] starting ===", stage)
    report = _make_report("data_validator", stage)

    try:
        if stage == "D1":
            path = latest_file(config["paths"]["data_raw"], "openalex_raw_*.parquet")
            manifest_path = f"{config['paths']['data_raw']}/collection_manifest.json"
            required_cols = REQUIRED_RAW_COLS
        else:
            path = Path(f"{config['paths']['data_clean']}/openalex_clean.parquet")
            manifest_path = f"{config['paths']['data_clean']}/cleaning_report.json"
            required_cols = REQUIRED_CLEAN_COLS

        # File existence
        _check(report, "file_exists", path is not None and Path(str(path)).exists(), str(path))
        if report["status"] == "FAIL":
            return report

        df = load_parquet(str(path))
        report["n_records"] = len(df)

        # Schema checks
        missing_cols = required_cols - set(df.columns)
        _check(
            report,
            "schema_required_columns",
            len(missing_cols) == 0,
            f"Missing: {missing_cols}" if missing_cols else "OK",
        )

        # ID checks
        _check(report, "id_no_nulls", df["id"].notna().all(), f"{df['id'].isna().sum()} null IDs")
        _check(report, "id_unique", df["id"].is_unique, f"{df['id'].duplicated().sum()} duplicates")
        if "id" in df.columns and df["id"].notna().any():
            bad_ids = (~df["id"].str.match(r"^https://openalex\.org/W\d+$", na=False)).sum()
            _check(
                report,
                "id_format_openalex",
                bad_ids == 0,
                f"{bad_ids} IDs with unexpected format",
                is_error=False,
            )

        # Title checks
        _check(
            report,
            "title_no_nulls",
            df["title"].notna().all(),
            f"{df['title'].isna().sum()} null titles",
        )

        # Year checks
        current_year = datetime.now(UTC).year
        _check(
            report,
            "year_no_nulls",
            df["year"].notna().all(),
            f"{df['year'].isna().sum()} null years",
        )
        if df["year"].notna().any():
            year_range_ok = df["year"].between(1900, current_year + 1).all()
            _check(
                report,
                "year_valid_range",
                year_range_ok,
                f"Year range: {int(df['year'].min())}–{int(df['year'].max())}",
            )

        # Citation checks
        _check(
            report,
            "citations_non_negative",
            (df["cited_by_count"] >= 0).all(),
            f"{(df['cited_by_count'] < 0).sum()} negative values",
        )

        # Completeness warnings
        if "abstract" in df.columns:
            abstract_rate = (df["abstract"].str.len() > 20).mean()
            _check(
                report,
                "abstract_coverage_50pct",
                abstract_rate >= 0.5,
                f"Abstract coverage: {abstract_rate:.1%}",
                is_error=False,
            )
            report["abstract_coverage_rate"] = round(abstract_rate, 4)

        if "concepts" in df.columns:
            concept_rate = (
                df["concepts"]
                .apply(lambda x: len(x) > 0 if hasattr(x, "__len__") and x is not None else False)
                .mean()
            )
            _check(
                report,
                "concept_coverage_60pct",
                concept_rate >= 0.6,
                f"Concept coverage: {concept_rate:.1%}",
                is_error=False,
            )

        # Manifest check
        if Path(manifest_path).exists():
            manifest = load_json(manifest_path)
            manifest_count = manifest.get("total_records") or manifest.get("output_records")
            if manifest_count:
                diff = abs(len(df) - manifest_count)
                _check(
                    report,
                    "record_count_matches_manifest",
                    diff <= 1,
                    f"DF={len(df)}, manifest={manifest_count}",
                    is_error=False,
                )

    except Exception as exc:
        report["errors"].append(f"Unexpected error: {exc}")
        report["status"] = "FAIL"

    save_json(report, f"{config['paths']['logs']}/validation_data_{stage}.json")
    logger.info(
        "Data Validator [%s]: %s (%d errors, %d warnings)",
        stage,
        report["status"],
        len(report["errors"]),
        len(report["warnings"]),
    )
    return report


# ═══════════════════════════════════════════════════════════════════════════
# STATISTICAL VALIDATOR
# ═══════════════════════════════════════════════════════════════════════════


def validate_statistical(config: dict) -> dict:
    logger = setup_logger("statistical_validator", config["paths"]["logs"])
    logger.info("=== Statistical Validator starting ===")
    report = _make_report("statistical_validator")
    report["status"] = "PASS"  # Statistical issues never hard-fail

    try:
        summary_path = f"{config['paths']['data_processed']}/bibliometric_summary.json"
        trends_path = f"{config['paths']['data_processed']}/publication_trends.json"
        authors_path = f"{config['paths']['data_processed']}/top_authors.json"

        for p in [summary_path, trends_path, authors_path]:
            _check(report, f"file_exists_{Path(p).name}", Path(p).exists(), p)

        if Path(summary_path).exists():
            summary = load_json(summary_path)
            _check(
                report,
                "n_records_positive",
                summary.get("n_records", 0) > 0,
                str(summary.get("n_records")),
                is_error=False,
            )

        if Path(trends_path).exists():
            trends = load_json(trends_path)
            annual = trends.get("annual", [])
            if annual:
                max_yoy = max(
                    (abs(r.get("yoy_growth_pct") or 0) for r in annual if r.get("yoy_growth_pct")),
                    default=0,
                )
                _check(
                    report,
                    "no_extreme_yoy_spike",
                    max_yoy <= 500,
                    f"Max YoY growth: {max_yoy:.1f}%",
                    is_error=False,
                )

        if Path(authors_path).exists():
            authors = load_json(authors_path)
            lotka_alpha = authors.get("lotka_alpha")
            lotka_r2 = authors.get("lotka_r2")
            if lotka_alpha is not None:
                _check(
                    report,
                    "lotka_alpha_plausible",
                    1.0 <= lotka_alpha <= 4.0,
                    f"α={lotka_alpha:.3f} (expected ~2.0)",
                    is_error=False,
                )
            if lotka_r2 is not None:
                _check(
                    report,
                    "lotka_r2_acceptable",
                    lotka_r2 >= 0.6,
                    f"R²={lotka_r2:.3f}",
                    is_error=False,
                )

    except Exception as exc:
        report["warnings"].append(f"Unexpected error: {exc}")

    save_json(report, f"{config['paths']['logs']}/validation_statistical.json")
    logger.info(
        "Statistical Validator: %s (%d warnings)", report["status"], len(report["warnings"])
    )
    return report


# ═══════════════════════════════════════════════════════════════════════════
# CLASSIFICATION VALIDATOR
# ═══════════════════════════════════════════════════════════════════════════


def validate_classification(config: dict) -> dict:
    logger = setup_logger("classification_validator", config["paths"]["logs"])
    logger.info("=== Classification Validator starting ===")
    report = _make_report("classification_validator")

    try:
        path = f"{config['paths']['data_processed']}/classified_works.parquet"
        _check(report, "file_exists", Path(path).exists(), path)
        if report["status"] == "FAIL":
            return report

        df = load_parquet(path)
        report["n_records"] = len(df)

        # Null domain check (FAIL threshold: >5%)
        null_rate = df["domain"].isna().mean()
        _check(
            report,
            "null_domain_under_5pct",
            null_rate <= 0.05,
            f"Null domain rate: {null_rate:.1%}",
        )

        # Valid domain values
        invalid_domains = set(df["domain"].dropna().unique()) - VALID_DOMAINS
        _check(
            report, "all_domains_valid", len(invalid_domains) == 0, f"Invalid: {invalid_domains}"
        )

        # Valid subcategory values
        bad_subs = 0
        for _, row in df.iterrows():
            domain = row.get("domain")
            sub = row.get("subcategory")
            if domain in VALID_SUBCATEGORIES:
                if sub not in VALID_SUBCATEGORIES[domain]:
                    bad_subs += 1
        _check(
            report,
            "all_subcategories_valid",
            bad_subs == 0,
            f"{bad_subs} invalid subcategory/domain pairs",
        )

        # Confidence range check
        conf_ok = df["domain_confidence"].between(0.0, 1.0).all()
        _check(report, "confidence_in_range", conf_ok, "All confidence values in [0,1]")

        # High uniform confidence warning (LLM hallucination signal)
        if "domain_source" in df.columns:
            llm_rows = df[df["domain_source"] == "llm"]
            if len(llm_rows) > 10:
                high_conf_rate = (llm_rows["domain_confidence"] > 0.95).mean()
                _check(
                    report,
                    "llm_confidence_not_uniformly_high",
                    high_conf_rate <= 0.8,
                    f"{high_conf_rate:.1%} of LLM results >0.95 confidence",
                    is_error=False,
                )

        # Other/interdisciplinary rate warning
        other_rate = ((df["domain"] == "Other") & (df["subcategory"] == "interdisciplinary")).mean()
        _check(
            report,
            "other_interdisciplinary_under_40pct",
            other_rate <= 0.4,
            f"Other/interdisciplinary rate: {other_rate:.1%}",
            is_error=False,
        )

        report["domain_distribution"] = df["domain"].value_counts().to_dict()
        report["source_distribution"] = (
            df["domain_source"].value_counts().to_dict() if "domain_source" in df.columns else {}
        )

    except Exception as exc:
        report["errors"].append(f"Unexpected error: {exc}")
        report["status"] = "FAIL"

    save_json(report, f"{config['paths']['logs']}/validation_classification.json")
    logger.info(
        "Classification Validator: %s (%d errors, %d warnings)",
        report["status"],
        len(report["errors"]),
        len(report["warnings"]),
    )
    return report


# ═══════════════════════════════════════════════════════════════════════════
# NETWORK VALIDATOR
# ═══════════════════════════════════════════════════════════════════════════


def validate_network(config: dict) -> dict:
    logger = setup_logger("network_validator", config["paths"]["logs"])
    logger.info("=== Network Validator starting ===")
    report = _make_report("network_validator")

    try:
        import networkx as nx

        net_dir = config["paths"]["outputs"] + "/networks"
        proc_dir = config["paths"]["data_processed"]

        # Check expected network files.
        # The network agent saves raw + VOS-filtered variants (e.g. bibcoupling_network_raw.graphml
        # and bibcoupling_network_vos.graphml). We accept any of the known variants.
        network_file_candidates = {
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
        }
        for net_name, candidates in network_file_candidates.items():
            found = next((c for c in candidates if (Path(net_dir) / c).exists()), None)
            _check(
                report,
                f"file_exists_{net_name}",
                found is not None,
                f"None of {candidates} found in {net_dir}",
                is_error=False,
            )
            if found:
                fpath = Path(net_dir) / found
                try:
                    G = nx.read_graphml(str(fpath))
                    _check(report, f"parseable_{net_name}", True, f"{G.number_of_nodes()} nodes")
                    self_loops = nx.number_of_selfloops(G)
                    _check(
                        report,
                        f"no_self_loops_{net_name}",
                        self_loops == 0,
                        f"{self_loops} self-loops",
                        is_error=False,
                    )
                except Exception as exc:
                    _check(report, f"parseable_{net_name}", False, str(exc))

        # Metrics JSON
        metrics_path = f"{proc_dir}/network_metrics.json"
        _check(report, "network_metrics_exists", Path(metrics_path).exists(), metrics_path)
        if Path(metrics_path).exists():
            metrics = load_json(metrics_path)
            _check(
                report,
                "metrics_has_bibcoupling",
                "bibcoupling" in metrics,
                str(list(metrics.keys())),
                is_error=False,
            )

        # Cluster assignments — agent saves cluster_id_louvain (Louvain) + cluster_id_spectral
        cluster_path = f"{proc_dir}/cluster_assignments.parquet"
        if Path(cluster_path).exists():
            df_clusters = load_parquet(cluster_path)
            # Accept either the legacy 'cluster_id' or the new 'cluster_id_louvain' column
            has_cluster_col = (
                "cluster_id_louvain" in df_clusters.columns or "cluster_id" in df_clusters.columns
            )
            required = {"work_id", "betweenness_centrality"}
            missing = required - set(df_clusters.columns)
            if not has_cluster_col:
                missing.add("cluster_id_louvain")
            _check(report, "cluster_assignments_schema", len(missing) == 0, f"Missing: {missing}")
            bc_ok = df_clusters["betweenness_centrality"].between(0, 1).all()
            _check(report, "betweenness_centrality_in_range", bc_ok, "All BC values in [0,1]")
            cluster_col = (
                "cluster_id_louvain"
                if "cluster_id_louvain" in df_clusters.columns
                else "cluster_id"
            )
            if cluster_col in df_clusters.columns:
                unassigned = (df_clusters[cluster_col] == -1).mean()
                _check(
                    report,
                    "cluster_coverage_90pct",
                    unassigned <= 0.10,
                    f"Unassigned: {unassigned:.1%}",
                    is_error=False,
                )

    except Exception as exc:
        report["errors"].append(f"Unexpected error: {exc}")
        report["status"] = "FAIL"

    save_json(report, f"{config['paths']['logs']}/validation_network.json")
    logger.info(
        "Network Validator: %s (%d errors, %d warnings)",
        report["status"],
        len(report["errors"]),
        len(report["warnings"]),
    )
    return report


# ═══════════════════════════════════════════════════════════════════════════
# CLI entry points
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validation Agent Runner")
    parser.add_argument(
        "--validator", required=True, choices=["data", "statistical", "classification", "network"]
    )
    parser.add_argument("--stage", default="D1", help="D1 or D2 (for data validator)")
    parser.add_argument("--config", default="config/config.yaml")
    args = parser.parse_args()

    cfg = load_yaml(args.config)

    if args.validator == "data":
        result = validate_data(cfg, stage=args.stage)
    elif args.validator == "statistical":
        result = validate_statistical(cfg)
    elif args.validator == "classification":
        result = validate_classification(cfg)
    elif args.validator == "network":
        result = validate_network(cfg)
    else:
        sys.exit(1)

    if result["status"] == "FAIL":
        print("\n[FAIL] Validation errors:")
        for e in result["errors"]:
            print(f"  ✗ {e}")
        sys.exit(1)
    else:
        print(f"\n[PASS] All critical checks passed. Warnings: {len(result.get('warnings', []))}")
