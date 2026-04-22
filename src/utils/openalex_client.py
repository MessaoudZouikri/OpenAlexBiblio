"""
OpenAlex API client.
Handles cursor-based pagination, rate limiting, abstract reconstruction,
and deduplication for the bibliometric pipeline.
"""

import logging
import time
from typing import Dict, Generator, Optional, Union

import requests

logger = logging.getLogger("openalex_client")


class OpenAlexClient:
    """
    Stateless HTTP client for the OpenAlex REST API.

    Respects rate limits, implements retry logic with exponential backoff,
    and reconstructs abstracts from the inverted index format.
    """

    BASE_URL = "https://api.openalex.org"

    def __init__(
        self,
        email: str = "",
        per_page: int = 200,
        rate_limit_delay: float = 0.15,
        max_retries: int = 3,
        retry_backoff: float = 2.0,
        timeout: int = 30,
    ):
        self.email = email
        self.per_page = min(per_page, 200)  # API cap
        self.rate_limit_delay = rate_limit_delay
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        self.timeout = timeout
        self.session = requests.Session()
        if email:
            self.session.headers.update(
                {"User-Agent": f"bibliometric-pipeline/0.1 (mailto:{email})"}
            )

    # ── Core HTTP ──────────────────────────────────────────────────────────

    def _get(self, url: str, params: Dict) -> Dict:
        """GET with retry + rate limiting."""
        delay = self.rate_limit_delay
        for attempt in range(1, self.max_retries + 1):
            try:
                if attempt > 1:
                    time.sleep(delay)
                resp = self.session.get(url, params=params, timeout=self.timeout)
                if resp.status_code == 429:
                    wait = int(resp.headers.get("Retry-After", 60))
                    logger.warning("Rate limited. Waiting %ds", wait)
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                return resp.json()
            except requests.RequestException as exc:
                logger.warning("Attempt %d/%d failed: %s", attempt, self.max_retries, exc)
                if attempt == self.max_retries:
                    raise
                delay *= self.retry_backoff
        return {}

    # ── Pagination ─────────────────────────────────────────────────────────

    def paginate_works(
        self,
        search_term: str,
        search_field: str = "title_and_abstract.search",
        filters: Optional[Dict[str, str]] = None,
        sort: str = "cited_by_count:desc",
        max_records: Union[int, float] = 500,
    ) -> Generator[Dict, None, None]:
        """
        Cursor-paginated generator of work records.
        Yields individual raw work dicts from the API.
        """
        params = {
            "filter": self._build_filter(search_term, search_field, filters),
            "sort": sort,
            "per-page": self.per_page,
            "select": ",".join(WORK_SELECT_FIELDS),
            "cursor": "*",
        }
        if self.email:
            params["mailto"] = self.email

        fetched = 0
        while fetched < max_records:
            data = self._get(f"{self.BASE_URL}/works", params)
            results = data.get("results", [])
            if not results:
                break
            for work in results:
                if fetched >= max_records:
                    return
                yield work
                fetched += 1
            cursor = data.get("meta", {}).get("next_cursor")
            if not cursor:
                break
            params["cursor"] = cursor
            logger.debug(
                "Fetched %d records so far (cursor=%s)", fetched, cursor[:20] if cursor else "none"
            )

    def _build_filter(
        self,
        term: str,
        field: str,
        extra: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        Build OpenAlex filter string with support for boolean operators.

        Examples:
        - "populism OR populist" in search field
        - "article OR book-chapter" in type field
        """
        parts = [f"{field}:{term}"]
        if extra:
            for k, v in extra.items():
                if v:
                    # Handle boolean operators in filter values
                    if " OR " in str(v):
                        # Convert "article OR book-chapter" to "article|book-chapter"
                        v = v.replace(" OR ", "|")
                    elif " AND " in str(v):
                        # Convert "article AND book-chapter" to "article,book-chapter"
                        v = v.replace(" AND ", ",")
                    parts.append(f"{k}:{v}")
        return ",".join(parts)

    # ── Record Normalization ───────────────────────────────────────────────

    @staticmethod
    def reconstruct_abstract(inverted_index: Optional[Dict]) -> str:
        """
        Reconstruct abstract text from OpenAlex inverted index format.
        Format: {"word": [position1, position2, ...], ...}
        """
        if not inverted_index:
            return ""
        positions = []
        for word, pos_list in inverted_index.items():
            for pos in pos_list:
                positions.append((pos, word))
        positions.sort(key=lambda x: x[0])
        return " ".join(w for _, w in positions)

    @staticmethod
    def normalize_work(raw: Dict, query_term: str, query_batch: str) -> Dict:
        """
        Flatten and normalize a raw OpenAlex work record into pipeline schema.
        """
        authors = []
        for authorship in raw.get("authorships", []):
            author = authorship.get("author", {}) or {}
            insts = [
                {
                    "id": i.get("id", ""),
                    "name": i.get("display_name", ""),
                    "country": i.get("country_code", ""),
                    "type": i.get("type", ""),
                }
                for i in authorship.get("institutions", [])
            ]
            authors.append(
                {
                    "id": author.get("id", ""),
                    "name": author.get("display_name", ""),
                    "orcid": author.get("orcid", ""),
                    "institutions": insts,
                }
            )

        concepts = [
            {
                "id": c.get("id", ""),
                "name": c.get("display_name", ""),
                "level": c.get("level", -1),
                "score": c.get("score", 0.0),
            }
            for c in raw.get("concepts", [])
        ]

        source = raw.get("primary_location", {}) or {}
        source_info = source.get("source") or {}

        oa = raw.get("open_access", {}) or {}

        return {
            "id": raw.get("id", ""),
            "doi": raw.get("doi", ""),
            "title": raw.get("title", "") or "",
            "abstract": OpenAlexClient.reconstruct_abstract(raw.get("abstract_inverted_index")),
            "year": raw.get("publication_year"),
            "publication_date": raw.get("publication_date", ""),
            "cited_by_count": raw.get("cited_by_count", 0) or 0,
            "authors": authors,
            # Flat list for quick filtering; author_institutions preserves the mapping.
            "institutions": [inst for a in authors for inst in a["institutions"]],
            "author_institutions": [
                {"author_id": a["id"], "institution_ids": [i["id"] for i in a["institutions"]]}
                for a in authors
            ],
            "concepts": concepts,
            "journal": source_info.get("display_name", ""),
            "journal_id": source_info.get("id", ""),
            "open_access": oa.get("is_oa", False),
            "type": raw.get("type", ""),
            "references": raw.get("referenced_works", []) or [],
            "mesh_terms": [m.get("descriptor_name", "") for m in raw.get("mesh", [])],
            "keywords_matched": [query_term],
            "query_batch": query_batch,
        }


# Fields to request from OpenAlex API (reduces payload size)
WORK_SELECT_FIELDS = [
    "id",
    "doi",
    "title",
    "abstract_inverted_index",
    "publication_year",
    "publication_date",
    "cited_by_count",
    "authorships",
    "concepts",
    "primary_location",
    "open_access",
    "type",
    "referenced_works",
    "mesh",
]
