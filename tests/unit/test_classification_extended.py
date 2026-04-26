"""
Extended unit tests for src/agents/classification.py

Covers: make_input_text, stage1_rule, HybridClassifier.classify_dataframe,
run_feedback_loop — all using the real production implementations.
"""

import logging
from unittest.mock import Mock, patch

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
        row = pd.Series(
            {
                "title": "Test",
                "abstract": "This is a test abstract.",
                "concepts": [],
            }
        )
        result = make_input_text(row)
        assert "This is a test abstract." in result

    @pytest.mark.unit
    def test_abstract_truncated_at_600_chars(self):
        row = pd.Series(
            {
                "title": "Test",
                "abstract": "x" * 1000,
                "concepts": [],
            }
        )
        result = make_input_text(row)
        # After truncation the text should not contain more than 600 x's
        abstract_part = result.split(" | ")[1] if " | " in result else result
        assert len(abstract_part) <= 600

    @pytest.mark.unit
    def test_concepts_included_as_topics(self):
        row = pd.Series(
            {
                "title": "Test",
                "abstract": "",
                "concepts": [{"name": "Populism"}, {"name": "Democracy"}],
            }
        )
        result = make_input_text(row)
        assert "Topics:" in result
        assert "Populism" in result

    @pytest.mark.unit
    def test_at_most_four_concepts_used(self):
        row = pd.Series(
            {
                "title": "Test",
                "abstract": "",
                "concepts": [{"name": f"C{i}"} for i in range(10)],
            }
        )
        result = make_input_text(row)
        # C0-C3 should appear; C4+ should not influence the Topics line
        topics_line = [p for p in result.split(" | ") if "Topics:" in p]
        assert len(topics_line) == 1
        # At most 4 concepts in the topics line
        concept_count = topics_line[0].count(",") + 1
        assert concept_count <= 4

    @pytest.mark.unit
    def test_non_dict_concepts_skipped(self):
        row = pd.Series(
            {
                "title": "Test",
                "abstract": "",
                "concepts": ["string_concept", 42, None],
            }
        )
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
        row = pd.Series(
            {
                "title": "Title",
                "abstract": "Abstract text",
                "concepts": [{"name": "Populism"}],
            }
        )
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
        row = pd.Series(
            {
                "title": "electoral politics and radical right populism",
                "abstract": "",
                "concepts": [],
            }
        )
        domain, subcat, conf = stage1_rule(row)
        assert domain == "Political Science"
        assert conf > 0.0

    @pytest.mark.unit
    def test_economics_keyword_detected(self):
        row = pd.Series(
            {
                "title": "inequality redistribution and trade globalization",
                "abstract": "",
                "concepts": [],
            }
        )
        domain, subcat, conf = stage1_rule(row)
        assert domain == "Economics"

    @pytest.mark.unit
    def test_concept_signal_used(self):
        row = pd.Series(
            {
                "title": "random title",
                "abstract": "",
                "concepts": [{"display_name": "Political Science", "score": 0.9}],
            }
        )
        domain, _, conf = stage1_rule(row)
        assert domain == "Political Science"
        assert conf > 0.0

    @pytest.mark.unit
    def test_non_dict_concepts_ignored(self):
        row = pd.Series(
            {
                "title": "quantum physics",
                "abstract": "",
                "concepts": ["not_a_dict", 42],
            }
        )
        domain, _, conf = stage1_rule(row)
        # Should not crash and no domain signal from bad concepts
        assert isinstance(domain, str)

    @pytest.mark.unit
    def test_subcategory_is_valid_string(self):
        row = pd.Series(
            {
                "title": "radical right and populism",
                "abstract": "",
                "concepts": [],
            }
        )
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
        return pd.DataFrame(
            {
                "id": [f"W{i}" for i in range(n)],
                "title": ["populism and democracy"] * n,
                "abstract": ["Study of populist movements"] * n,
                "concepts": [[]] * n,
            }
        )

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
        for col in [
            "domain",
            "subcategory",
            "domain_confidence",
            "domain_source",
            "classification_notes",
        ]:
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
        df = pd.DataFrame(
            {
                "id": ["W1"],
                "title": ["radical right populist party electoral authoritarian"],
                "abstract": ["far-right nativist populism in European elections"],
                "concepts": [[{"display_name": "Political Science", "score": 0.95}]],
            }
        )
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
            return [
                (
                    "Political Science",
                    "radical_right",
                    0.65,
                    [("Political Science::radical_right", 0.65)],
                )
                for _ in texts
            ]

        store.classify_batch.side_effect = classify_batch
        store.update_centroids_from_corpus.return_value = {}

        clf = HybridClassifier(
            embed_client=Mock(),
            prototype_store=store,
            llm_client=None,
            embed_high_threshold=0.80,
            embed_low_threshold=0.55,
        )
        df = pd.DataFrame(
            {
                "id": ["W1"],
                "title": ["something unrelated"],
                "abstract": [""],
                "concepts": [[]],
            }
        )
        result = clf.classify_dataframe(df)
        # Should not raise; domain source should not be "llm"
        assert result.iloc[0]["domain_source"] in (
            "embedding",
            "embedding_ambiguous",
            "embedding_outlier",
        )

    @pytest.mark.unit
    def test_stage2_high_confidence_accept(self):
        """When stage1 rejects and stage2 returns high confidence, row is tagged 'embedding'."""
        store = Mock()
        # Return confidence above embed_high_threshold (0.80)
        store.classify_batch.return_value = [
            ("Economics", "political_economy", 0.90, [("Economics::political_economy", 0.90)])
        ]
        store.update_centroids_from_corpus.return_value = {}
        clf = HybridClassifier(
            embed_client=Mock(),
            prototype_store=store,
            llm_client=None,
            rule_threshold=0.99,  # Force everything to stage2
            embed_high_threshold=0.80,
            embed_low_threshold=0.55,
        )
        df = pd.DataFrame(
            {"id": ["W1"], "title": ["some title"], "abstract": ["some text"], "concepts": [[]]}
        )
        result = clf.classify_dataframe(df)
        assert result.iloc[0]["domain_source"] == "embedding"
        assert result.iloc[0]["domain"] == "Economics"

    @pytest.mark.unit
    def test_stage3_llm_resolution(self):
        """When stage2 returns mid-range confidence and LLM is available, LLM resolves it."""
        store = Mock()
        # Mid-range confidence → goes to stage3
        store.classify_batch.return_value = [
            ("Political Science", "radical_right", 0.65, [("Political Science::radical_right", 0.65)])
        ]
        store.update_centroids_from_corpus.return_value = {}

        llm_client = Mock()
        llm_client.is_available.return_value = True
        llm_client.generate_json.return_value = (
            {"domain": "Sociology", "subcategory": "social_movements", "confidence": 0.88},
            True,
        )

        clf = HybridClassifier(
            embed_client=Mock(),
            prototype_store=store,
            llm_client=llm_client,
            rule_threshold=0.99,  # Force to stage2
            embed_high_threshold=0.80,
            embed_low_threshold=0.55,
        )
        llm_cfg = {
            "prompts": {
                "classification_system": "sys",
                "classification_user": "classify {title} {abstract} {concepts}",
            }
        }
        df = pd.DataFrame(
            {"id": ["W1"], "title": ["some title"], "abstract": ["some text"], "concepts": [[]]}
        )
        result = clf.classify_dataframe(df, llm_cfg=llm_cfg)
        # LLM should have been used
        assert result.iloc[0]["domain_source"] in ("llm", "embedding_ambiguous")

    @pytest.mark.unit
    def test_stage3_llm_concurrent_execution(self):
        """Multiple ambiguous rows exercise the ThreadPoolExecutor path."""
        store = Mock()
        store.classify_batch.return_value = [
            ("Political Science", "radical_right", 0.65, [("Political Science::radical_right", 0.65)])
        ] * 3
        store.update_centroids_from_corpus.return_value = {}

        llm_client = Mock()
        llm_client.is_available.return_value = True
        llm_client.generate_json.return_value = (
            {"domain": "Political Science", "subcategory": "radical_right", "confidence": 0.82},
            True,
        )

        clf = HybridClassifier(
            embed_client=Mock(),
            prototype_store=store,
            llm_client=llm_client,
            rule_threshold=0.99,
            embed_high_threshold=0.80,
            embed_low_threshold=0.55,
        )
        llm_cfg = {
            "prompts": {
                "classification_system": "sys",
                "classification_user": "classify {title} {abstract} {concepts}",
            }
        }
        df = pd.DataFrame(
            {
                "id": ["W1", "W2", "W3"],
                "title": ["title1", "title2", "title3"],
                "abstract": ["a", "b", "c"],
                "concepts": [[], [], []],
            }
        )
        result = clf.classify_dataframe(df, llm_cfg=llm_cfg)
        assert len(result) == 3


# ── run_feedback_loop ─────────────────────────────────────────────────────────


class TestRunFeedbackLoop:
    def _classified_df(self, n=10):
        return pd.DataFrame(
            {
                "id": [f"W{i}" for i in range(n)],
                "domain": ["Political Science"] * n,
                "subcategory": ["radical_right"] * n,
                "domain_confidence": [0.90] * n,
                "domain_source": ["rule"] * n,
            }
        )

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

        df = pd.DataFrame(
            {
                "id": ["W1"],
                "domain": ["Political Science"],
                "subcategory": ["radical_right"],
                "domain_confidence": [0.50],  # Below 0.80 threshold
                "domain_source": ["rule"],
            }
        )
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

        df = pd.DataFrame(
            {
                "id": [f"W{i}" for i in range(10)],
                "domain": ["Political Science"] * 10,
                "subcategory": ["radical_right"] * 10,
                "domain_confidence": [0.90, 0.90, 0.90, 0.90, 0.90, 0.50, 0.50, 0.50, 0.50, 0.50],
                "domain_source": ["rule"] * 10,
            }
        )
        texts = [f"text {i}" for i in range(10)]
        run_feedback_loop(df, clf, texts, min_samples=3)

        call_args = store.update_centroids_from_corpus.call_args
        passed_texts = call_args[0][0]
        assert len(passed_texts) == 5  # Only high-confidence rows


# ── validate_classification_result ───────────────────────────────────────────


from src.agents.classification import validate_classification_result


class TestValidateClassificationResult:
    @pytest.mark.unit
    def test_valid_result_returns_true(self):
        result = {"domain": "Political Science", "subcategory": "radical_right", "confidence": 0.85}
        ok, errors = validate_classification_result(result)
        assert ok is True
        assert errors == []

    @pytest.mark.unit
    def test_missing_domain_key_flagged(self):
        result = {"subcategory": "radical_right", "confidence": 0.85}
        ok, errors = validate_classification_result(result)
        assert ok is False
        assert any("domain" in e for e in errors)

    @pytest.mark.unit
    def test_missing_subcategory_key_flagged(self):
        result = {"domain": "Political Science", "confidence": 0.85}
        ok, errors = validate_classification_result(result)
        assert ok is False
        assert any("subcategory" in e for e in errors)

    @pytest.mark.unit
    def test_missing_confidence_key_flagged(self):
        result = {"domain": "Political Science", "subcategory": "radical_right"}
        ok, errors = validate_classification_result(result)
        assert ok is False
        assert any("confidence" in e for e in errors)

    @pytest.mark.unit
    def test_confidence_above_one_invalid(self):
        result = {"domain": "Political Science", "subcategory": "radical_right", "confidence": 1.5}
        ok, errors = validate_classification_result(result)
        assert ok is False
        assert any("confidence" in e for e in errors)

    @pytest.mark.unit
    def test_confidence_below_zero_invalid(self):
        result = {"domain": "Political Science", "subcategory": "radical_right", "confidence": -0.1}
        ok, errors = validate_classification_result(result)
        assert ok is False

    @pytest.mark.unit
    def test_confidence_string_invalid(self):
        result = {"domain": "Political Science", "subcategory": "radical_right", "confidence": "high"}
        ok, errors = validate_classification_result(result)
        assert ok is False
        assert any("confidence" in e for e in errors)

    @pytest.mark.unit
    def test_unknown_domain_flagged(self):
        result = {"domain": "Astrology", "subcategory": "horoscopes", "confidence": 0.8}
        ok, errors = validate_classification_result(result)
        assert ok is False
        assert any("domain" in e.lower() for e in errors)

    @pytest.mark.unit
    def test_other_domain_accepted(self):
        result = {"domain": "Other", "subcategory": "interdisciplinary", "confidence": 0.6}
        ok, errors = validate_classification_result(result)
        assert ok is True

    @pytest.mark.unit
    def test_boundary_confidence_zero_valid(self):
        result = {"domain": "Economics", "subcategory": "political_economy", "confidence": 0.0}
        ok, errors = validate_classification_result(result)
        assert ok is True

    @pytest.mark.unit
    def test_boundary_confidence_one_valid(self):
        result = {"domain": "Economics", "subcategory": "political_economy", "confidence": 1.0}
        ok, errors = validate_classification_result(result)
        assert ok is True


# ── rule_based_classification (public API) ────────────────────────────────────


from src.agents.classification import rule_based_classification


class TestRuleBasedClassificationPublicAPI:
    @pytest.mark.unit
    def test_returns_dict_with_required_keys(self):
        result = rule_based_classification(
            {"title": "populism and democracy", "abstract": "", "id": "W1"}
        )
        for key in ("domain", "subcategory", "confidence", "stage"):
            assert key in result

    @pytest.mark.unit
    def test_political_science_signal(self):
        result = rule_based_classification(
            {
                "title": "radical right populist party electoral authoritarian",
                "abstract": "far-right nativist populism in European elections",
                "id": "W1",
            }
        )
        assert result["domain"] == "Political Science"
        assert 0.0 <= result["confidence"] <= 1.0

    @pytest.mark.unit
    def test_no_signal_returns_other(self):
        result = rule_based_classification(
            {"title": "quantum chromodynamics", "abstract": "quark gluon plasma", "id": "W2"}
        )
        assert result["domain"] == "Other"
        assert result["subcategory"] == "interdisciplinary"

    @pytest.mark.unit
    def test_no_signal_confidence_in_range(self):
        result = rule_based_classification(
            {"title": "random noise", "abstract": "xyz abc", "id": "W3"}
        )
        assert 0.5 <= result["confidence"] <= 0.9

    @pytest.mark.unit
    def test_dict_input_works(self):
        result = rule_based_classification({"title": "political economy inequality"})
        assert isinstance(result["domain"], str)

    @pytest.mark.unit
    def test_series_input_works(self):
        row = pd.Series({"title": "populism electoral democracy", "abstract": "", "concepts": []})
        result = rule_based_classification(row)
        assert isinstance(result["domain"], str)

    @pytest.mark.unit
    def test_non_dict_non_series_input_safe(self):
        result = rule_based_classification("unexpected string input")
        assert result["domain"] == "Other"

    @pytest.mark.unit
    def test_stage_field_is_rule_based(self):
        result = rule_based_classification({"title": "populism"})
        assert result["stage"] == "rule_based"

    @pytest.mark.unit
    def test_deterministic_for_same_input(self):
        inp = {"title": "random xyz", "abstract": "no signal", "id": "W99"}
        r1 = rule_based_classification(inp)
        r2 = rule_based_classification(inp)
        assert r1["confidence"] == r2["confidence"]


# ── stage3_llm ────────────────────────────────────────────────────────────────


from src.agents.classification import stage3_llm


class TestStage3LLM:
    def _row(self, title="populism and democracy", abstract="study of populism"):
        return pd.Series(
            {"id": "W1", "title": title, "abstract": abstract, "concepts": []}
        )

    def _llm_cfg(self):
        return {
            "prompts": {
                "classification_system": "You are a classifier.",
                "classification_user": "Classify: {title} | {abstract} | {concepts}",
            }
        }

    @pytest.mark.unit
    def test_successful_llm_response(self):
        client = Mock()
        client.generate_json.return_value = (
            {"domain": "Political Science", "subcategory": "radical_right", "confidence": 0.9},
            True,
        )
        domain, subcat, conf, src = stage3_llm(
            self._row(), client, self._llm_cfg(), logging.getLogger()
        )
        assert domain == "Political Science"
        assert subcat == "radical_right"
        assert conf == 0.9
        assert src == "llm"

    @pytest.mark.unit
    def test_llm_failure_returns_other(self):
        client = Mock()
        client.generate_json.return_value = (None, False)
        domain, subcat, conf, src = stage3_llm(
            self._row(), client, self._llm_cfg(), logging.getLogger()
        )
        assert domain == "Other"
        assert src == "llm_failed"

    @pytest.mark.unit
    def test_llm_invalid_response_returns_other(self):
        client = Mock()
        # Return a response that fails validate_classification_response
        client.generate_json.return_value = (
            {"domain": "InvalidDomain", "subcategory": "x", "confidence": 5.0},
            True,
        )
        domain, subcat, conf, src = stage3_llm(
            self._row(), client, self._llm_cfg(), logging.getLogger()
        )
        assert domain == "Other"
        assert src == "llm_invalid"

    @pytest.mark.unit
    def test_embed_hint_appended_to_prompt(self):
        client = Mock()
        client.generate_json.return_value = (
            {"domain": "Political Science", "subcategory": "radical_right", "confidence": 0.8},
            True,
        )
        hints = [("Political Science::radical_right", 0.85), ("Economics::political_economy", 0.60)]
        stage3_llm(self._row(), client, self._llm_cfg(), logging.getLogger(), embed_top_k=hints)
        call_kwargs = client.generate_json.call_args
        user_prompt = call_kwargs.kwargs.get("user_prompt") or call_kwargs.args[1]
        assert "0.850" in user_prompt or "0.85" in user_prompt


# ── llm_classification (public API) ──────────────────────────────────────────


from src.agents.classification import llm_classification


class TestLLMClassification:
    @pytest.mark.unit
    def test_no_client_returns_other(self):
        result = llm_classification({"title": "populism", "abstract": ""})
        assert result["domain"] == "Other"
        assert result["stage"] == "llm_unavailable"

    @pytest.mark.unit
    def test_unavailable_client_returns_other(self):
        client = Mock()
        client.is_available.return_value = False
        result = llm_classification({"title": "populism", "abstract": ""}, client=client)
        assert result["domain"] == "Other"
        assert result["stage"] == "llm_unavailable"

    @pytest.mark.unit
    def test_available_client_calls_stage3(self):
        client = Mock()
        client.is_available.return_value = True
        client.generate_json.return_value = (
            {"domain": "Political Science", "subcategory": "radical_right", "confidence": 0.85},
            True,
        )
        llm_cfg = {
            "prompts": {
                "classification_system": "sys",
                "classification_user": "user {title} {abstract} {concepts}",
            }
        }
        result = llm_classification(
            {"title": "populism party", "abstract": "radical right"}, client=client, llm_cfg=llm_cfg
        )
        assert result["domain"] == "Political Science"
        assert result["method"] == "llm"

    @pytest.mark.unit
    def test_exception_in_stage3_returns_other(self):
        client = Mock()
        client.is_available.return_value = True
        client.generate_json.side_effect = RuntimeError("connection refused")
        llm_cfg = {
            "prompts": {
                "classification_system": "sys",
                "classification_user": "user {title} {abstract} {concepts}",
            }
        }
        result = llm_classification(
            {"title": "test", "abstract": ""}, client=client, llm_cfg=llm_cfg
        )
        assert result["domain"] == "Other"
        assert result["stage"] == "llm_error"


# ── embedding_similarity_classification (fallback path) ───────────────────────


from src.agents.classification import embedding_similarity_classification


class TestEmbeddingSimilarityClassification:
    @pytest.mark.unit
    def test_fallback_on_exception_returns_other(self):
        """When EmbeddingClient.from_config raises, function returns Other gracefully."""
        with patch(
            "src.agents.classification.EmbeddingClient.from_config",
            side_effect=RuntimeError("no GPU"),
        ):
            result = embedding_similarity_classification({"title": "populism", "abstract": ""})
        assert result["domain"] == "Other"
        assert result["stage"] == "embedding_fallback"
        assert result["method"] == "embedding_similarity"

    @pytest.mark.unit
    def test_returns_dict_with_required_keys(self):
        with patch(
            "src.agents.classification.EmbeddingClient.from_config",
            side_effect=RuntimeError("no GPU"),
        ):
            result = embedding_similarity_classification({"title": "test"})
        for key in ("domain", "subcategory", "confidence", "stage", "method"):
            assert key in result

    @pytest.mark.unit
    def test_successful_embedding_path(self):
        mock_client = Mock()
        mock_store = Mock()
        mock_store.classify_batch.return_value = [
            ("Political Science", "radical_right", 0.88, [])
        ]
        with (
            patch("src.agents.classification.EmbeddingClient.from_config", return_value=mock_client),
            patch("src.agents.classification.PrototypeStore", return_value=mock_store),
        ):
            result = embedding_similarity_classification({"title": "populism electoral"})
        assert result["domain"] == "Political Science"
        assert result["stage"] == "embedding"
