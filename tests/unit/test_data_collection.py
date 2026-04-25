"""
Unit tests for src/agents/data_collection.py

Covers: _sanitize_term, _build_filters, collect_openalex_data, run_collection.
All HTTP calls are mocked — no network activity.
"""

import logging
from unittest.mock import MagicMock, Mock, patch

import pandas as pd
import pytest

from src.agents.data_collection import (
    _build_filters,
    _sanitize_term,
    collect_openalex_data,
    run_collection,
)
from src.utils.openalex_client import OpenAlexClient as _RealOpenAlexClient


# ── _sanitize_term ────────────────────────────────────────────────────────────


class TestSanitizeTerm:
    def _logger(self):
        return logging.getLogger("test")

    @pytest.mark.unit
    def test_ascii_term_unchanged(self):
        assert _sanitize_term("populism", self._logger()) == "populism"

    @pytest.mark.unit
    def test_strips_non_ascii(self):
        result = _sanitize_term("populisóm", self._logger())
        assert result == "populism"

    @pytest.mark.unit
    def test_empty_string(self):
        assert _sanitize_term("", self._logger()) == ""

    @pytest.mark.unit
    def test_all_non_ascii_becomes_empty(self):
        result = _sanitize_term("éàü", self._logger())
        assert result == ""

    @pytest.mark.unit
    def test_logs_warning_on_change(self):
        mock_log = Mock()
        _sanitize_term("café", mock_log)
        mock_log.warning.assert_called_once()

    @pytest.mark.unit
    def test_no_warning_when_unchanged(self):
        mock_log = Mock()
        _sanitize_term("populism", mock_log)
        mock_log.warning.assert_not_called()

    @pytest.mark.unit
    def test_leading_trailing_whitespace_stripped(self):
        result = _sanitize_term("  populism  ", self._logger())
        assert result == "populism"


# ── _build_filters ─────────────────────────────────────────────────────────────


class TestBuildFilters:
    @pytest.mark.unit
    def test_empty_config_returns_empty_dict(self):
        assert _build_filters({}) == {}

    @pytest.mark.unit
    def test_type_filter(self):
        result = _build_filters({"type": "article"})
        assert result["type"] == "article"

    @pytest.mark.unit
    def test_from_date_filter(self):
        result = _build_filters({"from_publication_date": "2010-01-01"})
        assert result["from_publication_date"] == "2010-01-01"

    @pytest.mark.unit
    def test_to_date_filter(self):
        result = _build_filters({"to_publication_date": "2023-12-31"})
        assert result["to_publication_date"] == "2023-12-31"

    @pytest.mark.unit
    def test_open_access_sets_is_oa(self):
        result = _build_filters({"open_access_only": True})
        assert result["is_oa"] == "true"

    @pytest.mark.unit
    def test_open_access_false_not_included(self):
        result = _build_filters({"open_access_only": False})
        assert "is_oa" not in result

    @pytest.mark.unit
    def test_all_filters_combined(self):
        cfg = {
            "type": "article",
            "from_publication_date": "2015-01-01",
            "to_publication_date": "2023-12-31",
            "open_access_only": True,
        }
        result = _build_filters(cfg)
        assert result["type"] == "article"
        assert result["from_publication_date"] == "2015-01-01"
        assert result["to_publication_date"] == "2023-12-31"
        assert result["is_oa"] == "true"

    @pytest.mark.unit
    def test_unrecognised_keys_ignored(self):
        result = _build_filters({"unknown_key": "value"})
        assert "unknown_key" not in result
        assert result == {}


# ── collect_openalex_data ─────────────────────────────────────────────────────


class TestCollectOpenAlexData:
    @pytest.mark.unit
    def test_returns_dataframe_on_success(self):
        raw_work = {
            "id": "W123",
            "title": "Test Populism Paper",
            "publication_year": 2021,
            "cited_by_count": 10,
            "abstract_inverted_index": {"This": [0], "is": [1], "an": [2], "abstract": [3]},
            "authorships": [],
            "concepts": [],
            "primary_location": {},
            "open_access": {"is_oa": True},
            "type": "article",
            "referenced_works": [],
            "mesh": [],
            "doi": "10.1234/test",
            "publication_date": "2021-01-01",
        }

        with patch("src.agents.data_collection.OpenAlexClient") as MockClient:
            instance = MockClient.return_value
            instance.paginate_works.return_value = iter([raw_work])
            # Keep the static normalize_work working correctly
            MockClient.normalize_work.side_effect = _RealOpenAlexClient.normalize_work
            df = collect_openalex_data("populism", max_results=1)

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 1
        assert df.iloc[0]["id"] == "W123"

    @pytest.mark.unit
    def test_returns_empty_dataframe_when_no_records(self):
        with patch("src.agents.data_collection.OpenAlexClient") as MockClient:
            instance = MockClient.return_value
            instance.paginate_works.return_value = iter([])
            df = collect_openalex_data("populism", max_results=10)

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0

    @pytest.mark.unit
    def test_skips_records_without_id(self):
        no_id_work = {"title": "No ID Work", "cited_by_count": 5}

        with patch("src.agents.data_collection.OpenAlexClient") as MockClient:
            instance = MockClient.return_value
            instance.paginate_works.return_value = iter([no_id_work])
            df = collect_openalex_data("populism")

        assert len(df) == 0

    @pytest.mark.unit
    def test_returns_empty_on_client_init_error(self):
        with patch(
            "src.agents.data_collection.OpenAlexClient",
            side_effect=Exception("init failed"),
        ):
            df = collect_openalex_data("populism")

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0

    @pytest.mark.unit
    def test_returns_empty_on_pagination_exception(self):
        with patch("src.agents.data_collection.OpenAlexClient") as MockClient:
            instance = MockClient.return_value
            instance.paginate_works.side_effect = Exception("connection error")
            df = collect_openalex_data("populism")

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0

    @pytest.mark.unit
    def test_returns_empty_for_non_iterable_paginator(self):
        with patch("src.agents.data_collection.OpenAlexClient") as MockClient:
            instance = MockClient.return_value
            instance.paginate_works.return_value = 42  # non-iterable
            df = collect_openalex_data("populism")

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0

    @pytest.mark.unit
    def test_filters_non_dict_results(self):
        with patch("src.agents.data_collection.OpenAlexClient") as MockClient:
            instance = MockClient.return_value
            instance.paginate_works.return_value = iter(["not_a_dict", None, 42])
            df = collect_openalex_data("populism")

        assert len(df) == 0

    @pytest.mark.unit
    def test_multiple_records_collected(self):
        works = [
            {
                "id": f"W{i}",
                "title": f"Paper {i}",
                "publication_year": 2020,
                "cited_by_count": i,
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
            for i in range(5)
        ]

        with patch("src.agents.data_collection.OpenAlexClient") as MockClient:
            instance = MockClient.return_value
            instance.paginate_works.return_value = iter(works)
            MockClient.normalize_work.side_effect = _RealOpenAlexClient.normalize_work
            df = collect_openalex_data("populism", max_results=5)

        assert len(df) == 5


# ── run_collection ────────────────────────────────────────────────────────────


class TestRunCollection:
    def _make_config(self, tmp_path):
        return {
            "paths": {
                "data_raw": str(tmp_path / "raw"),
                "logs": str(tmp_path / "logs"),
            },
            "pipeline": {
                "test_max_records": 5,
                "full_max_records": 1000,
            },
        }

    def _make_openalex_cfg(self):
        return {
            "api": {
                "polite_email": "test@example.com",
                "per_page": 25,
                "rate_limit_delay": 0.0,
                "max_retries": 1,
                "retry_backoff": 1.0,
                "timeout": 5,
                "base_url": "https://api.openalex.org",
            },
            "queries": {
                "filters": {"type": "article"},
                "sort": {"field": "cited_by_count", "order": "desc"},
                "keywords": [
                    {"term": "populism", "field": "title.search"},
                ],
            },
        }

    def _raw_work(self, work_id="W001"):
        return {
            "id": work_id,
            "title": "Populism paper",
            "publication_year": 2021,
            "cited_by_count": 10,
            "abstract_inverted_index": None,
            "authorships": [],
            "concepts": [],
            "primary_location": {},
            "open_access": {"is_oa": False},
            "type": "article",
            "referenced_works": [],
            "mesh": [],
            "doi": "",
            "publication_date": "2021-01-01",
        }

    @pytest.mark.unit
    def test_run_collection_returns_manifest(self, tmp_path):
        config = self._make_config(tmp_path)
        openalex_cfg = self._make_openalex_cfg()

        with patch("src.agents.data_collection.OpenAlexClient") as MockClient:
            instance = MockClient.return_value
            instance.paginate_works.return_value = iter([self._raw_work()])
            MockClient.normalize_work.side_effect = _RealOpenAlexClient.normalize_work

            manifest = run_collection(config, openalex_cfg, test_mode=True)

        assert isinstance(manifest, dict)
        assert manifest["total_records"] == 1
        assert manifest["mode"] == "test"

    @pytest.mark.unit
    def test_run_collection_returns_empty_on_zero_records(self, tmp_path):
        config = self._make_config(tmp_path)
        openalex_cfg = self._make_openalex_cfg()

        with patch("src.agents.data_collection.OpenAlexClient") as MockClient:
            instance = MockClient.return_value
            instance.paginate_works.return_value = iter([])

            manifest = run_collection(config, openalex_cfg, test_mode=True)

        assert manifest == {}

    @pytest.mark.unit
    def test_run_collection_deduplicates_by_id(self, tmp_path):
        config = self._make_config(tmp_path)
        openalex_cfg = self._make_openalex_cfg()
        # Two queries with same work ID
        openalex_cfg["queries"]["keywords"] = [
            {"term": "populism", "field": "title.search"},
            {"term": "populist", "field": "title.search"},
        ]

        same_work = self._raw_work("W999")

        with patch("src.agents.data_collection.OpenAlexClient") as MockClient:
            instance = MockClient.return_value
            instance.paginate_works.return_value = iter([same_work, same_work])
            MockClient.normalize_work.side_effect = _RealOpenAlexClient.normalize_work

            manifest = run_collection(config, openalex_cfg, test_mode=True)

        assert manifest["total_records"] == 1

    @pytest.mark.unit
    def test_run_collection_skips_empty_query_term(self, tmp_path):
        config = self._make_config(tmp_path)
        openalex_cfg = self._make_openalex_cfg()
        # Force _sanitize_term to produce empty string
        openalex_cfg["queries"]["keywords"] = [
            {"term": "éà", "field": "title.search"},  # All non-ASCII
        ]

        with patch("src.agents.data_collection.OpenAlexClient") as MockClient:
            instance = MockClient.return_value
            instance.paginate_works.return_value = iter([])

            manifest = run_collection(config, openalex_cfg, test_mode=True)

        # paginate_works should never be called for an empty term
        instance.paginate_works.assert_not_called()
        assert manifest == {}

    @pytest.mark.unit
    def test_run_collection_saves_parquet_file(self, tmp_path):
        config = self._make_config(tmp_path)
        openalex_cfg = self._make_openalex_cfg()

        with patch("src.agents.data_collection.OpenAlexClient") as MockClient:
            instance = MockClient.return_value
            instance.paginate_works.return_value = iter([self._raw_work()])
            MockClient.normalize_work.side_effect = _RealOpenAlexClient.normalize_work

            manifest = run_collection(config, openalex_cfg, test_mode=True)

        raw_dir = tmp_path / "raw"
        parquet_files = list(raw_dir.glob("openalex_raw_*.parquet"))
        assert len(parquet_files) == 1
        assert manifest["output_file"] == str(parquet_files[0])

    @pytest.mark.unit
    def test_run_collection_full_mode_uses_full_max_records(self, tmp_path):
        config = self._make_config(tmp_path)
        openalex_cfg = self._make_openalex_cfg()
        captured = {}

        original_paginate = None

        with patch("src.agents.data_collection.OpenAlexClient") as MockClient:
            instance = MockClient.return_value
            MockClient.normalize_work.side_effect = _RealOpenAlexClient.normalize_work

            def fake_paginate(**kwargs):
                captured["max_records"] = kwargs.get("max_records")
                return iter([self._raw_work()])

            instance.paginate_works.side_effect = fake_paginate

            run_collection(config, openalex_cfg, test_mode=False)

        assert captured["max_records"] == 1000

    @pytest.mark.unit
    def test_run_collection_test_mode_uses_test_max_records(self, tmp_path):
        config = self._make_config(tmp_path)
        openalex_cfg = self._make_openalex_cfg()
        captured = {}

        with patch("src.agents.data_collection.OpenAlexClient") as MockClient:
            instance = MockClient.return_value
            MockClient.normalize_work.side_effect = _RealOpenAlexClient.normalize_work

            def fake_paginate(**kwargs):
                captured["max_records"] = kwargs.get("max_records")
                return iter([self._raw_work()])

            instance.paginate_works.side_effect = fake_paginate

            run_collection(config, openalex_cfg, test_mode=True)

        assert captured["max_records"] == 5
