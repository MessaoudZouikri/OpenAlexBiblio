"""
Data Cleaning Agent
===================
Transforms raw OpenAlex data into a clean, analysis-ready dataset.
Handles deduplication, normalization, field derivation, domain pre-labeling.
Outputs: data/clean/openalex_clean.parquet + cleaning_report.json

Standalone:
    python src/agents/data_cleaning.py --config config/config.yaml
"""
import argparse
import logging
import sys
import unicodedata
from datetime import datetime, UTC
from pathlib import Path
from typing import Dict, List

import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.utils.io_utils import load_parquet, save_parquet, save_json, load_yaml, latest_file
from src.utils.logging_utils import setup_logger


# ── Domain concept mapping (concept name fragments) ──────────────────────

DOMAIN_CONCEPT_FRAGMENTS = {
    "Political Science": [
        "political science", "politics", "democracy", "populism",
        "government", "voting", "electoral", "party", "parliament",
    ],
    "Economics": [
        "economics", "economy", "political economy", "macroeconomics",
        "inequality", "redistribution", "trade",
    ],
    "Sociology": [
        "sociology", "social science", "social movement", "identity",
        "media", "communication", "culture",
    ],
}

SUBCATEGORY_KEYWORD_MAP = {
    "comparative_politics": ["comparative", "cross-national"],
    "political_theory": ["theory", "theoretical", "conceptual", "normative", "definition"],
    "electoral_politics": ["election", "electoral", "voting", "vote", "ballot"],
    "democratic_theory": ["democracy", "democratic", "backsliding", "illiberal", "autocratization"],
    "radical_right": ["far-right", "radical right", "extreme right", "right-wing extremi"],
    "latin_american_politics": ["latin america", "brazil", "venezuela", "argentina", "mexico", "peru"],
    "european_politics": ["europe", "european union", "france", "germany", "italy", "spain"],
    "political_economy": ["political economy", "macroeconomic", "fiscal policy"],
    "redistribution": ["redistribution", "welfare", "social protection", "inequality"],
    "trade_globalization": ["globalization", "trade", "import", "export", "protectionism"],
    "financial_crisis": ["crisis", "recession", "austerity", "financial crash"],
    "social_movements": ["social movement", "mobilization", "protest", "civil society"],
    "identity_politics": ["identity", "ethnic", "nationalism", "religion", "nativism"],
    "media_communication": ["media", "communication", "framing", "social media", "twitter", "facebook"],
    "culture_values": ["culture", "values", "post-material", "cultural backlash", "resentment"],
}

DOMAIN_SUBCATEGORY = {
    "Political Science": [
        "comparative_politics", "political_theory", "electoral_politics",
        "democratic_theory", "radical_right", "latin_american_politics", "european_politics"
    ],
    "Economics": ["political_economy", "redistribution", "trade_globalization", "financial_crisis"],
    "Sociology": ["social_movements", "identity_politics", "media_communication", "culture_values"],
    "Other": ["international_relations", "history", "psychology", "geography", "interdisciplinary"],
}


def normalize_unicode(text: str) -> str:
    if not text:
        return ""
    return unicodedata.normalize("NFC", text).strip()


def rule_based_domain(concepts) -> tuple:
    """
    Assign domain using OpenAlex concept names.
    Returns (domain, confidence).
    """
    concepts = list(concepts) if concepts is not None else []
    if not concepts:
        return "Other", 0.0

    domain_scores: Dict[str, float] = {}
    for concept in concepts:
        name_lower = concept.get("name", "").lower()
        score = concept.get("score", 0.5)
        for domain, fragments in DOMAIN_CONCEPT_FRAGMENTS.items():
            for frag in fragments:
                if frag in name_lower:
                    domain_scores[domain] = domain_scores.get(domain, 0.0) + score

    if not domain_scores:
        return "Other", 0.0

    best_domain = max(domain_scores, key=domain_scores.__getitem__)
    total_score = sum(domain_scores.values())
    confidence = domain_scores[best_domain] / total_score if total_score > 0 else 0.0
    return best_domain, round(confidence, 4)


def rule_based_subcategory(title: str, abstract: str, domain: str) -> str:
    """
    Assign subcategory by keyword matching in title + abstract.
    Returns subcategory string.
    """
    text = (title + " " + abstract).lower()
    valid_subs = DOMAIN_SUBCATEGORY.get(domain, ["interdisciplinary"])

    for subcat in valid_subs:
        keywords = SUBCATEGORY_KEYWORD_MAP.get(subcat, [])
        for kw in keywords:
            if kw in text:
                return subcat

    return "interdisciplinary" if domain == "Other" else valid_subs[-1]


def clean_dataframe(df: pd.DataFrame, logger: logging.Logger, min_year: int = 1980) -> tuple[pd.DataFrame, dict]:
    """
    Apply all cleaning operations. Returns (cleaned_df, report_dict).
    """
    report = {"input_records": len(df), "operations": []}
    current_year = datetime.now(UTC).year

    # ── 1. Drop records with null ID or title ─────────────────────────
    n_before = len(df)
    df = df.dropna(subset=["id", "title"])
    df = df[df["title"].str.len() > 5]
    dropped = n_before - len(df)
    logger.info("Dropped %d records with null/short title or null ID", dropped)
    report["operations"].append({"op": "drop_null_title_or_id", "dropped": dropped})

    # ── 2. Drop records with missing or invalid year ──────────────────
    n_before = len(df)
    df = df.dropna(subset=["year"])
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df = df[df["year"].between(min_year, current_year + 1)]
    dropped = n_before - len(df)
    logger.info("Dropped %d records with invalid year", dropped)
    report["operations"].append({"op": "filter_year", "dropped": dropped, "range": f"{min_year}-present"})

    df["year"] = df["year"].astype(int)

    # ── 3. Final deduplication on OpenAlex ID ─────────────────────────
    n_before = len(df)
    df = df.sort_values("cited_by_count", ascending=False)
    df = df.drop_duplicates(subset=["id"], keep="first")
    dupes = n_before - len(df)
    logger.info("Removed %d duplicates (by OpenAlex ID)", dupes)
    report["operations"].append({"op": "dedup_id", "removed": dupes})

    # ── 4. Fill / normalize fields ────────────────────────────────────
    df["cited_by_count"] = df["cited_by_count"].fillna(0).astype(int)
    df["title"] = df["title"].apply(normalize_unicode)
    df["abstract"] = df["abstract"].fillna("").apply(normalize_unicode)
    df["journal"] = df["journal"].fillna("").apply(normalize_unicode)
    df["doi"] = df["doi"].fillna("")

    # Ensure list columns are actual Python lists (parquet may produce numpy arrays)
    for col in ["authors", "institutions", "concepts", "references", "mesh_terms", "keywords_matched"]:
        if col in df.columns:
            df[col] = df[col].apply(
                lambda x: list(x) if x is not None and not isinstance(x, list) else (x if isinstance(x, list) else [])
            )

    # ── 5. Derived fields ─────────────────────────────────────────────
    df["has_abstract"] = df["abstract"].str.len() > 20
    df["has_concepts"] = df["concepts"].apply(lambda x: len(list(x)) > 0 if x is not None else False)
    df["has_references"] = df["references"].apply(lambda x: len(list(x)) > 0 if x is not None else False)
    df["author_count"] = df["authors"].apply(lambda x: len(list(x)) if x is not None else 0)
    df["institution_count"] = df["institutions"].apply(
        lambda x: len({i.get("id", "") for i in list(x) if isinstance(i, dict) and i.get("id")}) if x is not None else 0
    )
    df["country_list"] = df["institutions"].apply(
        lambda x: list({i.get("country", "") for i in list(x) if isinstance(i, dict) and i.get("country")}) if x is not None else []
    )
    df["is_international"] = df["country_list"].apply(lambda x: len(x) > 1)
    df["top_concept"] = df["concepts"].apply(
        lambda x: list(x)[0]["name"] if x is not None and len(list(x)) > 0 and isinstance(list(x)[0], dict) else ""
    )
    df["top_concept_id"] = df["concepts"].apply(
        lambda x: list(x)[0]["id"] if x is not None and len(list(x)) > 0 and isinstance(list(x)[0], dict) else ""
    )
    df["decade"] = (df["year"] // 10 * 10).astype(int)

    # ── 6. Rule-based domain pre-labeling ─────────────────────────────
    logger.info("Applying rule-based domain classification...")
    domain_results = df["concepts"].apply(rule_based_domain)
    df["domain_preliminary"] = domain_results.apply(lambda x: x[0])
    df["domain_confidence_preliminary"] = domain_results.apply(lambda x: x[1])
    df["subcategory_preliminary"] = df.apply(
        lambda row: rule_based_subcategory(row["title"], row["abstract"], row["domain_preliminary"]),
        axis=1,
    )

    # ── 7. Outlier flags ──────────────────────────────────────────────
    p99 = df["cited_by_count"].quantile(0.99)
    df["citation_outlier"] = df["cited_by_count"] > p99
    df["high_author_count"] = df["author_count"] > 50

    # ── 8. Report ─────────────────────────────────────────────────────
    report["output_records"] = len(df)
    report["abstract_coverage"] = int(df["has_abstract"].sum())
    report["abstract_coverage_rate"] = round(df["has_abstract"].mean(), 4)
    report["concept_coverage"] = int(df["has_concepts"].sum())
    report["concept_coverage_rate"] = round(df["has_concepts"].mean(), 4)
    report["domain_distribution"] = df["domain_preliminary"].value_counts().to_dict()
    report["year_range"] = [int(df["year"].min()), int(df["year"].max())]
    report["timestamp"] = datetime.now(UTC).isoformat()

    logger.info(
        "Cleaning complete: %d records (from %d)", len(df), report["input_records"]
    )
    return df, report


def main():
    parser = argparse.ArgumentParser(description="Data Cleaning Agent")
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--input", default=None, help="Path to raw parquet (overrides auto-detect)")
    args = parser.parse_args()

    config = load_yaml(args.config)
    logger = setup_logger("data_cleaning", config["paths"]["logs"])
    logger.info("=== Data Cleaning Agent starting ===")

    # Auto-detect latest raw file
    raw_dir = config["paths"]["data_raw"]
    if args.input:
        raw_path = args.input
    else:
        detected = latest_file(raw_dir, "openalex_raw_*.parquet")
        if not detected:
            logger.error("No raw parquet found in %s", raw_dir)
            sys.exit(1)
        raw_path = str(detected)

    logger.info("Loading raw data from: %s", raw_path)
    df_raw = load_parquet(raw_path)
    logger.info("Loaded %d records", len(df_raw))

    min_year = config.get("pipeline", {}).get("min_year", 1980)
    df_clean, report = clean_dataframe(df_raw, logger, min_year=min_year)

    clean_dir = config["paths"]["data_clean"]
    Path(clean_dir).mkdir(parents=True, exist_ok=True)
    clean_path = f"{clean_dir}/openalex_clean.parquet"
    save_parquet(df_clean, clean_path)
    save_json(report, f"{clean_dir}/cleaning_report.json")

    logger.info("Saved clean data to: %s", clean_path)
    logger.info("=== Data Cleaning Agent complete ===")


if __name__ == "__main__":
    main()
