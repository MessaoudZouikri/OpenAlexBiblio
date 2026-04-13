"""
Data Collection Agent
=====================
Retrieves works from OpenAlex using keyword queries on populism/populist(s).
Handles pagination, deduplication, and abstract reconstruction.
Outputs: data/raw/openalex_raw_{timestamp}.parquet + collection_manifest.json

Standalone execution:
    python src/agents/data_collection.py --config config/config.yaml [--test]
"""
import argparse
import json
import logging
import sys
import time
from datetime import datetime, UTC
from pathlib import Path

import pandas as pd

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.utils.openalex_client import OpenAlexClient
from src.utils.io_utils import save_parquet, save_json, load_yaml, timestamped_path
from src.utils.logging_utils import setup_logger


def run_collection(config: dict, openalex_cfg: dict, test_mode: bool = False) -> dict:
    """
    Execute data collection for all configured queries.
    
    Returns:
        manifest dict with collection statistics
    """
    logger = setup_logger("data_collection", config["paths"]["logs"])
    logger.info("=== Data Collection Agent starting ===")
    logger.info("Mode: %s", "TEST" if test_mode else "FULL")

    max_records = (
        config["pipeline"]["test_max_records"]
        if test_mode
        else config["pipeline"]["full_max_records"]
    )

    client = OpenAlexClient(
        email=openalex_cfg["api"]["polite_email"],
        per_page=openalex_cfg["api"]["per_page"],
        rate_limit_delay=openalex_cfg["api"]["rate_limit_delay"],
        max_retries=openalex_cfg["api"]["max_retries"],
        retry_backoff=openalex_cfg["api"]["retry_backoff"],
        timeout=openalex_cfg["api"]["timeout"],
    )

    # Build extra filters from config
    api_filters = {}
    flt = openalex_cfg["queries"]["filters"]
    if flt.get("type"):
        api_filters["type"] = flt["type"]
    if flt.get("from_publication_date"):
        api_filters["from_publication_date"] = flt["from_publication_date"]

    sort_cfg = openalex_cfg["queries"]["sort"]
    sort_str = f"{sort_cfg['field']}:{sort_cfg['order']}"

    all_records: dict[str, dict] = {}  # keyed by OpenAlex ID for deduplication
    query_stats = []

    for query_cfg in openalex_cfg["queries"]["keywords"]:
        raw_term = query_cfg["term"]
        field    = query_cfg["field"]

        # Sanitise: strip non-ASCII characters that can corrupt query terms
        # (common Mac keyboard accident: e.g. Option+Shift key produces Ò, ©, etc.)
        term = raw_term.encode("ascii", errors="ignore").decode("ascii").strip()
        if term != raw_term:
            logger.warning(
                "Query term sanitised: '%s' → '%s'  "
                "(non-ASCII characters removed — check config/openalex.yaml)",
                raw_term, term,
            )
        if not term:
            logger.warning("Skipping empty query term (was: '%s')", raw_term)
            continue

        logger.info("Querying: field=%s, term='%s', max=%d", field, term, max_records)

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
                # Deduplication: merge keywords_matched, keep existing record
                existing_keywords = all_records[work_id].get("keywords_matched", [])
                if term not in existing_keywords:
                    existing_keywords.append(term)
                all_records[work_id]["keywords_matched"] = existing_keywords
            else:
                all_records[work_id] = normalized
                batch_count += 1

        elapsed = time.time() - batch_start
        logger.info("  → %d new records in %.1fs", batch_count, elapsed)
        query_stats.append({
            "term": term,
            "field": field,
            "new_records": batch_count,
            "elapsed_s": round(elapsed, 2),
        })

    total = len(all_records)
    logger.info("Total unique records collected: %d", total)

    if total == 0:
        logger.error("No records collected. Check API connectivity and query parameters.")
        return {}

    # Convert to DataFrame
    records_list = list(all_records.values())
    df = pd.DataFrame(records_list)

    # Save output
    raw_dir = config["paths"]["data_raw"]
    Path(raw_dir).mkdir(parents=True, exist_ok=True)
    output_path = timestamped_path(raw_dir, "openalex_raw", "parquet")
    save_parquet(df, str(output_path))
    logger.info("Saved raw data to: %s", output_path)

    # Build manifest
    manifest = {
        "timestamp": datetime.now(UTC).isoformat(),
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
        "abstract_coverage": int((df["abstract"].str.len() > 0).sum()),
        "concept_coverage": int((df["concepts"].apply(len) > 0).sum()),
    }
    save_json(manifest, f"{raw_dir}/collection_manifest.json")
    logger.info("Saved collection manifest.")
    logger.info("=== Data Collection Agent complete ===")
    return manifest


def main():
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
