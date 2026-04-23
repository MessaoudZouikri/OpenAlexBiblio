"""
Unit tests for src/utils/validation_utils.py
Pure pandas operations — no file I/O for SchemaValidator tests.
"""

import tempfile
from pathlib import Path

import pandas as pd
import pytest

from src.utils.validation_utils import (
    DataValidationError,
    SchemaValidator,
    require_schema,
    validate_parquet_file,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def raw_df():
    return pd.DataFrame(
        {
            "id": ["W1", "W2", "W3"],
            "title": ["Title A", "Title B", "Title C"],
            "year": [2018, 2020, 2022],
            "cited_by_count": [10, 5, 0],
            "is_open_access": [True, False, True],
            "concepts": [["Populism"], ["Economics"], ["Sociology"]],
        }
    )


@pytest.fixture
def cleaned_df():
    return pd.DataFrame(
        {
            "id": ["W1", "W2", "W3"],
            "title": ["Title A", "Title B", "Title C"],
            "abstract": ["Abstract A", "Abstract B", "Abstract C"],
            "year": [2018, 2020, 2022],
            "cited_by_count": [10, 5, 0],
            "authors": [["Alice"], ["Bob"], ["Carol"]],
            "institution": [["Uni A"], ["Uni B"], ["Uni C"]],
            "journal": ["Journal A", "Journal B", "Journal C"],
            "concepts": [["Populism"], ["Economics"], ["Sociology"]],
            "decade": [2010, 2020, 2020],
        }
    )


@pytest.fixture
def classified_df():
    return pd.DataFrame(
        {
            "id": ["W1", "W2", "W3"],
            "title": ["Title A", "Title B", "Title C"],
            "domain": ["Political Science", "Economics", "Sociology"],
            "subcategory": ["radical_right", "political_economy", "social_movements"],
            "confidence": [0.85, 0.92, 0.78],
            "classification_stage": ["llm", "embedding", "rule_based"],
            "classification_method": ["qwen", "sentence-transformer", "keyword"],
        }
    )


@pytest.fixture
def network_df():
    return pd.DataFrame(
        {
            "id": ["W1", "W2", "W3"],
            "shared_references": [5, 3, 8],
            "cited_by_count": [45, 23, 67],
        }
    )


# ── DataValidationError ───────────────────────────────────────────────────────


@pytest.mark.unit
def test_data_validation_error_is_exception():
    with pytest.raises(DataValidationError):
        raise DataValidationError("bad data")


# ── SchemaValidator.validate_columns ─────────────────────────────────────────


@pytest.mark.unit
def test_validate_columns_passes_when_all_present(raw_df):
    assert SchemaValidator.validate_columns(raw_df, ["id", "title", "year"]) is True


@pytest.mark.unit
def test_validate_columns_raises_on_missing(raw_df):
    with pytest.raises(DataValidationError, match="Missing required columns"):
        SchemaValidator.validate_columns(raw_df, ["id", "nonexistent_column"])


@pytest.mark.unit
def test_validate_columns_empty_required_list(raw_df):
    assert SchemaValidator.validate_columns(raw_df, []) is True


@pytest.mark.unit
def test_validate_columns_stage_name_in_error(raw_df):
    with pytest.raises(DataValidationError, match="MyStage"):
        SchemaValidator.validate_columns(raw_df, ["missing"], stage_name="MyStage")


# ── SchemaValidator.validate_non_null_columns ─────────────────────────────────


@pytest.mark.unit
def test_validate_non_null_columns_passes(raw_df):
    ok, counts = SchemaValidator.validate_non_null_columns(raw_df, ["id", "title"])
    assert ok is True
    assert counts == {}


@pytest.mark.unit
def test_validate_non_null_columns_raises_on_null():
    df = pd.DataFrame({"id": ["W1", None, "W3"], "title": ["A", "B", "C"]})
    with pytest.raises(DataValidationError, match="Null values"):
        SchemaValidator.validate_non_null_columns(df, ["id"])


@pytest.mark.unit
def test_validate_non_null_columns_skips_missing_column(raw_df):
    ok, counts = SchemaValidator.validate_non_null_columns(raw_df, ["nonexistent"])
    assert ok is True


# ── SchemaValidator.validate_raw_openalex ─────────────────────────────────────


@pytest.mark.unit
def test_validate_raw_openalex_happy_path(raw_df):
    result = SchemaValidator.validate_raw_openalex(raw_df)
    assert result["status"] == "✓ Valid"
    assert result["n_rows"] == 3


@pytest.mark.unit
def test_validate_raw_openalex_year_range(raw_df):
    result = SchemaValidator.validate_raw_openalex(raw_df)
    assert result["year_range"] == (2018, 2022)


@pytest.mark.unit
def test_validate_raw_openalex_missing_column(raw_df):
    df = raw_df.drop(columns=["concepts"])
    with pytest.raises(DataValidationError):
        SchemaValidator.validate_raw_openalex(df)


@pytest.mark.unit
def test_validate_raw_openalex_year_out_of_range(raw_df):
    df = raw_df.copy()
    df["year"] = [1800, 2020, 2022]
    with pytest.raises(DataValidationError, match="Year"):
        SchemaValidator.validate_raw_openalex(df)


@pytest.mark.unit
def test_validate_raw_openalex_null_id():
    df = pd.DataFrame(
        {
            "id": [None, "W2"],
            "title": ["T1", "T2"],
            "year": [2020, 2021],
            "cited_by_count": [0, 1],
            "is_open_access": [True, False],
            "concepts": [[], []],
        }
    )
    with pytest.raises(DataValidationError):
        SchemaValidator.validate_raw_openalex(df)


# ── SchemaValidator.validate_cleaned_data ─────────────────────────────────────


@pytest.mark.unit
def test_validate_cleaned_data_happy_path(cleaned_df):
    result = SchemaValidator.validate_cleaned_data(cleaned_df)
    assert result["status"] == "✓ Valid"
    assert result["n_rows"] == 3


@pytest.mark.unit
def test_validate_cleaned_data_missing_column(cleaned_df):
    df = cleaned_df.drop(columns=["abstract"])
    with pytest.raises(DataValidationError):
        SchemaValidator.validate_cleaned_data(df)


@pytest.mark.unit
def test_validate_cleaned_data_null_abstract(cleaned_df):
    df = cleaned_df.copy()
    df.loc[0, "abstract"] = None
    with pytest.raises(DataValidationError):
        SchemaValidator.validate_cleaned_data(df)


# ── SchemaValidator.validate_classified_data ──────────────────────────────────


@pytest.mark.unit
def test_validate_classified_data_happy_path(classified_df):
    result = SchemaValidator.validate_classified_data(classified_df)
    assert result["status"] == "✓ Valid"
    assert result["n_domains"] == 3


@pytest.mark.unit
def test_validate_classified_data_confidence_out_of_range(classified_df):
    df = classified_df.copy()
    df.loc[0, "confidence"] = 1.5
    with pytest.raises(DataValidationError, match="Confidence"):
        SchemaValidator.validate_classified_data(df)


@pytest.mark.unit
def test_validate_classified_data_missing_schema_column(classified_df):
    df = classified_df.drop(columns=["domain"])
    with pytest.raises(DataValidationError):
        SchemaValidator.validate_classified_data(df)


@pytest.mark.unit
def test_validate_classified_data_avg_confidence(classified_df):
    result = SchemaValidator.validate_classified_data(classified_df)
    expected = round((0.85 + 0.92 + 0.78) / 3, 3)
    assert result["avg_confidence"] == expected


# ── SchemaValidator.validate_network_data ─────────────────────────────────────


@pytest.mark.unit
def test_validate_network_data_happy_path(network_df):
    result = SchemaValidator.validate_network_data(network_df)
    assert result["status"] == "✓ Valid"
    assert result["n_nodes"] == 3


@pytest.mark.unit
def test_validate_network_data_negative_values():
    df = pd.DataFrame(
        {
            "id": ["W1", "W2"],
            "shared_references": [-1, 3],
            "cited_by_count": [10, 5],
        }
    )
    with pytest.raises(DataValidationError, match="Negative"):
        SchemaValidator.validate_network_data(df)


@pytest.mark.unit
def test_validate_network_data_missing_column(network_df):
    df = network_df.drop(columns=["shared_references"])
    with pytest.raises(DataValidationError):
        SchemaValidator.validate_network_data(df)


# ── validate_parquet_file ─────────────────────────────────────────────────────


@pytest.mark.unit
def test_validate_parquet_file_happy_path(tmp_path, raw_df):
    p = tmp_path / "test.parquet"
    raw_df.to_parquet(p, engine="pyarrow")
    result = validate_parquet_file(str(p))
    assert result["n_rows"] == 3
    assert result["status"] == "✓ Valid"


@pytest.mark.unit
def test_validate_parquet_file_not_found():
    with pytest.raises(FileNotFoundError):
        validate_parquet_file("/nonexistent/path/file.parquet")


@pytest.mark.unit
def test_validate_parquet_file_with_schema(tmp_path, raw_df):
    p = tmp_path / "test.parquet"
    raw_df.to_parquet(p, engine="pyarrow")
    result = validate_parquet_file(str(p), expected_schema=["id", "title"])
    assert "id" in result["columns"]


@pytest.mark.unit
def test_validate_parquet_file_schema_mismatch_raises(tmp_path, raw_df):
    p = tmp_path / "test.parquet"
    raw_df.to_parquet(p, engine="pyarrow")
    with pytest.raises(DataValidationError):
        validate_parquet_file(str(p), expected_schema=["id", "nonexistent_col"])


# ── require_schema decorator ─────────────────────────────────────────────────


@pytest.mark.unit
def test_require_schema_passes_valid_df(raw_df):
    @require_schema(["id", "title"], "TestStage")
    def dummy(df):
        return "ok"

    assert dummy(raw_df) == "ok"


@pytest.mark.unit
def test_require_schema_raises_on_missing_column(raw_df):
    @require_schema(["id", "missing_col"], "TestStage")
    def dummy(df):
        return "ok"

    with pytest.raises(DataValidationError):
        dummy(raw_df)


@pytest.mark.unit
def test_require_schema_preserves_function_name():
    @require_schema(["id"])
    def my_func(df):
        pass

    assert my_func.__name__ == "my_func"
