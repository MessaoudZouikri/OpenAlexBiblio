"""
Pytest Configuration and Shared Fixtures
========================================

This module provides shared fixtures and configuration for all tests in the
bibliometric pipeline testing suite.

Usage:
    pytest tests/ -v --cov=src --cov-report=html
"""

import shutil
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd
import pytest

# Add src to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# ── Test Data Fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def sample_raw_openalex_data():
    """Sample raw OpenAlex data for testing."""
    return pd.DataFrame({
        "id": ["W123456789", "W987654321", "W111111111"],
        "title": [
            "The Rise of Populism in Europe",
            "Economic Inequality and Political Behavior",
            "Social Movements in Latin America"
        ],
        "abstract": [
        "This paper examines the rise of populism in Europe.",
        "We analyze how economic inequality affects political behavior.",
        "This study explores social movements in Latin America."
        ],  # Raw data may not have abstracts initially
        "year": [2020, 2019, 2021],
        "cited_by_count": [45, 23, 67],
        "is_open_access": [True, False, True],
        "concepts": [
            [{"display_name": "Political Science"}, {"display_name": "Populism"}],
            [{"display_name": "Economics"}, {"display_name": "Inequality"}],
            [{"display_name": "Sociology"}, {"display_name": "Social Movements"}]
        ],
        "authors": [[], [], []],  # Raw data structure
        "institutions": [[], [], []],
        "journal": ["", "", ""],
        "doi": ["", "", ""]
    })

# ─── Add to tests/conftest.py ───────────────────────────────────────────

@pytest.fixture
def manifest_path(raw_dir: str) -> str:
    """Path to the collection manifest JSON (may not yet exist at test time)."""
    return str(Path(raw_dir) / "collection_manifest.json")


@pytest.fixture
def report_path(clean_path: str) -> str:
    """Path to the cleaning report JSON."""
    return str(Path(clean_path).parent / "cleaning_report.json")


@pytest.fixture
def classified_path(proc_dir: str) -> str:
    """Path to the classified works parquet."""
    return str(Path(proc_dir) / "classified_works.parquet")


@pytest.fixture
def outputs_dir(tmp_path) -> str:
    """Directory for pipeline outputs (figures, networks, reports)."""
    d = tmp_path / "outputs"
    d.mkdir(parents=True, exist_ok=True)
    return str(d)


@pytest.fixture
def df_raw(sample_raw_openalex_data) -> pd.DataFrame:
    """Alias for sample_raw_openalex_data, matching pipeline naming."""
    return sample_raw_openalex_data


@pytest.fixture
def df_clean(sample_cleaned_data) -> pd.DataFrame:
    """Alias for sample_cleaned_data, matching pipeline naming."""
    return sample_cleaned_data


@pytest.fixture
def df_classified(sample_classified_data) -> pd.DataFrame:
    """Alias for sample_classified_data, matching pipeline naming."""
    return sample_classified_data

@pytest.fixture
def sample_cleaned_data():
    """Sample cleaned bibliometric data."""
    return pd.DataFrame({
        "id": ["W123456789", "W987654321", "W111111111"],
        "title": [
            "The Rise of Populism in Europe",
            "Economic Inequality and Political Behavior",
            "Social Movements in Latin America",
        ],
        "abstract": [
            "This paper examines the rise of populism across Western democracies using panel data from 1990 to 2015.",
            "We analyze how economic inequality affects political behavior and voter polarization in OECD countries.",
            "This study explores social movements and collective action over three decades of Latin American politics.",
        ],
        "year": [2020, 2019, 2021],
        "cited_by_count": [45, 23, 45],  # ← was [45, 23, 67]
        "authors": [
            ["John Smith", "Jane Doe"],
            ["Bob Johnson"],
            ["Maria Garcia", "Carlos Rodriguez"],
        ],
        "institution": [
            ["University of Amsterdam", "Harvard University"],
            ["MIT"],
            ["University of Sao Paulo", "UNAM"],
        ],
        "journal": [
            "European Journal of Political Research",
            "American Political Science Review",
            "Latin American Perspectives",
        ],
        "concepts": [
            ["Political Science", "Populism"],
            ["Economics", "Political Behavior"],
            ["Sociology", "Social Movements"],
        ],
        "decade": [2020, 2010, 2020],
        "domain_preliminary": ["Political Science", "Economics", "Sociology"],
    })


@pytest.fixture
def sample_classified_data():
    """Sample classified data with domains and subcategories."""
    return pd.DataFrame({
        "id": ["W123456789", "W987654321", "W111111111"],
        "title": [
            "The Rise of Populism in Europe",
            "Economic Inequality and Political Behavior",
            "Social Movements in Latin America"
        ],
        "domain": ["Political Science", "Economics", "Sociology"],
        "subcategory": ["radical_right", "political_economy", "social_movements"],
        "confidence": [0.85, 0.92, 0.78],
        "classification_stage": ["llm", "embedding", "rule_based"],
        "classification_method": ["gpt-4", "sentence-transformer", "keyword_matching"]
    })


@pytest.fixture
def sample_network_data():
    """Sample network analysis input data."""
    return pd.DataFrame({
        "id": ["W123456789", "W987654321", "W111111111"],
        "shared_references": [5, 3, 8],
        "cited_by_count": [45, 23, 67]
    })


@pytest.fixture
def mock_openalex_response():
    """Mock response from OpenAlex API."""
    return {
        "results": [
            {
                "id": "W123456789",
                "display_name": "The Rise of Populism in Europe",
                "publication_year": 2020,
                "cited_by_count": 45,
                "open_access": {"is_oa": True},
                "concepts": [
                    {"display_name": "Political Science", "level": 0},
                    {"display_name": "Populism", "level": 1}
                ],
                "authorships": [
                    {
                        "author": {"display_name": "John Smith"},
                        "institutions": [{"display_name": "University of Amsterdam"}]
                    }
                ]
            }
        ],
        "meta": {"count": 1, "page": 1, "per_page": 25}
    }


# ── Mock Fixtures ───────────────────────────────────────────────────────────

@pytest.fixture
def mock_openalex_client():
    """Mock OpenAlex API client."""
    with patch('src.utils.openalex_client.OpenAlexClient') as mock_client:
        mock_instance = Mock()
        mock_instance.search_works.return_value = {
            "results": [
                {
                    "id": "W123456789",
                    "display_name": "Test Work",
                    "publication_year": 2020,
                    "cited_by_count": 10,
                    "open_access": {"is_oa": True},
                    "concepts": [{"display_name": "Political Science"}],
                    "authorships": [{"author": {"display_name": "Test Author"}}]
                }
            ]
        }
        mock_client.return_value = mock_instance
        yield mock_client


@pytest.fixture
def mock_llm_client():
    """Mock LLM client for classification."""
    with patch('src.utils.llm_client.OllamaClient') as mock_client:
        mock_instance = Mock()
        mock_instance.classify_work.return_value = {
            "domain": "Political Science",
            "subcategory": "radical_right",
            "confidence": 0.85,
            "reasoning": "Based on populism keywords"
        }
        mock_client.return_value = mock_instance
        yield mock_client


@pytest.fixture
def mock_embedding_client():
    """Mock embedding client."""
    with patch('src.utils.embedding_client.EmbeddingClient') as mock_client:
        mock_instance = Mock()
        mock_instance.encode_texts.return_value = np.random.rand(3, 384)  # Mock embeddings
        mock_client.return_value = mock_instance
        yield mock_client


# ── Temporary Directory Fixtures ────────────────────────────────────────────

@pytest.fixture
def temp_data_dir():
    """Create a temporary directory for test data."""
    temp_dir = Path(tempfile.mkdtemp())
    try:
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir)


@pytest.fixture
def temp_config():
    """Create a temporary config for testing."""
    config = {
        "paths": {
            "data_raw": "tests/fixtures/raw",
            "data_processed": "tests/fixtures/processed",
            "outputs": "tests/fixtures/outputs",
            "logs": "tests/fixtures/logs"
        },
        "openalex": {
            "email": "test@example.com",
            "per_page": 25,
            "max_pages": 1
        },
        "llm": {
            "provider": "openai",
            "model": "gpt-4",
            "temperature": 0.1
        },
        "pipeline": {
            "mode": "test"
        }
    }
    return config

# ── New Temporary Directory Fixtures ────────────────────────────────────────

@pytest.fixture
def raw_dir(tmp_path):
    """Fixture to provide a temporary directory for raw data."""
    dir = tmp_path / "raw"
    dir.mkdir()
    return str(dir)

@pytest.fixture
def clean_path(tmp_path):
    """Fixture to provide a temporary path for cleaned data."""
    path = tmp_path / "cleaned_data.csv"
    return str(path)

@pytest.fixture
def proc_dir(tmp_path):
    """Fixture to provide a temporary directory for processed data."""
    dir = tmp_path / "processed"
    dir.mkdir()
    return str(dir)

@pytest.fixture
def net_dir(tmp_path):
    """Fixture to provide a temporary directory for network data."""
    dir = tmp_path / "networks"
    dir.mkdir()
    return str(dir)

@pytest.fixture
def fig_dir(tmp_path):
    """Fixture to provide a temporary directory for figures."""
    dir = tmp_path / "figures"
    dir.mkdir()
    return str(dir)


# ── Pytest Configuration ────────────────────────────────────────────────────

def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "unit: Unit tests for individual functions")
    config.addinivalue_line("markers", "integration: Tests for agent interactions")
    config.addinivalue_line("markers", "robustness: Tests for error handling and edge cases")
    config.addinivalue_line("markers", "regression: Tests to prevent regressions")
    config.addinivalue_line("markers", "slow: Tests that take longer to run")
    config.addinivalue_line("markers", "bibliometric: Domain-specific bibliometric tests")


def pytest_collection_modifyitems(config, items):
    """Automatically mark tests based on their location."""
    for item in items:
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "robustness" in str(item.fspath):
            item.add_marker(pytest.mark.robustness)
        elif "regression" in str(item.fspath):
            item.add_marker(pytest.mark.regression)
