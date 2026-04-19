"""
Data Validation Utilities
==========================
Comprehensive schema and data quality validation for pipeline stages.
"""

from typing import Dict, List, Optional, Tuple
import pandas as pd
from pathlib import Path


class DataValidationError(Exception):
    """Raised when data validation fails."""

    pass


class SchemaValidator:
    """Validate DataFrame schemas at various pipeline stages."""

    # Define required schemas for each pipeline stage
    RAW_OPENALEX_SCHEMA = ["id", "title", "year", "cited_by_count", "is_open_access", "concepts"]

    CLEANED_DATA_SCHEMA = [
        "id",
        "title",
        "abstract",
        "year",
        "cited_by_count",
        "authors",
        "institution",
        "journal",
        "concepts",
        "decade",
    ]

    CLASSIFIED_DATA_SCHEMA = [
        "id",
        "title",
        "domain",
        "subcategory",
        "confidence",
        "classification_stage",
        "classification_method",
    ]

    @staticmethod
    def validate_columns(
        df: pd.DataFrame, required_columns: List[str], stage_name: str = "Unknown"
    ) -> bool:
        """
        Validate that DataFrame has all required columns.

        Args:
            df: DataFrame to validate
            required_columns: List of column names required
            stage_name: Name of pipeline stage (for error messages)

        Returns:
            True if valid

        Raises:
            DataValidationError: If columns are missing
        """
        missing = set(required_columns) - set(df.columns)
        if missing:
            raise DataValidationError(
                f"[{stage_name}] Missing required columns: {missing}. " f"Found: {list(df.columns)}"
            )
        return True

    @staticmethod
    def validate_non_null_columns(
        df: pd.DataFrame, columns: List[str], stage_name: str = "Unknown"
    ) -> Tuple[bool, Dict]:
        """
        Check for null values in critical columns.

        Args:
            df: DataFrame to validate
            columns: Columns to check for nulls
            stage_name: Name of pipeline stage

        Returns:
            Tuple of (is_valid, null_counts_dict)

        Raises:
            DataValidationError: If critical nulls found
        """
        null_counts = {}
        for col in columns:
            if col in df.columns:
                n_nulls = df[col].isna().sum()
                if n_nulls > 0:
                    null_counts[col] = n_nulls

        if null_counts:
            pct_invalid = {k: f"{100*v/len(df):.1f}%" for k, v in null_counts.items()}
            raise DataValidationError(
                f"[{stage_name}] Null values in critical columns: {pct_invalid}"
            )
        return True, null_counts

    @staticmethod
    def validate_raw_openalex(df: pd.DataFrame) -> Dict:
        """Validate raw OpenAlex data schema and content."""
        SchemaValidator.validate_columns(
            df, SchemaValidator.RAW_OPENALEX_SCHEMA, "Raw OpenAlex Data"
        )
        SchemaValidator.validate_non_null_columns(df, ["id", "title", "year"], "Raw OpenAlex Data")

        # Check year range
        if df["year"].min() < 1900 or df["year"].max() > 2100:
            raise DataValidationError("Year values out of reasonable range [1900-2100]")

        return {
            "n_rows": len(df),
            "n_columns": len(df.columns),
            "year_range": (int(df["year"].min()), int(df["year"].max())),
            "status": "✓ Valid",
        }

    @staticmethod
    def validate_cleaned_data(df: pd.DataFrame) -> Dict:
        """Validate cleaned data schema and content."""
        SchemaValidator.validate_columns(df, SchemaValidator.CLEANED_DATA_SCHEMA, "Cleaned Data")
        SchemaValidator.validate_non_null_columns(df, ["id", "title", "abstract"], "Cleaned Data")

        return {
            "n_rows": len(df),
            "n_columns": len(df.columns),
            "unique_years": df["year"].nunique(),
            "status": "✓ Valid",
        }

    @staticmethod
    def validate_classified_data(df: pd.DataFrame) -> Dict:
        """Validate classified data schema and content."""
        SchemaValidator.validate_columns(
            df, SchemaValidator.CLASSIFIED_DATA_SCHEMA, "Classified Data"
        )
        SchemaValidator.validate_non_null_columns(
            df, ["id", "domain", "subcategory"], "Classified Data"
        )

        # Validate confidence scores
        if (df["confidence"] < 0).any() or (df["confidence"] > 1).any():
            raise DataValidationError("Confidence scores out of range [0-1]")

        return {
            "n_rows": len(df),
            "n_domains": df["domain"].nunique(),
            "n_subcategories": df["subcategory"].nunique(),
            "avg_confidence": round(df["confidence"].mean(), 3),
            "status": "✓ Valid",
        }

    @staticmethod
    def validate_network_data(df: pd.DataFrame) -> Dict:
        """Validate network analysis input data."""
        required = ["id", "shared_references", "cited_by_count"]
        SchemaValidator.validate_columns(df, required, "Network Data")

        # Check for non-negative values
        for col in ["shared_references", "cited_by_count"]:
            if (df[col] < 0).any():
                raise DataValidationError(f"Negative values in {col}")

        return {
            "n_nodes": df["id"].nunique(),
            "n_edges": df["shared_references"].sum() / 2,  # Symmetric edges
            "status": "✓ Valid",
        }


def validate_parquet_file(path: str, expected_schema: Optional[List[str]] = None) -> Dict:
    """
    Safely load and validate parquet file.

    Args:
        path: Path to parquet file
        expected_schema: List of expected column names

    Returns:
        Validation result dict

    Raises:
        FileNotFoundError: If file doesn't exist
        DataValidationError: If validation fails
    """
    path_obj = Path(path)
    if not path_obj.exists():
        raise FileNotFoundError(f"Parquet file not found: {path}")

    try:
        df = pd.read_parquet(path, engine="pyarrow")
    except Exception as e:
        raise DataValidationError(f"Failed to read parquet: {e}")

    if expected_schema:
        SchemaValidator.validate_columns(df, expected_schema, f"Parquet: {path_obj.name}")

    return {
        "file": path,
        "n_rows": len(df),
        "n_columns": len(df.columns),
        "columns": list(df.columns),
        "status": "✓ Valid",
    }


# Decorator for automatic validation
def require_schema(required_columns: List[str], stage_name: str = "Unknown"):
    """Decorator to enforce schema validation on function input."""

    def decorator(func):
        def wrapper(df: pd.DataFrame, *args, **kwargs):
            SchemaValidator.validate_columns(df, required_columns, stage_name)
            return func(df, *args, **kwargs)

        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper

    return decorator
