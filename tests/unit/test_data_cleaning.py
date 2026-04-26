"""
Unit Tests for Data Cleaning Agent
===================================

Tests data cleaning functionality including:
- Text normalization
- Author parsing
- Institution extraction
- Concept processing
- Duplicate handling
"""

import pandas as pd

from src.agents.data_cleaning import (
    clean_dataframe,
    normalize_unicode,
    rule_based_domain,
    rule_based_subcategory,
)


class TestUnicodeNormalization:
    """Test unicode normalization functions."""

    def test_normalize_unicode_basic(self):
        """Test basic unicode normalization."""
        text = "  This is a TEST string with   extra spaces!  "
        result = normalize_unicode(text)
        assert result == "This is a TEST string with   extra spaces!"

    def test_normalize_unicode_none(self):
        """Test normalizing None input."""
        result = normalize_unicode(None)
        assert result == ""

    def test_normalize_unicode_empty(self):
        """Test normalizing empty string."""
        result = normalize_unicode("")
        assert result == ""

    def test_normalize_unicode_special_chars(self):
        """Test normalizing special unicode characters."""
        text = "Text with café résumé naïve"
        result = normalize_unicode(text)
        # Should normalize to NFC form
        assert "café" in result or "cafe" in result  # Depends on normalization


class TestRuleBasedDomain:
    """Test rule-based domain classification."""

    def test_rule_based_domain_match(self):
        """Test successful domain matching."""
        concepts = [{"name": "Political Science", "score": 0.8}, {"name": "Populism", "score": 0.6}]

        domain, confidence = rule_based_domain(concepts)
        assert domain == "Political Science"
        assert confidence > 0.5

    def test_rule_based_domain_no_match(self):
        """Test when no concepts match."""
        concepts = [
            {"name": "Quantum Physics", "score": 0.8},
            {"name": "Particle Acceleration", "score": 0.6},
        ]

        domain, confidence = rule_based_domain(concepts)
        assert domain == "Other"
        assert confidence == 0.0

    def test_rule_based_domain_empty(self):
        """Test with empty concepts."""
        domain, confidence = rule_based_domain([])
        assert domain == "Other"
        assert confidence == 0.0

    def test_rule_based_domain_none(self):
        """Test with None concepts."""
        domain, confidence = rule_based_domain(None)
        assert domain == "Other"
        assert confidence == 0.0


class TestRuleBasedSubcategory:
    """Test rule-based subcategory classification."""

    def test_rule_based_subcategory_match(self):
        """Test successful subcategory matching."""
        title = "The rise of radical right populism"
        abstract = "This paper examines far-right political parties"

        result = rule_based_subcategory(title, abstract, "Political Science")
        assert result == "radical_right"

    def test_rule_based_subcategory_no_match(self):
        """Test when no keywords match."""
        title = "Economic theory and applications"
        abstract = "This paper discusses macroeconomic models"

        result = rule_based_subcategory(title, abstract, "Economics")
        # Should return last subcategory for Economics
        assert result in [
            "political_economy",
            "redistribution",
            "trade_globalization",
            "financial_crisis",
        ]

    def test_rule_based_subcategory_other_domain(self):
        """Test subcategory for Other domain."""
        title = "Historical analysis"
        abstract = "This paper examines historical events"

        result = rule_based_subcategory(title, abstract, "Other")
        assert result == "history"


class TestDataframeCleaning:
    """Test the main dataframe cleaning pipeline."""

    def test_clean_dataframe_basic(self, sample_raw_openalex_data, caplog):
        """Test basic dataframe cleaning."""
        import logging

        # Create a mock logger
        logger = logging.getLogger("test")
        logger.setLevel(logging.INFO)

        result_df, report = clean_dataframe(sample_raw_openalex_data, logger)

        # Check that required columns exist
        expected_cols = ["id", "title", "year", "cited_by_count", "domain_preliminary"]
        for col in expected_cols:
            assert col in result_df.columns

        # Check report structure
        assert "input_records" in report
        assert "output_records" in report
        assert "operations" in report
        assert isinstance(report["operations"], list)

    def test_clean_dataframe_missing_data(self, caplog):
        """Test cleaning with missing critical data."""
        import logging

        # Create data with missing IDs and titles
        problematic_data = pd.DataFrame(
            {
                "id": ["W1", None, "W3", "W4"],
                "title": ["Title1", None, "", "Title4"],  # Empty title
                "year": [2020, 2021, 2022, 2023],
                "cited_by_count": [10, 20, 30, 40],
                "is_open_access": [True, False, True, False],
                "concepts": [
                    [{"name": "Test"}],
                    [{"name": "Test2"}],
                    [{"name": "Test3"}],
                    [{"name": "Test4"}],
                ],
            }
        )

        logger = logging.getLogger("test")
        result_df, report = clean_dataframe(problematic_data, logger)

        # Should have fewer records after cleaning
        assert len(result_df) < len(problematic_data)
        assert len(result_df) >= 2  # At least the valid ones

        # Check that operations were recorded
        operations = [op["op"] for op in report["operations"]]
        assert "drop_null_title_or_id" in operations

    def test_clean_dataframe_year_filtering(self, caplog):
        """Test year-based filtering."""
        import logging

        # Create data with invalid years
        year_data = pd.DataFrame(
            {
                "id": ["W1", "W2", "W3", "W4"],
                "title": ["Title1", "Title2", "Title3", "Title4"],
                "year": [1800, 2020, 2021, 2050],  # Invalid years
                "cited_by_count": [10, 20, 30, 40],
                "is_open_access": [True, False, True, False],
                "concepts": [[{"name": "Test"}] for _ in range(4)],
            }
        )

        logger = logging.getLogger("test")
        result_df, report = clean_dataframe(year_data, logger, min_year=1900)

        # Should filter out 1800 and 2050
        valid_years = result_df["year"].tolist()
        assert 1800 not in valid_years
        assert 2050 not in valid_years
        assert 2020 in valid_years
        assert 2021 in valid_years

    def test_clean_dataframe_duplicate_removal(self, caplog):
        """Test duplicate removal by ID."""
        import logging

        # Create data with duplicates
        duplicate_data = pd.DataFrame(
            {
                "id": ["W1", "W1", "W2", "W3"],  # W1 appears twice
                "title": ["Title1", "Title1 Duplicate", "Title2", "Title3"],
                "year": [2020, 2020, 2021, 2022],
                "cited_by_count": [10, 5, 20, 30],  # First W1 has higher citations
                "is_open_access": [True, False, True, False],
                "concepts": [[{"name": "Test"}] for _ in range(4)],
            }
        )

        logger = logging.getLogger("test")
        result_df, report = clean_dataframe(duplicate_data, logger)

        # Should have one less record
        assert len(result_df) == len(duplicate_data) - 1

        # Should keep the one with higher citation count
        w1_record = result_df[result_df["id"] == "W1"]
        assert len(w1_record) == 1
        assert w1_record["cited_by_count"].iloc[0] == 10

    def test_clean_dataframe_derived_fields(self, sample_raw_openalex_data, caplog):
        """Test that derived fields are correctly calculated."""
        import logging

        logger = logging.getLogger("test")
        result_df, report = clean_dataframe(sample_raw_openalex_data, logger)

        # Check derived fields exist
        derived_fields = [
            "has_abstract",
            "has_concepts",
            "author_count",
            "institution_count",
            "decade",
            "domain_preliminary",
            "subcategory_preliminary",
        ]

        for field in derived_fields:
            assert field in result_df.columns

        # Check boolean fields
        assert result_df["has_abstract"].dtype == bool
        assert result_df["has_concepts"].dtype == bool

        # Check decade calculation
        assert all(result_df["decade"] == (result_df["year"] // 10 * 10))

    def test_clean_dataframe_report_completeness(self, sample_raw_openalex_data, caplog):
        """Test that cleaning report is complete."""
        import logging

        logger = logging.getLogger("test")
        result_df, report = clean_dataframe(sample_raw_openalex_data, logger)

        # Check required report fields
        required_fields = [
            "input_records",
            "output_records",
            "operations",
            "abstract_coverage",
            "concept_coverage",
            "domain_distribution",
        ]

        for field in required_fields:
            assert field in report

        # Check operations structure
        assert isinstance(report["operations"], list)
        for op in report["operations"]:
            assert "op" in op
            assert "dropped" in op or "removed" in op

        # Check coverage rates
        assert 0 <= report["abstract_coverage_rate"] <= 1
        assert 0 <= report["concept_coverage_rate"] <= 1


# ── main() ────────────────────────────────────────────────────────────────────


def _make_minimal_df():
    import pandas as pd

    return pd.DataFrame(
        {
            "id": ["W1", "W2"],
            "title": ["Populism and Democracy", "Economic Inequality"],
            "abstract": ["Study of populism", "Study of inequality"],
            "year": [2019, 2020],
            "cited_by_count": [5, 10],
            "authors": [[{"id": "A1", "name": "Alice"}], [{"id": "A2", "name": "Bob"}]],
            "institution": ["Univ A", "Univ B"],
            "journal": ["J1", "J2"],
            "concepts": [
                [{"name": "Populism", "display_name": "Populism", "score": 0.9}],
                [],
            ],
            "is_open_access": [True, False],
            "type": ["article", "article"],
            "references": [["R1"], ["R2"]],
            "keywords_matched": [["populism"], ["inequality"]],
        }
    )


def test_main_saves_clean_parquet_and_report(tmp_path):
    """main() with --input saves clean parquet and cleaning report."""
    from unittest.mock import MagicMock, patch

    from src.agents.data_cleaning import main

    raw_dir = tmp_path / "raw"
    clean_dir = tmp_path / "clean"
    logs_dir = tmp_path / "logs"
    raw_dir.mkdir()
    clean_dir.mkdir()
    logs_dir.mkdir()

    config = {
        "paths": {
            "data_raw": str(raw_dir),
            "data_clean": str(clean_dir),
            "logs": str(logs_dir),
        },
        "pipeline": {"min_year": 1990},
    }

    with (
        patch("sys.argv", ["data_cleaning.py"]),
        patch("src.agents.data_cleaning.load_yaml", return_value=config),
        patch("src.agents.data_cleaning.setup_logger", return_value=MagicMock()),
        patch("src.agents.data_cleaning.latest_file", return_value=tmp_path / "dummy.parquet"),
        patch("src.agents.data_cleaning.load_parquet", return_value=_make_minimal_df()),
        patch("src.agents.data_cleaning.save_parquet") as mock_save_parquet,
        patch("src.agents.data_cleaning.save_json") as mock_save_json,
    ):
        main()

    mock_save_parquet.assert_called_once()
    mock_save_json.assert_called_once()


def test_main_explicit_input_path(tmp_path):
    """main() with --input flag uses the given path instead of auto-detect."""
    from unittest.mock import MagicMock, patch

    from src.agents.data_cleaning import main

    config = {
        "paths": {
            "data_raw": str(tmp_path),
            "data_clean": str(tmp_path),
            "logs": str(tmp_path),
        },
        "pipeline": {"min_year": 1990},
    }

    with (
        patch("sys.argv", ["data_cleaning.py", "--input", "some/raw.parquet"]),
        patch("src.agents.data_cleaning.load_yaml", return_value=config),
        patch("src.agents.data_cleaning.setup_logger", return_value=MagicMock()),
        patch("src.agents.data_cleaning.load_parquet", return_value=_make_minimal_df()),
        patch("src.agents.data_cleaning.save_parquet"),
        patch("src.agents.data_cleaning.save_json"),
    ):
        main()  # should not raise


def test_main_exits_when_no_raw_file(tmp_path):
    """main() calls sys.exit(1) when no raw parquet is found and --input is not given."""
    from unittest.mock import MagicMock, patch

    import pytest

    from src.agents.data_cleaning import main

    config = {
        "paths": {
            "data_raw": str(tmp_path),
            "data_clean": str(tmp_path),
            "logs": str(tmp_path),
        },
        "pipeline": {"min_year": 1990},
    }

    with (
        patch("sys.argv", ["data_cleaning.py"]),
        patch("src.agents.data_cleaning.load_yaml", return_value=config),
        patch("src.agents.data_cleaning.setup_logger", return_value=MagicMock()),
        patch("src.agents.data_cleaning.latest_file", return_value=None),
        pytest.raises(SystemExit) as exc_info,
    ):
        main()

    assert exc_info.value.code == 1
