"""
Robustness Tests for Bibliometric Pipeline
==========================================

Tests system behavior under adverse conditions:
- Corrupted or incomplete data
- External API failures
- Large data volumes
- Network issues
- Resource constraints
"""

from unittest.mock import Mock, patch

import numpy as np
import pandas as pd
import requests


class TestCorruptedDataHandling:
    """Test handling of corrupted or malformed input data."""

    def test_corrupted_openalex_response(self, mock_openalex_client):
        """Test handling of corrupted OpenAlex API responses."""
        # Mock corrupted response
        mock_instance = mock_openalex_client.return_value
        mock_instance.search_works.return_value = {
            "results": [
                {
                    "id": None,  # Corrupted: missing ID
                    "display_name": "Test Work",
                    "publication_year": "invalid_year",  # Corrupted: string instead of int
                    "cited_by_count": "not_a_number",  # Corrupted: string instead of int
                    "open_access": {"is_oa": "yes"},  # Corrupted: string instead of bool
                    "concepts": "not_a_list",  # Corrupted: string instead of list
                    "authorships": [{"author": "not_a_dict"}]  # Corrupted: wrong structure
                }
            ]
        }

        from src.agents.data_collection import collect_openalex_data

        # Should handle corruption gracefully
        result = collect_openalex_data("test query", max_results=1)
        assert isinstance(result, pd.DataFrame)

        # Should have some data even if corrupted
        if len(result) > 0:
            # Check that critical fields are handled
            assert 'id' in result.columns
            assert 'title' in result.columns

    def test_incomplete_bibliometric_records(self):
        """Test handling of incomplete bibliometric records."""
        from src.agents.data_cleaning import clean_bibliometric_data

        # Create data with various missing fields
        incomplete_data = pd.DataFrame({
            "id": ["W1", "W2", "W3", "W4"],
            "title": ["Title1", None, "", "Title4"],
            "year": [2020, None, 2022, "not_a_year"],
            "cited_by_count": [10, 20, None, "thirty"],
            "is_open_access": [True, False, None, "maybe"],
            "concepts": [
                [{"display_name": "Concept1"}],
                None,
                [],
                [{"display_name": None}]
            ]
        })

        # Should not crash
        result = clean_bibliometric_data(incomplete_data)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 4  # Should preserve all rows

    def test_malformed_classification_input(self):
        """Test classification with malformed input data."""
        from src.agents.classification import classify_work

        malformed_inputs = [
            {},  # Empty dict
            {"title": None, "abstract": None},  # None values
            {"title": "", "abstract": ""},  # Empty strings
            {"title": 123, "abstract": 456},  # Wrong types
            {"title": "Valid", "abstract": "Valid", "extra_field": "ignored"}  # Extra fields
        ]

        for malformed_input in malformed_inputs:
            result = classify_work(malformed_input)
            # Should return valid result structure even for malformed input
            assert isinstance(result, dict)
            assert 'domain' in result
            assert 'confidence' in result
            assert 'stage' in result

    def test_corrupted_network_data(self):
        """Test network analysis with corrupted graph data."""
        from src.agents.network_analysis import enhanced_cross_domain_analysis

        # Create corrupted graph mock
        with patch('networkx.Graph') as mock_graph:
            mock_instance = Mock()
            # Corrupted edges: wrong data types, missing weights
            mock_instance.edges.return_value = [
                ("node1", "node2", {}),  # Missing weight
                ("node2", "node3", {"weight": "not_a_number"}),  # Wrong type
                ("node3", "node1", {"weight": None})  # None weight
            ]
            mock_instance.number_of_nodes.return_value = 3
            mock_graph.return_value = mock_instance

            domain_map = {"node1": "Political Science", "node2": "Economics", "node3": "Sociology"}

            # Should handle corruption gracefully
            result = enhanced_cross_domain_analysis(mock_instance, domain_map)
            assert isinstance(result, dict)
            assert 'raw_coupling_matrix' in result


class TestExternalAPIFailures:
    """Test behavior when external APIs are unavailable."""

    def test_openalex_api_timeout(self):
        """Test handling of OpenAlex API timeouts."""
        with patch('src.utils.openalex_client.OpenAlexClient') as mock_client:
            mock_instance = Mock()
            mock_instance.search_works.side_effect = requests.exceptions.Timeout("Connection timed out")
            mock_client.return_value = mock_instance

            from src.agents.data_collection import collect_openalex_data

            result = collect_openalex_data("test query", max_results=1)
            # Should return empty DataFrame or handle gracefully
            assert isinstance(result, pd.DataFrame)

    def test_openalex_api_rate_limit(self):
        """Test handling of OpenAlex API rate limits."""
        with patch('src.utils.openalex_client.OpenAlexClient') as mock_client:
            mock_instance = Mock()
            mock_instance.search_works.side_effect = requests.exceptions.HTTPError("429 Client Error: Too Many Requests")
            mock_client.return_value = mock_instance

            from src.agents.data_collection import collect_openalex_data

            result = collect_openalex_data("test query", max_results=1)
            assert isinstance(result, pd.DataFrame)

    def test_llm_api_failure(self):
        """Test handling of LLM API failures."""
        with patch('src.utils.llm_client.LLMClient') as mock_client:
            mock_instance = Mock()
            mock_instance.classify_work.side_effect = Exception("API quota exceeded")
            mock_client.return_value = mock_instance

            from src.agents.classification import llm_classification

            work_data = {"title": "Test", "abstract": "Test"}
            result = llm_classification(work_data)

            # Should fallback gracefully
            assert result['domain'] == 'Other'
            assert result['confidence'] == 0.0

    def test_embedding_api_failure(self):
        """Test handling of embedding API failures."""
        with patch('src.agents.classification.EmbeddingClient') as mock_client:
            mock_instance = Mock()
            mock_instance.encode_texts.side_effect = Exception("GPU memory error")
            mock_client.from_config.side_effect = Exception("GPU memory error")
            mock_client.return_value = mock_instance

            from src.agents.classification import embedding_similarity_classification

            work_data = {"title": "Test", "abstract": "Test"}
            result = embedding_similarity_classification(work_data)

            # Should fallback gracefully
            assert result['domain'] == 'Other'
            assert result['confidence'] == 0.0


class TestLargeDataVolumes:
    """Test behavior with large data volumes."""

    def test_large_batch_classification(self):
        """Test classification of large batches."""
        # Create large dataset
        n_works = 1000
        large_dataset = [
            {
                "title": f"Work {i}",
                "abstract": f"This is work number {i} about populism"
            }
            for i in range(n_works)
        ]

        from src.agents.classification import classify_batch

        # Should handle large batches without crashing
        results = classify_batch(large_dataset)

        assert len(results) == n_works
        assert all('domain' in r for r in results)
        assert all('confidence' in r for r in results)

    def test_large_network_analysis(self):
        """Test network analysis with large graphs."""
        # Create large mock graph
        n_nodes = 500
        n_edges = 2000

        with patch('networkx.Graph') as mock_graph:
            mock_instance = Mock()
            # Generate mock edges
            mock_edges = [
                (f"node_{i}", f"node_{(i+1)%n_nodes}", {"weight": np.random.randint(1, 10)})
                for i in range(n_edges)
            ]
            mock_instance.edges.return_value = mock_edges
            mock_instance.number_of_nodes.return_value = n_nodes
            mock_graph.return_value = mock_instance

            from src.agents.network_analysis import enhanced_cross_domain_analysis

            # Create domain map
            domain_map = {f"node_{i}": np.random.choice(["Political Science", "Economics", "Sociology", "Other"])
                         for i in range(n_nodes)}

            # Should handle large graphs
            result = enhanced_cross_domain_analysis(mock_instance, domain_map)
            assert isinstance(result, dict)
            assert 'raw_coupling_matrix' in result

    def test_memory_efficient_processing(self):
        """Test that processing is memory efficient."""
        import psutil
        import os

        # Create moderately large dataset
        n_works = 500
        large_dataset = [
            {
                "title": f"Work {i}",
                "abstract": f"This is work number {i} about populism and political science"
            }
            for i in range(n_works)
        ]

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        from src.agents.classification import classify_batch

        # Process large dataset
        results = classify_batch(large_dataset)

        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_used = final_memory - initial_memory

        # Should not use excessive memory (< 500MB for 500 works)
        assert memory_used < 500, f"Used {memory_used:.1f}MB memory"
        assert len(results) == n_works


class TestResourceConstraints:
    """Test behavior under resource constraints."""

    def test_low_memory_conditions(self):
        """Test behavior when memory is limited."""
        # This is hard to test directly, but we can test cleanup
        import gc

        # Create some data
        test_data = pd.DataFrame({
            "id": [f"W{i}" for i in range(100)],
            "title": [f"Title {i}" for i in range(100)],
            "abstract": [f"Abstract {i}" for i in range(100)],
            "year": [2020] * 100,
            "cited_by_count": [10] * 100,
            "is_open_access": [True] * 100,
            "concepts": [[{"display_name": "Test"}]] * 100
        })

        from src.agents.data_cleaning import clean_bibliometric_data

        # Process and cleanup
        result = clean_bibliometric_data(test_data)
        del test_data
        gc.collect()

        assert len(result) == 100

    def test_concurrent_processing_safety(self):
        """Test that functions are safe for concurrent processing."""
        import threading

        results = []
        errors = []

        def process_work(work_id):
            try:
                from src.agents.classification import classify_work
                work_data = {
                    "title": f"Concurrent work {work_id}",
                    "abstract": f"Testing concurrent processing {work_id}"
                }
                result = classify_work(work_data)
                results.append(result)
            except Exception as e:
                errors.append(str(e))

        # Create multiple threads
        threads = []
        for i in range(10):
            t = threading.Thread(target=process_work, args=(i,))
            threads.append(t)
            t.start()

        # Wait for all threads
        for t in threads:
            t.join()

        # Should have results for all threads
        assert len(results) == 10
        assert len(errors) == 0

    def test_file_handle_leaks(self):
        """Test that file handles are properly closed."""
        import psutil
        import os

        process = psutil.Process(os.getpid())
        initial_handles = len(process.open_files())

        # Perform operations that might open files
        from src.agents.data_cleaning import clean_bibliometric_data

        test_data = pd.DataFrame({
            "id": ["W1", "W2"],
            "title": ["Title1", "Title2"],
            "abstract": ["Abstract1", "Abstract2"],
            "year": [2020, 2021],
            "cited_by_count": [10, 20],
            "is_open_access": [True, False],
            "concepts": [[{"display_name": "Test"}], [{"display_name": "Test2"}]]
        })

        result = clean_bibliometric_data(test_data)

        final_handles = len(process.open_files())

        # Should not leak file handles
        assert final_handles <= initial_handles + 2  # Allow small margin


class TestNetworkIssues:
    """Test behavior under network connectivity issues."""

    def test_dns_resolution_failure(self):
        """Test handling of DNS resolution failures."""
        with patch('requests.get') as mock_get:
            mock_get.side_effect = requests.exceptions.ConnectionError("DNS resolution failed")

            # This would affect any HTTP-based operations
            # For now, test that the system handles it gracefully
            try:
                requests.get("https://httpbin.org/status/200", timeout=1)
            except requests.exceptions.ConnectionError:
                # This is expected - we're testing error handling
                pass

    def test_partial_network_failures(self):
        """Test handling of intermittent network failures."""
        call_count = 0

        def intermittent_failure(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count % 3 == 0:  # Fail every 3rd call
                raise requests.exceptions.ConnectionError("Intermittent failure")
            return Mock(status_code=200, json=lambda: {"results": []})

        with patch('requests.get', side_effect=intermittent_failure):
            # Test that retry logic or graceful degradation works
            # This is a placeholder for actual retry implementation
            pass


class TestDataConsistencyUnderStress:
    """Test data consistency when system is under stress."""

    def test_id_preservation_through_pipeline(self):
        """Test that work IDs are preserved through all pipeline stages."""
        from src.agents.data_cleaning import clean_bibliometric_data
        from src.agents.classification import classify_batch

        # Create test data with specific IDs
        test_ids = ["W100", "W200", "W300"]
        raw_data = pd.DataFrame({
            "id": test_ids,
            "title": ["Title1", "Title2", "Title3"],
            "year": [2020, 2021, 2022],
            "cited_by_count": [10, 20, 30],
            "is_open_access": [True, False, True],
            "concepts": [
                [{"display_name": "Political Science"}],
                [{"display_name": "Economics"}],
                [{"display_name": "Sociology"}]
            ]
        })

        # Process through cleaning
        cleaned = clean_bibliometric_data(raw_data)
        assert set(cleaned['id']) == set(test_ids)

        # Process through classification
        works = cleaned.to_dict('records')
        classifications = classify_batch(works)

        # Verify IDs are preserved
        classified_ids = [c['id'] for c in classifications]
        assert set(classified_ids) == set(test_ids)

    def test_data_type_stability(self):
        """Test that data types remain stable under stress."""
        from src.agents.data_cleaning import clean_bibliometric_data

        # Create data with mixed types that might cause issues
        mixed_data = pd.DataFrame({
            "id": ["W1", "W2", "W3"],
            "title": ["Title1", "Title2", "Title3"],
            "year": [2020, "2021", 2022.0],  # Mixed numeric types
            "cited_by_count": [10, "20", 30.0],  # Mixed types
            "is_open_access": [True, "False", False],  # Mixed types
            "concepts": [
                [{"display_name": "Test1"}],
                [{"display_name": "Test2"}],
                [{"display_name": "Test3"}]
            ]
        })

        result = clean_bibliometric_data(mixed_data)

        # Check that types are normalized appropriately
        assert pd.api.types.is_integer_dtype(result['year'])
        assert pd.api.types.is_integer_dtype(result['cited_by_count'])
        assert pd.api.types.is_bool_dtype(result['is_open_access'])
