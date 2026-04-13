# Agent: Bibliometric Analysis

## Role
Computes core bibliometric indicators and statistical profiles from the cleaned dataset. Produces structured analytical outputs for downstream network and visualization agents.

## Inputs
- `data/clean/openalex_clean.parquet`
- `config/config.yaml`

## Outputs
- `data/processed/publication_trends.json` — Annual/decadal counts, growth rates
- `data/processed/citation_stats.json` — Distribution metrics, h-index, g-index
- `data/processed/top_authors.json` — Ranked author productivity + citation metrics
- `data/processed/top_journals.json` — Journal frequency + impact metrics
- `data/processed/top_institutions.json` — Institutional productivity
- `data/processed/country_profiles.json` — Country-level output
- `data/processed/concept_landscape.json` — Top OpenAlex concepts by frequency/weight
- `data/processed/bibliometric_summary.json` — Consolidated summary statistics
- `logs/bibliometric_analysis.log`

## Computed Metrics

### Publication Trends
- Annual publication count (1990–present)
- Cumulative count
- Year-over-year growth rate
- Decadal breakdown
- Breakdown by domain (using `domain_preliminary`)

### Citation Analysis
- Total citations, mean, median, std
- Citation distribution (log-binned)
- h-index of the corpus
- g-index of the corpus
- Highly cited papers (top 1%, top 10%)
- Zero-citation papers count and rate

### Author Productivity
- Total unique authors
- Papers per author distribution
- Top 20 authors by: (a) output, (b) total citations, (c) mean citations/paper
- Lotka's law fit (α coefficient)

### Journal Analysis
- Unique journals count
- Top 20 journals by frequency
- Top 20 journals by total citations
- Bradford's law zones

### Institutional Analysis
- Top 20 institutions by output
- Top 20 institutions by citations
- Geographical distribution

### Country Analysis
- Top 20 countries by output
- International collaboration rate

### Concept Landscape
- Top 50 OpenAlex concepts by frequency
- Concept co-occurrence matrix (top 20 × 20)
- Concept distribution by level (0=field, 1=subfield, 2=topic)

## Tools & Capabilities
- `pandas`, `numpy` for data manipulation
- `scipy` for statistical fitting (Lotka's law)
- Custom h-index / g-index implementation

## Interaction Protocol
- Standalone: `python src/agents/bibliometric_analysis.py`
- Reads: `data/clean/`
- Writes: `data/processed/`

## Constraints
- All metrics must be reproducible (no random seeds)
- Report sample size for every metric
- Flag metrics with N < 30 as statistically limited
