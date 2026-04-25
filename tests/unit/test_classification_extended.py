"""
Extended unit tests for src/agents/classification.py

Covers: make_input_text, stage1_rule, HybridClassifier.classify_dataframe,
run_feedback_loop — all using the real production implementations.
"""

import logging
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd
import pytest

from src.agents.classification import (
    HybridClassifier,
    make_input_text,
    run_feedback_loop,
    stage1_rule,
)


# ── make_input_text ───────────────────────────────────────────────────────────


class TestMakeInputText:
    @pytest.mark.unit
    def test_title_included(self):
        row = pd.Series({"title": "Populism in Europe", "abstract": "", "concepts": []})
        result = make_input_text(row)
        assert "Populism in Europe" in result

    @pytest.mark.unit
    def test_abstract_included_when_present(self):
        row = pd.Series({
            "title": "Test",
            "abstract": "This is a test abstract.",
            "concepts": [],
        })
        result = make_input_text(row)
        assert "This is a test abstract." in result

    @pytest.mark.unit
    def test_abstract_truncated_at_600_chars(self):
        row = pd.Series({
            "title": "Test",
            "abstract": "x" * 1000,
            "concepts": [],
        })
        result = make_input_text(row)
        # After truncation the text should not contain more than 600 x's
        abstract_part = result.split(" | ")[1] if " | " in result else result
        assert len(abstract_part) <= 600

    @pytest.mark.unit
    def test_concepts_included_as_topics(self):
        row = pd.Series({
            "title": "Test",
            "abstract": "",
            "concepts": [{"name": "Populism"}, {"name": "Democracy"}],
        })
        result = make_input_text(row)
        assert "Topics:" in result
        assert "Populism" in result

    @pytest.mark.unit
    def test_at_most_four_concepts_used(self):
        row = pd.Series({
            "title": "Test",
            "abstract": "",
            "concepts": [{"name": f"C{i}"} for i in range(10)],
        })
        result = make_input_text(row)
        # C0-C3 should appear; C4+ should not influence the Topics line
        topics_line = [p for p in result.split(" | ") if "Topics:" in p]
        assert len(topics_line) == 1
        # At most 4 concepts in the topics line
        concept_count = topics_line[0].count(",") + 1
        assert concept_count <= 4

    @pytest.mark.unit
    def test_non_dict_concepts_skipped(self):
        row = pd.Series({
            "title": "Test",
            "abstract": "",
            "concepts": ["string_concept", 42, None],
        })
        result = make_input_text(row)
        # None of the bad items should appear; no Topics section added
        assert "Topics:" not in result

    @pytest.mark.unit
    def test_empty_row_returns_just_empty_title(self):
        row = pd.Series({"title": None, "abstract": None, "concepts": None})
        result = make_input_text(row)
        assert isinstance(result, str)

    @pytest.mark.unit
    def test_parts_joined_by_pipe_separator(self):
        row = pd.Series({
            "title": "Title",
            "abstract": "Abstract text",
            "concepts": [{"name": "Populism"}],
        })
        result = make_input_text(row)
        assert " | " in result


# ── stage1_rule ───────────────────────────────────────────────────────────────


class TestStage1Rule:
    @pytest.mark.unit
    def test_returns_three_tuple(self):
        row = pd.Series({"title": "Test", "abstract": "", "concepts": []})
        result = stage1_rule(row)
        assert len(result) == 3

    @pytest.mark.unit
    def test_confidence_between_zero_and_one(self):
        row = pd.Series({"title": "populism democracy", "abstract": "", "concepts": []})
        _, _, conf = stage1_rule(row)
        assert 0.0 <= conf <= 1.0

    @pytest.mark.unit
    def test_no_signal_returns_other(self):
        row = pd.Series({"title": "quantum physics", "abstract": "lasers", "concepts": []})
        domain, subcat, conf = stage1_rule(row)
        assert domain == "Other"
        assert conf == 0.0

    @pytest.mark.unit
    def test_political_science_keyword_detected(self):
        row = pd.Series({
            "title": "electoral politics and radical right populism",
            "abstract": "",
            "concepts": [],
        })
        domain, subcat, conf = stage1_rule(row)
        assert domain == "Political Science"
        assert conf > 0.0

    @pytest.mark.unit
    def test_economics_keyword_detected(self):
        row = pd.Series({
            "title": "inequality redistribution and trade globalization",
            "abstract": "",
            "concepts": [],
        })
        domain, subcat, conf = stage1_rule(row)
        assert domain == "Economics"

    @pytest.mark.unit
    def test_concept_signal_used(self):
        row = pd.Series({
            "title": "random title",
            "abstract": "",
            "concepts": [{"display_name": "Political Science", "score": 0.9}],
        })
        domain, _, conf = stage1_rule(row)
        assert domain == "Political Science"
        assert conf > 0.0

    @pytest.mark.unit
    def test_non_dict_concepts_ignored(self):
        row = pd.Series({
            "title": "quantum physics",
            "abstract": "",
            "concepts": ["not_a_dict", 42],
        })
        domain, _, conf = stage1_rule(row)
        # Should not crash and no domain signal from bad concepts
        assert isinstance(domain, str)

    @pytest.mark.unit
    def test_subcategory_is_valid_string(self):
        row = pd.Series({
            "title": "radical right and populism",
            "abstract": "",
            "concepts": [],
        })
        _, subcat, _ = stage1_rule(row)
        assert isinstance(subcat, str)
        assert len(subcat) > 0

    @pytest.mark.unit
    def test_confidence_rounded_to_four_decimals(self):
        row = pd.Series({"title": "populism", "abstract": "", "concepts": []})
        _, _, conf = stage1_rule(row)
        assert conf == round(conf, 4)


# ── HybridClassifier ──────────────────────────────────────────────────────────


def _make_store(labels, dim=8):
    """Build a mock PrototypeStore whose classify_batch returns fixed labels."""
    store = Mock()

    def classify_batch(texts, top_k=3):
        results = []
        for _ in texts:
            best = labels[0]
            domain, subcat = best.split("::")
            top = [(labels[0], 0.9)] + [(labels[1], 0.5)] if len(labels) > 1 else [(labels[0], 0.9)]
            results.append((domain, subcat, 0.9, top))
        return results

    store.classify_batch.side_effect = classify_batch
    store.update_centroids_from_corpus.return_value = {}
    return store


class TestHybridClassifier:
    def _make_df(self, n=3):
        return pd.DataFrame({
            "id": [f"W{i}" for i in range(n)],
            "title": ["populism and democracy"] * n,
            "abstract": ["Study of populist movements"] * n,
            "concepts": [[]] * n,
        })

    @pytest.mark.unit
    def test_classify_dataframe_returns_dataframe(self):
        store = _make_store(["Political Science::radical_right", "Economics::political_economy"])
        clf = HybridClassifier(
            embed_client=Mock(),
            prototype_store=store,
            llm_client=None,
        )
        df = self._make_df()
        result = clf.classify_dataframe(df)
        assert isinstance(result, pd.DataFrame)

    @pytest.mark.unit
    def test_output_has_required_columns(self):
        store = _make_store(["Political Science::radical_right"])
        clf = HybridClassifier(embed_client=Mock(), prototype_store=store, llm_client=None)
        result = clf.classify_dataframe(self._make_df())
        for col in ["domain", "subcategory", "domain_confidence", "domain_source", "classification_notes"]:
            assert col in result.columns

    @pytest.mark.unit
    def test_row_count_preserved(self):
        store = _make_store(["Political Science::radical_right"])
        clf = HybridClassifier(embed_client=Mock(), prototype_store=store, llm_client=None)
        df = self._make_df(n=5)
        result = clf.classify_dataframe(df)
        assert len(result) == 5

    @pytest.mark.unit
    def test_confidence_in_valid_range(self):
        store = _make_store(["Political Science::radical_right"])
        clf = HybridClassifier(embed_client=Mock(), prototype_store=store, llm_client=None)
        result = clf.classify_dataframe(self._make_df())
        assert (result["domain_confidence"].between(0.0, 1.0)).all()

    @pytest.mark.unit
    def test_stage1_acceptance_when_high_confidence(self):
        """Stage 1 should accept rows that have unambiguous rule-based signals."""
        df = pd.DataFrame({
            "id": ["W1"],
            "title": ["radical right populist party electoral authoritarian"],
            "abstract": ["far-right nativist populism in European elections"],
            "concepts": [[{"display_name": "Political Science", "score": 0.95}]],
        })
        store = _make_store(["Political Science::radical_right"])
        clf = HybridClassifier(
            embed_client=Mock(),
            prototype_store=store,
            llm_client=None,
            rule_threshold=0.5,
        )
        result = clf.classify_dataframe(df)
        # With a strong political science signal, stage 1 should fire
        assert result.iloc[0]["domain"] == "Political Science"

    @pytest.mark.unit
    def test_routing_stats_populated(self):
        store = _make_store(["Political Science::radical_right"])
        clf = HybridClassifier(embed_client=Mock(), prototype_store=store, llm_client=None)
        clf.classify_dataframe(self._make_df(n=4))
        stats = clf.routing_stats(total=4)
        assert isinstance(stats, dict)
        # At least one routing bucket should be populated
        assert len(stats) > 0

    @pytest.mark.unit
    def test_llm_skipped_when_client_is_none(self):
        """When llm_client is None, stage-3 ambiguous rows fall back to embedding."""
        store = Mock()

        def classify_batch(texts, top_k=3):
            # Return mid-range confidence → would normally go to LLM
            return [("Political Science", "radical_right", 0.65, [("Political Science::radical_right", 0.65)]) for _ in texts]

        store.classify_batch.side_effect = classify_batch
        store.update_centroids_from_corpus.return_value = {}

        clf = HybridClassifier(
            embed_client=Mock(),
            prototype_store=store,
            llm_client=None,
            embed_high_threshold=0.80,
            embed_low_threshold=0.55,
        )
        df = pd.DataFrame({
            "id": ["W1"],
            "title": ["something unrelated"],
            "abstract": [""],
            "concepts": [[]],
        })
        result = clf.classify_dataframe(df)
        # Should not raise; domain source should not be "llm"
        assert result.iloc[0]["domain_source"] in (
            "embedding", "embedding_ambiguous", "embedding_outlier"
        )


# ── run_feedback_loop ─────────────────────────────────────────────────────────


class TestRunFeedbackLoop:
    def _classified_df(self, n=10):
        return pd.DataFrame({
            "id": [f"W{i}" for i in range(n)],
            "domain": ["Political Science"] * n,
            "subcategory": ["radical_right"] * n,
            "domain_confidence": [0.90] * n,
            "domain_source": ["rule"] * n,
        })

    @pytest.mark.unit
    def test_returns_dict(self):
        store = Mock()
        store.update_centroids_from_corpus.return_value = {"Political Science::radical_right": 10}
        clf = Mock()
        clf.store = store

        df = self._classified_df()
        texts = [f"text {i}" for i in range(len(df))]
        result = run_feedback_loop(df, clf, texts, min_samples=5)

        assert isinstance(result, dict)

    @pytest.mark.unit
    def test_calls_update_centroids(self):
        store = Mock()
        store.update_centroids_from_corpus.return_value = {}
        clf = Mock()
        clf.store = store

        df = self._classified_df(n=10)
        texts = [f"text {i}" for i in range(len(df))]
        run_feedback_loop(df, clf, texts, min_samples=5)

        store.update_centroids_from_corpus.assert_called_once()

    @pytest.mark.unit
    def test_skips_when_too_few_high_confidence(self):
        store = Mock()
        store.update_centroids_from_corpus.return_value = {}
        clf = Mock()
        clf.store = store

        df = pd.DataFrame({
            "id": ["W1"],
            "domain": ["Political Science"],
            "subcategory": ["radical_right"],
            "domain_confidence": [0.50],  # Below 0.80 threshold
            "domain_source": ["rule"],
        })
        texts = ["text"]
        result = run_feedback_loop(df, clf, texts, min_samples=5)

        # Too few samples → should return empty dict
        assert result == {}
        store.update_centroids_from_corpus.assert_not_called()

    @pytest.mark.unit
    def test_only_high_confidence_used(self):
        store = Mock()
        store.update_centroids_from_corpus.return_value = {}
        clf = Mock()
        clf.store = store

        df = pd.DataFrame({
            "id": [f"W{i}" for i in range(10)],
            "domain": ["Political Science"] * 10,
            "subcategory": ["radical_right"] * 10,
            "domain_confidence": [0.90, 0.90, 0.90, 0.90, 0.90, 0.50, 0.50, 0.50, 0.50, 0.50],
            "domain_source": ["rule"] * 10,
        })
        texts = [f"text {i}" for i in range(10)]
        run_feedback_loop(df, clf, texts, min_samples=3)

        call_args = store.update_centroids_from_corpus.call_args
        passed_texts = call_args[0][0]
        assert len(passed_texts) == 5  # Only high-confidence rows
