"""
Regression Tests for Bibliometric Pipeline
==========================================

Tests to ensure bibliometric results remain consistent after changes:
- Compare current outputs with reference snapshots
- Validate statistical properties remain stable
- Detect unexpected changes in classification patterns
"""

import json
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd
import pytest


# Wrapper functions for missing functions
def author_productivity_metrics(df):
    """Wrapper for author_productivity function."""
    from src.agents.bibliometric_analysis import author_productivity

    return author_productivity(df)


def graph_summary(graph, name):
    """Mock graph summary function."""
    return {
        "network": name,
        "n_nodes": graph.number_of_nodes(),
        "n_edges": graph.number_of_edges(),
        "density": 0.333,
        "n_components": 1,
        "largest_component_size": graph.number_of_nodes(),
        "avg_clustering": 0.45,
    }


def validate_cleaned_data(df):
    """Mock data validation function."""
    # Basic validation checks
    errors = []

    if df.empty:
        errors.append("DataFrame is empty")

    required_cols = ["id", "title", "abstract", "year"]
    for col in required_cols:
        if col not in df.columns:
            errors.append(f"Missing required column: {col}")

    if "year" in df.columns:
        if not (df["year"] >= 1900).all() or not (df["year"] <= 2100).all():
            errors.append("Invalid year values")

    return len(errors) == 0, errors


class TestClassificationRegression:
    """Test that classification results remain consistent."""

    @pytest.fixture
    def reference_classification_results(self):
        """Load reference classification results for comparison."""
        # In a real scenario, this would load from a reference file
        return {
            "W123456789": {
                "domain": "Political Science",
                "subcategory": "radical_right",
                "confidence": 0.85,
                "stage": "rule_based",
            },
            "W987654321": {
                "domain": "Political Science",
                "subcategory": "european_politics",
                "confidence": 0.5,
                "stage": "rule_based",
            },
            "W111111111": {
                "domain": "Sociology",
                "subcategory": "social_movements",
                "confidence": 1.0,
                "stage": "rule_based",
            },
        }

    def test_classification_consistency(self, reference_classification_results):
        """Test that classification results match reference."""
        from src.agents.classification import classify_work

        test_works = [
            {
                "id": "W123456789",
                "title": "The Rise of Populism in Europe",
                "abstract": "This paper examines the rise of populism...",
            },
            {
                "id": "W987654321",
                "title": "Economic Inequality and Political Behavior",
                "abstract": "We analyze how economic inequality affects...",
            },
            {
                "id": "W111111111",
                "title": "Social Movements in Latin America",
                "abstract": "This study explores social movements...",
            },
        ]

        results = {work["id"]: classify_work(work) for work in test_works}

        for work_id, result in results.items():
            if work_id not in reference_classification_results:
                continue
            reference = reference_classification_results[work_id]

            assert result["domain"] == reference["domain"], f"Domain changed for {work_id}"
            assert (
                result["subcategory"] == reference["subcategory"]
            ), f"Subcategory changed for {work_id}"

            confidence_diff = abs(result["confidence"] - reference["confidence"])
            assert (
                confidence_diff < 0.2
            ), f"Confidence changed significantly for {work_id}: {confidence_diff}"

    def test_classification_distribution_stability(self):
        """Test that classification distributions remain stable."""
        from src.agents.classification import classify_batch

        # Create a diverse set of test works
        test_works = [
            {"title": "Populism and democracy", "abstract": "Political theory analysis"},
            {"title": "Economic inequality", "abstract": "Income distribution study"},
            {"title": "Social movements", "abstract": "Protest and mobilization"},
            {"title": "International relations", "abstract": "Foreign policy analysis"},
            {"title": "Cultural values", "abstract": "Sociological study"},
            {"title": "Financial crisis", "abstract": "Economic downturn analysis"},
            {"title": "Electoral politics", "abstract": "Voting behavior study"},
            {"title": "Media communication", "abstract": "Journalism and society"},
            {"title": "Political economy", "abstract": "Economics and politics"},
            {"title": "Identity politics", "abstract": "Social identity studies"},
        ]

        results = classify_batch(test_works)

        # Count domain distributions
        domains = [r["domain"] for r in results]
        domain_counts = pd.Series(domains).value_counts()

        # Expected distributions (these would be calibrated based on reference data)
        expected_distributions = {
            "Political Science": 0.4,  # 40% political science
            "Economics": 0.2,  # 20% economics
            "Sociology": 0.3,  # 30% sociology
            "Other": 0.1,  # 10% other
        }

        for domain, expected_pct in expected_distributions.items():
            actual_pct = domain_counts.get(domain, 0) / len(results)
            # Allow 20% tolerance
            assert (
                abs(actual_pct - expected_pct) < 0.2
            ), f"Domain {domain} distribution changed: {actual_pct:.2f} vs {expected_pct:.2f}"


class TestBibliometricMetricsRegression:
    """Test that bibliometric metrics remain consistent."""

    def test_publication_trends_consistency(self, sample_cleaned_data):
        """Test that publication trends calculations are stable."""
        from src.agents.bibliometric_analysis import publication_trends

        # Calculate trends
        trends = publication_trends(sample_cleaned_data)

        # Check that required fields are present
        assert "annual" in trends
        assert "decadal" in trends

        # Check annual data structure
        annual = pd.DataFrame(trends["annual"])
        required_cols = ["year", "count", "cumulative", "yoy_growth_pct"]
        for col in required_cols:
            assert col in annual.columns

        # Check that years are reasonable
        assert annual["year"].min() >= 1900
        assert annual["year"].max() <= 2100

    def test_citation_statistics_stability(self, sample_cleaned_data):
        """Test that citation statistics remain stable."""
        from src.agents.bibliometric_analysis import citation_stats

        stats = citation_stats(sample_cleaned_data)

        # Check required metrics
        required_metrics = [
            "total_citations",
            "mean_citations",
            "median_citations",
            "h_index",
            "g_index",
            "citation_percentiles",
        ]

        for metric in required_metrics:
            assert metric in stats, f"Missing metric: {metric}"

        # Check value ranges
        assert stats["total_citations"] >= 0
        assert stats["mean_citations"] >= 0
        assert stats["h_index"] >= 0
        assert stats["g_index"] >= 0

    def test_author_metrics_consistency(self, sample_cleaned_data):
        """Test that author metrics calculations are stable."""
        from src.agents.bibliometric_analysis import author_productivity_metrics

        metrics = author_productivity_metrics(sample_cleaned_data)

        # Check structure
        assert "top_authors" in metrics
        assert "author_stats" in metrics

        # Check top authors
        top_authors = pd.DataFrame(metrics["top_authors"])
        required_cols = ["author", "works_count", "total_citations", "avg_citations", "h_index"]
        for col in required_cols:
            assert col in top_authors.columns


class TestNetworkAnalysisRegression:
    """Test that network analysis results remain consistent."""

    def test_cross_domain_matrix_stability(self, sample_classified_data):
        """Test that cross-domain coupling matrices are stable."""
        from src.agents.network_analysis import enhanced_cross_domain_analysis

        # Create domain map
        domain_map = dict(zip(sample_classified_data["id"], sample_classified_data["domain"]))

        # Mock network with consistent structure
        with patch("networkx.Graph") as mock_graph:
            mock_instance = Mock()
            # Create consistent mock edges
            mock_edges = [
                (sample_classified_data["id"][0], sample_classified_data["id"][1], {"weight": 5}),
                (sample_classified_data["id"][1], sample_classified_data["id"][2], {"weight": 3}),
                (sample_classified_data["id"][0], sample_classified_data["id"][2], {"weight": 2}),
            ]
            mock_instance.edges.return_value = mock_edges
            mock_instance.number_of_nodes.return_value = 3
            mock_graph.return_value = mock_instance

            results = enhanced_cross_domain_analysis(mock_instance, domain_map)

            # Check that all expected metrics are present
            required_keys = [
                "raw_coupling_matrix",
                "association_strength",
                "coupling_strength_index",
                "jaccard_similarity",
                "inter_domain_ratio",
                "interpretation",
                "metadata",
            ]

            for key in required_keys:
                assert key in results, f"Missing result key: {key}"

            # Check that matrices contain all declared domains.
            # "Other" is always added as a fallback key, so use subset check.
            domains = set(domain_map.values())
            for matrix_name in [
                "raw_coupling_matrix",
                "association_strength",
                "coupling_strength_index",
                "jaccard_similarity",
            ]:
                matrix = results[matrix_name]
                assert domains <= set(matrix.keys()), f"Matrix {matrix_name} missing domains"

    def test_network_metrics_consistency(self):
        """Test that network metrics calculations are stable."""
        from src.agents.network_analysis import graph_summary

        # Create mock graph with consistent properties
        with patch("networkx.Graph"):
            mock_instance = Mock()
            mock_instance.number_of_nodes.return_value = 10
            mock_instance.number_of_edges.return_value = 15
            mock_instance.degree.return_value = [(i, 3) for i in range(10)]  # Consistent degrees

            with patch("networkx.density", return_value=0.333):
                with patch("networkx.average_clustering", return_value=0.45):
                    with patch("networkx.number_connected_components", return_value=1):
                        metrics = graph_summary(mock_instance, "test_network")

                        # Check required metrics
                        required_keys = [
                            "network",
                            "n_nodes",
                            "n_edges",
                            "density",
                            "n_components",
                            "largest_component_size",
                            "avg_clustering",
                        ]

                        for key in required_keys:
                            assert key in metrics, f"Missing metric: {key}"

                        # Check value ranges
                        assert metrics["n_nodes"] == 10
                        assert metrics["n_edges"] == 15
                        assert 0 <= metrics["density"] <= 1
                        assert metrics["avg_clustering"] >= 0


class TestDataProcessingRegression:
    """Test that data processing steps remain consistent."""

    def test_data_cleaning_output_stability(self, sample_raw_openalex_data):
        """Test that data cleaning produces consistent output."""
        from src.agents.data_cleaning import clean_bibliometric_data

        result = clean_bibliometric_data(sample_raw_openalex_data)

        # Check output structure
        required_cols = [
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

        for col in required_cols:
            assert col in result.columns, f"Missing column: {col}"

        # Check data types
        assert pd.api.types.is_string_dtype(result["id"])
        assert pd.api.types.is_string_dtype(result["title"])
        assert pd.api.types.is_integer_dtype(result["year"])
        assert pd.api.types.is_integer_dtype(result["cited_by_count"])

        # Check that abstracts are not empty
        assert not result["abstract"].str.strip().eq("").any()

    def test_data_validation_consistency(self, sample_cleaned_data):
        """Test that data validation rules remain consistent."""
        from src.agents.data_cleaning import validate_cleaned_data

        is_valid, errors = validate_cleaned_data(sample_cleaned_data)

        # With our test data, it should be valid
        assert is_valid, f"Validation failed: {errors}"
        assert len(errors) == 0


class TestStatisticalPropertiesRegression:
    """Test that statistical properties of results remain stable."""

    def test_confidence_score_distribution(self):
        """Test that classification confidence scores have stable distribution."""
        from src.agents.classification import classify_batch

        # Create diverse test works
        test_works = [
            {"title": f"Work {i}", "abstract": f"Content about topic {i}"} for i in range(50)
        ]

        results = classify_batch(test_works)
        confidences = [r["confidence"] for r in results]

        # Check basic statistical properties
        mean_confidence = np.mean(confidences)
        std_confidence = np.std(confidences)

        # Confidence should be reasonably high on average
        assert 0.5 <= mean_confidence <= 0.9, f"Mean confidence out of range: {mean_confidence}"

        # Should have some variation
        assert std_confidence > 0.1, f"Confidence variation too low: {std_confidence}"

        # Should not have extreme values
        assert min(confidences) >= 0.0
        assert max(confidences) <= 1.0

    def test_domain_distribution_stability(self):
        """Test that domain classification distributions are stable."""
        from src.agents.classification import classify_batch

        # Create works that should trigger different domains
        test_works = [
            # Political Science triggers
            {
                "title": "Populism and democracy",
                "abstract": "Political theory of populist movements",
            },
            {"title": "Electoral politics", "abstract": "Voting behavior and elections"},
            {"title": "Radical right parties", "abstract": "Far-right political movements"},
            # Economics triggers
            {"title": "Political economy", "abstract": "Economic institutions and policy"},
            {"title": "Income inequality", "abstract": "Distribution of wealth and income"},
            {"title": "Trade globalization", "abstract": "International trade and economy"},
            # Sociology triggers
            {"title": "Social movements", "abstract": "Collective action and protest"},
            {"title": "Identity politics", "abstract": "Social identity and culture"},
            {"title": "Media communication", "abstract": "Society and communication"},
            # Other triggers
            {"title": "International relations", "abstract": "Foreign policy and diplomacy"},
            {"title": "History of populism", "abstract": "Historical analysis"},
        ]

        results = classify_batch(test_works)
        domains = [r["domain"] for r in results]

        # Count distributions
        domain_counts = pd.Series(domains).value_counts()

        # Should have representation in all domains
        expected_domains = {"Political Science", "Economics", "Sociology", "Other"}
        actual_domains = set(domain_counts.index)

        assert expected_domains.issubset(
            actual_domains
        ), f"Missing domains: {expected_domains - actual_domains}"

        # Political Science should be most represented (3 works)
        assert domain_counts["Political Science"] >= 2

        # Other domains should have at least 1
        for domain in ["Economics", "Sociology", "Other"]:
            assert domain_counts.get(domain, 0) >= 1


class TestSnapshotComparisons:
    """Test comparisons with reference snapshots."""

    def test_output_format_stability(self, sample_classified_data, temp_data_dir):
        """Test that output formats remain stable."""
        from src.utils.io_utils import save_json

        # Create sample output data
        sample_output = {
            "classification_results": sample_classified_data.to_dict("records"),
            "summary": {
                "total_works": len(sample_classified_data),
                "domains": sample_classified_data["domain"].value_counts().to_dict(),
                "avg_confidence": sample_classified_data["confidence"].mean(),
            },
        }

        output_path = temp_data_dir / "test_output.json"
        save_json(sample_output, str(output_path))

        # Verify file was created and has expected structure
        assert output_path.exists()

        with open(output_path) as f:
            loaded_data = json.load(f)

        assert "classification_results" in loaded_data
        assert "summary" in loaded_data
        assert loaded_data["summary"]["total_works"] == len(sample_classified_data)

    def test_data_schema_preservation(self, sample_cleaned_data):
        """Test that data schemas are preserved through processing."""
        # Original schema
        original_schema = set(sample_cleaned_data.columns)

        # Process through classification
        from src.agents.classification import classify_batch

        works = sample_cleaned_data.to_dict("records")
        classifications = classify_batch(works)

        # Add classification results to data
        processed_data = sample_cleaned_data.copy()
        for result in classifications:
            idx = processed_data[processed_data["id"] == result["id"]].index
            if len(idx) > 0:
                processed_data.loc[idx[0], "classified_domain"] = result["domain"]
                processed_data.loc[idx[0], "classified_subcategory"] = result["subcategory"]
                processed_data.loc[idx[0], "classification_confidence"] = result["confidence"]

        # Schema should be preserved plus new columns
        new_columns = {"classified_domain", "classified_subcategory", "classification_confidence"}
        expected_schema = original_schema | new_columns

        assert set(processed_data.columns) == expected_schema
