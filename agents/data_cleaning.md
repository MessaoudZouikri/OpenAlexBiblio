# Agent: Data Cleaning

## Role
Transforms raw OpenAlex data into a clean, analysis-ready dataset. Handles missing values, normalizes fields, filters noise, and ensures schema compliance.

## Inputs
- `data/raw/openalex_raw_{timestamp}.parquet` — Raw records
- `data/raw/collection_manifest.json` — Collection metadata
- `config/config.yaml` — Cleaning parameters

## Outputs
- `data/clean/openalex_clean.parquet` — Cleaned dataset
- `data/clean/cleaning_report.json` — Statistics on transformations applied
- `logs/data_cleaning.log`

## Cleaning Operations

### 1. Deduplication (re-verification)
- Final dedup on (doi, title_normalized) composite key
- Keep record with highest cited_by_count on conflict

### 2. Missing Data Handling
- title: drop if missing
- year: drop if missing or < 1990
- abstract: flag as `has_abstract = False`, do NOT drop (used for filtering in classification)
- cited_by_count: fill 0 if missing
- authors: fill empty list if missing
- institutions: fill empty list if missing
- concepts: flag `has_concepts = False` if empty

### 3. Text Normalization
- title: strip whitespace, normalize unicode
- abstract: strip HTML artifacts, normalize unicode
- author names: normalize diacritics
- journal names: strip trailing punctuation, normalize case

### 4. Field Derivation
- `author_count`: len(authors)
- `institution_count`: len(set of unique institutions)
- `country_list`: extracted from institutions
- `is_international`: True if len(country_list) > 1
- `top_concept`: concepts[0].name (highest score)
- `top_concept_id`: concepts[0].id
- `decade`: floor(year / 10) * 10
- `has_references`: len(references) > 0

### 5. Domain Pre-labeling (rule-based, preliminary)
Based on OpenAlex concept IDs:
- Political Science: concept contains "Political science", "Politics", "Democracy"
- Economics: concept contains "Economics", "Political economy"  
- Sociology: concept contains "Sociology", "Social science"
- Other: remainder

### 6. Outlier Flagging
- `citation_outlier`: cited_by_count > 99th percentile
- `high_author_count`: author_count > 50

## Output Schema (Additional Cleaned Fields)
All raw fields + derived fields listed above.

## Interaction Protocol
- Standalone: `python src/agents/data_cleaning.py --input data/raw/openalex_raw_*.parquet`
- Reads: `data/raw/`
- Writes: `data/clean/`

## Constraints
- Must preserve all original IDs (OpenAlex ID, DOI)
- Must NOT impute or invent data values
- Must produce deterministic output (no random operations without seed)
