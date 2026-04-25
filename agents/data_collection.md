# Agent: Data Collection

## Role
Retrieves bibliographic records from OpenAlex API using keyword-based queries on "populism", "populist", "populists". Ensures deduplication and metadata completeness.

## Inputs
- `config/openalex.yaml` — Query parameters (keywords, date range, filters, page size, max_results)
- `config/config.yaml` — Global paths configuration

## Outputs
- `data/raw/openalex_raw_{timestamp}.parquet` — Raw records (all fields from API)
- `data/raw/collection_manifest.json` — Query log (parameters used, total records, timestamp, API version)
- `logs/data_collection.log`

## Schema (Output Parquet)
```
id            : str   # OpenAlex work ID (W...)
doi           : str   # DOI if available
title         : str
abstract      : str   # Reconstructed from inverted index
year          : int
publication_date : str
cited_by_count: int
authors       : list[dict]  # {id, name, orcid, institutions}
institutions  : list[dict]  # {id, name, country, type}
concepts      : list[dict]  # {id, name, level, score}
journal       : str   # Source display name
journal_id    : str   # OpenAlex source ID
open_access   : bool
type          : str   # article, book-chapter, etc.
references    : list[str]  # OpenAlex IDs of cited works
mesh_terms    : list[str]
keywords_matched: list[str]  # Which query terms matched
query_batch   : str   # Which query retrieved this record
```

## Query Strategy
Fully config-driven — driven by `config/openalex.yaml` `queries.keywords` list.
Each entry in the list is one API query; results are merged and deduplicated on OpenAlex work ID.

Recommended configuration (single boolean query):
```yaml
queries:
  keywords:
    - term: "populism OR populist OR populists OR far-right"
      field: "title_and_abstract.search"
  filters:
    type: "article OR book-chapter OR dissertation OR preprint"
    from_publication_date: "1980-01-01"
  sort:
    field: cited_by_count
    order: desc
```

Multiple separate terms are also supported (one list entry each); results are merged and
deduplicated automatically. A single boolean query is more efficient for most use cases.

## Tools & Capabilities
- Direct HTTP requests to `https://api.openalex.org` via `requests`
- Pagination handling (cursor-based, 200 records/page by default)
- Rate limiting: respects polite pool (10 req/s) via email in User-Agent header
- Abstract reconstruction from OpenAlex inverted index
- Retry logic: configurable attempts with exponential backoff

## Interaction Protocol
- Standalone execution: `python src/agents/data_collection.py --config config/config.yaml`
- Outputs to: `data/raw/`
- Signals completion via: checkpoint update + manifest file
- No upstream dependencies

## Reproducibility
- All query parameters stored in manifest
- Timestamp-versioned output files
- Deterministic deduplication (sort by ID before dedup)

## Constraints
- Max records per run: configurable (`test_max_records` default 200, `full_max_records` default null = unlimited)
- Must not skip deduplication even in test mode
- Must reconstruct abstracts (required for classification)
