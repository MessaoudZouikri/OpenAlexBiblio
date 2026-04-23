# Agent: Data Validation

## Role
Verifies the integrity and completeness of collected and cleaned data. First line of defense against data quality issues.

## Invocations
- D1: After data collection (validates raw data)
- D2: After data cleaning (validates clean data)

## Inputs
- D1: `data/raw/openalex_raw_*.parquet` + `data/raw/collection_manifest.json`
- D2: `data/clean/openalex_clean.parquet` + `data/clean/cleaning_report.json`

## Outputs
- `logs/validation_data_{D1|D2}.json` — Structured validation report
- Pipeline signal: `PASS` or `FAIL` (written to checkpoint)

## Validation Rules

### Schema Checks
- [ ] All required columns present
- [ ] Column types match schema definition
- [ ] No extra unrecognized columns (warn only)

### Content Checks
- [ ] id: no nulls, all match pattern `W\d+`
- [ ] year: range [1900, current_year], no nulls
- [ ] title: no nulls, length > 5 chars
- [ ] cited_by_count: >= 0, no nulls
- [ ] Deduplication: id column is unique

### Statistical Checks
- [ ] Record count matches manifest claim (±1 for edge cases)
- [ ] Year distribution: no suspicious spikes (> 3× mean in single year)
- [ ] cited_by_count: no negative values

### Completeness Metrics (warnings, not failures)
- abstract coverage rate (flag if < 50%)
- concept coverage rate (flag if < 60%)
- institution coverage rate

## PASS/FAIL Logic
- FAIL on: any Schema or critical Content check failure
- WARN on: Statistical anomalies and completeness metrics
- Pipeline halts on FAIL
