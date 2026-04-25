"""
Unit tests for src/utils/prototype_store.py

Covers: PrototypeStore.build_from_seeds, classify_one, classify_batch,
update_centroids_from_corpus, save, load.
A mock EmbeddingClient is used throughout — no real embeddings are computed.
"""

from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pytest

from src.utils.prototype_store import ALL_LABELS, SEED_TEXTS, PrototypeStore

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_client():
    """EmbeddingClient whose embed_batch returns deterministic unit vectors."""
    client = Mock()
    client.backend_name = "mock"

    def embed_batch(texts):
        n = len(texts)
        # Each text gets a random but reproducible unit vector in 32-d space
        rng = np.random.default_rng(42)
        vecs = rng.random((n, 32)).astype(np.float32)
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        return vecs / norms

    def embed_one(text):
        return embed_batch([text])[0]

    client.embed_batch.side_effect = embed_batch
    client.embed_one.side_effect = embed_one
    return client


@pytest.fixture
def built_store(mock_client):
    """A PrototypeStore that has been built from seeds."""
    store = PrototypeStore(mock_client)
    store.build_from_seeds()
    return store


# ── build_from_seeds ──────────────────────────────────────────────────────────


class TestBuildFromSeeds:
    @pytest.mark.unit
    def test_builds_centroid_for_every_label(self, mock_client):
        store = PrototypeStore(mock_client)
        store.build_from_seeds()
        assert set(store.labels) == set(ALL_LABELS)

    @pytest.mark.unit
    def test_centroids_are_unit_normalised(self, built_store):
        for label, centroid in built_store._centroids.items():
            norm = np.linalg.norm(centroid)
            assert abs(norm - 1.0) < 1e-5, f"Centroid for {label} not unit-normalised"

    @pytest.mark.unit
    def test_backend_name_stored(self, built_store):
        assert built_store._backend_name == "mock"

    @pytest.mark.unit
    def test_metadata_populated(self, built_store):
        assert built_store._metadata["backend"] == "mock"
        assert built_store._metadata["n_labels"] == len(ALL_LABELS)
        assert built_store._metadata["source"] == "seeds"

    @pytest.mark.unit
    def test_returns_self_for_chaining(self, mock_client):
        store = PrototypeStore(mock_client)
        result = store.build_from_seeds()
        assert result is store

    @pytest.mark.unit
    def test_n_labels_matches_seed_texts(self, built_store):
        assert built_store.n_labels == len(SEED_TEXTS)

    @pytest.mark.unit
    def test_embed_batch_called_per_label(self, mock_client):
        store = PrototypeStore(mock_client)
        store.build_from_seeds()
        assert mock_client.embed_batch.call_count == len(SEED_TEXTS)


# ── classify_one ──────────────────────────────────────────────────────────────


class TestClassifyOne:
    @pytest.mark.unit
    def test_returns_four_tuple(self, built_store):
        result = built_store.classify_one("populism in Europe")
        assert len(result) == 4

    @pytest.mark.unit
    def test_domain_is_string(self, built_store):
        domain, subcat, score, top_k = built_store.classify_one("populism")
        assert isinstance(domain, str)

    @pytest.mark.unit
    def test_subcategory_is_string(self, built_store):
        domain, subcat, score, top_k = built_store.classify_one("populism")
        assert isinstance(subcat, str)

    @pytest.mark.unit
    def test_score_is_float(self, built_store):
        domain, subcat, score, top_k = built_store.classify_one("populism")
        assert isinstance(score, float)

    @pytest.mark.unit
    def test_top_k_default_length(self, built_store):
        _, _, _, top_k = built_store.classify_one("populism")
        assert len(top_k) == 3

    @pytest.mark.unit
    def test_top_k_custom_length(self, built_store):
        _, _, _, top_k = built_store.classify_one("populism", top_k=5)
        assert len(top_k) == 5

    @pytest.mark.unit
    def test_domain_subcat_from_best_label(self, built_store):
        domain, subcat, score, top_k = built_store.classify_one("populism")
        best_label, _ = top_k[0]
        expected_domain, expected_subcat = best_label.split("::")
        assert domain == expected_domain
        assert subcat == expected_subcat

    @pytest.mark.unit
    def test_top_k_sorted_descending(self, built_store):
        _, _, _, top_k = built_store.classify_one("populism")
        scores = [s for _, s in top_k]
        assert scores == sorted(scores, reverse=True)


# ── classify_batch ────────────────────────────────────────────────────────────


class TestClassifyBatch:
    @pytest.mark.unit
    def test_empty_input_returns_empty_list(self, built_store):
        result = built_store.classify_batch([])
        assert result == []

    @pytest.mark.unit
    def test_returns_one_result_per_text(self, built_store):
        texts = ["populism text", "economics text", "sociology text"]
        results = built_store.classify_batch(texts)
        assert len(results) == len(texts)

    @pytest.mark.unit
    def test_each_result_is_four_tuple(self, built_store):
        results = built_store.classify_batch(["text1", "text2"])
        for result in results:
            assert len(result) == 4

    @pytest.mark.unit
    def test_top_k_default_three(self, built_store):
        results = built_store.classify_batch(["populism"])
        _, _, _, top_k = results[0]
        assert len(top_k) == 3

    @pytest.mark.unit
    def test_top_k_custom(self, built_store):
        results = built_store.classify_batch(["text"], top_k=2)
        _, _, _, top_k = results[0]
        assert len(top_k) == 2

    @pytest.mark.unit
    def test_single_embed_batch_call(self, mock_client, built_store):
        # After build_from_seeds, reset call count
        mock_client.embed_batch.reset_mock()
        built_store.classify_batch(["text1", "text2", "text3"])
        # classify_batch calls embed_batch once for all texts
        assert mock_client.embed_batch.call_count == 1

    @pytest.mark.unit
    def test_domain_subcat_consistent_with_label(self, built_store):
        results = built_store.classify_batch(["test"])
        domain, subcat, score, top_k = results[0]
        best_label, _ = top_k[0]
        assert best_label == f"{domain}::{subcat}"


# ── update_centroids_from_corpus ──────────────────────────────────────────────


class TestUpdateCentroidsFromCorpus:
    @pytest.mark.unit
    def test_returns_dict_of_updated_labels(self, built_store):
        texts = ["text"] * 10
        labels = ["Political Science::radical_right"] * 10
        updated = built_store.update_centroids_from_corpus(texts, labels, min_samples=5)
        assert isinstance(updated, dict)
        assert "Political Science::radical_right" in updated

    @pytest.mark.unit
    def test_count_matches_label_occurrences(self, built_store):
        texts = ["text"] * 8
        labels = ["Political Science::radical_right"] * 8
        updated = built_store.update_centroids_from_corpus(texts, labels, min_samples=5)
        assert updated["Political Science::radical_right"] == 8

    @pytest.mark.unit
    def test_skips_labels_below_min_samples(self, built_store):
        texts = ["a", "b"]
        labels = ["Political Science::radical_right"] * 2
        updated = built_store.update_centroids_from_corpus(texts, labels, min_samples=5)
        assert "Political Science::radical_right" not in updated

    @pytest.mark.unit
    def test_new_centroid_is_unit_normalised(self, built_store):
        texts = ["text"] * 10
        labels = ["Political Science::radical_right"] * 10
        built_store.update_centroids_from_corpus(texts, labels, min_samples=5)
        centroid = built_store._centroids["Political Science::radical_right"]
        assert abs(np.linalg.norm(centroid) - 1.0) < 1e-5

    @pytest.mark.unit
    def test_metadata_updated_to_corpus_feedback(self, built_store):
        texts = ["text"] * 10
        labels = ["Political Science::radical_right"] * 10
        built_store.update_centroids_from_corpus(texts, labels, min_samples=5)
        assert "corpus" in built_store._metadata["source"]

    @pytest.mark.unit
    def test_multiple_labels_updated(self, built_store):
        texts = ["text1"] * 6 + ["text2"] * 7
        labels = ["Political Science::radical_right"] * 6 + ["Economics::political_economy"] * 7
        updated = built_store.update_centroids_from_corpus(texts, labels, min_samples=5)
        assert len(updated) == 2
        assert updated["Political Science::radical_right"] == 6
        assert updated["Economics::political_economy"] == 7


# ── save / load ───────────────────────────────────────────────────────────────


class TestSaveLoad:
    @pytest.mark.unit
    def test_save_creates_npz_file(self, built_store, tmp_path):
        path = str(tmp_path / "centroids.npz")
        built_store.save(path)
        assert Path(path).exists()

    @pytest.mark.unit
    def test_save_creates_metadata_json(self, built_store, tmp_path):
        path = str(tmp_path / "centroids.npz")
        built_store.save(path)
        meta_path = Path(path.replace(".npz", "_metadata.json"))
        assert meta_path.exists()

    @pytest.mark.unit
    def test_load_restores_all_centroids(self, built_store, mock_client, tmp_path):
        path = str(tmp_path / "centroids.npz")
        built_store.save(path)

        new_store = PrototypeStore(mock_client)
        new_store.load(path)

        assert set(new_store.labels) == set(built_store.labels)

    @pytest.mark.unit
    def test_load_centroids_numerically_close(self, built_store, mock_client, tmp_path):
        path = str(tmp_path / "centroids.npz")
        built_store.save(path)

        new_store = PrototypeStore(mock_client)
        new_store.load(path)

        for label in built_store.labels:
            np.testing.assert_allclose(
                new_store._centroids[label],
                built_store._centroids[label].astype(np.float32),
                rtol=1e-4,
            )

    @pytest.mark.unit
    def test_load_restores_metadata(self, built_store, mock_client, tmp_path):
        path = str(tmp_path / "centroids.npz")
        built_store.save(path)

        new_store = PrototypeStore(mock_client)
        new_store.load(path)

        assert new_store._metadata.get("backend") == "mock"

    @pytest.mark.unit
    def test_load_returns_self_for_chaining(self, built_store, mock_client, tmp_path):
        path = str(tmp_path / "centroids.npz")
        built_store.save(path)

        new_store = PrototypeStore(mock_client)
        result = new_store.load(path)
        assert result is new_store

    @pytest.mark.unit
    def test_save_creates_parent_dirs(self, built_store, tmp_path):
        nested = str(tmp_path / "a" / "b" / "centroids.npz")
        built_store.save(nested)
        assert Path(nested).exists()

    @pytest.mark.unit
    def test_load_without_metadata_file(self, built_store, mock_client, tmp_path):
        path = str(tmp_path / "centroids.npz")
        built_store.save(path)
        # Remove metadata file
        Path(path.replace(".npz", "_metadata.json")).unlink()

        new_store = PrototypeStore(mock_client)
        new_store.load(path)  # Should not raise
        assert new_store.n_labels == built_store.n_labels


# ── labels / n_labels properties ─────────────────────────────────────────────


class TestProperties:
    @pytest.mark.unit
    def test_labels_empty_before_build(self, mock_client):
        store = PrototypeStore(mock_client)
        assert store.labels == []

    @pytest.mark.unit
    def test_n_labels_zero_before_build(self, mock_client):
        store = PrototypeStore(mock_client)
        assert store.n_labels == 0

    @pytest.mark.unit
    def test_labels_after_build(self, built_store):
        assert len(built_store.labels) == len(ALL_LABELS)

    @pytest.mark.unit
    def test_n_labels_after_build(self, built_store):
        assert built_store.n_labels == len(ALL_LABELS)
