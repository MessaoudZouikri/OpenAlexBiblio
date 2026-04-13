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
1. Query 1: title_and_abstract.search = "populism"
2. Query 2: title_and_abstract.search = "populist"  
3. Query 3: title_and_abstract.search = "populists"
4. Merge results → deduplicate on OpenAlex work ID
5. Filter: type = article (configurable)
6. Sort: cited_by_count:desc (configurable)

## Tools & Capabilities
- `pyalex` library OR direct HTTP requests to `https://api.openalex.org`
- Pagination handling (cursor-based, 200 records/page)
- Rate limiting: respect 10 req/s polite limit (User-Agent + email header)
- Abstract reconstruction from OpenAlex inverted index
- Retry logic: 3 attempts with exponential backoff

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
- Max records per run: configurable (default: 500 for test, 50000 for full)
- Must not skip deduplication even in test mode
- Must reconstruct abstracts (required for classification)
