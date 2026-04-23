"""
Data Cleaning Agent
===================
Transforms raw OpenAlex data into a clean, analysis-ready dataset.
Handles deduplication, normalization, field derivation, and domain pre-labeling.

Outputs:
    data/clean/openalex_clean.parquet
    data/clean/cleaning_report.json

Standalone:
    python src/agents/data_cleaning.py --config config/config.yaml
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
import unicodedata
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.utils.io_utils import (
    latest_file,
    load_parquet,
    load_yaml,
    save_json,
    save_parquet,
)
from src.utils.logging_utils import setup_logger
from src.utils.taxonomy import (
    DOMAIN_CONCEPT_FRAGMENTS,
    DOMAIN_SUBCATEGORY,
)
from src.utils.taxonomy import (
    SUBCATEGORY_KEYWORDS as SUBCATEGORY_KEYWORD_MAP,
)

# Columns expected by downstream pipeline, with safe defaults
EXPECTED_COLUMNS: Dict[str, Any] = {
    "id": "",
    "title": "",
    "doi": "",
    "abstract": "",
    "journal": "",
    "year": None,
    "cited_by_count": 0,
    "is_open_access": False,
    "concepts": None,  # list
    "authors": None,  # list
    "institutions": None,  # list (flat, all institutions)
    "author_institutions": None,  # list of {author_id, institution_ids}
    "references": None,  # list
    "mesh_terms": None,  # list
    "keywords_matched": None,  # list
}

_DOI_REGEX = re.compile(r"(10\.\d{4,9}/[^\s]+)", re.IGNORECASE)


# ═══════════════════════════════════════════════════════════════════════════
# Normalisation Utilities
# ═══════════════════════════════════════════════════════════════════════════


def normalize_unicode(text: Optional[str]) -> str:
    """NFC-normalise and strip a string. Returns '' for None/non-string input."""
    if text is None or not isinstance(text, str):
        return ""
    return unicodedata.normalize("NFC", text).strip()


def normalize_doi(doi: Optional[str]) -> str:
    """
    Normalise a DOI string to its canonical form.

    Canonical DOIs start with '10.' followed by a registrant code and suffix.
    Accepts inputs like:
      - '10.1038/nature12345'
      - 'https://doi.org/10.1038/nature12345'
      - 'doi:10.1038/nature12345'
      - 'DOI: 10.1038/nature12345'

    Returns the canonical DOI (lowercased prefix is not applied — DOIs are
    case-insensitive but usually stored as given) or '' if no valid pattern
    is found.
    """
    if not doi or not isinstance(doi, str):
        return ""

    candidate = doi.strip()
    if not candidate:
        return ""

    # Reject URL-like DOI strings that lack an http(s) protocol.
    # e.g. 'doi.org/10.1000/...' is ambiguous and should not be silently
    # accepted — a real DOI reference uses either the bare '10.xxxx/...'
    # form or includes an explicit protocol.
    if re.match(r"^(dx\.)?doi\.org/", candidate, flags=re.IGNORECASE):
        return ""

    # Strip recognised valid prefixes (protocol required for URL forms)
    candidate = re.sub(r"^https?://(dx\.)?doi\.org/", "", candidate, flags=re.IGNORECASE)
    candidate = re.sub(r"^doi:\s*", "", candidate, flags=re.IGNORECASE)

    # Must match the canonical DOI pattern: 10.<registrant>/<suffix>
    match = _DOI_REGEX.search(candidate)
    if not match:
        return ""

    return match.group(1)


def normalize_author_name(name: Optional[str]) -> Optional[str]:
    """
    Normalise an author name to 'First Last' title case.

    Handles:
      - 'SMITH, JOHN'       → 'John Smith'
      - 'smith, john'       → 'John Smith'
      - 'Smith, J.'         → 'J. Smith'
      - 'John Smith'        → 'John Smith'  (already canonical)
      - ''                  → ''
      - None                → None

    Preserves existing formatting when name is already canonical.
    """
    if name is None:
        return None
    if not isinstance(name, str):
        return ""
    cleaned = name.strip()
    if not cleaned:
        return ""

    # 'Last, First' → 'First Last'
    if "," in cleaned:
        parts = [p.strip() for p in cleaned.split(",", 1)]
        if len(parts) == 2 and parts[1]:
            cleaned = f"{parts[1]} {parts[0]}"

    # Apply title case but preserve initials (e.g. 'J.')
    words = []
    for word in cleaned.split():
        if re.fullmatch(r"[A-Za-z]\.", word):
            words.append(word[0].upper() + ".")
        else:
            words.append(word.capitalize())
    return " ".join(words)


def calculate_title_similarity(title1: Optional[str], title2: Optional[str]) -> float:
    """
    Compute a similarity score in [0, 1] between two titles.

    Uses Jaccard similarity over token sets (lowercased, punctuation-stripped),
    which is robust for detecting near-duplicate titles with minor variations
    (e.g. subtitle additions). Returns 0.0 for empty/missing input.
    """
    if not title1 or not title2:
        return 0.0

    def tokenise(text: str) -> set:
        cleaned = re.sub(r"[^\w\s]", " ", text.lower())
        return {t for t in cleaned.split() if len(t) > 1}

    a = tokenise(title1)
    b = tokenise(title2)
    if not a or not b:
        return 0.0

    intersection = len(a & b)
    union = len(a | b)
    return round(intersection / union, 4) if union else 0.0


def calculate_completeness_score(df: pd.DataFrame) -> float:
    """
    Data completeness score as a percentage in [0, 100].

    Measures the fraction of non-null, non-empty values across the set of
    columns considered critical for bibliometric analysis.
    """
    critical_cols = ["id", "title", "abstract", "year", "cited_by_count"]
    present_cols = [c for c in critical_cols if c in df.columns]
    if not present_cols or len(df) == 0:
        return 0.0

    total_cells = len(df) * len(present_cols)
    filled_cells = 0
    for col in present_cols:
        series = df[col]
        if series.dtype == object:
            filled_cells += series.apply(lambda v: v is not None and str(v).strip() != "").sum()
        else:
            filled_cells += series.notna().sum()

    return round(100.0 * filled_cells / total_cells, 2) if total_cells else 0.0


# ═══════════════════════════════════════════════════════════════════════════
# Column Normalisation
# ═══════════════════════════════════════════════════════════════════════════


def _ensure_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Guarantee all expected columns exist with safe default values."""
    df = df.copy()
    for col, default in EXPECTED_COLUMNS.items():
        if col not in df.columns:
            if default is None:
                df[col] = [[] for _ in range(len(df))]
            else:
                df[col] = default
    return df


def _as_list(value: Any) -> list:
    """Safely coerce any value to a list."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, (tuple, set, np.ndarray)):
        return list(value)
    try:
        return list(value)
    except TypeError:
        return []


def _coerce_bool(value: Any) -> bool:
    """
    Value-aware boolean coercion.

    Unlike ``bool(value)``, this recognises common string spellings of
    falsy values — essential when upstream data carries strings like
    ``"False"`` or ``"None"`` that would otherwise be truthy.

    Examples
    --------
    >>> _coerce_bool(True)       -> True
    >>> _coerce_bool("False")    -> False
    >>> _coerce_bool("true")     -> True
    >>> _coerce_bool(None)       -> False
    >>> _coerce_bool("maybe")    -> False   (unknown strings → False, conservative)
    >>> _coerce_bool(1)          -> True
    >>> _coerce_bool(0)          -> False
    """
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value) and not pd.isna(value)
    if isinstance(value, str):
        s = value.strip().lower()
        if s in ("true", "t", "yes", "y", "1"):
            return True
        return False  # "false", "none", "nan", "", "maybe" → False
    return False


def _extract_concept_field(concepts: Any, field: str) -> str:
    """
    Safely extract a field from the first concept in a list.
    Returns '' when concepts is None/empty, or the field is missing.
    """
    concepts_list = _as_list(concepts)
    if not concepts_list:
        return ""
    first = concepts_list[0]
    if not isinstance(first, dict):
        return ""
    value = first.get(field)
    return str(value) if value is not None and value != "" else ""


# ═══════════════════════════════════════════════════════════════════════════
# Rule-Based Domain Pre-Labelling
# ═══════════════════════════════════════════════════════════════════════════


def rule_based_domain(concepts: Any) -> Tuple[str, float]:
    """
    Assign a preliminary domain using OpenAlex concept names.

    Returns:
        (domain, confidence) where confidence is in [0, 1].
    """
    concepts_list = _as_list(concepts)
    if not concepts_list:
        return "Other", 0.0

    domain_scores: Dict[str, float] = {}
    for concept in concepts_list:
        if not isinstance(concept, dict):
            continue
        name_lower = str(concept.get("name") or concept.get("display_name") or "").lower()
        score = float(concept.get("score", 0.5) or 0.0)
        for domain, fragments in DOMAIN_CONCEPT_FRAGMENTS.items():
            if any(frag in name_lower for frag in fragments):
                domain_scores[domain] = domain_scores.get(domain, 0.0) + score

    if not domain_scores:
        return "Other", 0.0

    best = max(domain_scores, key=domain_scores.__getitem__)
    total = sum(domain_scores.values())
    confidence = domain_scores[best] / total if total > 0 else 0.0
    return best, round(confidence, 4)


def rule_based_subcategory(title: str, abstract: str, domain: str) -> str:
    """Assign a subcategory by keyword matching in title + abstract."""
    text = f"{title or ''} {abstract or ''}".lower()
    valid_subs = DOMAIN_SUBCATEGORY.get(domain, ["interdisciplinary"])

    for subcat in valid_subs:
        for kw in SUBCATEGORY_KEYWORD_MAP.get(subcat, []):
            if kw in text:
                return subcat

    return "interdisciplinary" if domain == "Other" else valid_subs[-1]


# ═══════════════════════════════════════════════════════════════════════════
# Core Cleaning Pipeline
# ═══════════════════════════════════════════════════════════════════════════


def clean_dataframe(
    df: pd.DataFrame,
    logger: logging.Logger,
    min_year: int = 1980,
) -> Tuple[pd.DataFrame, dict]:
    """
    Apply the full cleaning pipeline.

    Returns:
        (cleaned_df, report_dict)
    """
    report: Dict[str, Any] = {"input_records": len(df), "operations": []}
    current_year = datetime.now(timezone.utc).year

    # ── 0. Ensure expected schema ────────────────────────────────────────
    df = _ensure_columns(df)

    # ── 1. Drop records with null ID or title ────────────────────────────
    n_before = len(df)
    df = df.dropna(subset=["id", "title"])
    df = df[df["title"].astype(str).str.len() > 5]
    dropped = n_before - len(df)
    logger.info("Dropped %d records with null/short title or null ID", dropped)
    report["operations"].append({"op": "drop_null_title_or_id", "dropped": int(dropped)})

    # ── 2. Drop records with missing or invalid year ─────────────────────
    n_before = len(df)
    df = df.dropna(subset=["year"])
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df = df[df["year"].between(min_year, current_year)]
    df = df.dropna(subset=["year"])
    dropped = n_before - len(df)
    logger.info("Dropped %d records with invalid year", dropped)
    report["operations"].append(
        {"op": "filter_year", "dropped": int(dropped), "range": f"{min_year}-{current_year}"}
    )
    df["year"] = df["year"].astype(int)

    # ── 3. Deduplicate on OpenAlex ID (keep most-cited copy) ─────────────
    df["cited_by_count"] = (
        pd.to_numeric(df["cited_by_count"], errors="coerce").fillna(0).astype(int)
    )
    n_before = len(df)
    df = df.sort_values("cited_by_count", ascending=False).drop_duplicates(
        subset=["id"], keep="first"
    )
    dupes = n_before - len(df)
    logger.info("Removed %d duplicates (by OpenAlex ID)", dupes)
    report["operations"].append({"op": "dedup_id", "removed": int(dupes)})

    # ── 4. Normalise text fields ─────────────────────────────────────────
    df["title"] = df["title"].apply(normalize_unicode)
    df["abstract"] = df["abstract"].fillna("").apply(normalize_unicode)
    df["journal"] = df["journal"].fillna("").apply(normalize_unicode)
    df["doi"] = df["doi"].fillna("").apply(normalize_doi)

    # ── 4b. Coerce boolean field ─────────────────────────────────────────
    # ``is_open_access`` may arrive as real bools, strings ("True"/"False"),
    # or missing values. A plain ``.astype(bool)`` would incorrectly coerce
    # the string "False" to True (any non-empty string is truthy), so we
    # use a value-aware parser instead.
    df["is_open_access"] = df["is_open_access"].apply(_coerce_bool).astype(bool)

    # ── 5. Coerce list columns to real lists ─────────────────────────────
    for col in (
        "authors",
        "institutions",
        "concepts",
        "references",
        "mesh_terms",
        "keywords_matched",
    ):
        df[col] = df[col].apply(_as_list)

    # ── 6. Derived fields ────────────────────────────────────────────────
    df["has_abstract"] = df["abstract"].str.len() > 20
    df["has_concepts"] = df["concepts"].apply(bool)
    df["has_references"] = df["references"].apply(bool)
    df["author_count"] = df["authors"].apply(len)

    # Expose `institution` (singular) as an alias to `institutions` for tests
    # and downstream code that uses either spelling. Both point to the same
    # underlying list data — no duplication of storage.
    df["institution"] = df["institutions"].copy()

    df["institution_count"] = df["institutions"].apply(
        lambda insts: len({i.get("id", "") for i in insts if isinstance(i, dict) and i.get("id")})
    )
    df["country_list"] = df["institutions"].apply(
        lambda insts: sorted(
            {i.get("country", "") for i in insts if isinstance(i, dict) and i.get("country")}
        )
    )
    df["is_international"] = df["country_list"].apply(lambda xs: len(xs) > 1)

    df["top_concept"] = df["concepts"].apply(
        lambda c: _extract_concept_field(c, "display_name") or _extract_concept_field(c, "name")
    )
    df["top_concept_id"] = df["concepts"].apply(lambda c: _extract_concept_field(c, "id"))
    df["decade"] = (df["year"] // 10 * 10).astype(int)

    # ── 7. Rule-based domain pre-labelling ───────────────────────────────
    logger.info("Applying rule-based domain classification...")
    domain_results = df["concepts"].apply(rule_based_domain)
    df["domain_preliminary"] = domain_results.apply(lambda r: r[0])
    df["domain_confidence_preliminary"] = domain_results.apply(lambda r: r[1])
    df["subcategory_preliminary"] = df.apply(
        lambda row: rule_based_subcategory(
            row["title"], row["abstract"], row["domain_preliminary"]
        ),
        axis=1,
    )

    # ── 8. Outlier flags ─────────────────────────────────────────────────
    if len(df) > 0:
        p99 = df["cited_by_count"].quantile(0.99)
        df["citation_outlier"] = df["cited_by_count"] > p99
    else:
        df["citation_outlier"] = False
    df["high_author_count"] = df["author_count"] > 50

    # ── 9. Finalise report ───────────────────────────────────────────────
    report.update(
        {
            "output_records": len(df),
            "abstract_coverage": int(df["has_abstract"].sum()) if len(df) else 0,
            "abstract_coverage_rate": (
                round(float(df["has_abstract"].mean()), 4) if len(df) else 0.0
            ),
            "concept_coverage": int(df["has_concepts"].sum()) if len(df) else 0,
            "concept_coverage_rate": round(float(df["has_concepts"].mean()), 4) if len(df) else 0.0,
            "domain_distribution": (
                df["domain_preliminary"].value_counts().to_dict() if len(df) else {}
            ),
            "year_range": (
                [int(df["year"].min()), int(df["year"].max())] if len(df) else [None, None]
            ),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )

    logger.info("Cleaning complete: %d records (from %d)", len(df), report["input_records"])
    return df, report


# ═══════════════════════════════════════════════════════════════════════════
# Public API (used by orchestrator, tests, and other agents)
# ═══════════════════════════════════════════════════════════════════════════


def clean_bibliometric_data(
    df: pd.DataFrame,
    logger: Optional[logging.Logger] = None,
    min_year: int = 1980,
    preserve_invalid_rows: bool = True,
) -> pd.DataFrame:
    """
    Convenience wrapper returning only the cleaned DataFrame.

    Args:
        preserve_invalid_rows: When True (default), apply schema normalisation
            and type coercion but do NOT drop rows with null/short titles or
            invalid years. When False, use the strict pipeline that drops
            invalid rows (suitable for production collection runs).

    Use ``clean_dataframe`` directly when the cleaning report is needed.
    """
    log = logger or logging.getLogger("data_cleaning")

    if not preserve_invalid_rows:
        cleaned, _ = clean_dataframe(df, log, min_year=min_year)
        return cleaned

    # ── Lenient mode: normalise in place, preserve all rows ──────────────
    df = _ensure_columns(df).copy()

    # Numeric coercion — never drops rows, just turns bad values into NaN/0
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    df["cited_by_count"] = pd.to_numeric(df["cited_by_count"], errors="coerce").astype("Int64")

    # Text normalisation (no row drops)
    df["title"] = df["title"].fillna("").apply(normalize_unicode)
    df["abstract"] = df["abstract"].fillna("").apply(normalize_unicode)
    df["journal"] = df["journal"].fillna("").apply(normalize_unicode)
    df["doi"] = df["doi"].fillna("").apply(normalize_doi)

    # Value-aware boolean coercion
    df["is_open_access"] = df["is_open_access"].apply(_coerce_bool).astype(bool)

    # List-column coercion
    for col in (
        "authors",
        "institutions",
        "concepts",
        "references",
        "mesh_terms",
        "keywords_matched",
    ):
        df[col] = df[col].apply(_as_list)

    # Alias for test compatibility
    df["institution"] = df["institutions"].copy()

    # Derived fields (safe for missing values)
    df["has_abstract"] = df["abstract"].str.len() > 20
    df["has_concepts"] = df["concepts"].apply(bool)
    df["author_count"] = df["authors"].apply(len)
    df["top_concept"] = df["concepts"].apply(
        lambda c: _extract_concept_field(c, "display_name") or _extract_concept_field(c, "name")
    )
    df["top_concept_id"] = df["concepts"].apply(lambda c: _extract_concept_field(c, "id"))

    # decade can stay blank if year is NaN
    df["decade"] = df["year"].apply(lambda y: int(y // 10 * 10) if pd.notna(y) else None)

    # Outlier flags — safe on empty / small frames
    if len(df) > 0:
        p99 = df["cited_by_count"].quantile(0.99)
        df["citation_outlier"] = df["cited_by_count"] > p99
    else:
        df["citation_outlier"] = False
    df["high_author_count"] = df["author_count"] > 50

    log.info("Lenient cleaning complete: %d records preserved", len(df))
    return df


def validate_cleaned_data(df: pd.DataFrame) -> Tuple[bool, List[str]]:
    """
    Validate a cleaned DataFrame against the pipeline's schema contract.

    Returns:
        (is_valid, errors) where errors is a list of human-readable messages.
        On success, returns (True, []).
    """
    errors: List[str] = []
    required_cols = ["id", "title", "year", "cited_by_count"]

    for col in required_cols:
        if col not in df.columns:
            errors.append(f"Missing required column: {col}")

    if "id" in df.columns and df["id"].duplicated().any():
        errors.append("Duplicate IDs found")

    if "year" in df.columns:
        try:
            years = pd.to_numeric(df["year"], errors="coerce")
            if (years < 1900).any() or (years > 2030).any():
                errors.append("Out-of-range years detected")
        except Exception as exc:
            errors.append(f"Year validation failed: {exc}")

    return (not errors), errors


def detect_exact_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """
    Flag exact duplicate records by (title, year).

    Returns:
        A DataFrame with an additional `is_duplicate` column marking every
        row that shares (title, year) with another row. Original row order
        is preserved.
    """
    result = df.copy()
    if "title" not in result.columns:
        result["is_duplicate"] = False
        return result

    subset = ["title"] + (["year"] if "year" in result.columns else [])
    result["is_duplicate"] = result.duplicated(subset=subset, keep=False)
    return result


_NEAR_DUP_MAX_ROWS = 5_000


def detect_near_duplicates(
    df,
    threshold: float = 0.85,
) -> pd.DataFrame:
    """
    Flag near-duplicates using title similarity.

    Accepts either a ``pd.DataFrame`` or a ``list[dict]``. Uses
    ``SequenceMatcher`` for character-level similarity (more forgiving than
    the Jaccard token score). Runs in O(n²) — capped at _NEAR_DUP_MAX_ROWS
    rows; larger corpora are sampled to the first _NEAR_DUP_MAX_ROWS records
    and the rest receive near_duplicate_of=None.
    """
    import logging as _logging

    _nd_logger = _logging.getLogger(__name__)

    # ── Coerce list-of-dicts input to DataFrame ─────────────────────────
    if isinstance(df, list):
        df = pd.DataFrame(df)

    result = df.copy()
    result["near_duplicate_of"] = None

    if "title" not in result.columns or len(result) < 2:
        return result

    if len(result) > _NEAR_DUP_MAX_ROWS:
        _nd_logger.warning(
            "detect_near_duplicates: corpus has %d rows — O(n²) check capped at first %d rows. "
            "Remaining rows receive near_duplicate_of=None.",
            len(result),
            _NEAR_DUP_MAX_ROWS,
        )
        check_df = result.iloc[:_NEAR_DUP_MAX_ROWS]
    else:
        check_df = result

    titles = check_df["title"].fillna("").astype(str).tolist()
    ids = check_df["id"].tolist() if "id" in check_df.columns else list(range(len(check_df)))

    check_index = check_df.index.tolist()
    for i in range(len(titles)):
        for j in range(i + 1, len(titles)):
            if not titles[i] or not titles[j]:
                continue
            sim = SequenceMatcher(None, titles[i].lower(), titles[j].lower()).ratio()
            if sim >= threshold:
                result.at[check_index[j], "near_duplicate_of"] = ids[i]

    return result


def generate_quality_report(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Produce a structured data-quality report with the four ISO-inspired
    dimensions required by the test contract:
        - completeness  (missingness)
        - consistency   (type coherence)
        - validity      (schema + range checks)
        - uniqueness    (duplicate analysis)
    """
    is_valid, validation_errors = validate_cleaned_data(df)

    completeness_score = calculate_completeness_score(df)
    duplicate_rate = 0.0
    if "id" in df.columns and len(df) > 0:
        duplicate_rate = round(float(df["id"].duplicated().sum() / len(df)), 4)

    type_ok = True
    if "year" in df.columns:
        type_ok = pd.api.types.is_numeric_dtype(df["year"])
    if "cited_by_count" in df.columns and type_ok:
        type_ok = pd.api.types.is_numeric_dtype(df["cited_by_count"])

    return {
        "completeness": {
            "overall_score": completeness_score,
            "total_records": len(df),
        },
        "consistency": {
            "type_coherence": type_ok,
        },
        "validity": {
            "is_valid": is_valid,
            "validation_errors": validation_errors,
        },
        "uniqueness": {
            "duplicate_rate": duplicate_rate,
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ═══════════════════════════════════════════════════════════════════════════
# CLI Entry Point
# ═══════════════════════════════════════════════════════════════════════════


def main() -> None:
    parser = argparse.ArgumentParser(description="Data Cleaning Agent")
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--input", default=None, help="Path to raw parquet (overrides auto-detect)")
    args = parser.parse_args()

    config = load_yaml(args.config)
    logger = setup_logger("data_cleaning", config["paths"]["logs"])
    logger.info("=== Data Cleaning Agent starting ===")

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
