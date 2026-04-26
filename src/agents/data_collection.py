"""
Data Collection Agent
=====================
Retrieves works from OpenAlex using keyword queries on populism / populist(s).
Handles pagination, deduplication, and abstract reconstruction.

Outputs:
    data/raw/openalex_raw_{timestamp}.parquet
    data/raw/collection_manifest.json

Standalone:
    python src/agents/data_collection.py --config config/config.yaml [--test]
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.utils.io_utils import load_yaml, save_json, save_parquet, timestamped_path
from src.utils.logging_utils import setup_logger
from src.utils.openalex_client import OpenAlexClient

# ═══════════════════════════════════════════════════════════════════════════
# Query Helpers
# ═══════════════════════════════════════════════════════════════════════════


def _sanitize_term(raw_term: str, logger) -> str:
    """
    Strip non-ASCII characters from a query term.
    Common cause of corruption: accidental Option/AltGr keystrokes on macOS
    producing characters like 'Ò', '©', etc. that the OpenAlex query parser
    cannot tolerate.
    """
    term = raw_term.encode("ascii", errors="ignore").decode("ascii").strip()
    if term != raw_term:
        logger.warning(
            "Query term sanitised: %r → %r  (non-ASCII removed — check config)",
            raw_term,
            term,
        )
    return term


def _build_filters(flt_cfg: dict) -> Dict[str, str]:
    """Translate a filter config block into OpenAlex API parameters."""
    api_filters: Dict[str, str] = {}
    if flt_cfg.get("type"):
        api_filters["type"] = flt_cfg["type"]
    if flt_cfg.get("from_publication_date"):
        api_filters["from_publication_date"] = flt_cfg["from_publication_date"]
    if flt_cfg.get("to_publication_date"):
        api_filters["to_publication_date"] = flt_cfg["to_publication_date"]
    if flt_cfg.get("open_access_only"):
        api_filters["is_oa"] = "true"
    return api_filters


# ═══════════════════════════════════════════════════════════════════════════
# Collection Orchestration
# ═══════════════════════════════════════════════════════════════════════════


def run_collection(
    config: dict,
    openalex_cfg: dict,
    test_mode: bool = False,
) -> Dict[str, Any]:
    """
    Execute data collection for all configured queries.

    Returns:
        A manifest dict summarising the collection run. Empty dict on failure.
    """
    logger = setup_logger("data_collection", config["paths"]["logs"])
    logger.info("=== Data Collection Agent starting ===")
    logger.info("Mode: %s", "TEST" if test_mode else "FULL")

    max_records = (
        config["pipeline"]["test_max_records"]
        if test_mode
        else config["pipeline"]["full_max_records"]
    )
    # null / missing → unlimited
    if max_records is None:
        max_records = float("inf")

    client = OpenAlexClient(
        email=openalex_cfg["api"]["polite_email"],
        per_page=openalex_cfg["api"]["per_page"],
        rate_limit_delay=openalex_cfg["api"]["rate_limit_delay"],
        max_retries=openalex_cfg["api"]["max_retries"],
        retry_backoff=openalex_cfg["api"]["retry_backoff"],
        timeout=openalex_cfg["api"]["timeout"],
    )

    api_filters = _build_filters(openalex_cfg["queries"]["filters"])
    sort_cfg = openalex_cfg["queries"]["sort"]
    sort_str = f"{sort_cfg['field']}:{sort_cfg['order']}"

    all_records: Dict[str, dict] = {}  # keyed by OpenAlex ID for deduplication
    query_stats: List[dict] = []

    for query_cfg in openalex_cfg["queries"]["keywords"]:
        raw_term = query_cfg["term"]
        field = query_cfg["field"]
        term = _sanitize_term(raw_term, logger)
        if not term:
            logger.warning("Skipping empty query term (was: %r)", raw_term)
            continue

        logger.info(
            "Querying: field=%s, term=%r, max=%s",
            field,
            term,
            "unlimited" if max_records == float("inf") else max_records,
        )

        batch_start = time.time()
        batch_count = 0

        for raw_work in client.paginate_works(
            search_term=term,
            search_field=field,
            filters=api_filters,
            sort=sort_str,
            max_records=max_records,
        ):
            work_id = raw_work.get("id", "")
            if not work_id:
                continue

            normalized = OpenAlexClient.normalize_work(raw_work, term, f"query_{term}")

            if work_id in all_records:
                # Merge keywords_matched, keep existing record
                existing = all_records[work_id].get("keywords_matched", [])
                if term not in existing:
                    existing.append(term)
                all_records[work_id]["keywords_matched"] = existing
            else:
                all_records[work_id] = normalized
                batch_count += 1

        elapsed = time.time() - batch_start
        logger.info("  → %d new records in %.1fs", batch_count, elapsed)
        query_stats.append(
            {
                "term": term,
                "field": field,
                "new_records": batch_count,
                "elapsed_s": round(elapsed, 2),
            }
        )

    total = len(all_records)
    logger.info("Total unique records collected: %d", total)

    if total == 0:
        logger.error("No records collected. Check API connectivity and query parameters.")
        return {}

    df = pd.DataFrame(list(all_records.values()))

    raw_dir = config["paths"]["data_raw"]
    Path(raw_dir).mkdir(parents=True, exist_ok=True)
    output_path = timestamped_path(raw_dir, "openalex_raw", "parquet")
    save_parquet(df, str(output_path))
    logger.info("Saved raw data to: %s", output_path)

    manifest = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": "test" if test_mode else "full",
        "total_records": total,
        "output_file": str(output_path),
        "query_stats": query_stats,
        "api_parameters": {
            "base_url": openalex_cfg["api"]["base_url"],
            "per_page": openalex_cfg["api"]["per_page"],
            "filters": api_filters,
            "sort": sort_str,
            "max_records_per_query": max_records,
        },
        "columns": list(df.columns),
        "abstract_coverage": (
            int((df["abstract"].str.len() > 0).sum()) if "abstract" in df.columns else 0
        ),
        "concept_coverage": (
            int((df["concepts"].apply(len) > 0).sum()) if "concepts" in df.columns else 0
        ),
    }
    save_json(manifest, f"{raw_dir}/collection_manifest.json")
    logger.info("Saved collection manifest.")
    logger.info("=== Data Collection Agent complete ===")
    return manifest


# ═══════════════════════════════════════════════════════════════════════════
# Public API (used by orchestrator and tests)
# ═══════════════════════════════════════════════════════════════════════════


def collect_openalex_data(
    search_term: str,
    max_results: int = 50,
    polite_email: str = "",
    per_page: int = 50,
) -> pd.DataFrame:
    """
    Lightweight single-query collector. Returns empty DataFrame on API errors
    (timeout, rate limit, non-iterable mock responses, etc.) rather than
    raising — this mirrors graceful-degradation expectations in tests.
    """
    _logger = logging.getLogger(__name__)

    try:
        client = OpenAlexClient(
            email=polite_email,
            per_page=per_page,
            rate_limit_delay=0.1,
            max_retries=3,
            retry_backoff=2.0,
            timeout=30,
        )
    except Exception as exc:
        _logger.error("collect_openalex_data: client init failed for %r: %s", search_term, exc)
        return pd.DataFrame()

    records: List[dict] = []
    try:
        for raw in client.paginate_works(
            search_term=search_term,
            search_field="search",
            filters={},
            sort="cited_by_count:desc",
            max_records=max_results,
        ):
            if isinstance(raw, dict) and raw.get("id"):
                records.append(
                    OpenAlexClient.normalize_work(raw, search_term, f"query_{search_term}")
                )
    except Exception as exc:
        _logger.error(
            "collect_openalex_data: pagination failed for %r after %d records: %s",
            search_term,
            len(records),
            exc,
            exc_info=True,
        )
        return pd.DataFrame()

    return pd.DataFrame(records)


# ═══════════════════════════════════════════════════════════════════════════
# CLI Entry Point
# ═══════════════════════════════════════════════════════════════════════════


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenAlex Data Collection Agent")
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--openalex-config", default="config/openalex.yaml")
    parser.add_argument("--test", action="store_true", help="Run in test mode (limited records)")
    args = parser.parse_args()

    config = load_yaml(args.config)
    openalex_cfg = load_yaml(args.openalex_config)
    test_mode = args.test or config["pipeline"]["mode"] == "test"

    manifest = run_collection(config, openalex_cfg, test_mode=test_mode)
    if not manifest:
        sys.exit(1)


if __name__ == "__main__":
    main()
