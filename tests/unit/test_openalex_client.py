"""
Unit tests for src/utils/openalex_client.py

Covers: reconstruct_abstract, normalize_work, _build_filter, paginate_works.
All HTTP calls are mocked via unittest.mock.
"""

from unittest.mock import MagicMock, Mock, patch

import pytest
import requests

from src.utils.openalex_client import OpenAlexClient


# ── reconstruct_abstract ──────────────────────────────────────────────────────


class TestReconstructAbstract:
    @pytest.mark.unit
    def test_basic_reconstruction(self):
        index = {"Hello": [0], "world": [1]}
        result = OpenAlexClient.reconstruct_abstract(index)
        assert result == "Hello world"

    @pytest.mark.unit
    def test_out_of_order_positions(self):
        index = {"second": [1], "first": [0], "third": [2]}
        result = OpenAlexClient.reconstruct_abstract(index)
        assert result == "first second third"

    @pytest.mark.unit
    def test_word_at_multiple_positions(self):
        index = {"the": [0, 3], "cat": [1], "sat": [2]}
        result = OpenAlexClient.reconstruct_abstract(index)
        assert result == "the cat sat the"

    @pytest.mark.unit
    def test_empty_dict_returns_empty_string(self):
        assert OpenAlexClient.reconstruct_abstract({}) == ""

    @pytest.mark.unit
    def test_none_returns_empty_string(self):
        assert OpenAlexClient.reconstruct_abstract(None) == ""

    @pytest.mark.unit
    def test_single_word(self):
        assert OpenAlexClient.reconstruct_abstract({"hello": [0]}) == "hello"


# ── normalize_work ────────────────────────────────────────────────────────────


class TestNormalizeWork:
    def _base_raw(self):
        return {
            "id": "W123",
            "doi": "10.1234/test",
            "title": "Test Paper on Populism",
            "abstract_inverted_index": {"A": [0], "test": [1]},
            "publication_year": 2021,
            "publication_date": "2021-06-15",
            "cited_by_count": 42,
            "authorships": [
                {
                    "author": {
                        "id": "A001",
                        "display_name": "Jane Doe",
                        "orcid": "0000-0001-2345-6789",
                    },
                    "institutions": [
                        {
                            "id": "I001",
                            "display_name": "MIT",
                            "country_code": "US",
                            "type": "education",
                        }
                    ],
                }
            ],
            "concepts": [{"id": "C001", "display_name": "Populism", "level": 1, "score": 0.9}],
            "primary_location": {"source": {"display_name": "Nature", "id": "S001"}},
            "open_access": {"is_oa": True},
            "type": "article",
            "referenced_works": ["W999"],
            "mesh": [{"descriptor_name": "Politics"}],
        }

    @pytest.mark.unit
    def test_basic_fields_extracted(self):
        result = OpenAlexClient.normalize_work(self._base_raw(), "populism", "batch1")
        assert result["id"] == "W123"
        assert result["doi"] == "10.1234/test"
        assert result["title"] == "Test Paper on Populism"
        assert result["year"] == 2021
        assert result["cited_by_count"] == 42
        assert result["is_open_access"] is True
        assert result["type"] == "article"

    @pytest.mark.unit
    def test_abstract_reconstructed(self):
        result = OpenAlexClient.normalize_work(self._base_raw(), "populism", "batch1")
        assert result["abstract"] == "A test"

    @pytest.mark.unit
    def test_authors_extracted(self):
        result = OpenAlexClient.normalize_work(self._base_raw(), "populism", "batch1")
        assert len(result["authors"]) == 1
        author = result["authors"][0]
        assert author["name"] == "Jane Doe"
        assert author["orcid"] == "0000-0001-2345-6789"
        assert len(author["institutions"]) == 1
        assert author["institutions"][0]["name"] == "MIT"
        assert author["institutions"][0]["country"] == "US"

    @pytest.mark.unit
    def test_concepts_extracted(self):
        result = OpenAlexClient.normalize_work(self._base_raw(), "populism", "batch1")
        assert len(result["concepts"]) == 1
        assert result["concepts"][0]["name"] == "Populism"
        assert result["concepts"][0]["score"] == 0.9

    @pytest.mark.unit
    def test_journal_extracted(self):
        result = OpenAlexClient.normalize_work(self._base_raw(), "populism", "batch1")
        assert result["journal"] == "Nature"
        assert result["journal_id"] == "S001"

    @pytest.mark.unit
    def test_references_extracted(self):
        result = OpenAlexClient.normalize_work(self._base_raw(), "populism", "batch1")
        assert result["references"] == ["W999"]

    @pytest.mark.unit
    def test_mesh_terms_extracted(self):
        result = OpenAlexClient.normalize_work(self._base_raw(), "populism", "batch1")
        assert result["mesh_terms"] == ["Politics"]

    @pytest.mark.unit
    def test_keywords_matched_set(self):
        result = OpenAlexClient.normalize_work(self._base_raw(), "populism", "batch1")
        assert result["keywords_matched"] == ["populism"]
        assert result["query_batch"] == "batch1"

    @pytest.mark.unit
    def test_missing_authorships_handled(self):
        raw = self._base_raw()
        del raw["authorships"]
        result = OpenAlexClient.normalize_work(raw, "populism", "batch1")
        assert result["authors"] == []

    @pytest.mark.unit
    def test_missing_abstract_inverted_index_gives_empty(self):
        raw = self._base_raw()
        raw["abstract_inverted_index"] = None
        result = OpenAlexClient.normalize_work(raw, "populism", "batch1")
        assert result["abstract"] == ""

    @pytest.mark.unit
    def test_null_primary_location_handled(self):
        raw = self._base_raw()
        raw["primary_location"] = None
        result = OpenAlexClient.normalize_work(raw, "populism", "batch1")
        assert result["journal"] == ""

    @pytest.mark.unit
    def test_null_open_access_handled(self):
        raw = self._base_raw()
        raw["open_access"] = None
        result = OpenAlexClient.normalize_work(raw, "populism", "batch1")
        assert result["is_open_access"] is False

    @pytest.mark.unit
    def test_null_title_becomes_empty_string(self):
        raw = self._base_raw()
        raw["title"] = None
        result = OpenAlexClient.normalize_work(raw, "populism", "batch1")
        assert result["title"] == ""

    @pytest.mark.unit
    def test_institution_flat_list_populated(self):
        result = OpenAlexClient.normalize_work(self._base_raw(), "populism", "batch1")
        assert any(inst["name"] == "MIT" for inst in result["institutions"])

    @pytest.mark.unit
    def test_author_institutions_mapping(self):
        result = OpenAlexClient.normalize_work(self._base_raw(), "populism", "batch1")
        mapping = result["author_institutions"]
        assert len(mapping) == 1
        assert mapping[0]["author_id"] == "A001"
        assert "I001" in mapping[0]["institution_ids"]


# ── _build_filter ─────────────────────────────────────────────────────────────


class TestBuildFilter:
    def _client(self):
        return OpenAlexClient(email="test@example.com")

    @pytest.mark.unit
    def test_basic_filter_string(self):
        client = self._client()
        result = client._build_filter("populism", "title.search")
        assert result == "title.search:populism"

    @pytest.mark.unit
    def test_extra_filters_appended(self):
        client = self._client()
        result = client._build_filter("populism", "title.search", {"type": "article"})
        assert "title.search:populism" in result
        assert "type:article" in result

    @pytest.mark.unit
    def test_or_operator_converted_to_pipe(self):
        client = self._client()
        result = client._build_filter("test", "title.search", {"type": "article OR book"})
        assert "article|book" in result

    @pytest.mark.unit
    def test_and_operator_converted_to_comma(self):
        client = self._client()
        result = client._build_filter("test", "title.search", {"type": "article AND review"})
        assert "article,review" in result

    @pytest.mark.unit
    def test_empty_filter_value_skipped(self):
        client = self._client()
        result = client._build_filter("test", "title.search", {"type": ""})
        assert "type" not in result

    @pytest.mark.unit
    def test_no_extra_filters(self):
        client = self._client()
        result = client._build_filter("populism", "search", None)
        assert result == "search:populism"


# ── OpenAlexClient.__init__ ───────────────────────────────────────────────────


class TestClientInit:
    @pytest.mark.unit
    def test_per_page_capped_at_200(self):
        client = OpenAlexClient(per_page=500)
        assert client.per_page == 200

    @pytest.mark.unit
    def test_per_page_below_200_preserved(self):
        client = OpenAlexClient(per_page=50)
        assert client.per_page == 50

    @pytest.mark.unit
    def test_email_stored(self):
        client = OpenAlexClient(email="test@example.com")
        assert client.email == "test@example.com"

    @pytest.mark.unit
    def test_user_agent_set_when_email_provided(self):
        client = OpenAlexClient(email="test@example.com")
        ua = client.session.headers.get("User-Agent", "")
        assert "test@example.com" in ua

    @pytest.mark.unit
    def test_no_user_agent_without_email(self):
        client = OpenAlexClient(email="")
        ua = client.session.headers.get("User-Agent", "")
        assert "mailto:" not in ua


# ── paginate_works ─────────────────────────────────────────────────────────────


class TestPaginateWorks:
    def _raw_work(self, work_id="W001"):
        return {
            "id": work_id,
            "title": "Test",
            "publication_year": 2020,
            "cited_by_count": 5,
            "abstract_inverted_index": None,
            "authorships": [],
            "concepts": [],
            "primary_location": {},
            "open_access": {"is_oa": False},
            "type": "article",
            "referenced_works": [],
            "mesh": [],
            "doi": "",
            "publication_date": "2020-01-01",
        }

    @pytest.mark.unit
    def test_yields_works_from_single_page(self):
        client = OpenAlexClient()
        page_response = {
            "results": [self._raw_work("W1"), self._raw_work("W2")],
            "meta": {"next_cursor": None},
        }

        with patch.object(client, "_get", return_value=page_response):
            works = list(client.paginate_works("populism", max_records=10))

        assert len(works) == 2
        assert works[0]["id"] == "W1"

    @pytest.mark.unit
    def test_stops_at_max_records(self):
        client = OpenAlexClient()
        page_response = {
            "results": [self._raw_work(f"W{i}") for i in range(10)],
            "meta": {"next_cursor": None},
        }

        with patch.object(client, "_get", return_value=page_response):
            works = list(client.paginate_works("populism", max_records=3))

        assert len(works) == 3

    @pytest.mark.unit
    def test_follows_cursor_to_next_page(self):
        client = OpenAlexClient()
        page1 = {
            "results": [self._raw_work("W1")],
            "meta": {"next_cursor": "cursor_abc"},
        }
        page2 = {
            "results": [self._raw_work("W2")],
            "meta": {"next_cursor": None},
        }

        with patch.object(client, "_get", side_effect=[page1, page2]):
            works = list(client.paginate_works("populism", max_records=10))

        assert len(works) == 2
        assert {w["id"] for w in works} == {"W1", "W2"}

    @pytest.mark.unit
    def test_stops_when_results_empty(self):
        client = OpenAlexClient()
        page_response = {"results": [], "meta": {"next_cursor": "cursor_abc"}}

        with patch.object(client, "_get", return_value=page_response):
            works = list(client.paginate_works("populism", max_records=100))

        assert len(works) == 0

    @pytest.mark.unit
    def test_email_added_to_params(self):
        client = OpenAlexClient(email="test@example.com")
        captured = {}

        def fake_get(url, params):
            captured["params"] = params
            return {"results": [], "meta": {"next_cursor": None}}

        with patch.object(client, "_get", side_effect=fake_get):
            list(client.paginate_works("populism"))

        assert captured["params"].get("mailto") == "test@example.com"


# ── _get (retry logic) ────────────────────────────────────────────────────────


class TestGetWithRetry:
    @pytest.mark.unit
    def test_returns_json_on_success(self):
        client = OpenAlexClient(max_retries=1, rate_limit_delay=0)
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"results": []}
        mock_resp.raise_for_status = Mock()

        with patch.object(client.session, "get", return_value=mock_resp):
            result = client._get("http://example.com", {})

        assert result == {"results": []}

    @pytest.mark.unit
    def test_raises_after_max_retries(self):
        client = OpenAlexClient(max_retries=2, rate_limit_delay=0, retry_backoff=1.0)

        with patch.object(
            client.session,
            "get",
            side_effect=requests.ConnectionError("timeout"),
        ):
            with pytest.raises(requests.ConnectionError):
                client._get("http://example.com", {})

    @pytest.mark.unit
    def test_handles_rate_limit_429(self):
        client = OpenAlexClient(max_retries=2, rate_limit_delay=0)
        rate_limited = Mock()
        rate_limited.status_code = 429
        rate_limited.headers = {"Retry-After": "0"}

        success = Mock()
        success.status_code = 200
        success.json.return_value = {"ok": True}
        success.raise_for_status = Mock()

        with patch.object(client.session, "get", side_effect=[rate_limited, success]):
            with patch("time.sleep"):
                result = client._get("http://example.com", {})

        assert result == {"ok": True}
